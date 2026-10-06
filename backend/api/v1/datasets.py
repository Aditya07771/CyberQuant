import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import settings
from core.dependencies import get_current_org, get_current_user, require_dataset_access, require_role
from core.errors import BadInputError, ResourceNotFoundError
from db.models import (
    Asset,
    Dataset,
    DatasetVersion,
    IngestionJob,
    Organization,
    RiskRun,
    SourceArtifact,
    User,
    VulnerabilityFinding,
)
from db.session import get_db
from jobs.runner import enqueue_job
from risk_engine.excel_mapper import build_excel_summary, is_card_dataset, map_cards_to_risk_tables
from risk_engine.scanners import AppSecCSVParser, NessusParser, OpenVASParser, ScanNormalizer
from services.audit import AuditService
from services.dataset_service import REQUIRED_TABLES, DatasetService

router = APIRouter(prefix="/api/v1/datasets", tags=["datasets"])


@router.get("")
def list_datasets(
    current_org: Organization = Depends(get_current_org),
    db: Session = Depends(get_db),
):
    """Lists all datasets belonging to the active organization."""
    datasets = db.scalars(
        select(Dataset).where(
            Dataset.organization_id == current_org.id,
            Dataset.status == "active",
        ).order_by(Dataset.created_at.desc())
    ).all()

    results = []
    for d in datasets:
        v_count = db.query(DatasetVersion).filter(DatasetVersion.dataset_id == d.id).count()
        run_count = db.query(RiskRun).filter(RiskRun.dataset_id == d.id).count()
        results.append({
            "id": d.id,
            "name": d.name,
            "description": d.description,
            "dataset_type": d.dataset_type,
            "active_version_id": d.active_version_id,
            "versions_count": v_count,
            "runs_count": run_count,
            "created_at": d.created_at.isoformat(),
            "updated_at": d.updated_at.isoformat(),
        })
    return results


def _background_ingest_data(
    data: Dict[str, pd.DataFrame],
    dataset_id: str,
    user_id: Optional[str],
    source_format: str,
    excel_summary: Optional[dict],
    job_id: str,
    version_id: Optional[str] = None,
) -> dict:
    from db.session import SessionLocal
    db = SessionLocal()
    try:
        dataset = db.scalars(select(Dataset).where(Dataset.id == dataset_id)).first()
        service = DatasetService(db)
        version_row = None
        if version_id:
            version_row = db.scalars(
                select(DatasetVersion).where(DatasetVersion.id == version_id)
            ).first()
        version = service.create_dataset_version(
            dataset=dataset,
            data=data,
            uploader_id=user_id,
            source_format=source_format,
            excel_summary=excel_summary,
            version=version_row,
        )
        return {
            "dataset_id": dataset.id,
            "version_id": version.id,
            "row_counts": version.row_counts,
        }
    finally:
        db.close()


