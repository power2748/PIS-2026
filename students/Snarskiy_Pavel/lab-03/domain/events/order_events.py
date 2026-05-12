from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol
 
 
class DomainEvent(Protocol):
    """Базовый протокол для всех доменных событий"""
    occurred_at: datetime
 
 
@dataclass(frozen=True)
class OrderCreatedEvent:
    """
    Доменное событие: заказ создан.
    Публикуется при вызове конструктора Order.
    Слушатели: logging, analytics, table-status service.
    """
    order_id: str
    table_number: int
    guests: int
    occurred_at: datetime = field(default_factory=datetime.now)
 
 
@dataclass(frozen=True)
class OrderSentToKitchenEvent:
    """
    Доменное событие: заказ отправлен на кухню.
    Публикуется при Order.send_to_kitchen().
    Слушатели: KDS (кухонный дисплей), notification worker.
    """
    order_id: str
    ticket_id: str
    table_number: int
    occurred_at: datetime = field(default_factory=datetime.now)
 
 
@dataclass(frozen=True)
class PaymentInitiatedEvent:
    """
    Доменное событие: оплата инициирована.
    Публикуется при Order.initiate_payment().
    Слушатели: payment worker (outbox → Stripe).
    """
    order_id: str
    payment_id: str
    amount: float
    currency: str
    occurred_at: datetime = field(default_factory=datetime.now)
 
 
@dataclass(frozen=True)
class PaymentCompletedEvent:
    """
    Доменное событие: оплата завершена успешно.
    Публикуется при Order.complete_payment().
    Слушатели: table-status service, analytics, loyalty service.
    """
    order_id: str
    payment_id: str
    transaction_id: str
    table_number: int
    occurred_at: datetime = field(default_factory=datetime.now)
 
 
@dataclass(frozen=True)
class OrderCancelledEvent:
    """
    Доменное событие: заказ отменён.
    Публикуется при Order.cancel().
    Слушатели: inventory service (освободить резервацию).
    """
    order_id: str
    reason: str
    table_number: int
    occurred_at: datetime = field(default_factory=datetime.now)