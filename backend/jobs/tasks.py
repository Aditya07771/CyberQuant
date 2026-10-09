"""RQ worker entrypoints.

Run a durable worker with::

    rq worker cyberquant --url $REDIS_URL

The enqueued callable is ``jobs.tasks.execute_job`` which resolves the original
task function by its import path and reuses the same lifecycle bookkeeping as the
in-process worker.
"""

import importlib
import logging
from typing import Any, Callable, Dict, Tuple

logger = logging.getLogger(__name__)


def _resolve_callable(fn_path: str) -> Callable:
    module_name, _, qualname = fn_path.partition(":")
    module = importlib.import_module(module_name)
    target: Any = module
    for attr in qualname.split("."):
        target = getattr(target, attr)
    return target


def execute_job(job_id: str, fn_path: str, args: Tuple[Any, ...] = (), kwargs: Dict[str, Any] | None = None) -> None:
    """RQ entrypoint: resolve the task and run it through the job lifecycle wrapper."""
    from jobs.runner import execute_job_wrapper

    fn = _resolve_callable(fn_path)
    execute_job_wrapper(job_id, fn, *(args or ()), **(kwargs or {}))
