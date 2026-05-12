from dataclasses import dataclass
 
@dataclass(frozen=True)
class CompletePaymentCommand:
    """Команда: подтвердить успешное списание от эквайринга"""
    payment_id: str
    transaction_id: str
 
    def __post_init__(self):
        if not self.payment_id:
            raise ValueError("payment_id не может быть пустым")
        if not self.transaction_id:
            raise ValueError("transaction_id не может быть пустым")