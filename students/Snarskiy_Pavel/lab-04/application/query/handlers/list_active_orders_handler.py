from typing import List
from application.query.list_active_orders_query import ListActiveOrdersQuery
from application.query.dto.order_dto import OrderSummaryDto
from application.port.out.order_repository import IOrderRepository
 
ACTIVE_STATUSES = {"NEW", "IN_PROGRESS", "READY", "AWAITING_PAYMENT"}
 
 
class ListActiveOrdersHandler:
    """
    Query Handler: список активных заказов в зале.
    Возвращает краткие сводки (OrderSummaryDto) без тяжёлых вложений.
    """
 
    def __init__(self, order_repository: IOrderRepository):
        self._repo = order_repository
 
    def handle(self, query: ListActiveOrdersQuery) -> List[OrderSummaryDto]:
        statuses = (
            {query.status_filter} if query.status_filter else ACTIVE_STATUSES
        )
        orders = self._repo.find_by_statuses(
            statuses=statuses,
            offset=(query.page - 1) * query.page_size,
            limit=query.page_size,
        )
        return [self._to_summary(o) for o in orders]
 
    @staticmethod
    def _to_summary(order) -> OrderSummaryDto:
        return OrderSummaryDto(
            order_id=order.order_id,
            table_id=order.table_number.value,
            guests=order._guests,
            status=order.status.value,
            total=order.calculate_total().amount,
            items_count=len(order.items),
            created_at=order._created_at.isoformat(),
        )