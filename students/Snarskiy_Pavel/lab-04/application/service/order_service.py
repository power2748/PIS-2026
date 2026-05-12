from application.command.create_order_command import CreateOrderCommand
from application.command.send_to_kitchen_command import SendToKitchenCommand
from application.command.initiate_payment_command import InitiatePaymentCommand
from application.command.complete_payment_command import CompletePaymentCommand
from application.command.cancel_order_command import CancelOrderCommand
from application.command.handlers.create_order_handler import CreateOrderHandler
from application.command.handlers.send_to_kitchen_handler import SendToKitchenHandler
from application.command.handlers.initiate_payment_handler import InitiatePaymentHandler
from application.command.handlers.complete_payment_handler import CompletePaymentHandler
from application.command.handlers.cancel_order_handler import CancelOrderHandler
from application.query.get_order_by_id_query import GetOrderByIdQuery
from application.query.list_active_orders_query import ListActiveOrdersQuery
from application.query.handlers.get_order_by_id_handler import GetOrderByIdHandler
from application.query.handlers.list_active_orders_handler import ListActiveOrdersHandler
from application.query.dto.order_dto import OrderDto, OrderSummaryDto
from typing import List
 
 
class OrderService:
    """
    Application Service — фасад над Command и Query Handlers.
    Не содержит бизнес-логики: только делегирует вызовы специализированным handlers.
    Это единственная точка входа для внешних слоёв (REST-контроллера, тестов).
    """
 
    def __init__(
        self,
        create_order_handler: CreateOrderHandler,
        send_to_kitchen_handler: SendToKitchenHandler,
        initiate_payment_handler: InitiatePaymentHandler,
        complete_payment_handler: CompletePaymentHandler,
        cancel_order_handler: CancelOrderHandler,
        get_order_by_id_handler: GetOrderByIdHandler,
        list_active_orders_handler: ListActiveOrdersHandler,
    ):
        # Все handlers инжектируются (DI), сервис-фасад ничего не создаёт сам
        self._create_order = create_order_handler
        self._send_to_kitchen = send_to_kitchen_handler
        self._initiate_payment = initiate_payment_handler
        self._complete_payment = complete_payment_handler
        self._cancel_order = cancel_order_handler
        self._get_order_by_id = get_order_by_id_handler
        self._list_active_orders = list_active_orders_handler
 
    # ── Commands ──────────────────────────────────────────────────
 
    def create_order(self, command: CreateOrderCommand) -> str:
        """Создать новый заказ. Возвращает order_id."""
        return self._create_order.handle(command)
 
    def send_to_kitchen(self, command: SendToKitchenCommand) -> str:
        """Отправить заказ на кухню. Возвращает ticket_id."""
        return self._send_to_kitchen.handle(command)
 
    def initiate_payment(self, command: InitiatePaymentCommand) -> str:
        """Инициировать оплату. Возвращает payment_id."""
        return self._initiate_payment.handle(command)
 
    def complete_payment(self, command: CompletePaymentCommand) -> None:
        """Подтвердить оплату от эквайринга."""
        self._complete_payment.handle(command)
 
    def cancel_order(self, command: CancelOrderCommand) -> None:
        """Отменить заказ."""
        self._cancel_order.handle(command)
 
    # ── Queries ───────────────────────────────────────────────────
 
    def get_order_by_id(self, query: GetOrderByIdQuery) -> OrderDto:
        """Получить полную информацию о заказе."""
        return self._get_order_by_id.handle(query)
 
    def list_active_orders(self, query: ListActiveOrdersQuery) -> List[OrderSummaryDto]:
        """Получить список активных заказов в зале."""
        return self._list_active_orders.handle(query)