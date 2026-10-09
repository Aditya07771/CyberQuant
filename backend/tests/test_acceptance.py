import io
import time

import pytest

from conftest import build_valid_csv_bundle, wait_for_job


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def test_auth_lifecycle_and_unauthorized_access(app_client):
    email = f"auth_{time.time_ns()}@example.com"
    password = "Str0ng!Passw0rd"

    reg = app_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Auth User", "organization_name": "Auth Org"},
    )
    assert reg.status_code in (200, 201), reg.text
    tokens = reg.json()["tokens"]
    assert tokens["access_token"] and tokens["refresh_token"]

    login = app_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    access = login.json()["tokens"]["access_token"]
    refresh = login.json()["tokens"]["refresh_token"]

    me = app_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 200
    assert me.json()["user"]["email"] == email

    rotated = app_client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert rotated.status_code == 200, rotated.text
    assert rotated.json()["tokens"]["access_token"]
    assert rotated.json()["tokens"]["refresh_token"] != refresh

    logout = app_client.post("/api/v1/auth/logout", json={"refresh_token": rotated.json()["tokens"]["refresh_token"]})
    assert logout.status_code == 204

    # Unauthenticated access is rejected with the uniform error shape.
    unauthed = app_client.get("/api/v1/datasets")
    assert unauthed.status_code == 401
    body = unauthed.json()
    assert body["error"]["code"]
    assert "request_id" in body["error"]


def test_login_with_wrong_password_rejected(app_client):
    email = f"auth_bad_{time.time_ns()}@example.com"
    app_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Str0ng!Passw0rd", "full_name": "X", "organization_name": "Y"},
    )
    bad = app_client.post("/api/v1/auth/login", json={"email": email, "password": "WrongPassword1!"})
    assert bad.status_code == 401


