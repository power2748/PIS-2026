from dataclasses import dataclass
 
@dataclass(frozen=True)
class Money:
    """
    Value Object: Денежная сумма.
    Иммутабельный — равенство по значениям amount и currency.
    """
    amount: float
    currency: str = "RUB"
 
    def __post_init__(self):
        if self.amount < 0:
            raise ValueError(f"Сумма не может быть отрицательной: {self.amount}")
        if not self.currency or len(self.currency) != 3:
            raise ValueError(f"Код валюты должен содержать 3 символа: '{self.currency}'")
        # frozen=True запрещает изменение полей после создания
 
    def add(self, other: "Money") -> "Money":
        """Сложить две суммы. Возвращает новый объект (иммутабельность)."""
        if self.currency != other.currency:
            raise ValueError(
                f"Нельзя складывать суммы в разных валютах: {self.currency} и {other.currency}"
            )
        return Money(amount=self.amount + other.amount, currency=self.currency)
 
    def multiply(self, factor: int) -> "Money":
        """Умножить сумму на количество."""
        if factor < 0:
            raise ValueError(f"Множитель не может быть отрицательным: {factor}")
        return Money(amount=self.amount * factor, currency=self.currency)
 
    def __str__(self) -> str:
        return f"{self.amount:.2f} {self.currency}"
 
    ZERO = None  # инициализируется ниже
 
Money.ZERO = Money(amount=0.0, currency="RUB")