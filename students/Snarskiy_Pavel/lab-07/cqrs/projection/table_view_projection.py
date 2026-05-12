from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert
 
from cqrs.read_model.orm_models import TableViewModel
from domain.events.order_events import (
    OrderCreatedEvent, PaymentCompletedEvent, OrderCancelledEvent,
)
 
 
class TableViewProjection:
    """
    Проекция: синхронизирует состояние столиков.
    Подписана на: OrderCreated, PaymentCompleted, OrderCancelled.
    Используется для карты зала.
    """
 
    def __init__(self, read_session: Session):
        self._session = read_session
 
    def on_order_created(self, event: OrderCreatedEvent) -> None:
        """Столик занят при создании заказа"""
        view = self._session.get(TableViewModel, event.table_number)
        if view is None:
            view = TableViewModel(
                table_id=event.table_number,
                table_label=f"Столик №{event.table_number}",
                capacity=4,  # дефолт, реальное значение из справочника
                updated_at=event.occurred_at,
            )
            self._session.add(view)
 
        view.status              = "OCCUPIED"
        view.active_order_id     = event.order_id
        view.active_order_status = "NEW"
        view.guests              = event.guests
        view.occupied_since      = event.occurred_at
        view.total_amount        = None
        view.updated_at          = event.occurred_at
        self._session.flush()
 
    def on_payment_completed(self, event: PaymentCompletedEvent) -> None:
        """Столик освобождается после оплаты"""
        view = self._session.get(TableViewModel, event.table_number)
        if view is None:
            return
 
        view.status              = "FREE"
        view.active_order_id     = None
        view.active_order_status = None
        view.guests              = None
        view.occupied_since      = None
        view.total_amount        = None
        view.updated_at          = event.occurred_at
        self._session.flush()
 
    def on_order_cancelled(self, event: OrderCancelledEvent) -> None:
        """Столик освобождается при отмене заказа"""
        view = self._session.get(TableViewModel, event.table_number)
        if view is None:
            return
 
        view.status              = "FREE"
        view.active_order_id     = None
        view.active_order_status = None
        view.guests              = None
        view.occupied_since      = None
        view.updated_at          = event.occurred_at
        self._session.flush()