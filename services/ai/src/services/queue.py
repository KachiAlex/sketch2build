import json
import uuid
from datetime import datetime, timezone
from celery import Celery
from redis import Redis

from src.config import get_settings

settings = get_settings()

celery_app = Celery(
    "sketch2build_ai",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["src.services.queue"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minutes max per task
    worker_prefetch_multiplier=1,  # Don't prefetch tasks (important for GPU)
)

redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


def _store_job_metadata(job_id: str, status: str, progress: float = 0.0, output: dict | None = None, error: str | None = None):
    """Store job metadata in Redis for fast polling."""
    data = {
        "job_id": job_id,
        "status": status,
        "progress": progress,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if output is not None:
        data["output"] = output
    if error is not None:
        data["error"] = error
    redis_client.hset(f"job:{job_id}", mapping={k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) for k, v in data.items()})
    redis_client.expire(f"job:{job_id}", 86400)  # 24h TTL


def get_task_result(job_id: str) -> dict | None:
    raw = redis_client.hgetall(f"job:{job_id}")
    if not raw:
        return None
    result = {}
    for k, v in raw.items():
        try:
            result[k] = json.loads(v)
        except (json.JSONDecodeError, TypeError):
            result[k] = v
    return result


@celery_app.task(bind=True)
def generate_design_task(self, job_id: str, **kwargs):
    """Celery task: runs the full design generation pipeline."""
    from src.inference.pipeline import DesignPipeline

    _store_job_metadata(job_id, "processing", progress=0.1)
    self.update_state(state="PROGRESS", meta={"progress": 10})

    try:
        pipeline = DesignPipeline()
        result = pipeline.run(job_id=job_id, **kwargs)

        _store_job_metadata(job_id, "completed", progress=1.0, output=result)
        self.update_state(state="SUCCESS", meta={"progress": 100})
        return result

    except Exception as exc:
        _store_job_metadata(job_id, "failed", error=str(exc))
        self.update_state(state="FAILURE", meta={"error": str(exc)})
        raise
