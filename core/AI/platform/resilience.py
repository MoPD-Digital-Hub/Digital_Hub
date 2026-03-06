import time
import threading
from dataclasses import dataclass


@dataclass
class CircuitState:
    failures: int = 0
    opened_until: float = 0.0


class CircuitBreakerRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._states: dict[str, CircuitState] = {}

    def _get(self, name: str) -> CircuitState:
        if name not in self._states:
            self._states[name] = CircuitState()
        return self._states[name]

    def allow(self, name: str) -> bool:
        with self._lock:
            state = self._get(name)
            return time.time() >= state.opened_until

    def record_success(self, name: str):
        with self._lock:
            state = self._get(name)
            state.failures = 0
            state.opened_until = 0.0

    def record_failure(self, name: str, threshold: int = 3, cooldown_seconds: int = 30):
        with self._lock:
            state = self._get(name)
            state.failures += 1
            if state.failures >= threshold:
                state.opened_until = time.time() + cooldown_seconds


breaker_registry = CircuitBreakerRegistry()


def retry_call(fn, *, retries=2, base_delay=0.2, on_exception=(Exception,), dependency_name="dependency"):
    if not breaker_registry.allow(dependency_name):
        raise RuntimeError(f"Circuit open for {dependency_name}")

    last_exc = None
    for attempt in range(retries + 1):
        try:
            result = fn()
            breaker_registry.record_success(dependency_name)
            return result
        except on_exception as exc:
            last_exc = exc
            breaker_registry.record_failure(dependency_name)
            if attempt < retries:
                time.sleep(base_delay * (2 ** attempt))

    raise last_exc
