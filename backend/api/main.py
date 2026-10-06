import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy import text

from core.config import settings
from core.errors import AppException, build_error_response
from db.session import engine, init_db, SessionLocal

# Import API v1 routers
from api.v1.alerts import router as alerts_v1_router
from api.v1.auth import router as auth_v1_router
from api.v1.chat import router as chat_v1_router
from api.v1.datasets import router as datasets_v1_router
from api.v1.jobs import router as jobs_v1_router
from api.v1.live_feed import router as live_feed_v1_router
from api.v1.organizations import router as organizations_v1_router
from api.v1.policies import router as policies_v1_router
from api.v1.regulatory import router as regulatory_v1_router
from api.v1.remediation import router as remediation_v1_router
from api.v1.risk import router as risk_v1_router
from api.v1.threat_intel import router as threat_intel_v1_router

# Deprecated unversioned compatibility stubs (return 410 Gone)
from api.legacy import router as legacy_router

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup
    init_db()
    # Ensure regulatory rules are pre-populated
    try:
        from risk_engine.regulatory.engine import RegulatoryAssessmentEngine
        db = SessionLocal()
        engine_reg = RegulatoryAssessmentEngine(db)
        engine_reg.sync_rules()
        db.close()
    except Exception as e:
        logger.warning("Could not sync regulatory rules on startup: %s", str(e))
    yield


app = FastAPI(
    title="CyberQuant Risk Quantification API",
    description="FAIR-aligned enterprise cyber risk quantification, investment optimization, and compliance platform.",
    version="2.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware: Request ID & Security Headers
# ---------------------------------------------------------------------------
@app.middleware("http")
async def request_id_and_security_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = req_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = req_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    return response


# ---------------------------------------------------------------------------
# Exception Handlers: Uniform Error Shape
# ---------------------------------------------------------------------------
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return build_error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        request_id=req_id,
        details=exc.details,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return build_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code="VALIDATION_ERROR",
        message="Request validation failed",
        request_id=req_id,
        details=exc.errors(),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        410: "ENDPOINT_DEPRECATED",
        413: "PAYLOAD_TOO_LARGE",
        422: "UNPROCESSABLE_ENTITY",
        500: "INTERNAL_SERVER_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
    }
    return build_error_response(
        status_code=exc.status_code,
        code=code_map.get(exc.status_code, "ERROR"),
        message=str(exc.detail),
        request_id=req_id,
    )


# ---------------------------------------------------------------------------
# CORS Configuration
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Mount Versioned Canonical Routers (/api/v1)
# ---------------------------------------------------------------------------
app.include_router(auth_v1_router)
app.include_router(organizations_v1_router)
app.include_router(datasets_v1_router)
app.include_router(jobs_v1_router)
app.include_router(risk_v1_router)
app.include_router(threat_intel_v1_router)
app.include_router(policies_v1_router)
app.include_router(regulatory_v1_router)
app.include_router(alerts_v1_router)
app.include_router(remediation_v1_router)
app.include_router(chat_v1_router)
app.include_router(live_feed_v1_router)

# Deprecated unversioned paths now return 410 Gone with a migration pointer.
app.include_router(legacy_router)


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")


@app.get("/health")
def health_check():
    """Basic health liveness check."""
    return {"status": "ok", "version": "2.0.0"}


@app.get("/readyz")
def readiness_check():
    """Deep readiness check verifying database and worker execution readiness."""
    db_ok = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            db_ok = True
    except Exception as e:
        logger.error("Readiness check DB error: %s", str(e))

    if not db_ok:
        raise HTTPException(status_code=503, detail="Database dependency unavailable")

    return {
        "status": "ready",
        "database": "connected",
        "worker": "in_process" if settings.USE_IN_PROCESS_WORKER else "redis_rq",
    }
