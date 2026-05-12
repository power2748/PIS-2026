from dataclasses import dataclass
 
@dataclass(frozen=True)
class GetOrderByIdQuery:
    """
    Запрос: получить полную информацию о заказе по ID.
    Не изменяет состояние системы.
    """
    order_id: str
 
    def __post_init__(self):
        if not self.order_id:
            raise ValueError("order_id не может быть пустым")