import io
import json
import time
import zipfile

import pytest
from fastapi.testclient import TestClient

from conftest import build_valid_csv_bundle, wait_for_job


def test_legacy_dataset_endpoints_are_deprecated(app_client):
    assert app_client.get("/api/datasets/status").status_code == 410
    assert app_client.post("/api/datasets/demo").status_code == 410
    assert app_client.get("/risk/assets").status_code == 410
    assert app_client.post("/chat", json={"message": "hi"}).status_code == 410


def test_status_and_list_require_auth(app_client):
    assert app_client.get("/api/v1/datasets").status_code == 401
    assert app_client.get("/api/v1/datasets/does-not-exist/status").status_code == 401


def test_upload_multiple_csvs_enqueues_ingestion(tenant_a):
    client = tenant_a["client"]
    headers = tenant_a["headers"]
    bundle = build_valid_csv_bundle()
    files = [("files", (name, io.BytesIO(content), "text/csv")) for name, content in bundle.items()]

    resp = client.post(
        "/api/v1/datasets",
        headers=headers,
        data={"name": "CSV Bundle", "dataset_type": "tabular"},
        files=files,
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["dataset_id"]
    assert body["version_id"]
    assert body["job_id"]

    job = wait_for_job(client, body["job_id"], headers)
    assert job["state"] == "succeeded", job

    detail = client.get(f"/api/v1/datasets/{body['dataset_id']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["active_version_id"] == body["version_id"]


def test_upload_zip_archive(tenant_a):
    client = tenant_a["client"]
    headers = tenant_a["headers"]
    bundle = build_valid_csv_bundle()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, content in bundle.items():
            z.writestr(name, content)
    buf.seek(0)

    resp = client.post(
        "/api/v1/datasets",
        headers=headers,
        data={"name": "ZIP Bundle"},
        files=[("files", ("bundle.zip", buf, "application/zip"))],
    )
    assert resp.status_code == 202, resp.text
    job = wait_for_job(client, resp.json()["job_id"], headers)
    assert job["state"] == "succeeded", job


def test_upload_zip_rejects_path_traversal(tenant_a):
    client = tenant_a["client"]
    headers = tenant_a["headers"]

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("../../evil.csv", "asset_id\nx\n")
        for name, content in build_valid_csv_bundle().items():
            z.writestr(name, content)
    buf.seek(0)

    resp = client.post(
        "/api/v1/datasets",
        headers=headers,
        data={"name": "Evil ZIP"},
        files=[("files", ("evil.zip", buf, "application/zip"))],
    )
    assert resp.status_code == 400, resp.text


def test_upload_missing_required_tables_rejected(tenant_a):
    client = tenant_a["client"]
    headers = tenant_a["headers"]
    bundle = build_valid_csv_bundle()
    bundle.pop("controls.csv")
    files = [("files", (name, io.BytesIO(content), "text/csv")) for name, content in bundle.items()]

    resp = client.post(
        "/api/v1/datasets",
        headers=headers,
        data={"name": "Incomplete"},
        files=files,
    )
    assert resp.status_code == 400, resp.text


def test_upload_rejects_invalid_risk_reduction(tenant_a):
    client = tenant_a["client"]
    headers = tenant_a["headers"]
    bundle = build_valid_csv_bundle()
    bundle["controls.csv"] = (
        "control_id,name,risk_reduction_pct,cost_usd\n"
        "CTRL-1,EDR,1.8,20000\n"
    ).encode("utf-8")
    files = [("files", (name, io.BytesIO(content), "text/csv")) for name, content in bundle.items()]

    resp = client.post(
        "/api/v1/datasets",
        headers=headers,
        data={"name": "Bad Controls"},
        files=files,
    )
    assert resp.status_code == 400, resp.text


def test_demo_dataset_endpoint(tenant_a):
    client = tenant_a["client"]
    headers = tenant_a["headers"]

    resp = client.post("/api/v1/datasets/demo", headers=headers)
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["dataset_type"] == "demo"
    job = wait_for_job(client, body["job_id"], headers, timeout=120)
    assert job["state"] == "succeeded", job


def test_dataset_isolation_between_tenants(tenant_a, tenant_b):
    client_a = tenant_a["client"]
    headers_a = tenant_a["headers"]

    bundle = build_valid_csv_bundle()
    files = [("files", (name, io.BytesIO(content), "text/csv")) for name, content in bundle.items()]
    resp = client_a.post(
        "/api/v1/datasets",
        headers=headers_a,
        data={"name": "Tenant A Only"},
        files=files,
    )
    dataset_id = resp.json()["dataset_id"]
    wait_for_job(client_a, resp.json()["job_id"], headers_a)

    # Tenant B must not see or access Tenant A's dataset.
    assert client_a.get("/api/v1/datasets", headers=tenant_b["headers"]).json() == []
    cross = client_a.get(f"/api/v1/datasets/{dataset_id}", headers=tenant_b["headers"])
    assert cross.status_code == 404
