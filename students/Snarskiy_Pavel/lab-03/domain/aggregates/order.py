from typing import List, Optional
from datetime import datetime
 
from domain.value_objects.money import Money
from domain.value_objects.order_status import OrderStatus
from domain.value_objects.table_number import TableNumber
from domain.entities.order_item import OrderItem
from domain.entities.kitchen_ticket import KitchenTicket, TicketItem
from domain.entities.payment import Payment
from domain.events.order_events import (
    OrderCreatedEvent,
    OrderSentToKitchenEvent,
    PaymentInitiatedEvent,
    PaymentCompletedEvent,
    OrderCancelledEvent,
)
from domain.exceptions.domain_exception import (
    DomainException,
    DishUnavailableException,
    InvalidOrderStateException,
)
 
 
class Order:
    """
    Aggregate Root: Заказ в ресторанной системе.
    Управляет полным жизненным циклом заказа.
    Инкапсулирует OrderItem, KitchenTicket, Payment.
    Внешний код работает только через публичные методы агрегата.
    """
 
    MAX_ITEMS = 30  # максимум позиций в одном заказе
 
    def __init__(self, order_id: str, table_number: TableNumber, guests: int):
        if not order_id:
            raise ValueError("order_id не может быть пустым")
        if guests <= 0:
            raise ValueError(f"Количество гостей должно быть > 0: {guests}")
 
        self._order_id = order_id
        self._table_number = table_number   # Value Object
        self._guests = guests
        self._items: List[OrderItem] = []
        self._kitchen_ticket: Optional[KitchenTicket] = None
        self._payment: Optional[Payment] = None
        self._status = OrderStatus("NEW")
        self._comment: Optional[str] = None
        self._version = 1                   # для optimistic locking
        self._created_at = datetime.now()
        self._updated_at = datetime.now()
        self._events: List = []             # накопленные доменные события
 
        self._events.append(OrderCreatedEvent(
            order_id=self._order_id,
            table_number=self._table_number.value,
            guests=self._guests,
        ))
 
    # ──────────────────────────────────────────
    # Бизнес-методы (публичный интерфейс агрегата)
    # ──────────────────────────────────────────
 
    def add_item(self, item: OrderItem) -> None:
        """
        Добавить позицию в заказ.
        Инвариант: только пока заказ в статусе NEW.
        Инвариант: не более MAX_ITEMS позиций.
        """
        if self._status.value != "NEW":
            raise InvalidOrderStateException(
                f"Нельзя добавить блюдо: заказ уже в статусе {self._status}"
            )
        if len(self._items) >= self.MAX_ITEMS:
            raise DomainException(
                f"Превышен лимит позиций в заказе ({self.MAX_ITEMS})"
            )
        self._items.append(item)
        self._touch()
 
    def send_to_kitchen(self, ticket_id: str) -> KitchenTicket:
        """
        Создать тикет кухни и отправить заказ на приготовление.
        Инвариант: нельзя отправить пустой заказ.
        Инвариант: нельзя отправить повторно.
        """
        if self._status.value != "NEW":
            raise InvalidOrderStateException(
                f"Заказ уже отправлен на кухню (статус: {self._status})"
            )
        if not self._items:
            raise DomainException("Нельзя отправить пустой заказ на кухню")
 
        # Создаём тикет внутри агрегата
        ticket_items = [
            TicketItem(
                dish_id=item.dish_id,
                dish_name=item.dish_name,
                quantity=item.quantity,
                station=item.station.value,
            )
            for item in self._items
        ]
        self._kitchen_ticket = KitchenTicket(
            ticket_id=ticket_id,
            order_id=self._order_id,
            items=ticket_items,
        )
 
        self._status = self._status.transition_to(OrderStatus("IN_PROGRESS"))
        self._version += 1
        self._touch()
 
        self._events.append(OrderSentToKitchenEvent(
            order_id=self._order_id,
            ticket_id=ticket_id,
            table_number=self._table_number.value,
        ))
 
        return self._kitchen_ticket
 
    def mark_ready(self) -> None:
        """Кухня выполнила заказ — готов к подаче"""
        if self._kitchen_ticket is None:
            raise DomainException("Тикет кухни не существует")
        self._kitchen_ticket.complete()
        self._status = self._status.transition_to(OrderStatus("READY"))
        self._version += 1
        self._touch()
 
    def initiate_payment(self, payment_id: str, method: str) -> Payment:
        """
        Инициировать оплату заказа.
        Инвариант: заказ должен быть в статусе READY.
        """
        if self._status.value != "READY":
            raise InvalidOrderStateException(
                f"Нельзя инициировать оплату: заказ в статусе {self._status}"
            )
        total = self.calculate_total()
        self._payment = Payment(
            payment_id=payment_id,
            order_id=self._order_id,
            amount=total,
            method=method,
        )
        self._status = self._status.transition_to(OrderStatus("AWAITING_PAYMENT"))
        self._version += 1
        self._touch()
 
        self._events.append(PaymentInitiatedEvent(
            order_id=self._order_id,
            payment_id=payment_id,
            amount=total.amount,
            currency=total.currency,
        ))
 
        return self._payment
 
    def complete_payment(self, transaction_id: str) -> None:
        """
        Завершить оплату успешно.
        Инвариант: платёж должен быть инициирован.
        Инвариант: только после подтверждения столик освобождается.
        """
        if self._payment is None:
            raise DomainException("Платёж не был инициирован")
        self._payment.complete(transaction_id)
        self._status = self._status.transition_to(OrderStatus("PAID"))
        self._version += 1
        self._touch()
 
        self._events.append(PaymentCompletedEvent(
            order_id=self._order_id,
            payment_id=self._payment.payment_id,
            transaction_id=transaction_id,
            table_number=self._table_number.value,
        ))
 
    def cancel(self, reason: str = "") -> None:
        """
        Отменить заказ.
        Инвариант: нельзя отменить оплаченный заказ.
        """
        if self._status.value == "PAID":
            raise InvalidOrderStateException("Нельзя отменить оплаченный заказ")
        self._status = self._status.transition_to(OrderStatus("CANCELLED"))
        self._version += 1
        self._touch()
 
        self._events.append(OrderCancelledEvent(
            order_id=self._order_id,
            reason=reason,
            table_number=self._table_number.value,
        ))
 
    def calculate_total(self) -> Money:
        """Итоговая сумма заказа = сумма price * quantity по всем позициям"""
        if not self._items:
            return Money.ZERO
        total = Money.ZERO
        for item in self._items:
            total = total.add(item.price.multiply(item.quantity))
        return total
 
    # ──────────────────────────────────────────
    # Свойства (только чтение снаружи)
    # ──────────────────────────────────────────
 
    @property
    def order_id(self) -> str:
        return self._order_id
 
    @property
    def table_number(self) -> TableNumber:
        return self._table_number
 
    @property
    def status(self) -> OrderStatus:
        return self._status
 
    @property
    def version(self) -> int:
        return self._version
 
    @property
    def items(self) -> List[OrderItem]:
        return list(self._items)  # защитная копия
 
    @property
    def kitchen_ticket(self) -> Optional[KitchenTicket]:
        return self._kitchen_ticket
 
    @property
    def payment(self) -> Optional[Payment]:
        return self._payment
 
    def pull_events(self) -> List:
        """Забрать накопленные доменные события и очистить список"""
        events = list(self._events)
        self._events.clear()
        return events
 
    # ──────────────────────────────────────────
    # Identity
    # ──────────────────────────────────────────
 
    def _touch(self) -> None:
        self._updated_at = datetime.now()
 
    def __eq__(self, other) -> bool:
        if not isinstance(other, Order):
            return False
        return self._order_id == other._order_id
 
    def __hash__(self) -> int:
        return hash(self._order_id)
 
    def __repr__(self) -> str:
        return (
            f"Order(id={self._order_id}, table={self._table_number}, "
            f"status={self._status}, version={self._version})"
        )