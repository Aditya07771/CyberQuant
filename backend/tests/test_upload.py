import io
import json
import zipfile
import pytest
import pandas as pd
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def _create_sample_csv_bytes():
    assets_csv = (
        "asset_id,business_unit,criticality,data_sensitivity_tier,financial_value_usd,downtime_cost_per_hour_usd\n"
        "AST-1,Finance,3,Internal,100000,1000\n"
        "AST-2,HR,2,Public,50000,500\n"
    ).encode("utf-8")

    controls_csv = (
        "control_id,name,risk_reduction_pct,cost_usd\n"
        "CTRL-1,EDR,0.8,20000\n"
        "CTRL-2,MFA,0.6,5000\n"
    ).encode("utf-8")

    asset_controls_csv = (
        "asset_id,control_id\n"
        "AST-1,CTRL-1\n"
    ).encode("utf-8")

    threat_events_csv = (
        "event_id,asset_id,downtime_hours_caused,records_compromised\n"
        "EVT-1,AST-1,2,50\n"
    ).encode("utf-8")

    vulnerabilities_csv = (
        "asset_id,cve_id,cvss_score,epss_score\n"
        "AST-1,CVE-2023-1234,7.5,0.4\n"
    ).encode("utf-8")

    return {
        "assets.csv": assets_csv,
        "controls.csv": controls_csv,
        "asset_controls.csv": asset_controls_csv,
        "threat_events.csv": threat_events_csv,
        "vulnerabilities.csv": vulnerabilities_csv,
    }


def test_status_endpoint():
    response = client.get("/api/datasets/status")
    assert response.status_code == 200
    data = response.json()
    assert "outputs_ready" in data
    assert "asset_count" in data