# ---------------------------------------------------------------------------
# Shared run fixture: demo dataset + completed risk run
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def demo_run(app_client):
    email = f"demo_owner_{time.time_ns()}@example.com"
    reg = app_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Str0ng!Passw0rd", "full_name": "Demo Owner", "organization_name": "Demo Org"},
    )
    headers = {"Authorization": f"Bearer {reg.json()['tokens']['access_token']}"}
    org_id = reg.json()["organization"]["id"]

    demo = app_client.post("/api/v1/datasets/demo", headers=headers)
    assert demo.status_code == 202, demo.text
    dataset_id = demo.json()["dataset_id"]
    wait_for_job(app_client, demo.json()["job_id"], headers, timeout=180)

    run_resp = app_client.post(f"/api/v1/datasets/{dataset_id}/runs", headers=headers, json={"rng_seed": 42, "n_simulations": 5000})
    assert run_resp.status_code == 202, run_resp.text
    run_id = run_resp.json()["run_id"]
    job = wait_for_job(app_client, run_resp.json()["job_id"], headers, timeout=180)
    assert job["state"] == "succeeded", job

    detail = app_client.get(f"/api/v1/datasets/{dataset_id}/runs/{run_id}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["state"] == "completed", detail.json()

    return {"client": app_client, "headers": headers, "org_id": org_id, "dataset_id": dataset_id, "run_id": run_id}


# ---------------------------------------------------------------------------
# Risk envelope + tenant isolation
# ---------------------------------------------------------------------------

def test_risk_endpoints_return_run_envelope(demo_run):
    client = demo_run["client"]
    headers = demo_run["headers"]
    base = f"/api/v1/datasets/{demo_run['dataset_id']}/runs/{demo_run['run_id']}"

    assets = client.get(f"{base}/risk/assets", headers=headers)
    assert assets.status_code == 200, assets.text
    body = assets.json()
    assert body["run"]["run_id"] == demo_run["run_id"]
    assert body["run"]["currency"] == "USD"
    assert body["run"]["model_version"]
    assert body["run"]["data_quality"]
    assert isinstance(body["results"], list)

    org = client.get(f"{base}/risk/organization", headers=headers)
    assert org.status_code == 200
    assert "data" in org.json()

    lec = client.get(f"{base}/risk/portfolio-lec", headers=headers)
    assert lec.status_code == 200
    assert "total_eal_usd" in lec.json()["data"]

    graph = client.get(f"{base}/risk/dependency-graph", headers=headers)
    assert graph.status_code == 200
    assert graph.json()["data"]["edge_source"] == "inferred"

    posture = client.get(f"{base}/compliance/posture", headers=headers)
    assert posture.status_code == 200
    assert posture.json()["data"]["mapping_version"]

    preds = client.get(f"{base}/predictions/vulnerabilities", headers=headers)
    assert preds.status_code == 200
    assert preds.json()["ml_metadata"]["human_review_required"] is True


def test_risk_endpoints_are_tenant_isolated(demo_run, tenant_b):
    client = tenant_b["client"]
    headers = tenant_b["headers"]
    base = f"/api/v1/datasets/{demo_run['dataset_id']}/runs/{demo_run['run_id']}"

    assert client.get(f"{base}/risk/assets", headers=headers).status_code == 404
    assert client.get(f"{base}/compliance/posture", headers=headers).status_code == 404
    assert client.get(f"{base}/predictions/threat-forecast", headers=headers).status_code == 404
    # Unknown run in the correct dataset must also 404.
    assert client.get(
        f"/api/v1/datasets/{demo_run['dataset_id']}/runs/does-not-exist/risk/assets",
        headers=headers,
    ).status_code == 404


# ---------------------------------------------------------------------------
# Threat intelligence
# ---------------------------------------------------------------------------

def test_threat_intel_status_reports_offline_without_imputation(tenant_a):
    client = tenant_a["client"]
    resp = client.get("/api/v1/threat-intel/status", headers=tenant_a["headers"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "offline_sample"
    assert "note" in body
    assert body["sources"]["first_epss"]["status"] == "offline_sample"


def test_threat_intel_refresh_requires_admin(app_client):
    email = f"viewer_{time.time_ns()}@example.com"
    reg = app_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Str0ng!Passw0rd", "full_name": "V", "organization_name": "V Org"},
    )
    headers = {"Authorization": f"Bearer {reg.json()['tokens']['access_token']}"}
    org_id = reg.json()["organization"]["id"]

    # Downgrade the freshly-registered owner to a viewer to test role enforcement.
    from db.session import SessionLocal
    from db.models import Membership

    db = SessionLocal()
    try:
        m = db.query(Membership).filter(Membership.organization_id == org_id).first()
        m.role = "viewer"
        db.commit()
    finally:
        db.close()

    resp = app_client.post("/api/v1/threat-intel/refresh", headers=headers)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Scanners
# ---------------------------------------------------------------------------

OPENVAS_XML = """<?xml version="1.0"?>
<report>
  <results>
    <result id="r1">
      <host>AST-1</host>
      <port>443/tcp</port>
      <severity>9.8</severity>
      <threat>Critical</threat>
      <description>Log4Shell detected</description>
      <nvt>
        <name>Log4Shell</name>
        <cve>CVE-2021-44228</cve>
        <solution>Upgrade log4j</solution>
      </nvt>
    </result>
    <result id="r2">
      <host>UNKNOWN-HOST</host>
      <port>80/tcp</port>
      <severity>5.0</severity>
      <threat>Medium</threat>
      <description>Unknown asset finding</description>
      <nvt>
        <name>Generic</name>
        <cve>CVE-2020-0001</cve>
      </nvt>
    </result>
  </results>
</report>
"""

APPSEC_CSV = "id,cve_id,asset_id,cvss_score,severity,package\nA1,CVE-2021-44228,AST-2,10.0,Critical,log4j-core\n"


@pytest.fixture(scope="session")
def uploaded_dataset(app_client):
    email = f"scan_owner_{time.time_ns()}@example.com"
    reg = app_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Str0ng!Passw0rd", "full_name": "Scan Owner", "organization_name": "Scan Org"},
    )
    headers = {"Authorization": f"Bearer {reg.json()['tokens']['access_token']}"}

    bundle = build_valid_csv_bundle()
    files = [("files", (name, io.BytesIO(content), "text/csv")) for name, content in bundle.items()]
    resp = app_client.post("/api/v1/datasets", headers=headers, data={"name": "Scan Dataset"}, files=files)
    assert resp.status_code == 202, resp.text
    wait_for_job(app_client, resp.json()["job_id"], headers)
    return {"client": app_client, "headers": headers, "dataset_id": resp.json()["dataset_id"]}


def test_scanner_upload_and_finding_reconciliation(uploaded_dataset):
    client = uploaded_dataset["client"]
    headers = uploaded_dataset["headers"]
    dataset_id = uploaded_dataset["dataset_id"]

    openvas = client.post(
        f"/api/v1/datasets/{dataset_id}/scans",
        headers=headers,
        data={"scanner_type": "openvas"},
        files=[("file", ("report.xml", OPENVAS_XML.encode("utf-8"), "text/xml"))],
    )
    assert openvas.status_code == 202, openvas.text
    assert openvas.json()["scan_id"]
    wait_for_job(client, openvas.json()["job_id"], headers)

    appsec = client.post(
        f"/api/v1/datasets/{dataset_id}/scans",
        headers=headers,
        data={"scanner_type": "appsec"},
        files=[("file", ("appsec.csv", APPSEC_CSV.encode("utf-8"), "text/csv"))],
    )
    assert appsec.status_code == 202, appsec.text
    wait_for_job(client, appsec.json()["job_id"], headers)

    scans = client.get(f"/api/v1/datasets/{dataset_id}/scans", headers=headers)
    assert scans.status_code == 200
    assert scans.json()["total"] >= 2

    scan_id = openvas.json()["scan_id"]
    detail = client.get(f"/api/v1/datasets/{dataset_id}/scans/{scan_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["state"] == "succeeded"

    findings = client.get(f"/api/v1/datasets/{dataset_id}/scans/{scan_id}/findings", headers=headers)
    assert findings.status_code == 200
    rows = findings.json()["findings"]
    assert len(rows) >= 2
    assert any(f["match_status"] == "matched" for f in rows)
    assert any(f["match_status"] == "unmatched" for f in rows)


def test_scan_history_is_tenant_isolated(uploaded_dataset, tenant_b):
    resp = tenant_b["client"].get(
        f"/api/v1/datasets/{uploaded_dataset['dataset_id']}/scans",
        headers=tenant_b["headers"],
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Regulatory
# ---------------------------------------------------------------------------

def test_regulatory_rules_and_assessment_review(uploaded_dataset, tenant_b):
    client = uploaded_dataset["client"]
    headers = uploaded_dataset["headers"]
    dataset_id = uploaded_dataset["dataset_id"]

    rules = client.get("/api/v1/regulatory/rules", headers=headers)
    assert rules.status_code == 200, rules.text
    assert len(rules.json()) > 0

    evaluate = client.post(f"/api/v1/datasets/{dataset_id}/regulatory/assessments", headers=headers)
    assert evaluate.status_code == 200, evaluate.text
    assert "total_assessments" in evaluate.json()

    from db.session import SessionLocal
    from db.models import RegulatoryAssessment

    db = SessionLocal()
    try:
        assessment = db.query(RegulatoryAssessment).filter(RegulatoryAssessment.dataset_id == dataset_id).first()
        assessment_id = assessment.id if assessment else None
    finally:
        db.close()

    if assessment_id is None:
        pytest.skip("No regulatory assessments generated for the uploaded fixture")

    reviewed = client.post(
        f"/api/v1/regulatory/assessments/{assessment_id}/review",
        headers=headers,
        json={"decision": "reviewed", "rationale": "Reviewed by compliance."},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["new_status"] == "reviewed"

    # Cross-tenant review must not be possible.
    cross = tenant_b["client"].post(
        f"/api/v1/regulatory/assessments/{assessment_id}/review",
        headers=tenant_b["headers"],
        json={"decision": "not_applicable", "rationale": "n/a"},
    )
    assert cross.status_code == 404


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

def _insert_alert(org_id, dataset_id, run_id):
    from db.session import SessionLocal
    from db.models import RiskAlert

    db = SessionLocal()
    try:
        alert = RiskAlert(
            organization_id=org_id,
            dataset_id=dataset_id,
            run_id=run_id,
            severity="high",
            category="risk_appetite_breach",
            dedupe_key=f"test-{time.time_ns()}",
            title="Test alert",
            description="Synthetic alert for testing.",
            status="open",
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        return alert.id
    finally:
        db.close()


def test_alert_lifecycle_and_scoping(demo_run, tenant_b):
    client = demo_run["client"]
    headers = demo_run["headers"]
    alert_id = _insert_alert(demo_run["org_id"], demo_run["dataset_id"], demo_run["run_id"])

    listed = client.get("/api/v1/alerts", headers=headers)
    assert listed.status_code == 200
    assert any(a["id"] == alert_id for a in listed.json()["alerts"])

    ack = client.post(f"/api/v1/alerts/{alert_id}/acknowledge", headers=headers)
    assert ack.status_code == 200, ack.text
    assert ack.json()["new_status"] == "acknowledged"

    resolve = client.post(f"/api/v1/alerts/{alert_id}/resolve", headers=headers)
    assert resolve.status_code == 200
    assert resolve.json()["new_status"] == "resolved"

    # Assigning to a non-member is rejected.
    bad_assign = client.post(
        f"/api/v1/alerts/{alert_id}/assign",
        headers=headers,
        json={"owner_id": "not-a-member"},
    )
    assert bad_assign.status_code == 404

    # Cross-tenant access yields 404, not the alert.
    assert tenant_b["client"].get(f"/api/v1/alerts/{alert_id}", headers=tenant_b["headers"]).status_code == 404
    assert tenant_b["client"].get(f"/api/v1/alerts/{alert_id}/deliveries", headers=tenant_b["headers"]).status_code == 404
    cross_ack = tenant_b["client"].post(f"/api/v1/alerts/{alert_id}/acknowledge", headers=tenant_b["headers"])
    assert cross_ack.status_code == 404


def test_alert_list_is_org_scoped(demo_run, tenant_b):
    alerts_b = tenant_b["client"].get("/api/v1/alerts", headers=tenant_b["headers"])
    assert alerts_b.status_code == 200
    assert alerts_b.json()["alerts"] == []


# ---------------------------------------------------------------------------
# Live feed
# ---------------------------------------------------------------------------

def test_live_feed_labels_demo_telemetry_as_synthetic(demo_run):
    resp = demo_run["client"].get(
        "/api/v1/live-feed/recent",
        headers=demo_run["headers"],
        params={"dataset_id": demo_run["dataset_id"]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["source_type"] == "synthetic_demo"
    assert len(body["events"]) > 0
    assert all(e["source_type"] == "synthetic_demo" for e in body["events"])


def test_live_feed_rejects_other_tenants_dataset(demo_run, tenant_b):
    resp = tenant_b["client"].get(
        "/api/v1/live-feed/recent",
        headers=tenant_b["headers"],
        params={"dataset_id": demo_run["dataset_id"]},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Legacy deprecation
# ---------------------------------------------------------------------------

def test_legacy_endpoints_return_410(app_client):
    for path in ["/risk/assets", "/controls/scenarios", "/compliance/posture", "/api/datasets/status"]:
        resp = app_client.get(path)
        assert resp.status_code == 410, path
        assert resp.json()["error"]["code"] == "ENDPOINT_DEPRECATED"
