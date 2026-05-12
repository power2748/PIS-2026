from datetime import datetime
from sqlalchemy.orm import Session
 
from cqrs.read_model.orm_models import KitchenDashboardViewModel
from domain.events.order_events import OrderSentToKitchenEvent, PaymentCompletedEvent
from infrastructure.adapter.out.postgres_order_repository import PostgresOrderRepository
 
STATION_PRIORITY = {"GRILL": 3, "PASTA": 2, "DESSERT": 1, "BAR": 1, "COLD": 1}
 
 
class KitchenDashboardProjection:
    """
    Проекция: очередь блюд для кухонных дисплеев (KDS).
    При OrderSentToKitchen создаёт одну строку на каждую станцию.
    При PaymentCompleted/OrderCancelled удаляет строки тикета.
    """
 
    def __init__(self, read_session: Session, write_repo: PostgresOrderRepository):
        self._session = read_session
        self._write_repo = write_repo
 
    def on_order_sent_to_kitchen(self, event: OrderSentToKitchenEvent) -> None:
        order = self._write_repo.find_by_id(event.order_id)
        if order is None:
            return
 
        # Группируем позиции по станциям
        stations: dict = {}
        for item in order.items:
            station = item.station.value
            if station not in stations:
                stations[station] = []
            stations[station].append({
                "dish_id":   item.dish_id,
                "dish_name": item.dish_name,
                "quantity":  item.quantity,
                "comment":   item.comment,
            })
 
        for station, items in stations.items():
            view = KitchenDashboardViewModel(
                ticket_id=event.ticket_id,
                order_id=event.order_id,
                table_label=f"Столик №{event.table_number}",
                station=station,
                items_json=items,
                priority=STATION_PRIORITY.get(station, 1),
                status="PENDING",
                created_at=event.occurred_at,
                updated_at=event.occurred_at,
            )
            self._session.add(view)
 
        self._session.flush()
 
    def on_payment_completed(self, event: PaymentCompletedEvent) -> None:
        """Убираем тикет с дисплея после оплаты"""
        self._session.query(KitchenDashboardViewModel).filter(
            KitchenDashboardViewModel.order_id == event.order_id
        ).delete(synchronize_session=False)
        self._session.flush()