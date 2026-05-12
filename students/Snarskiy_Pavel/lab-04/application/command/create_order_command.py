from dataclasses import dataclass, field
from typing import List, Optional
 
 
@dataclass(frozen=True)
class OrderItemData:
    """DTO: одна позиция в команде создания заказа"""
    dish_id: str
    dish_name: str
    quantity: int
    price: float        # цена за единицу, в рублях
    station: str        # GRILL, PASTA, DESSERT, BAR, COLD
    comment: Optional[str] = None
 
    def __post_init__(self):
        if not self.dish_id:
            raise ValueError("dish_id не может быть пустым")
        if self.quantity <= 0:
            raise ValueError(f"quantity должен быть > 0: {self.quantity}")
        if self.price < 0:
            raise ValueError(f"price не может быть отрицательным: {self.price}")
 
 
@dataclass(frozen=True)
class CreateOrderCommand:
    """
    Команда: создать новый заказ.
    Иммутабельный DTO без бизнес-логики.
    Валидирует только примитивы — инварианты домена проверяет Order.
    """
    table_id: int
    guests: int
    items: List[OrderItemData]
    comment: Optional[str] = None
    idempotency_key: Optional[str] = None
 
    def __post_init__(self):
        if self.table_id <= 0:
            raise ValueError(f"table_id должен быть > 0: {self.table_id}")
        if self.guests <= 0:
            raise ValueError(f"guests должен быть > 0: {self.guests}")
        if not self.items:
            raise ValueError("Список позиций не может быть пустым")