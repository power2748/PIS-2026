import json
import pika
import os
from cqrs.projection.order_view_projection import OrderViewProjection
from cqrs.projection.table_view_projection import TableViewProjection
from cqrs.projection.kitchen_dashboard_projection import KitchenDashboardProjection
from cqrs.projection.revenue_projection import RevenueProjection
from domain.events.order_events import (
    OrderCreatedEvent, OrderSentToKitchenEvent,
    PaymentInitiatedEvent, PaymentCompletedEvent, OrderCancelledEvent,
)
from infrastructure.config.database import ReadSessionLocal, WriteSessionLocal
from infrastructure.adapter.out.postgres_order_repository import PostgresOrderRepository
from datetime import datetime
 
 
EVENT_TYPE_MAP = {
    "order.created":       OrderCreatedEvent,
    "order.sent_to_kitchen": OrderSentToKitchenEvent,
    "payment.initiated":   PaymentInitiatedEvent,
    "payment.completed":   PaymentCompletedEvent,
    "order.cancelled":     OrderCancelledEvent,
}
 
 
class ProjectionEventDispatcher:
    """
    Слушает RabbitMQ и маршрутизирует события в нужные проекции.
    Запускается как отдельный процесс/воркер.
    """
 
    def __init__(self):
        self._url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
 
    def start(self):
        connection = pika.BlockingConnection(pika.URLParameters(self._url))
        channel = connection.channel()
 
        channel.exchange_declare(
            exchange="restaurant.events",
            exchange_type="topic",
            durable=True,
        )
        result = channel.queue_declare(queue="projections", durable=True)
        channel.queue_bind(
            exchange="restaurant.events",
            queue="projections",
            routing_key="order.*",
        )
        channel.queue_bind(
            exchange="restaurant.events",
            queue="projections",
            routing_key="payment.*",
        )
        channel.basic_consume(
            queue="projections",
            on_message_callback=self._handle,
            auto_ack=False,
        )
        print("[Dispatcher] Waiting for events...")
        channel.start_consuming()
 
    def _handle(self, ch, method, properties, body):
        routing_key = method.routing_key
        event_class = EVENT_TYPE_MAP.get(routing_key)
        if event_class is None:
            ch.basic_ack(method.delivery_tag)
            return
 
        data = json.loads(body)
        # Восстанавливаем объект события из JSON
        data["occurred_at"] = datetime.fromisoformat(data.get("occurred_at", datetime.now().isoformat()))
        event = event_class(**{k: v for k, v in data.items()
                               if k in event_class.__dataclass_fields__})
 
        read_db   = ReadSessionLocal()
        write_db  = WriteSessionLocal()
        write_repo = PostgresOrderRepository(write_db)
 
        try:
            order_proj   = OrderViewProjection(read_db, write_repo)
            table_proj   = TableViewProjection(read_db)
            kitchen_proj = KitchenDashboardProjection(read_db, write_repo)
            revenue_proj = RevenueProjection(read_db)
 
            self._dispatch(event, order_proj, table_proj, kitchen_proj, revenue_proj)
 
            read_db.commit()
            ch.basic_ack(method.delivery_tag)
        except Exception as exc:
            read_db.rollback()
            print(f"[Dispatcher] ERROR processing {routing_key}: {exc}")
            ch.basic_nack(method.delivery_tag, requeue=True)
        finally:
            read_db.close()
            write_db.close()
 
    def _dispatch(self, event, order_proj, table_proj, kitchen_proj, revenue_proj):
        if isinstance(event, OrderCreatedEvent):
            order_proj.on_order_created(event)
            table_proj.on_order_created(event)
        elif isinstance(event, OrderSentToKitchenEvent):
            order_proj.on_order_sent_to_kitchen(event)
            kitchen_proj.on_order_sent_to_kitchen(event)
        elif isinstance(event, PaymentInitiatedEvent):
            order_proj.on_payment_initiated(event)
        elif isinstance(event, PaymentCompletedEvent):
            order_proj.on_payment_completed(event)
            table_proj.on_payment_completed(event)
            kitchen_proj.on_payment_completed(event)
            revenue_proj.on_payment_completed(event)
        elif isinstance(event, OrderCancelledEvent):
            order_proj.on_order_cancelled(event)
            table_proj.on_order_cancelled(event)