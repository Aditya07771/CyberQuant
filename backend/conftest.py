import os
import sys
import tempfile
import time
from pathlib import Path

# Add backend directory to sys.path so risk_engine and api are importable in tests
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Configure a throwaway database and offline, in-process behaviour BEFORE the
# application settings/database modules are imported by any test module.
_TEST_DB_PATH = Path(tempfile.gettempdir()) / "cyberquant_pytest.sqlite3"
if _TEST_DB_PATH.exists():
    try:
        _TEST_DB_PATH.unlink()
    except OSError:
        pass
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH.as_posix()}"
os.environ["USE_IN_PROCESS_WORKER"] = "true"
os.environ["THREAT_INTEL_OFFLINE_MODE"] = "true"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def app_client():
    from api.main import app

    with TestClient(app) as client:
        yield client


def _register_and_login(client: TestClient, email: str, password: str = "Str0ng!Passw0rd", org_name: str = "Test Org"):
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Test User",
            "organization_name": org_name,
        },
    )
    assert resp.status_code in (200, 201), resp.text
    data = resp.json()
    tokens = data.get("tokens") or {}
    access = tokens.get("access_token") or data.get("access_token")
    assert access, data
    return {"Authorization": f"Bearer {access}"}, data


@pytest.fixture()
def tenant_a(app_client):
    headers, payload = _register_and_login(app_client, f"tenant_a_{time.time_ns()}@example.com", org_name="Tenant A")
    return {"client": app_client, "headers": headers, "auth": payload}


@pytest.fixture()
def tenant_b(app_client):
    headers, payload = _register_and_login(app_client, f"tenant_b_{time.time_ns()}@example.com", org_name="Tenant B")
    return {"client": app_client, "headers": headers, "auth": payload}


def wait_for_job(client: TestClient, job_id: str, headers: dict, timeout: float = 60.0):
    """Polls a job until it reaches a terminal state."""
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        resp = client.get(f"/api/v1/jobs/{job_id}", headers=headers)
        assert resp.status_code == 200, resp.text
        last = resp.json()
        if last.get("state") in ("succeeded", "failed"):
            return last
        time.sleep(0.25)
    raise AssertionError(f"Job {job_id} did not finish within {timeout}s; last={last}")


def build_valid_csv_bundle():
    assets = (
        "asset_id,business_unit,criticality,data_sensitivity_tier,financial_value_usd,downtime_cost_per_hour_usd\n"
        "AST-1,Finance,3,Internal,100000,1000\n"
        "AST-2,HR,2,Public,50000,500\n"
    ).encode("utf-8")
    controls = (
        "control_id,name,risk_reduction_pct,cost_usd\n"
        "CTRL-1,EDR,0.8,20000\n"
        "CTRL-2,MFA,0.6,5000\n"
    ).encode("utf-8")
    asset_controls = "asset_id,control_id\nAST-1,CTRL-1\n".encode("utf-8")
    threat_events = (
        "event_id,asset_id,downtime_hours_caused,records_compromised\n"
        "EVT-1,AST-1,2,50\n"
    ).encode("utf-8")
    vulnerabilities = (
        "asset_id,cve_id,cvss_score,epss_score\n"
        "AST-1,CVE-2021-44228,10.0,0.9\n"
    ).encode("utf-8")
    return {
        "assets.csv": assets,
        "controls.csv": controls,
        "asset_controls.csv": asset_controls,
        "threat_events.csv": threat_events,
        "vulnerabilities.csv": vulnerabilities,
    }
