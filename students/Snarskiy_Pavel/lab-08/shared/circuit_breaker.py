import time
from enum import Enum
from typing import Callable, Any
 
 
class CBState(Enum):
    CLOSED    = "CLOSED"     # нормальная работа
    OPEN      = "OPEN"       # все запросы блокируются
    HALF_OPEN = "HALF_OPEN"  # пробная попытка
 
 
class CircuitBreaker:
    """
    Circuit Breaker для межсервисных HTTP-вызовов.
    CLOSED → OPEN при N ошибках за окно времени.
    OPEN → HALF_OPEN через timeout_seconds.
    HALF_OPEN → CLOSED при успехе, → OPEN при ошибке.
    """
 
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout_seconds: float = 30.0,
    ):
        self.name              = name
        self._failure_threshold = failure_threshold
        self._success_threshold = success_threshold
        self._timeout           = timeout_seconds
        self._state             = CBState.CLOSED
        self._failure_count     = 0
        self._success_count     = 0
        self._last_failure_time: float = 0
 
    def call(self, func: Callable, *args, fallback=None, **kwargs) -> Any:
        if self._state == CBState.OPEN:
            if time.time() - self._last_failure_time >= self._timeout:
                self._state = CBState.HALF_OPEN
                self._success_count = 0
                print(f"[CB:{self.name}] OPEN → HALF_OPEN")
            else:
                print(f"[CB:{self.name}] OPEN — запрос отклонён")
                if fallback is not None:
                    return fallback()
                raise CircuitBreakerOpenError(f"Circuit breaker {self.name} is OPEN")
 
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
 
    def _on_success(self):
        if self._state == CBState.HALF_OPEN:
            self._success_count += 1
            if self._success_count >= self._success_threshold:
                self._state = CBState.CLOSED
                self._failure_count = 0
                print(f"[CB:{self.name}] HALF_OPEN → CLOSED")
        elif self._state == CBState.CLOSED:
            self._failure_count = 0
 
    def _on_failure(self):
        self._failure_count    += 1
        self._last_failure_time = time.time()
        if self._state == CBState.HALF_OPEN:
            self._state = CBState.OPEN
            print(f"[CB:{self.name}] HALF_OPEN → OPEN")
        elif self._failure_count >= self._failure_threshold:
            self._state = CBState.OPEN
            print(f"[CB:{self.name}] CLOSED → OPEN ({self._failure_count} failures)")
 
    @property
    def state(self) -> CBState:
        return self._state
 
 
class CircuitBreakerOpenError(Exception):
    pass
 
 
# Пример использования в Payment Service при вызове Stripe:
#
# stripe_cb = CircuitBreaker("stripe-gateway", failure_threshold=3, timeout_seconds=60)
#
# def charge_with_cb(payment_id, amount, idempotency_key):
#     return stripe_cb.call(
#         stripe_gateway.charge,
#         payment_id, amount, idempotency_key,
#         fallback=lambda: {"status": "RETRY_PENDING"},
#     )