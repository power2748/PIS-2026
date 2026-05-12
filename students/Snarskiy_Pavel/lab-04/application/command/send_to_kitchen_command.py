from dataclasses import dataclass
 
@dataclass(frozen=True)
class SendToKitchenCommand:
    """Команда: отправить заказ на кухню"""
    order_id: str
    waiter_id: str
 
    def __post_init__(self):
        if not self.order_id:
            raise ValueError("order_id не может быть пустым")
        if not self.waiter_id:
            raise ValueError("waiter_id не может быть пустым")