from sqlalchemy.orm import Session
from typing import List, Optional
from cqrs.read_model.orm_models import (
    OrderViewModel, TableViewModel,
    KitchenDashboardViewModel, RevenueViewModel,
)
 
 
class OrderViewQueryHandler:
    """Query Handler: читает ТОЛЬКО из Read-таблиц. Никаких JOIN с Write."""
 
    def __init__(self, read_session: Session):
        self._session = read_session
 
    def get_by_id(self, order_id: str) -> Optional[OrderViewModel]:
        return self._session.get(OrderViewModel, order_id)
 
    def get_active_by_table(self, table_id: int) -> Optional[OrderViewModel]:
        return (
            self._session.query(OrderViewModel)
            .filter(
                OrderViewModel.table_id == table_id,
                OrderViewModel.status.notin_(["PAID", "CANCELLED"]),
            )
            .first()
        )
 
    def list_active(self, page: int = 1, page_size: int = 20) -> List[OrderViewModel]:
        return (
            self._session.query(OrderViewModel)
            .filter(OrderViewModel.status.notin_(["PAID", "CANCELLED"]))
            .order_by(OrderViewModel.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
 
 
class KitchenDashboardQueryHandler:
    """Query Handler: очередь для конкретной кухонной станции"""
 
    def __init__(self, read_session: Session):
        self._session = read_session
 
    def get_queue_for_station(self, station: str) -> List[KitchenDashboardViewModel]:
        return (
            self._session.query(KitchenDashboardViewModel)
            .filter(
                KitchenDashboardViewModel.station == station,
                KitchenDashboardViewModel.status == "PENDING",
            )
            .order_by(
                KitchenDashboardViewModel.priority.desc(),
                KitchenDashboardViewModel.created_at.asc(),
            )
            .all()
        )
 
 
class RevenueQueryHandler:
    """Query Handler: выручка за смену"""
 
    def __init__(self, read_session: Session):
        self._session = read_session
 
    def get_daily_revenue(self, date: str) -> List[RevenueViewModel]:
        return (
            self._session.query(RevenueViewModel)
            .filter(RevenueViewModel.date == date)
            .order_by(RevenueViewModel.hour)
            .all()
        )