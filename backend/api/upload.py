import io
import json
import logging
import os
import shutil
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from risk_engine.config import EngineConfig
from risk_engine.ingest import DataIngestor, IngestionError
from risk_engine.pipeline import RiskPipeline
from risk_engine.excel_mapper import (
    build_excel_summary,
    is_card_dataset,
    map_cards_to_risk_tables,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/datasets", tags=["datasets"])

BASE_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
UPLOADS_DIR = BASE_DATA_DIR / "uploads"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs"

EXCEL_EXTENSIONS = (".xlsx", ".xls", ".xlsm")

REQUIRED_TABLES = [
    "assets",
    "vulnerabilities",
    "threat_events",
    "controls",
    "asset_controls"
]

REQUIRED_COLUMNS = {
    "assets": [
        "asset_id", "business_unit", "criticality",
        "data_sensitivity_tier", "financial_value_usd", "downtime_cost_per_hour_usd"
    ],
    "controls": [
        "control_id", "name", "risk_reduction_pct", "cost_usd"
    ],
    "asset_controls": [
        "asset_id", "control_id"
    ],
    "threat_events": [
        "event_id", "asset_id", "downtime_hours_caused", "records_compromised"
    ],
    "vulnerabilities": [
        "asset_id", "cve_id", "cvss_score", "epss_score"
    ]
}


def _validate_dataframes(data: Dict[str, pd.DataFrame]) -> None:
    """Performs strict schema and domain validation across all 5 datasets."""
    # 1. Ensure all 5 datasets are present
    missing_tables = [table for table in REQUIRED_TABLES if table not in data or data[table] is None]
    if missing_tables:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Missing required datasets: {', '.join(missing_tables)}. All 5 datasets are required."
        )

    # 2. Validate columns for each table
    for table_name, req_cols in REQUIRED_COLUMNS.items():
        df = data[table_name]
        if df.empty and table_name in ("assets", "controls"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Dataset '{table_name}.csv' cannot be empty."
            )
        
        missing_cols = [col for col in req_cols if col not in df.columns]
        if missing_cols:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required columns in '{table_name}.csv': {', '.join(missing_cols)}"
            )

    # 3. Domain value validation: Assets
    assets_df = data["assets"]
    try:
        if (pd.to_numeric(assets_df["financial_value_usd"], errors="coerce") < 0).any():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Negative financial_value_usd values found in assets.csv"
            )
        if (pd.to_numeric(assets_df["downtime_cost_per_hour_usd"], errors="coerce") < 0).any():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Negative downtime_cost_per_hour_usd values found in assets.csv"
            )
    except TypeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Non-numeric values found in financial columns of assets.csv"
        )

    # 4. Domain value validation: Controls
    controls_df = data["controls"]
    try:
        rr_pct = pd.to_numeric(controls_df["risk_reduction_pct"], errors="coerce")
        if (rr_pct > 1.0).any() or (rr_pct < 0.0).any() or rr_pct.isna().any():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="risk_reduction_pct in controls.csv must be fractional numbers between 0.0 and 1.0 (e.g. 0.75 for 75%)"
            )
        cost = pd.to_numeric(controls_df["cost_usd"], errors="coerce")
        if (cost < 0).any() or cost.isna().any():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="cost_usd in controls.csv must be non-negative numeric values"
            )
    except TypeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid numeric types in controls.csv"
        )

    # 5. Ingestion validation
    try:
        ingestor = DataIngestor()
        ingestor._validate_schemas(data)
    except IngestionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Schema validation error: {str(e)}"
        )


def _adaptive_simulations(n_assets: int) -> int:
    """Keeps total Monte Carlo work bounded so the quantification pipeline
    completes in seconds while preserving statistical rigor (FAIR standard).

    - <= 50 assets: 10,000 iterations (~1-2s total)
    - 51 - 150 assets: 5,000 iterations (~3-4s total)
    - > 150 assets: 3,000 iterations (e.g. 300 assets -> ~6s total, 900k portfolio draws)
    """
    if n_assets <= 0:
        return 10_000
    if n_assets <= 50:
        return 10_000
    if n_assets <= 150:
        return 5_000
    return 3_000


def _select_primary_sheet(workbook: Dict[str, pd.DataFrame]):
    """Returns (sheet_name, dataframe) for the largest non-empty worksheet."""
    best_name = None
    best_df = None
    for name, df in workbook.items():
        if df is None or df.empty:
            continue
        if best_df is None or len(df) > len(best_df):
            best_name, best_df = str(name), df
    if best_df is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded Excel workbook contains no non-empty worksheets."
        )
    return best_name, best_df


