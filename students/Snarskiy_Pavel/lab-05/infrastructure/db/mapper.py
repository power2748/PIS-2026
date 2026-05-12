from infrastructure.db.models import (
    OrderModel, OrderItemModel, KitchenTicketModel,
    TicketItemModel, PaymentModel,
)
from domain.aggregates.order import Order
from domain.entities.order_item import OrderItem
from domain.entities.kitchen_ticket import KitchenTicket, TicketItem
from domain.entities.payment import Payment
from domain.value_objects.money import Money
from domain.value_objects.order_status import OrderStatus
from domain.value_objects.dish_station import DishStation
from domain.value_objects.table_number import TableNumber
 
 
class OrderMapper:
    """Двунаправленный маппинг: Domain Aggregate ↔ SQLAlchemy ORM Model"""
 
    @staticmethod
    def to_orm(order: Order) -> OrderModel:
        orm = OrderModel(
            order_id=order.order_id,
            table_id=order.table_number.value,
            guests=order._guests,
            status=order.status.value,
            comment=order._comment,
            version=order.version,
            created_at=order._created_at,
            updated_at=order._updated_at,
        )
        orm.items = [
            OrderMapper.item_to_orm(item, order.order_id)
            for item in order.items
        ]
        if order.kitchen_ticket:
            orm.kitchen_ticket = OrderMapper.ticket_to_orm(order.kitchen_ticket)
        if order.payment:
            orm.payment = OrderMapper.payment_to_orm(order.payment)
        return orm
 
    @staticmethod
    def item_to_orm(item: OrderItem, order_id: str) -> OrderItemModel:
        return OrderItemModel(
            item_id=item.item_id,
            order_id=order_id,
            dish_id=item.dish_id,
            dish_name=item.dish_name,
            quantity=item.quantity,
            price=item.price.amount,
            station=item.station.value,
            comment=item.comment,
        )
 
    @staticmethod
    def ticket_to_orm(ticket: KitchenTicket) -> KitchenTicketModel:
        orm = KitchenTicketModel(
            ticket_id=ticket.ticket_id,
            order_id=ticket.order_id,
            status=ticket.status,
        )
        orm.items = [
            TicketItemModel(
                ticket_id=ticket.ticket_id,
                dish_id=i.dish_id,
                dish_name=i.dish_name,
                quantity=i.quantity,
                station=i.station,
                is_done=int(i.is_done),
            )
            for i in ticket.items
        ]
        return orm
 
    @staticmethod
    def payment_to_orm(payment: Payment) -> PaymentModel:
        return PaymentModel(
            payment_id=payment.payment_id,
            order_id=payment.order_id,
            amount=payment.amount.amount,
            currency=payment.amount.currency,
            method=payment._method,
            status=payment.status,
            retry_count=payment.retry_count,
            transaction_id=payment._transaction_id,
        )
 
    @staticmethod
    def to_domain(orm: OrderModel) -> Order:
        """ORM → Domain Aggregate (восстановление агрегата из БД)"""
        order = object.__new__(Order)
        order._order_id    = orm.order_id
        order._table_number = TableNumber(orm.table_id)
        order._guests      = orm.guests
        order._status      = OrderStatus(orm.status)
        order._comment     = orm.comment
        order._version     = orm.version
        order._created_at  = orm.created_at
        order._updated_at  = orm.updated_at
        order._events      = []
 
        order._items = [
            OrderItem(
                item_id=i.item_id,
                dish_id=i.dish_id,
                dish_name=i.dish_name,
                quantity=i.quantity,
                price=Money(i.price, "RUB"),
                station=DishStation(i.station),
                comment=i.comment,
            )
            for i in orm.items
        ]
 
        order._kitchen_ticket = None
        if orm.kitchen_ticket:
            t = orm.kitchen_ticket
            ticket_items = [
                TicketItem(
                    dish_id=ti.dish_id,
                    dish_name=ti.dish_name,
                    quantity=ti.quantity,
                    station=ti.station,
                )
                for ti in t.items
            ]
            kt = object.__new__(KitchenTicket)
            kt._ticket_id = t.ticket_id
            kt._order_id  = t.order_id
            kt._status    = t.status
            kt._items     = ticket_items
            order._kitchen_ticket = kt
 
        order._payment = None
        if orm.payment:
            p = orm.payment
            payment = object.__new__(Payment)
            payment._payment_id    = p.payment_id
            payment._order_id      = p.order_id
            payment._amount        = Money(p.amount, p.currency)
            payment._method        = p.method
            payment._status        = p.status
            payment._retry_count   = p.retry_count
            payment._transaction_id = p.transaction_id
            order._payment = payment
 
        return order