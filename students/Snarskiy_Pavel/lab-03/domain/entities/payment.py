from datetime import datetime
from domain.value_objects.money import Money
 
class Payment:
    """
    Entity: Платёж за заказ.
    Управляет жизненным циклом оплаты: PENDING → COMPLETED / FAILED.
    Защищает инварианты: не допускает изменения завершённого платежа,
    ограничивает количество попыток списания.
    """
 
    MAX_RETRIES = 3
    VALID_METHODS = {"CARD", "CASH", "QR"}
 
    def __init__(self, payment_id: str, order_id: str, amount: Money, method: str):
        if not payment_id:
            raise ValueError("payment_id не может быть пустым")
        if amount.amount <= 0:
            raise ValueError(f"Сумма платежа должна быть > 0: {amount}")
        if method not in self.VALID_METHODS:
            raise ValueError(
                f"Недопустимый метод оплаты: '{method}'. "
                f"Допустимые: {self.VALID_METHODS}"
            )
 
        self._payment_id = payment_id
        self._order_id = order_id
        self._amount = amount
        self._method = method
        self._status = "PENDING"
        self._retry_count = 0
        self._transaction_id = None
        self._created_at = datetime.now()
        self._updated_at = datetime.now()
 
    @property
    def payment_id(self) -> str:
        return self._payment_id
 
    @property
    def order_id(self) -> str:
        return self._order_id
 
    @property
    def amount(self) -> Money:
        return self._amount
 
    @property
    def status(self) -> str:
        return self._status
 
    @property
    def retry_count(self) -> int:
        return self._retry_count
 
    def mark_retry_pending(self) -> None:
        """Зафиксировать неудачную попытку, поставить в очередь повтора"""
        if self._status in ("COMPLETED", "FAILED"):
            raise ValueError(
                f"Нельзя повторить завершённый платёж (статус: {self._status})"
            )
        if self._retry_count >= self.MAX_RETRIES:
            raise ValueError(
                f"Превышено максимальное количество попыток ({self.MAX_RETRIES})"
            )
        self._retry_count += 1
        self._status = "RETRY_PENDING"
        self._updated_at = datetime.now()
 
    def complete(self, transaction_id: str) -> None:
        """Завершить платёж успешно"""
        if self._status not in ("PENDING", "RETRY_PENDING"):
            raise ValueError(
                f"Нельзя завершить платёж в статусе {self._status}"
            )
        if not transaction_id:
            raise ValueError("transaction_id не может быть пустым")
        self._transaction_id = transaction_id
        self._status = "COMPLETED"
        self._updated_at = datetime.now()
 
    def fail(self) -> None:
        """Окончательно завершить платёж с ошибкой (исчерпаны все retry)"""
        if self._status == "COMPLETED":
            raise ValueError("Нельзя провалить уже завершённый платёж")
        self._status = "FAILED"
        self._updated_at = datetime.now()
 
    def __eq__(self, other) -> bool:
        if not isinstance(other, Payment):
            return False
        return self._payment_id == other._payment_id
 
    def __hash__(self) -> int:
        return hash(self._payment_id)
 
    def __repr__(self) -> str:
        return (
            f"Payment(id={self._payment_id}, order={self._order_id}, "
            f"amount={self._amount}, status={self._status})"
        )