def _summarize_workbook(
    workbook: Dict[str, pd.DataFrame],
    file_name: str,
    sheet_names: List[str],
) -> dict:
    """Builds a summary for a multi-sheet workbook that already contains the 5 tables."""
    merged_columns: List[str] = []
    seen = set()
    total_rows = 0
    for df in workbook.values():
        if df is None:
            continue
        total_rows += int(len(df))
        for col in df.columns:
            if col not in seen:
                seen.add(col)
                merged_columns.append(col)

    summary = build_excel_summary(
        pd.DataFrame(columns=merged_columns),
        file_name,
        sheet_names,
        dataset_type="Relational cyber risk dataset (multi-sheet workbook).",
    )
    summary["total_rows"] = total_rows
    return summary


def _process_and_save_data(
    data: Dict[str, pd.DataFrame],
    session_id: str,
    excel_summary: Optional[dict] = None,
) -> dict:
    """Saves raw dataframes to a session folder and executes the risk pipeline."""
    session_dir = UPLOADS_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    # Save CSVs to session upload directory
    for name, df in data.items():
        csv_filename = f"{name}.csv" if not name.endswith(".csv") else name
        df.to_csv(session_dir / csv_filename, index=False)

    n_assets = int(len(data["assets"]))
    n_simulations = _adaptive_simulations(n_assets)

    # Persist the Excel file summary alongside the normalized tables so the
    # original upload can be audited later.
    if excel_summary is not None:
        summary_payload = dict(excel_summary)
        summary_payload["simulation_iterations"] = n_simulations
        try:
            with open(session_dir / "excel_summary.json", "w", encoding="utf-8") as f:
                json.dump(summary_payload, f, indent=2, default=str)
        except Exception:
            logger.warning("Could not persist excel_summary.json for session %s", session_id)

    # Execute risk pipeline
    try:
        config = EngineConfig(
            data_dir=session_dir,
            output_dir=OUTPUT_DIR,
            n_simulations=n_simulations,
        )
        pipeline = RiskPipeline(config=config)
        pipeline.run_all()
    except Exception as e:
        logger.exception("Risk engine pipeline execution failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Risk engine execution failed: {str(e)}"
        )

    return {
        "status": "success",
        "session_id": session_id,
        "asset_count": n_assets,
        "controls_count": int(len(data["controls"])),
        "events_count": int(len(data["threat_events"])),
        "vulnerabilities_count": int(len(data["vulnerabilities"])),
        "simulation_iterations": n_simulations,
        "excel_summary": excel_summary,
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "message": "Dataset successfully processed and risk quantification pipeline completed."
    }


