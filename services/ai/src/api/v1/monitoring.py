"""Monitoring and health API endpoints."""

import time
from fastapi import APIRouter, Response
from fastapi.responses import PlainTextResponse

from src.services.monitoring import metrics, health_checker

router = APIRouter()


@router.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics() -> str:
    """Prometheus-compatible metrics endpoint."""
    return metrics.to_prometheus()


@router.get("/health/detailed")
async def detailed_health() -> dict:
    """Detailed health check with all subsystems."""
    health_checker.check_gpu()
    health_checker.check_models()
    return health_checker.get_health()


@router.get("/health/live")
async def liveness() -> dict:
    """Kubernetes-style liveness probe."""
    return {"status": "alive", "timestamp": time.time()}


@router.get("/health/ready")
async def readiness() -> dict:
    """Kubernetes-style readiness probe."""
    health_checker.check_gpu()
    health = health_checker.get_health()
    if health["status"] == "healthy":
        return {"status": "ready"}
    return {"status": "not_ready", "details": health}
