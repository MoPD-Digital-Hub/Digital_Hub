import time
import threading
from collections import defaultdict

_lock = threading.Lock()
_counters = defaultdict(int)
_latency = defaultdict(lambda: {"count": 0, "sum_ms": 0.0, "max_ms": 0.0})
_last_ingestion_report = {
    "processed": 0,
    "loaded": 0,
    "skipped": 0,
    "errors": 0,
    "details": [],
    "updated_at": None,
}


def increment(metric: str, value: int = 1):
    with _lock:
        _counters[metric] += value


def observe_latency(metric: str, duration_ms: float):
    with _lock:
        entry = _latency[metric]
        entry["count"] += 1
        entry["sum_ms"] += duration_ms
        if duration_ms > entry["max_ms"]:
            entry["max_ms"] = duration_ms


def timed(metric: str):
    start = time.perf_counter()

    def done():
        observe_latency(metric, (time.perf_counter() - start) * 1000.0)

    return done


def set_last_ingestion_report(report: dict):
    with _lock:
        _last_ingestion_report.clear()
        _last_ingestion_report.update(report)


def get_last_ingestion_report():
    with _lock:
        return dict(_last_ingestion_report)


def snapshot_metrics():
    with _lock:
        latency = {
            k: {
                "count": v["count"],
                "avg_ms": (v["sum_ms"] / v["count"]) if v["count"] else 0.0,
                "max_ms": v["max_ms"],
            }
            for k, v in _latency.items()
        }
        return {
            "counters": dict(_counters),
            "latency": latency,
        }