@router.post("/upload")
async def upload_datasets(
    files: List[UploadFile] = File(...),
):
    """
    Accepts dataset uploads in one of four formats:
    1. Multiple individual CSV files (assets.csv, controls.csv, asset_controls.csv, threat_events.csv, vulnerabilities.csv)
    2. A single .zip archive containing the 5 CSVs
    3. A single compiled_risk_dataset.json file
    4. A single Excel workbook (.xlsx/.xls/.xlsm) — either a multi-sheet
       workbook containing the 5 risk tables, or a raw financial card/account
       dataset (e.g. Financial Transactions.xlsx) that is auto-mapped onto the
       risk engine schema. The response includes an `excel_summary` describing
       the uploaded file.
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided for upload."
        )

    data: Dict[str, pd.DataFrame] = {}
    excel_summary: Optional[dict] = None
    session_id = f"upload_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    # Check if single file is ZIP, JSON, or Excel
    if len(files) == 1:
        single_file = files[0]
        filename = (single_file.filename or "").lower()

        if filename.endswith(".zip"):
            content = await single_file.read()
            try:
                with zipfile.ZipFile(io.BytesIO(content)) as z:
                    for name in z.namelist():
                        base_name = Path(name).name.lower()
                        for target in REQUIRED_TABLES:
                            if base_name == f"{target}.csv":
                                with z.open(name) as f:
                                    data[target] = pd.read_csv(f)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Could not read uploaded zip archive: {str(e)}"
                )

        elif filename.endswith(".json"):
            content = await single_file.read()
            try:
                json_data = json.loads(content.decode("utf-8"))
                for target in REQUIRED_TABLES:
                    if target in json_data and isinstance(json_data[target], list):
                        data[target] = pd.DataFrame(json_data[target])
                    elif f"{target}s" in json_data and isinstance(json_data[f"{target}s"], list):
                        data[target] = pd.DataFrame(json_data[f"{target}s"])
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Could not parse uploaded JSON dataset: {str(e)}"
                )

        elif filename.endswith(EXCEL_EXTENSIONS):
            content = await single_file.read()
            engine = "xlrd" if filename.endswith(".xls") else "openpyxl"
            try:
                workbook = pd.read_excel(io.BytesIO(content), sheet_name=None, engine=engine)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Could not read uploaded Excel workbook: {str(e)}"
                )

            if not workbook:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Uploaded Excel workbook contains no worksheets."
                )

            sheet_names = [str(s) for s in workbook.keys()]

            # Case A: workbook already contains the 5 authoritative tables as sheets.
            matched_tables: Dict[str, pd.DataFrame] = {}
            for target in REQUIRED_TABLES:
                for sheet_name, sheet_df in workbook.items():
                    if str(sheet_name).strip().lower() in (target, f"{target}s"):
                        matched_tables[target] = sheet_df
                        break

            if len(matched_tables) == len(REQUIRED_TABLES):
                data = matched_tables
                excel_summary = _summarize_workbook(workbook, single_file.filename, sheet_names)
                excel_summary["risk_table_counts"] = {k: int(len(v)) for k, v in data.items()}
                excel_summary["notes"] = [
                    "Workbook contained the 5 risk tables; rows were loaded directly without transformation."
                ]
            else:
                # Case B: raw financial card/account dataset -> auto-map.
                _, primary_df = _select_primary_sheet(workbook)
                if is_card_dataset(primary_df):
                    try:
                        data = map_cards_to_risk_tables(primary_df)
                    except Exception as e:
                        logger.exception("Failed to map Excel card dataset")
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Could not map Excel card dataset to the risk engine schema: {str(e)}"
                        )
                    excel_summary = build_excel_summary(primary_df, single_file.filename, sheet_names)
                    source_rows = int(len(primary_df))
                    modeled = int(len(data["assets"]))
                    excel_summary["risk_table_counts"] = {k: int(len(v)) for k, v in data.items()}
                    excel_summary["notes"] = []
                    if modeled != source_rows:
                        excel_summary["notes"].append(
                            f"{source_rows:,} card records were aggregated into {modeled:,} risk "
                            "assets (brand x product x chip x dark-web x credit segment) so the "
                            "Monte Carlo / ILP frontier stays within the API response budget."
                        )
                    else:
                        excel_summary["notes"].append(
                            "Each card record was modeled as an individual risk asset."
                        )
                elif not data:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            "Unsupported Excel workbook. Provide either a workbook with the 5 risk "
                            "sheets (assets, controls, asset_controls, threat_events, vulnerabilities) "
                            "or a financial card/account dataset such as Financial Transactions.xlsx."
                        )
                    )

    # Multi-file or individual CSVs
    if not data:
        for file in files:
            fname = (file.filename or "").lower()
            content = await file.read()
            
            clean_name = Path(fname).name.lower()
            for target in REQUIRED_TABLES:
                if clean_name == f"{target}.csv":
                    try:
                        data[target] = pd.read_csv(io.BytesIO(content))
                    except Exception as e:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Could not parse CSV file '{file.filename}': {str(e)}"
                        )
                    break

    # Validate all loaded DataFrames
    _validate_dataframes(data)

    # Process and run pipeline
    return _process_and_save_data(data, session_id, excel_summary=excel_summary)


class JsonDatasetPayload(BaseModel):
    assets: List[dict]
    controls: List[dict]
    asset_controls: List[dict]
    threat_events: List[dict]
    vulnerabilities: List[dict]


@router.post("/upload-json")
async def upload_json_dataset(payload: JsonDatasetPayload):
    """Direct JSON payload upload endpoint."""
    data = {
        "assets": pd.DataFrame(payload.assets),
        "controls": pd.DataFrame(payload.controls),
        "asset_controls": pd.DataFrame(payload.asset_controls),
        "threat_events": pd.DataFrame(payload.threat_events),
        "vulnerabilities": pd.DataFrame(payload.vulnerabilities),
    }

    _validate_dataframes(data)
    session_id = f"upload_json_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    return _process_and_save_data(data, session_id)


@router.post("/demo")
def load_demo_dataset():
    """Loads the authoritative built-in sample dataset from backend/data and runs the pipeline."""
    if not BASE_DATA_DIR.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Built-in demo data directory not found."
        )

    try:
        ingestor = DataIngestor(config=EngineConfig(data_dir=BASE_DATA_DIR))
        raw_data = ingestor.load_data()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load built-in demo dataset: {str(e)}"
        )

    session_id = f"demo_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    return _process_and_save_data(raw_data, session_id)


@router.get("/status")
def get_dataset_status():
    """Returns the current dataset and pipeline output readiness status."""
    required_outputs = [
        "asset_risk_summary.parquet",
        "business_unit_risk_summary.parquet",
        "org_risk_summary.parquet",
        "control_scenario_results.parquet"
    ]

    all_exist = all((OUTPUT_DIR / f).exists() for f in required_outputs)

    asset_count = 0
    last_updated = None

    if all_exist:
        try:
            asset_file = OUTPUT_DIR / "asset_risk_summary.parquet"
            mtime = os.path.getmtime(asset_file)
            last_updated = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
            df = pd.read_parquet(asset_file)
            asset_count = len(df)
        except Exception:
            pass

    return {
        "outputs_ready": all_exist,
        "asset_count": asset_count,
        "last_updated": last_updated,
    }
