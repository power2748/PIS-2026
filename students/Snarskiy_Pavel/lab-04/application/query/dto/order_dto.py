from dataclasses import dataclass, field
from typing import List, Optional
 
 
@dataclass(frozen=True)
class OrderItemDto:
    """Read DTO: позиция заказа"""
    dish_id: str
    dish_name: str
    quantity: int
    unit_price: float
    subtotal: float
    station: str
    comment: Optional[str]
 
 
@dataclass(frozen=True)
class KitchenTicketDto:
    """Read DTO: тикет кухни"""
    ticket_id: str
    status: str
    stations: List[str]
 
 
@dataclass(frozen=True)
class PaymentDto:
    """Read DTO: платёж"""
    payment_id: str
    method: str
    amount: float
    status: str
    transaction_id: Optional[str]
 
 
@dataclass(frozen=True)
class OrderDto:
    """
    Read DTO: заказ для чтения.
    Упрощённая плоская модель — не раскрывает доменные агрегаты наружу.
    Не содержит методов, только данные.
    """
    order_id: str
    table_id: int
    guests: int
    status: str
    comment: Optional[str]
    items: List[OrderItemDto]
    total: float
    currency: str
    version: int
    kitchen_ticket: Optional[KitchenTicketDto]
    payment: Optional[PaymentDto]
    created_at: str
    updated_at: str
 
 
@dataclass(frozen=True)
class OrderSummaryDto:
    """Read DTO: краткая сводка заказа для списка"""
    order_id: str
    table_id: int
    guests: int
    status: str
    total: float
    items_count: int
    created_at: str