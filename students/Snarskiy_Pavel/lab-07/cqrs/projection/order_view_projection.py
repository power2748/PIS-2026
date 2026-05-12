from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
 
from cqrs.read_model.orm_models import OrderViewModel, KitchenDashboardViewModel
from domain.events.order_events import (
    OrderCreatedEvent, OrderSentToKitchenEvent,
    PaymentInitiatedEvent, PaymentCompletedEvent, OrderCancelledEvent,
)
from infrastructure.adapter.out.postgres_order_repository import PostgresOrderRepository
 
 
STATUS_LABELS = {
    "NEW":               "Принят, ожидает отправки на кухню",
    "IN_PROGRESS":       "Готовится на кухне",
    "READY":             "Готов к подаче",
    "AWAITING_PAYMENT":  "Ожидает оплаты",
    "PAID":              "Оплачен, столик свободен",
    "CANCELLED":         "Отменён",
}
 
STATION_ETA = {
    "GRILL": 20, "PASTA": 15, "DESSERT": 10,
    "BAR": 5, "COLD": 5,
}
 
 
class OrderViewProjection:
    """
    Проекция: обновляет order_views при изменении состояния заказа.
    Подписана на все события Order-агрегата.
    Идемпотентна: использует INSERT ... ON CONFLICT DO UPDATE.
    """
 
    def __init__(self, read_session: Session, write_repo: PostgresOrderRepository):
        self._session = read_session
        self._write_repo = write_repo  # читаем Write Model для начального состояния
 
    # ── Обработчики событий ───────────────────────────────────────
 
    def on_order_created(self, event: OrderCreatedEvent) -> None:
        """
        OrderCreatedEvent → создать строку в order_views.
        Загружает полный агрегат из Write DB для получения позиций.
        """
        order = self._write_repo.find_by_id(event.order_id)
        if order is None:
            return  # событие пришло раньше, чем запись в Write DB — пропускаем
 
        items_json = [
            {
                "dish_id":   item.dish_id,
                "dish_name": item.dish_name,
                "quantity":  item.quantity,
                "price":     item.price.amount,
                "subtotal":  item.price.amount * item.quantity,
                "station":   item.station.value,
                "comment":   item.comment,
            }
            for item in order.items
        ]
        total = order.calculate_total().amount
 
        view = OrderViewModel(
            order_id=event.order_id,
            table_id=event.table_number,
            table_label=f"Столик №{event.table_number}",
            guests=event.guests,
            status="NEW",
            status_label=STATUS_LABELS["NEW"],
            comment=None,
            items_json=items_json,
            items_count=len(items_json),
            total_amount=total,
            currency="RUB",
            ticket_id=None,
            ticket_status=None,
            kitchen_stations=None,
            eta_minutes=None,
            payment_id=None,
            payment_method=None,
            payment_status=None,
            payment_amount=None,
            transaction_id=None,
            created_at=event.occurred_at,
            updated_at=event.occurred_at,
            version=1,
        )
 
        # Идемпотентный upsert
        stmt = pg_insert(OrderViewModel).values(
            **{c.name: getattr(view, c.name)
               for c in OrderViewModel.__table__.columns}
        ).on_conflict_do_nothing(index_elements=["order_id"])
        self._session.execute(stmt)
        self._session.flush()
 
    def on_order_sent_to_kitchen(self, event: OrderSentToKitchenEvent) -> None:
        """
        OrderSentToKitchenEvent → обновить статус + добавить ticket_id и ETA.
        """
        view = self._session.get(OrderViewModel, event.order_id)
        if view is None:
            return
 
        # Определяем максимальное ETA по станциям в заказе
        stations = list({item["station"] for item in view.items_json})
        eta = max((STATION_ETA.get(s, 15) for s in stations), default=15)
 
        view.status         = "IN_PROGRESS"
        view.status_label   = STATUS_LABELS["IN_PROGRESS"]
        view.ticket_id      = event.ticket_id
        view.ticket_status  = "PENDING"
        view.kitchen_stations = stations
        view.eta_minutes    = eta
        view.updated_at     = event.occurred_at
        view.version       += 1
        self._session.flush()
 
    def on_payment_initiated(self, event: PaymentInitiatedEvent) -> None:
        """PaymentInitiatedEvent → статус AWAITING_PAYMENT, добавляем payment_id"""
        view = self._session.get(OrderViewModel, event.order_id)
        if view is None:
            return
 
        view.status         = "AWAITING_PAYMENT"
        view.status_label   = STATUS_LABELS["AWAITING_PAYMENT"]
        view.payment_id     = event.payment_id
        view.payment_status = "PENDING"
        view.payment_amount = event.amount
        view.updated_at     = event.occurred_at
        view.version       += 1
        self._session.flush()
 
    def on_payment_completed(self, event: PaymentCompletedEvent) -> None:
        """PaymentCompletedEvent → статус PAID, фиксируем transaction_id"""
        view = self._session.get(OrderViewModel, event.order_id)
        if view is None:
            return
 
        view.status         = "PAID"
        view.status_label   = STATUS_LABELS["PAID"]
        view.payment_status = "COMPLETED"
        view.transaction_id = event.transaction_id
        view.updated_at     = event.occurred_at
        view.version       += 1
        self._session.flush()
 
    def on_order_cancelled(self, event: OrderCancelledEvent) -> None:
        """OrderCancelledEvent → статус CANCELLED"""
        view = self._session.get(OrderViewModel, event.order_id)
        if view is None:
            return
 
        view.status       = "CANCELLED"
        view.status_label = STATUS_LABELS["CANCELLED"]
        view.updated_at   = event.occurred_at
        view.version     += 1
        self._session.flush()