from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
 
from cqrs.read_model.orm_models import RevenueViewModel
from domain.events.order_events import PaymentCompletedEvent
 
 
class RevenueProjection:
    """
    Проекция: инкрементальное обновление выручки за смену.
    Подписана только на PaymentCompletedEvent.
    Хранит агрегированные данные без необходимости GROUP BY при запросе.
    """
 
    def __init__(self, read_session: Session):
        self._session = read_session
 
    def on_payment_completed(self, event: PaymentCompletedEvent) -> None:
        date_str = event.occurred_at.strftime("%Y-%m-%d")
        hour     = event.occurred_at.hour
 
        view = (
            self._session.query(RevenueViewModel)
            .filter(
                RevenueViewModel.date == date_str,
                RevenueViewModel.hour == hour,
            )
            .first()
        )
 
        if view is None:
            view = RevenueViewModel(
                date=date_str,
                hour=hour,
                orders_count=1,
                total_amount=event.amount,
                avg_order_amount=event.amount,
                currency=event.currency,
                updated_at=event.occurred_at,
            )
            self._session.add(view)
        else:
            view.orders_count   += 1
            view.total_amount   += event.amount
            view.avg_order_amount = view.total_amount / view.orders_count
            view.updated_at      = event.occurred_at
 
        self._session.flush()