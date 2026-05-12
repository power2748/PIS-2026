from application.query.get_order_by_id_query import GetOrderByIdQuery
from application.query.dto.order_dto import OrderDto, OrderItemDto, KitchenTicketDto, PaymentDto
from application.port.out.order_repository import IOrderRepository
from domain.exceptions.domain_exception import OrderNotFoundException
from typing import Optional
 
 
class GetOrderByIdHandler:
    """
    Query Handler: получение заказа по ID.
    Читает данные, НЕ изменяет состояние (Query в CQRS).
    Преобразует доменный агрегат в плоский DTO.
    """
 
    def __init__(self, order_repository: IOrderRepository):
        self._repo = order_repository
 
    def handle(self, query: GetOrderByIdQuery) -> OrderDto:
        # ── Шаг 1: Загрузка из репозитория ────────────────────────
        order = self._repo.find_by_id(query.order_id)
        if order is None:
            raise OrderNotFoundException(f"Заказ не найден: {query.order_id}")
 
        # ── Шаг 2: Преобразование в Read DTO ──────────────────────
        return self._to_dto(order)
 
    def _to_dto(self, order) -> OrderDto:
        items_dto = [
            OrderItemDto(
                dish_id=item.dish_id,
                dish_name=item.dish_name,
                quantity=item.quantity,
                unit_price=item.price.amount,
                subtotal=item.price.amount * item.quantity,
                station=item.station.value,
                comment=item.comment,
            )
            for item in order.items
        ]
 
        ticket_dto = None
        if order.kitchen_ticket:
            t = order.kitchen_ticket
            ticket_dto = KitchenTicketDto(
                ticket_id=t.ticket_id,
                status=t.status,
                stations=list({i.station for i in t.items}),
            )
 
        payment_dto = None
        if order.payment:
            p = order.payment
            payment_dto = PaymentDto(
                payment_id=p.payment_id,
                method=p._method,
                amount=p.amount.amount,
                status=p.status,
                transaction_id=getattr(p, "_transaction_id", None),
            )
 
        total = order.calculate_total()
 
        return OrderDto(
            order_id=order.order_id,
            table_id=order.table_number.value,
            guests=order._guests,
            status=order.status.value,
            comment=order._comment,
            items=items_dto,
            total=total.amount,
            currency=total.currency,
            version=order.version,
            kitchen_ticket=ticket_dto,
            payment=payment_dto,
            created_at=order._created_at.isoformat(),
            updated_at=order._updated_at.isoformat(),
        )