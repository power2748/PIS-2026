import pika, os
 
def setup_rabbitmq():
    url  = os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672/")
    conn = pika.BlockingConnection(pika.URLParameters(url))
    ch   = conn.channel()
 
    # Объявляем exchange
    ch.exchange_declare(
        exchange="restaurant.events",
        exchange_type="topic",
        durable=True,
    )
 
    # Объявляем очереди и привязываем routing keys
    from event_bus.rabbitmq_config import QUEUE_BINDINGS
    for queue, keys in QUEUE_BINDINGS.items():
        ch.queue_declare(queue=queue, durable=True)
        for key in keys:
            ch.queue_bind(
                exchange="restaurant.events",
                queue=queue,
                routing_key=key,
            )
        print(f"[Setup] Queue '{queue}' bound to {keys}")
 
    conn.close()
    print("[Setup] RabbitMQ configured.")
 
if __name__ == "__main__":
    setup_rabbitmq()