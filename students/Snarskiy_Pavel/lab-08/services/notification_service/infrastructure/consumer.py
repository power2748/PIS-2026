import json, pika, os, threading
from datetime import datetime
 
 
HANDLERS = {
    "order.created":          "_on_order_created",
    "order.sent_to_kitchen":  "_on_order_sent_to_kitchen",
    "payment.completed":      "_on_payment_completed",
    "payment.failed":         "_on_payment_failed",
}
 
 
class NotificationConsumer:
    """
    Notification Service — конечная точка событийной цепочки.
    Не публикует события, только потребляет и доставляет уведомления.
    """
    EXCHANGE = "restaurant.events"
    QUEUE    = "notification-service"
 
    def __init__(self):
        self._url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
 
    def start(self):
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()
 
    def _run(self):
        conn = pika.BlockingConnection(pika.URLParameters(self._url))
        ch = conn.channel()
        ch.exchange_declare(exchange=self.EXCHANGE, exchange_type="topic", durable=True)
        ch.queue_declare(queue=self.QUEUE, durable=True)
        for key in HANDLERS:
            ch.queue_bind(exchange=self.EXCHANGE, queue=self.QUEUE, routing_key=key)
        ch.basic_qos(prefetch_count=5)
        ch.basic_consume(queue=self.QUEUE, on_message_callback=self._handle)
        ch.start_consuming()
 
    def _handle(self, ch, method, props, body):
        try:
            data = json.loads(body)
            handler_name = HANDLERS.get(method.routing_key)
            if handler_name:
                getattr(self, handler_name)(data)
            ch.basic_ack(method.delivery_tag)
        except Exception as e:
            print(f"[NotificationService] ERROR: {e}")
            ch.basic_nack(method.delivery_tag, requeue=False)
 
    def _on_order_created(self, data: dict):
        print(f"[NOTIFY] Новый заказ {data['order_id']} на столике №{data['table_number']}")
        # В реальной реализации: push через WebSocket к менеджеру зала
 
    def _on_order_sent_to_kitchen(self, data: dict):
        print(f"[NOTIFY] KDS: тикет {data['ticket_id']} → кухня")
        # В реальной реализации: POST на KDS API по станциям
 
    def _on_payment_completed(self, data: dict):
        print(f"[NOTIFY] Оплата {data['payment_id']} подтверждена. Столик {data['table_number']} свободен")
 
    def _on_payment_failed(self, data: dict):
        print(f"[NOTIFY] ⚠️ Оплата {data['payment_id']} не прошла. Попросите наличные.")