"""
Схема обмена событиями между микросервисами.
 
Exchange: restaurant.events (topic, durable)
 
Routing keys и подписчики:
  order.created          → kitchen-service, notification-service
  order.sent_to_kitchen  → kitchen-service, notification-service
  order.cancelled        → kitchen-service, payment-service
  payment.initiated      → payment-service (внутренний retry worker)
  payment.completed      → notification-service
  payment.failed         → notification-service
  kitchen.ticket.done    → order-service (обновить статус READY)
"""
 
EXCHANGE = "restaurant.events"
 
# Очереди и их routing key binding
QUEUE_BINDINGS = {
    "order-service": [
        "kitchen.ticket.done",
    ],
    "kitchen-service": [
        "order.sent_to_kitchen",
        "order.cancelled",
    ],
    "payment-service": [
        "order.cancelled",
        "payment.initiated",
    ],
    "notification-service": [
        "order.created",
        "order.sent_to_kitchen",
        "payment.completed",
        "payment.failed",
    ],
}