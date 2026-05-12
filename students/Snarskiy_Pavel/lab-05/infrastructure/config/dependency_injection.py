from fastapi import Depends
from sqlalchemy.orm import Session
 
from infrastructure.config.database import get_db
from infrastructure.adapter.out.postgres_order_repository import PostgresOrderRepository
from infrastructure.adapter.out.in_memory_menu_inventory import InMemoryMenuInventory
from infrastructure.adapter.out.rabbitmq_event_publisher import RabbitMQEventPublisher
from application.command.handlers.create_order_handler import CreateOrderHandler
from application.command.handlers.send_to_kitchen_handler import SendToKitchenHandler
from application.command.handlers.initiate_payment_handler import InitiatePaymentHandler
from application.command.handlers.complete_payment_handler import CompletePaymentHandler
from application.command.handlers.cancel_order_handler import CancelOrderHandler
from application.query.handlers.get_order_by_id_handler import GetOrderByIdHandler
from application.query.handlers.list_active_orders_handler import ListActiveOrdersHandler
from application.service.order_service import OrderService
 
 
def get_order_service(db: Session = Depends(get_db)) -> OrderService:
    """Собирает граф зависимостей для каждого запроса"""
    repo      = PostgresOrderRepository(db)
    menu      = InMemoryMenuInventory()
    publisher = RabbitMQEventPublisher()
 
    return OrderService(
        create_order_handler      = CreateOrderHandler(repo, menu, publisher),
        send_to_kitchen_handler   = SendToKitchenHandler(repo, publisher),
        initiate_payment_handler  = InitiatePaymentHandler(repo, publisher),
        complete_payment_handler  = CompletePaymentHandler(repo, publisher),
        cancel_order_handler      = CancelOrderHandler(repo, menu, publisher),
        get_order_by_id_handler   = GetOrderByIdHandler(repo),
        list_active_orders_handler= ListActiveOrdersHandler(repo),
    )