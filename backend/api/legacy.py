"""
Deprecated unversioned endpoint stubs.

The original application exposed shared-output, unauthenticated endpoints
(filesystem-backed risk artifacts, chat, live feed and dataset uploads) at
unversioned paths. Those endpoints are unsafe for multi-tenant use and have been
replaced by the authenticated, dataset/run-scoped `/api/v1` routes.

These stubs keep the old paths resolvable but return `410 Gone` with a migration
pointer so existing clients fail loudly instead of silently reading another
tenant's outputs.
"""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["deprecated"])

DEPRECATED_PATHS = {
    ("GET", "/risk/assets"): "/api/v1/datasets/{dataset_id}/runs/{run_id}/risk/assets",
    ("GET", "/risk/assets/{asset_id}"): "/api/v1/datasets/{dataset_id}/runs/{run_id}/risk/assets/{asset_id}",
    ("GET", "/risk/assets/{asset_id}/drivers"): "/api/v1/datasets/{dataset_id}/runs/{run_id}/risk/assets/{asset_id}/drivers",
    ("GET", "/risk/business-units"): "/api/v1/datasets/{dataset_id}/runs/{run_id}/risk/business-units",
    ("GET", "/risk/organization"): "/api/v1/datasets/{dataset_id}/runs/{run_id}/risk/organization",
    ("GET", "/risk/portfolio-lec"): "/api/v1/datasets/{dataset_id}/runs/{run_id}/risk/portfolio-lec",
    ("GET", "/risk/trend"): "/api/v1/datasets/{dataset_id}/runs/{run_id}/risk/trend",
    ("GET", "/risk/dependency-graph"): "/api/v1/datasets/{dataset_id}/runs/{run_id}/risk/dependency-graph",
    ("GET", "/risk/dependency-graph/propagate"): "/api/v1/datasets/{dataset_id}/runs/{run_id}/risk/dependency-graph/propagate",
    ("GET", "/controls/scenarios"): "/api/v1/datasets/{dataset_id}/runs/{run_id}/controls/scenarios",
    ("GET", "/controls/roi"): "/api/v1/datasets/{dataset_id}/runs/{run_id}/controls/roi",
    ("GET", "/controls/optimize"): "/api/v1/datasets/{dataset_id}/runs/{run_id}/controls/optimize",
    ("GET", "/controls/frontier"): "/api/v1/datasets/{dataset_id}/runs/{run_id}/controls/frontier",
    ("GET", "/compliance/posture"): "/api/v1/datasets/{dataset_id}/runs/{run_id}/compliance/posture",
    ("GET", "/compliance/gaps"): "/api/v1/datasets/{dataset_id}/runs/{run_id}/compliance/gaps",
    ("GET", "/predictions/vulnerabilities"): "/api/v1/datasets/{dataset_id}/runs/{run_id}/predictions/vulnerabilities",
    ("GET", "/predictions/threat-forecast"): "/api/v1/datasets/{dataset_id}/runs/{run_id}/predictions/threat-forecast",
    ("POST", "/chat"): "/api/v1/chat",
    ("GET", "/api/live-feed/recent"): "/api/v1/live-feed/recent",
    ("POST", "/api/datasets/upload"): "/api/v1/datasets",
    ("POST", "/api/datasets/upload-json"): "/api/v1/datasets",
    ("POST", "/api/datasets/demo"): "/api/v1/datasets/demo",
    ("GET", "/api/datasets/status"): "/api/v1/datasets/{dataset_id}/status",
}


def _deprecated_handler(replacement: str):
    async def handler(request: Request):
        return JSONResponse(
            status_code=410,
            content={
                "error": {
                    "code": "ENDPOINT_DEPRECATED",
                    "message": (
                        "This unversioned endpoint has been retired because it served shared, "
                        "unauthenticated output. Use the authenticated /api/v1 equivalent."
                    ),
                    "request_id": getattr(request.state, "request_id", None),
                    "replacement": replacement,
                }
            },
        )

    return handler


for (method, path), replacement in DEPRECATED_PATHS.items():
    router.add_api_route(
        path,
        _deprecated_handler(replacement),
        methods=[method],
        include_in_schema=False,
        name=f"deprecated_{method}_{path}",
    )