def _create_pending_version(db: Session, dataset: Dataset) -> DatasetVersion:
    prev_versions = db.query(DatasetVersion).filter(DatasetVersion.dataset_id == dataset.id).count()
    version = DatasetVersion(
        dataset_id=dataset.id,
        version_number=prev_versions + 1,
        currency="USD",
        time_window_days=30.0,
        is_valid=False,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


def _build_workbook_summary(
    workbook: Dict[str, pd.DataFrame],
    file_name: str,
    sheet_names: List[str],
) -> dict:
    """Summarizes a multi-sheet workbook that already contains the risk tables."""
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


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def upload_dataset_bundle(
    request: Request,
    name: str = Form("Default Dataset"),
    description: Optional[str] = Form(None),
    dataset_type: str = Form("tabular"),
    files: List[UploadFile] = File(...),
    idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    current_org: Organization = Depends(get_current_org),
    current_user: User = Depends(get_current_user),
    _role: str = Depends(require_role("analyst")),
    db: Session = Depends(get_db),
):
    """
    Accepts dataset bundle uploads:
    - Multiple individual CSVs (assets, controls, asset_controls, threat_events, vulnerabilities)
    - A single hardened ZIP archive
    - A single JSON compiled dataset
    - A single Excel workbook (.xlsx/.xls/.xlsm)
    Returns 202 Accepted with dataset_id and job_id.
    """
    if not files:
        raise BadInputError(message="No files provided for upload")

    # Check request body size against MAX_UPLOAD_SIZE_BYTES
    data: Dict[str, pd.DataFrame] = {}
    excel_summary: Optional[dict] = None
    source_format = "csv_bundle"

    # Single-file logic
    if len(files) == 1:
        single_file = files[0]
        fname = (single_file.filename or "").lower()

        # Hardened ZIP extraction
        if fname.endswith(".zip"):
            source_format = "zip_archive"
            content = await single_file.read()
            if len(content) > settings.MAX_UPLOAD_SIZE_BYTES:
                raise HTTPException(status_code=413, detail="ZIP archive exceeds maximum allowed size")

            try:
                with zipfile.ZipFile(io.BytesIO(content)) as z:
                    # Security checks: prevent traversal, nested bomb, uncompressed size bomb
                    total_uncompressed = 0
                    for info in z.infolist():
                        if ".." in info.filename or info.filename.startswith(("/", "\\")):
                            raise BadInputError(message="Malicious path detected in ZIP archive")
                        total_uncompressed += info.file_size
                        if total_uncompressed > settings.MAX_UPLOAD_SIZE_BYTES * 5:
                            raise BadInputError(message="Decompression bomb detected in ZIP archive")

                        base_name = Path(info.filename).name.lower()
                        for target in REQUIRED_TABLES:
                            if base_name == f"{target}.csv":
                                with z.open(info.filename) as f:
                                    data[target] = pd.read_csv(f)
            except BadInputError:
                raise
            except Exception as e:
                raise BadInputError(message=f"Could not parse ZIP archive: {str(e)}")

        elif fname.endswith(".json"):
            source_format = "json_dataset"
            content = await single_file.read()
            try:
                json_data = json.loads(content.decode("utf-8"))
                for target in REQUIRED_TABLES:
                    if target in json_data and isinstance(json_data[target], list):
                        data[target] = pd.DataFrame(json_data[target])
                    elif f"{target}s" in json_data and isinstance(json_data[f"{target}s"], list):
                        data[target] = pd.DataFrame(json_data[f"{target}s"])
            except Exception as e:
                raise BadInputError(message=f"Invalid JSON dataset format: {str(e)}")

        elif fname.endswith((".xlsx", ".xls", ".xlsm")):
            source_format = "excel_workbook"
            content = await single_file.read()
            engine = "xlrd" if fname.endswith(".xls") else "openpyxl"
            try:
                workbook = pd.read_excel(io.BytesIO(content), sheet_name=None, engine=engine)
            except Exception as e:
                raise BadInputError(message=f"Could not read Excel workbook: {str(e)}")

            sheet_names = [str(s) for s in workbook.keys()]
            matched_tables: Dict[str, pd.DataFrame] = {}
            for target in REQUIRED_TABLES:
                for sheet_name, sheet_df in workbook.items():
                    if str(sheet_name).strip().lower() in (target, f"{target}s"):
                        matched_tables[target] = sheet_df
                        break

            if len(matched_tables) == len(REQUIRED_TABLES):
                data = matched_tables
                excel_summary = _build_workbook_summary(workbook, single_file.filename, sheet_names)
                excel_summary["risk_table_counts"] = {k: int(len(v)) for k, v in data.items()}
                excel_summary["notes"] = [
                    "Workbook contained the 5 risk tables; rows were loaded directly without transformation."
                ]
            else:
                # Try raw card dataset auto-mapping
                first_sheet = next(iter(workbook.values()), None)
                if first_sheet is not None and is_card_dataset(first_sheet):
                    data = map_cards_to_risk_tables(first_sheet)
                    source_rows = int(len(first_sheet))
                    modeled = int(len(data["assets"]))
                    excel_summary = build_excel_summary(first_sheet, single_file.filename, sheet_names)
                    excel_summary["risk_table_counts"] = {k: int(len(v)) for k, v in data.items()}
                    excel_summary["notes"] = []
                    if modeled != source_rows:
                        excel_summary["notes"].append(
                            f"{source_rows:,} card records were aggregated into {modeled:,} risk assets "
                            "so the Monte Carlo / ILP frontier stays within the API response budget."
                        )
                    else:
                        excel_summary["notes"].append("Each card record was modeled as an individual risk asset.")
                else:
                    raise BadInputError(message="Unsupported Excel format. Provide 5 risk sheets or financial transactions.")

    # Multiple CSV files
    if not data:
        for f in files:
            fname = (f.filename or "").lower()
            content = await f.read()
            clean_name = Path(fname).name.lower()
            for target in REQUIRED_TABLES:
                if clean_name == f"{target}.csv":
                    try:
                        data[target] = pd.read_csv(io.BytesIO(content))
                    except Exception as e:
                        raise BadInputError(message=f"Failed to parse CSV '{f.filename}': {str(e)}")
                    break

    # Validate before enqueueing
    service = DatasetService(db)
    service.validate_tables(data)

    # Create dataset record
    dataset = Dataset(
        organization_id=current_org.id,
        name=name.strip(),
        description=description,
        owner_id=current_user.id,
        dataset_type=dataset_type,
        status="active",
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    version = _create_pending_version(db, dataset)

    # Queue ingestion job
    job = enqueue_job(
        task_type="ingestion",
        fn=_background_ingest_data,
        kwargs={
            "data": data,
            "dataset_id": dataset.id,
            "user_id": current_user.id,
            "source_format": source_format,
            "excel_summary": excel_summary,
            "version_id": version.id,
        },
        org_id=current_org.id,
        dataset_id=dataset.id,
        idempotency_key=idempotency_key,
        db=db,
    )

    return {
        "status": "accepted",
        "dataset_id": dataset.id,
        "version_id": version.id,
        "job_id": job.id,
        "message": "Dataset ingestion job has been queued.",
    }


@router.post("/demo", status_code=status.HTTP_202_ACCEPTED)
def load_demo_dataset(
    current_org: Organization = Depends(get_current_org),
    current_user: User = Depends(get_current_user),
    _role: str = Depends(require_role("analyst")),
    db: Session = Depends(get_db),
):
    """
    Creates an organization-owned 'demo' dataset from the built-in sample bundle and
    queues ingestion. The resulting dataset is a normal tenant dataset with the
    built-in sample data written into this organization's isolated storage.
    """
    from risk_engine.config import EngineConfig
    from risk_engine.ingest import DataIngestor

    try:
        ingestor = DataIngestor(config=EngineConfig(data_dir=settings.DATA_BASE_DIR))
        raw_data = ingestor.load_data()
    except Exception as e:
        raise BadInputError(message=f"Failed to load built-in demo dataset: {str(e)}")

    service = DatasetService(db)
    service.validate_tables(raw_data)

    dataset = Dataset(
        organization_id=current_org.id,
        name="Sample Demo Dataset",
        description="Built-in sample dataset (demo/synthetic data, not customer data).",
        owner_id=current_user.id,
        dataset_type="demo",
        status="active",
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)

    version = _create_pending_version(db, dataset)

    excel_summary = {
        "file_name": "builtin_sample_bundle",
        "dataset_type": "Built-in synthetic/demo risk dataset.",
        "sheet_names": REQUIRED_TABLES,
        "total_rows": int(sum(len(df) for df in raw_data.values())),
        "risk_table_counts": {k: int(len(v)) for k, v in raw_data.items()},
        "notes": ["Built-in sample bundle provided with the product; treat as synthetic/demo data."],
    }

    job = enqueue_job(
        task_type="ingestion",
        fn=_background_ingest_data,
        kwargs={
            "data": raw_data,
            "dataset_id": dataset.id,
            "user_id": current_user.id,
            "source_format": "demo_bundle",
            "excel_summary": excel_summary,
            "version_id": version.id,
        },
        org_id=current_org.id,
        dataset_id=dataset.id,
        db=db,
    )

    return {
        "status": "accepted",
        "dataset_id": dataset.id,
        "version_id": version.id,
        "job_id": job.id,
        "dataset_type": "demo",
        "message": "Demo dataset ingestion job has been queued.",
    }


@router.get("/{dataset_id}")
def get_dataset(
    dataset_id: str,
    dataset: Dataset = Depends(require_dataset_access),
    db: Session = Depends(get_db),
):
    """Returns dataset metadata and available versions."""
    versions = db.scalars(
        select(DatasetVersion).where(DatasetVersion.dataset_id == dataset.id).order_by(DatasetVersion.version_number.desc())
    ).all()

    return {
        "id": dataset.id,
        "name": dataset.name,
        "description": dataset.description,
        "dataset_type": dataset.dataset_type,
        "active_version_id": dataset.active_version_id,
        "created_at": dataset.created_at.isoformat(),
        "versions": [
            {
                "version_id": v.id,
                "version_number": v.version_number,
                "row_counts": v.row_counts,
                "created_at": v.created_at.isoformat(),
            }
            for v in versions
        ],
    }


@router.get("/{dataset_id}/status")
def get_dataset_status(
    dataset_id: str,
    dataset: Dataset = Depends(require_dataset_access),
    db: Session = Depends(get_db),
):
    """Returns ingestion/readiness status for the dataset."""
    latest_job = db.scalars(
        select(IngestionJob).where(
            IngestionJob.dataset_id == dataset.id
        ).order_by(IngestionJob.created_at.desc())
    ).first()

    latest_run = db.scalars(
        select(RiskRun).where(
            RiskRun.dataset_id == dataset.id
        ).order_by(RiskRun.created_at.desc())
    ).first()

    return {
        "dataset_id": dataset.id,
        "active_version_id": dataset.active_version_id,
        "latest_job": {
            "id": latest_job.id if latest_job else None,
            "state": latest_job.state if latest_job else None,
            "progress_pct": latest_job.progress_pct if latest_job else None,
        } if latest_job else None,
        "latest_run": {
            "id": latest_run.id if latest_run else None,
            "state": latest_run.state if latest_run else None,
            "model_version": latest_run.model_version if latest_run else None,
        } if latest_run else None,
    }


def _background_risk_run(
    dataset_id: str,
    org_id: str,
    user_id: Optional[str],
    rng_seed: int,
    n_simulations: int,
    job_id: str,
    run_id: Optional[str] = None,
) -> dict:
    from db.session import SessionLocal
    db = SessionLocal()
    try:
        service = DatasetService(db)
        res = service.execute_risk_run(
            dataset_id=dataset_id,
            org_id=org_id,
            user_id=user_id,
            rng_seed=rng_seed,
            n_simulations=n_simulations,
            job_id=job_id,
            run_id=run_id,
        )
        return res
    finally:
        db.close()


class RunRequest(BaseModel):
    rng_seed: int = 42
    n_simulations: int = 10_000


@router.post("/{dataset_id}/runs", status_code=status.HTTP_202_ACCEPTED)
def queue_risk_run(
    dataset_id: str,
    payload: RunRequest = RunRequest(),
    dataset: Dataset = Depends(require_dataset_access),
    current_org: Organization = Depends(get_current_org),
    current_user: User = Depends(get_current_user),
    _role: str = Depends(require_role("analyst")),
    db: Session = Depends(get_db),
):
    """Queues a Monte Carlo financial risk calculation run for the dataset."""
    version_id = dataset.active_version_id
    if not version_id:
        raise BadInputError(message="Dataset has no ingested version to run. Upload data first.")

    run = RiskRun(
        organization_id=current_org.id,
        dataset_id=dataset.id,
        dataset_version_id=version_id,
        config_version="1.0.0",
        model_version="fair-v2.1",
        code_version="1.0.0",
        rng_seed=payload.rng_seed,
        state="queued",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    job = enqueue_job(
        task_type="risk_run",
        fn=_background_risk_run,
        kwargs={
            "dataset_id": dataset.id,
            "org_id": current_org.id,
            "user_id": current_user.id,
            "rng_seed": payload.rng_seed,
            "n_simulations": payload.n_simulations,
            "run_id": run.id,
        },
        org_id=current_org.id,
        dataset_id=dataset.id,
        db=db,
    )

    return {
        "status": "accepted",
        "run_id": run.id,
        "job_id": job.id,
        "message": "Risk quantification run queued.",
    }


@router.get("/{dataset_id}/runs")
def list_risk_runs(
    dataset_id: str,
    dataset: Dataset = Depends(require_dataset_access),
    db: Session = Depends(get_db),
):
    """Lists historical and active risk runs for the dataset."""
    runs = db.scalars(
        select(RiskRun).where(RiskRun.dataset_id == dataset.id).order_by(RiskRun.created_at.desc())
    ).all()

    return [
        {
            "id": r.id,
            "dataset_id": r.dataset_id,
            "dataset_version_id": r.dataset_version_id,
            "state": r.state,
            "model_version": r.model_version,
            "rng_seed": r.rng_seed,
            "summary_metrics": r.summary_metrics,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "created_at": r.created_at.isoformat(),
        }
        for r in runs
    ]


@router.get("/{dataset_id}/runs/{run_id}")
def get_risk_run_detail(
    dataset_id: str,
    run_id: str,
    dataset: Dataset = Depends(require_dataset_access),
    db: Session = Depends(get_db),
):
    """Returns status and configuration of a specific risk run."""
    run = db.scalars(
        select(RiskRun).where(
            RiskRun.id == run_id,
            RiskRun.dataset_id == dataset.id,
        )
    ).first()

    if not run:
        raise ResourceNotFoundError(message="Risk run not found")

    return {
        "id": run.id,
        "dataset_id": run.dataset_id,
        "dataset_version_id": run.dataset_version_id,
        "state": run.state,
        "model_version": run.model_version,
        "rng_seed": run.rng_seed,
        "threat_intel_snapshots": run.threat_intel_snapshot_refs,
        "summary_metrics": run.summary_metrics,
        "safe_error_code": run.safe_error_code,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }


# ---------------------------------------------------------------------------
# Scanners Sub-Resource (/api/v1/datasets/{dataset_id}/scans)
# ---------------------------------------------------------------------------

def _background_scan_import(
    raw_content: str,
    filename: str,
    scanner_type: str,
    dataset_id: str,
    version_id: str,
    user_id: Optional[str],
    job_id: str,
) -> dict:
    from db.session import SessionLocal
    db = SessionLocal()
    try:
        raw_findings = []
        if scanner_type == "openvas" or filename.lower().endswith(".xml"):
            raw_findings = OpenVASParser.parse(raw_content)
        elif scanner_type == "nessus" or filename.lower().endswith(".json"):
            raw_findings = NessusParser.parse(raw_content)
        elif scanner_type == "appsec" or filename.lower().endswith(".csv"):
            raw_findings = AppSecCSVParser.parse(raw_content)

        created = ScanNormalizer.match_and_create_findings(raw_findings, version_id, db)
        for f in created:
            db.add(f)
        db.commit()

        matched_count = sum(1 for f in created if f.match_status == "matched")
        unmatched_count = sum(1 for f in created if f.match_status != "matched")

        return {
            "total_findings": len(created),
            "matched_findings": matched_count,
            "unmatched_findings": unmatched_count,
        }
    finally:
        db.close()


@router.post("/{dataset_id}/scans", status_code=status.HTTP_202_ACCEPTED)
async def upload_scanner_export(
    dataset_id: str,
    file: UploadFile = File(...),
    scanner_type: str = Form("auto"),  # auto, openvas, nessus, appsec
    dataset: Dataset = Depends(require_dataset_access),
    current_org: Organization = Depends(get_current_org),
    current_user: User = Depends(get_current_user),
    _role: str = Depends(require_role("analyst")),
    db: Session = Depends(get_db),
):
    """
    Uploads an OpenVAS XML, Nessus JSON, or AppSec CSV report.
    Findings are parsed safely, normalized, and reconciled against dataset assets.
    """
    content_bytes = await file.read()
    raw_content = content_bytes.decode("utf-8", errors="replace")

    version_id = dataset.active_version_id
    if not version_id:
        version = db.scalars(
            select(DatasetVersion).where(DatasetVersion.dataset_id == dataset.id).order_by(DatasetVersion.version_number.desc())
        ).first()
        if not version:
            raise BadInputError(message="Dataset has no active version to attach scan findings")
        version_id = version.id

    job = enqueue_job(
        task_type="scan_import",
        fn=_background_scan_import,
        kwargs={
            "raw_content": raw_content,
            "filename": file.filename or "scan_export",
            "scanner_type": scanner_type,
            "dataset_id": dataset.id,
            "version_id": version_id,
            "user_id": current_user.id,
        },
        org_id=current_org.id,
        dataset_id=dataset.id,
        db=db,
    )

    return {
        "status": "accepted",
        "scan_id": job.id,
        "job_id": job.id,
        "message": f"Scanner report '{file.filename}' queued for parsing and asset normalization.",
    }


@router.get("/{dataset_id}/scans")
def list_scans(
    dataset_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    dataset: Dataset = Depends(require_dataset_access),
    db: Session = Depends(get_db),
):
    """Lists scan-import jobs (scan history) for the dataset, most recent first."""
    base = select(IngestionJob).where(
        IngestionJob.dataset_id == dataset.id,
        IngestionJob.task_type == "scan_import",
    )
    total = db.query(IngestionJob).filter(
        IngestionJob.dataset_id == dataset.id,
        IngestionJob.task_type == "scan_import",
    ).count()
    offset = (page - 1) * page_size
    jobs = db.scalars(base.order_by(IngestionJob.created_at.desc()).offset(offset).limit(page_size)).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "scans": [
            {
                "scan_id": j.id,
                "state": j.state,
                "progress_pct": j.progress_pct,
                "result_summary": j.result_summary,
                "safe_error_code": j.safe_error_code,
                "safe_error_message": j.safe_error_message,
                "created_at": j.created_at.isoformat(),
                "finished_at": j.finished_at.isoformat() if j.finished_at else None,
            }
            for j in jobs
        ],
    }


@router.get("/{dataset_id}/scans/{scan_id}")
def get_scan_detail(
    dataset_id: str,
    scan_id: str,
    dataset: Dataset = Depends(require_dataset_access),
    db: Session = Depends(get_db),
):
    """Returns processing status and summary for a single scan-import job."""
    job = db.scalars(
        select(IngestionJob).where(
            IngestionJob.id == scan_id,
            IngestionJob.dataset_id == dataset.id,
            IngestionJob.task_type == "scan_import",
        )
    ).first()
    if not job:
        raise ResourceNotFoundError(message="Scan not found")

    return {
        "scan_id": job.id,
        "dataset_id": job.dataset_id,
        "version_id": job.version_id,
        "state": job.state,
        "progress_pct": job.progress_pct,
        "result_summary": job.result_summary,
        "safe_error_code": job.safe_error_code,
        "safe_error_message": job.safe_error_message,
        "created_at": job.created_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


@router.get("/{dataset_id}/scans/{scan_id}/findings")
def list_scan_findings(
    dataset_id: str,
    scan_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    match_status: Optional[str] = Query(None),
    dataset: Dataset = Depends(require_dataset_access),
    db: Session = Depends(get_db),
):
    """Lists normalized vulnerability findings from scans (paginated)."""
    scan = db.scalars(
        select(IngestionJob).where(
            IngestionJob.id == scan_id,
            IngestionJob.dataset_id == dataset.id,
            IngestionJob.task_type == "scan_import",
        )
    ).first()
    if not scan:
        raise ResourceNotFoundError(message="Scan not found")

    version_id = scan.version_id or dataset.active_version_id
    query = select(VulnerabilityFinding).where(VulnerabilityFinding.dataset_version_id == version_id)
    count_query = db.query(VulnerabilityFinding).filter(VulnerabilityFinding.dataset_version_id == version_id)
    if match_status:
        query = query.where(VulnerabilityFinding.match_status == match_status)
        count_query = count_query.filter(VulnerabilityFinding.match_status == match_status)

    total = count_query.count()
    offset = (page - 1) * page_size
    findings = db.scalars(query.offset(offset).limit(page_size)).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "findings": [
            {
                "id": f.id,
                "asset_id": f.asset_id,
                "cve_id": f.cve_id,
                "cvss_score": f.cvss_score,
                "severity": f.severity,
                "scanner_source": f.scanner_source,
                "match_status": f.match_status,
                "evidence_ref": f.evidence_ref,
                "first_seen": f.first_seen.isoformat() if f.first_seen else None,
            }
            for f in findings
        ],
    }


class AssetMappingRequest(BaseModel):
    finding_id: str
    asset_id: str


@router.post("/{dataset_id}/scans/{scan_id}/asset-mappings")
def approve_asset_mapping(
    dataset_id: str,
    scan_id: str,
    payload: AssetMappingRequest,
    dataset: Dataset = Depends(require_dataset_access),
    _role: str = Depends(require_role("analyst")),
    db: Session = Depends(get_db),
):
    """Analyst approves manual mapping of an unresolved vulnerability finding to a known asset."""
    finding = db.scalars(
        select(VulnerabilityFinding).where(
            VulnerabilityFinding.id == payload.finding_id,
            VulnerabilityFinding.dataset_version_id == dataset.active_version_id,
        )
    ).first()

    if not finding:
        raise ResourceNotFoundError(message="Vulnerability finding not found")

    asset = db.scalars(
        select(Asset).where(
            Asset.id == payload.asset_id,
            Asset.dataset_version_id == dataset.active_version_id,
        )
    ).first()

    if not asset:
        raise ResourceNotFoundError(message="Asset not found")

    finding.asset_id = asset.id
    finding.match_status = "matched"
    db.commit()

    return {
        "status": "success",
        "finding_id": finding.id,
        "asset_id": asset.id,
        "match_status": "matched",
    }
