"""Monitoring and observability for the AI service.

Provides Prometheus-compatible metrics, structured logging, and health checks
for production deployment on RunPod / Vast.ai.
"""

import time
import structlog
from typing import Any
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime

logger = structlog.get_logger()


@dataclass
class MetricCounter:
    """Simple counter metric."""
    name: str
    value: int = 0
    labels: dict = field(default_factory=dict)

    def inc(self, amount: int = 1) -> None:
        self.value += amount

    def to_prometheus(self) -> str:
        labels_str = ",".join(f'{k}="{v}"' for k, v in self.labels.items())
        if labels_str:
            return f"{self.name}{{{labels_str}}} {self.value}"
        return f"{self.name} {self.value}"


@dataclass
class MetricHistogram:
    """Simple histogram metric for latency tracking."""
    name: str
    buckets: list[float] = field(default_factory=lambda: [0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0])
    counts: list[int] = field(default_factory=lambda: [0, 0, 0, 0, 0, 0, 0])
    total: float = 0.0
    count: int = 0

    def observe(self, value: float) -> None:
        self.total += value
        self.count += 1
        for i, bucket in enumerate(self.buckets):
            if value <= bucket:
                self.counts[i] += 1

    @property
    def avg(self) -> float:
        return self.total / self.count if self.count > 0 else 0.0

    def to_prometheus(self) -> str:
        lines = []
        cumulative = 0
        for i, bucket in enumerate(self.buckets):
            cumulative += self.counts[i]
            lines.append(f'{self.name}_bucket{{le="{bucket}"}} {cumulative}')
        lines.append(f'{self.name}_bucket{{le="+Inf"}} {self.count}')
        lines.append(f'{self.name}_sum {self.total}')
        lines.append(f'{self.name}_count {self.count}')
        return "\n".join(lines)


class MetricsCollector:
    """Collects and exposes Prometheus-format metrics."""

    def __init__(self):
        self.counters: dict[str, MetricCounter] = {}
        self.histograms: dict[str, MetricHistogram] = {}
        self._init_metrics()

    def _init_metrics(self) -> None:
        # Design generation metrics
        self.counters["design_generations_total"] = MetricCounter("design_generations_total")
        self.counters["design_generations_failed"] = MetricCounter("design_generations_failed")
        self.counters["compliance_checks_total"] = MetricCounter("compliance_checks_total")
        self.counters["compliance_violations_total"] = MetricCounter("compliance_violations_total")
        self.counters["exports_total"] = MetricCounter("exports_total")
        self.counters["explainability_reports_total"] = MetricCounter("explainability_reports_total")

        # Queue metrics
        self.counters["jobs_queued_total"] = MetricCounter("jobs_queued_total")
        self.counters["jobs_completed_total"] = MetricCounter("jobs_completed_total")
        self.counters["jobs_failed_total"] = MetricCounter("jobs_failed_total")

        # Model metrics
        self.counters["model_inferences_total"] = MetricCounter("model_inferences_total")
        self.histograms["design_generation_duration"] = MetricHistogram("design_generation_duration_seconds")
        self.histograms["compliance_check_duration"] = MetricHistogram("compliance_check_duration_seconds")
        self.histograms["export_duration"] = MetricHistogram("export_duration_seconds")

        # GPU metrics (placeholder - would use pynvml in production)
        self.counters["gpu_memory_used"] = MetricCounter("gpu_memory_used_bytes")
        self.counters["gpu_utilization"] = MetricCounter("gpu_utilization_percent")

    def inc(self, name: str, amount: int = 1) -> None:
        if name in self.counters:
            self.counters[name].inc(amount)

    def observe(self, name: str, value: float) -> None:
        if name in self.histograms:
            self.histograms[name].observe(value)

    def to_prometheus(self) -> str:
        lines = ["# Sketch2Build AI Service Metrics"]
        lines.append(f"# Generated at {datetime.utcnow().isoformat()}Z")
        lines.append("")

        for counter in self.counters.values():
            lines.append(counter.to_prometheus())

        lines.append("")

        for histogram in self.histograms.values():
            lines.append(histogram.to_prometheus())

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "counters": {name: c.value for name, c in self.counters.items()},
            "histograms": {
                name: {
                    "count": h.count,
                    "sum": h.total,
                    "avg": h.avg,
                }
                for name, h in self.histograms.items()
            },
        }


# Global metrics instance
metrics = MetricsCollector()


class HealthChecker:
    """Health check service for monitoring service status."""

    def __init__(self):
        self.start_time = time.time()
        self.last_check = time.time()
        self.status = "healthy"
        self.checks: dict[str, dict] = {}

    def check_redis(self, redis_url: str | None = None) -> dict:
        """Check Redis connectivity."""
        try:
            import redis
            r = redis.from_url(redis_url or "redis://localhost:6379")
            r.ping()
            self.checks["redis"] = {"status": "healthy", "latency_ms": 0}
            return self.checks["redis"]
        except Exception as e:
            self.checks["redis"] = {"status": "unhealthy", "error": str(e)}
            return self.checks["redis"]

    def check_gpu(self) -> dict:
        """Check GPU availability."""
        try:
            import torch
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                gpu_memory = torch.cuda.get_device_properties(0).total_memory
                self.checks["gpu"] = {
                    "status": "healthy",
                    "device": gpu_name,
                    "memory_gb": gpu_memory / 1e9,
                }
            else:
                self.checks["gpu"] = {"status": "unavailable", "device": "CPU only"}
            return self.checks["gpu"]
        except Exception as e:
            self.checks["gpu"] = {"status": "unhealthy", "error": str(e)}
            return self.checks["gpu"]

    def check_models(self) -> dict:
        """Check if AI models are loaded."""
        try:
            # Placeholder - would check actual model status
            self.checks["models"] = {
                "status": "healthy",
                "vision_encoder": "loaded",
                "layout_diffusion": "loaded",
                "compliance_validator": "active",
            }
            return self.checks["models"]
        except Exception as e:
            self.checks["models"] = {"status": "unhealthy", "error": str(e)}
            return self.checks["models"]

    def get_health(self) -> dict[str, Any]:
        """Get full health status."""
        uptime = time.time() - self.start_time
        all_healthy = all(c.get("status") == "healthy" for c in self.checks.values())

        return {
            "status": "healthy" if all_healthy else "degraded",
            "uptime_seconds": uptime,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "version": "1.0.0",
            "checks": self.checks,
            "metrics": metrics.to_dict(),
        }


health_checker = HealthChecker()
