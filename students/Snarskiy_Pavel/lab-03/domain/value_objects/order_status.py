from dataclasses import dataclass
from typing import Set
 
@dataclass(frozen=True)
class OrderStatus:
    """
    Value Object: Статус заказа.
    Хранит допустимые переходы и защищает от некорректных изменений статуса.
    """
    value: str
 
    VALID_STATUSES: frozenset = frozenset({
        "NEW", "IN_PROGRESS", "READY",
        "AWAITING_PAYMENT", "PAID", "CANCELLED"
    })
 
    TRANSITIONS: dict = None  # инициализируется ниже
 
    def __post_init__(self):
        if self.value not in self.VALID_STATUSES:
            raise ValueError(
                f"Недопустимый статус заказа: '{self.value}'. "
                f"Допустимые: {sorted(self.VALID_STATUSES)}"
            )
 
    def can_transition_to(self, next_status: "OrderStatus") -> bool:
        allowed = OrderStatus.TRANSITIONS.get(self.value, set())
        return next_status.value in allowed
 
    def transition_to(self, next_status: "OrderStatus") -> "OrderStatus":
        if not self.can_transition_to(next_status):
            raise ValueError(
                f"Недопустимый переход: {self.value} → {next_status.value}"
            )
        return next_status
 
    def __str__(self) -> str:
        return self.value
 
# Допустимые переходы (конечный автомат)
OrderStatus.TRANSITIONS = {
    "NEW":              {"IN_PROGRESS", "CANCELLED"},
    "IN_PROGRESS":      {"READY", "CANCELLED"},
    "READY":            {"AWAITING_PAYMENT", "CANCELLED"},
    "AWAITING_PAYMENT": {"PAID", "READY"},
    "PAID":             set(),
    "CANCELLED":        set(),
}