from dataclasses import dataclass
 
VALID_METHODS = frozenset({"CARD", "CASH", "QR"})
 
@dataclass(frozen=True)
class InitiatePaymentCommand:
    """Команда: инициировать оплату заказа"""
    order_id: str
    payment_method: str
    tip: float = 0.0
 
    def __post_init__(self):
        if not self.order_id:
            raise ValueError("order_id не может быть пустым")
        if self.payment_method not in VALID_METHODS:
            raise ValueError(
                f"Недопустимый метод оплаты: '{self.payment_method}'. "
                f"Допустимые: {sorted(VALID_METHODS)}"
            )
        if self.tip < 0:
            raise ValueError(f"tip не может быть отрицательным: {self.tip}")