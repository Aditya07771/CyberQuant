import logging
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.config import settings
from db.models import IngestionJob
from db.session import SessionLocal

logger = logging.getLogger(__name__)

# In-process worker thread pool for background tasks (development / single-node).
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="cyberquant-worker")


def _dispatch(job_id: str, fn: Callable, args: tuple, kwargs: Dict[str, Any]) -> None:
    """
    Sends a job to the configured worker backend.

    ``USE_IN_PROCESS_WORKER=true`` (default) runs in this process for local/dev
    use. Otherwise the job is enqueued on Redis/RQ; if the queue backend is
    unavailable the request fails loudly instead of silently degrading.
    """
    if settings.USE_IN_PROCESS_WORKER:
        _executor.submit(execute_job_wrapper, job_id, fn, *args, **kwargs)
        return

    try:
        from redis import Redis
        from rq import Queue
    except ImportError as exc:  # pragma: no cover - depends on deployment extras
        raise RuntimeError(
            "USE_IN_PROCESS_WORKER is disabled but redis/rq are not installed."
        ) from exc

    try:
        connection = Redis.from_url(settings.REDIS_URL)
        queue = Queue("cyberquant", connection=connection)
        fn_path = f"{fn.__module__}:{fn.__qualname__}"
        queue.enqueue(
            "jobs.tasks.execute_job",
            job_id,
            fn_path,
            args,
            kwargs,
            job_timeout=1800,
        )
    except Exception as exc:  # pragma: no cover - depends on deployment infra
        raise RuntimeError(f"Failed to enqueue job on Redis/RQ: {exc}") from exc


def execute_job_wrapper(job_id: str, fn: Callable, *args: Any, **kwargs: Any) -> None:
    """Wrapper that updates job state in DB across execution lifecycle."""
    db: Session = SessionLocal()
    try:
        job = db.scalars(select(IngestionJob).where(IngestionJob.id == job_id)).first()
        if not job:
            logger.error("Job %s not found in database for execution", job_id)
            return

        job.state = "running"
        job.started_at = datetime.now(timezone.utc)
        job.progress_pct = 5.0
        db.commit()

        # Execute task function
        result = fn(*args, job_id=job_id, **kwargs)

        # Refresh job record in case of concurrent updates
        db.refresh(job)
        job.state = "succeeded"
        job.progress_pct = 100.0
        job.finished_at = datetime.now(timezone.utc)
        if isinstance(result, dict):
            job.result_summary = result
        db.commit()
        logger.info("Job %s (%s) finished successfully", job_id, job.task_type)

    except Exception as e:
        logger.exception("Job %s failed with exception: %s", job_id, str(e))
        db.rollback()
        try:
            job = db.scalars(select(IngestionJob).where(IngestionJob.id == job_id)).first()
            if job:
                job.state = "failed"
                job.finished_at = datetime.now(timezone.utc)
                job.safe_error_code = type(e).__name__
                # Sanitize error message to prevent leaking internal traces to client
                job.safe_error_message = str(e)[:500]
                db.commit()
        except Exception:
            logger.exception("Failed to update failed state for job %s", job_id)
    finally:
        db.close()


def enqueue_job(
    task_type: str,
    fn: Callable,
    args: tuple = (),
    kwargs: Optional[Dict[str, Any]] = None,
    org_id: str = "",
    dataset_id: Optional[str] = None,
    version_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    db: Optional[Session] = None,
) -> IngestionJob:
    """
    Creates an IngestionJob row in DB and schedules it for background execution.
    Supports idempotency key: if key exists for org and is queued/running/succeeded, returns existing job.
    """
    close_db_when_done = False
    if db is None:
        db = SessionLocal()
        close_db_when_done = True

    try:
        if idempotency_key:
            existing = db.scalars(
                select(IngestionJob).where(
                    IngestionJob.organization_id == org_id,
                    IngestionJob.idempotency_key == idempotency_key,
                )
            ).first()
            if existing and existing.state in ("queued", "running", "succeeded"):
                logger.info("Returning existing job %s for idempotency key %s", existing.id, idempotency_key)
                return existing

        now = datetime.now(timezone.utc)
        job = IngestionJob(
            organization_id=org_id,
            dataset_id=dataset_id,
            version_id=version_id,
            task_type=task_type,
            idempotency_key=idempotency_key,
            state="queued",
            progress_pct=0.0,
            created_at=now,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        kw = kwargs or {}
        _dispatch(job.id, fn, args, kw)
        return job

    finally:
        if close_db_when_done:
            db.close()


def update_job_progress(job_id: str, progress_pct: float, db: Optional[Session] = None) -> None:
    """Updates the progress percentage of an active job."""
    local_db = db or SessionLocal()
    try:
        job = local_db.scalars(select(IngestionJob).where(IngestionJob.id == job_id)).first()
        if job and job.state == "running":
            job.progress_pct = max(0.0, min(100.0, progress_pct))
            local_db.commit()
    finally:
        if db is None:
            local_db.close()