def test_upload_multiple_csvs_success():
    csv_dict = _create_sample_csv_bytes()
    files = [
        ("files", (name, io.BytesIO(content), "text/csv"))
        for name, content in csv_dict.items()
    ]

    response = client.post("/api/datasets/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["asset_count"] == 2
    assert data["controls_count"] == 2


def test_upload_zip_success():
    csv_dict = _create_sample_csv_bytes()
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for name, content in csv_dict.items():
            z.writestr(name, content)
    zip_buffer.seek(0)

    files = [
        ("files", ("dataset.zip", zip_buffer, "application/zip"))
    ]

    response = client.post("/api/datasets/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["asset_count"] == 2


def test_upload_json_payload_success():
    payload = {
        "assets": [
            {
                "asset_id": "AST-1",
                "business_unit": "Finance",
                "criticality": 3,
                "data_sensitivity_tier": "Internal",
                "financial_value_usd": 100000,
                "downtime_cost_per_hour_usd": 1000
            }
        ],
        "controls": [
            {
                "control_id": "CTRL-1",
                "name": "EDR",
                "risk_reduction_pct": 0.85,
                "cost_usd": 20000
            }
        ],
        "asset_controls": [
            {"asset_id": "AST-1", "control_id": "CTRL-1"}
        ],
        "threat_events": [
            {
                "event_id": "EVT-1",
                "asset_id": "AST-1",
                "downtime_hours_caused": 1,
                "records_compromised": 10
            }
        ],
        "vulnerabilities": [
            {
                "asset_id": "AST-1",
                "cve_id": "CVE-2023-1111",
                "cvss_score": 8.0,
                "epss_score": 0.5
            }
        ]
    }

    response = client.post("/api/datasets/upload-json", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["asset_count"] == 1


def _create_card_excel_bytes(n_rows=40):
    import numpy as np

    rng = np.random.default_rng(7)
    df = pd.DataFrame({
        "id": [f"{1000 + i}" for i in range(n_rows)],
        "client_id": rng.integers(1, max(2, n_rows // 3), n_rows),
        "card_brand": rng.choice(["Visa", "Mastercard", "American Express"], n_rows),
        "card_type": rng.choice(["debit", "credit"], n_rows),
        "card_number": [f"4{i:015d}" for i in range(n_rows)],
        "expires": ["12/2027"] * n_rows,
        "cvv": rng.integers(100, 999, n_rows),
        "has_chip": rng.choice(["YES", "NO"], n_rows),
        "num_cards_issued": rng.integers(1, 4, n_rows),
        "credit_limit": rng.integers(500, 30000, n_rows),
        "acct_open_date": ["01/2015"] * n_rows,
        "year_pin_last_changed": rng.integers(2010, 2026, n_rows),
        "card_on_dark_web": rng.choice(["Yes", "No"], n_rows),
    })

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Sheet1", index=False)
    buffer.seek(0)
    return buffer, df


def test_upload_excel_card_dataset_success():
    buffer, df = _create_card_excel_bytes(n_rows=40)
    files = [("files", ("Financial Transactions.xlsx", buffer, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]

    response = client.post("/api/datasets/upload", files=files)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "success"
    assert data["asset_count"] == len(df)

    summary = data["excel_summary"]
    assert summary is not None
    assert summary["file_name"] == "Financial Transactions.xlsx"
    assert summary["total_rows"] == len(df)
    assert summary["total_columns"] == 13
    assert summary["worksheets"] == ["Sheet1"]
    assert "card" in summary["dataset_type"].lower()
    assert any(c["column"] == "card_on_dark_web" for c in summary["column_details"])


def test_upload_excel_multisheet_workbook_success():
    csv_dict = _create_sample_csv_bytes()
    frames = {name.replace(".csv", ""): pd.read_csv(io.BytesIO(content)) for name, content in csv_dict.items()}

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for sheet, frame in frames.items():
            frame.to_excel(writer, sheet_name=sheet, index=False)
    buffer.seek(0)

    files = [("files", ("risk_dataset.xlsx", buffer, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    response = client.post("/api/datasets/upload", files=files)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "success"
    assert data["asset_count"] == 2
    assert data["excel_summary"]["worksheet_count"] == 5


def test_upload_excel_unsupported_schema():
    df = pd.DataFrame({"foo": [1, 2, 3], "bar": ["a", "b", "c"]})
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Sheet1", index=False)
    buffer.seek(0)

    files = [("files", ("random.xlsx", buffer, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))]
    response = client.post("/api/datasets/upload", files=files)
    assert response.status_code == 400
    assert "Unsupported Excel workbook" in response.json()["detail"]


def test_upload_missing_required_files():
    # Only upload assets and controls
    csv_dict = _create_sample_csv_bytes()
    files = [
        ("files", ("assets.csv", io.BytesIO(csv_dict["assets.csv"]), "text/csv")),
        ("files", ("controls.csv", io.BytesIO(csv_dict["controls.csv"]), "text/csv")),
    ]

    response = client.post("/api/datasets/upload", files=files)
    assert response.status_code == 400
    assert "Missing required datasets" in response.json()["detail"]


def test_upload_invalid_risk_reduction_pct():
    csv_dict = _create_sample_csv_bytes()
    # Replace controls with percentage > 1.0 (e.g. 80 instead of 0.8)
    csv_dict["controls.csv"] = (
        "control_id,name,risk_reduction_pct,cost_usd\n"
        "CTRL-1,EDR,80.0,20000\n"
    ).encode("utf-8")

    files = [
        ("files", (name, io.BytesIO(content), "text/csv"))
        for name, content in csv_dict.items()
    ]

    response = client.post("/api/datasets/upload", files=files)
    assert response.status_code == 400
    assert "risk_reduction_pct" in response.json()["detail"]


def test_upload_negative_financial_value():
    csv_dict = _create_sample_csv_bytes()
    csv_dict["assets.csv"] = (
        "asset_id,business_unit,criticality,data_sensitivity_tier,financial_value_usd,downtime_cost_per_hour_usd\n"
        "AST-1,Finance,3,Internal,-5000,1000\n"
    ).encode("utf-8")

    files = [
        ("files", (name, io.BytesIO(content), "text/csv"))
        for name, content in csv_dict.items()
    ]

    response = client.post("/api/datasets/upload", files=files)
    assert response.status_code == 400
    assert "Negative financial_value_usd" in response.json()["detail"]


def test_load_demo_dataset():
    response = client.post("/api/datasets/demo")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["asset_count"] > 0
