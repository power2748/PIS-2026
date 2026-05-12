import grpc
from grpc.generated import order_service_pb2 as order_pb
from grpc.generated import order_service_pb2_grpc as order_pb_grpc
from grpc.generated import kitchen_service_pb2 as kitchen_pb
from grpc.generated import kitchen_service_pb2_grpc as kitchen_pb_grpc
 
 
class OrderServiceClient:
    """
    gRPC-клиент для Order Service.
    Используется другими микросервисами и тестами.
    """
 
    def __init__(self, host: str = "localhost", port: int = 50051):
        self._channel = grpc.insecure_channel(f"{host}:{port}")
        self._stub = order_pb_grpc.OrderServiceStub(self._channel)
 
    def create_order(
        self,
        table_id: int,
        guests: int,
        items: list,
        comment: str = "",
        idempotency_key: str = "",
    ) -> order_pb.CreateOrderResponse:
        request = order_pb.CreateOrderRequest(
            table_id=table_id,
            guests=guests,
            items=[
                order_pb.OrderItemProto(
                    dish_id=i["dish_id"], dish_name=i["dish_name"],
                    quantity=i["quantity"], price=i["price"],
                    station=i["station"], comment=i.get("comment", ""),
                )
                for i in items
            ],
            comment=comment,
            idempotency_key=idempotency_key,
        )
        return self._stub.CreateOrder(request)
 
    def get_order(self, order_id: str) -> order_pb.OrderDto:
        return self._stub.GetOrder(order_pb.GetOrderRequest(order_id=order_id))
 
    def mark_order_ready(self, order_id: str, ticket_id: str):
        return self._stub.MarkOrderReady(
            order_pb.MarkOrderReadyRequest(order_id=order_id, ticket_id=ticket_id)
        )
 
    def stream_active_orders(self, page_size: int = 50):
        """
        Генератор: подписывается на real-time обновления заказов.
        Использование:
            for order_dto in client.stream_active_orders():
                print(order_dto.order_id, order_dto.status)
        """
        request = order_pb.ListActiveOrdersRequest(page=1, page_size=page_size)
        for order_dto in self._stub.StreamActiveOrders(request):
            yield order_dto
 
    def close(self):
        self._channel.close()
 
 
class KitchenServiceClient:
    """gRPC-клиент для Kitchen Service (используется Order Service)"""
 
    def __init__(self, host: str = "kitchen-service", port: int = 50052):
        self._channel = grpc.insecure_channel(f"{host}:{port}")
        self._stub = kitchen_pb_grpc.KitchenServiceStub(self._channel)
 
    def create_ticket(
        self,
        ticket_id: str,
        order_id: str,
        table_number: int,
        items: list,
    ) -> kitchen_pb.CreateTicketResponse:
        request = kitchen_pb.CreateTicketRequest(
            ticket_id=ticket_id,
            order_id=order_id,
            table_number=table_number,
            items=[
                kitchen_pb.TicketItemProto(
                    dish_id=i["dish_id"], dish_name=i["dish_name"],
                    quantity=i["quantity"], station=i["station"],
                    comment=i.get("comment", ""),
                )
                for i in items
            ],
        )
        return self._stub.CreateTicket(request)
 
    def stream_station_updates(self, station: str):
        """
        Server-side streaming: KDS-дисплей подписывается на обновления станции.
        Пример:
            for event in client.stream_station_updates("GRILL"):
                print(f"[GRILL] {event.event_type}: {event.ticket_id}")
        """
        request = kitchen_pb.StationQueueRequest(station=station)
        for event in self._stub.StreamStationUpdates(request):
            yield event
 
    def close(self):
        self._channel.close()
 
 
# ── Пример использования ──────────────────────────────────────────
 
if __name__ == "__main__":
    import threading
 
    # ── Unary: создать заказ ───────────────────────────────────────
    order_client = OrderServiceClient("localhost", 50051)
 
    resp = order_client.create_order(
        table_id=12,
        guests=2,
        items=[
            {"dish_id": "D-01", "dish_name": "Стейк Рибай",
             "quantity": 1, "price": 1500.0, "station": "GRILL"},
            {"dish_id": "D-12", "dish_name": "Тирамису",
             "quantity": 2, "price": 400.0, "station": "DESSERT"},
        ],
        idempotency_key="demo-001",
    )
    print(f"Создан заказ: {resp.order_id}, total={resp.total} {resp.currency}")
 
    # ── Unary: получить заказ ──────────────────────────────────────
    order_dto = order_client.get_order(resp.order_id)
    print(f"Статус: {order_dto.status}, позиций: {len(order_dto.items)}")
 
    # ── Streaming: подписка на KDS-дисплей GRILL ──────────────────
    kitchen_client = KitchenServiceClient("localhost", 50052)
 
    def listen_grill():
        print("[GRILL KDS] Подключение к стриму...")
        for event in kitchen_client.stream_station_updates("GRILL"):
            print(f"[GRILL KDS] {event.event_type}: тикет {event.ticket_id}, "
                  f"столик №{event.table_number} @ {event.timestamp}")
 
    stream_thread = threading.Thread(target=listen_grill, daemon=True)
    stream_thread.start()
 
    # ── Streaming: подписка на обновления всех заказов (менеджер) ─
    def listen_hall():
        print("[Менеджер] Подписка на обновления зала...")
        for order in order_client.stream_active_orders():
            print(f"[Зал] Столик №{order.table_id}: {order.status_label}")
 
    hall_thread = threading.Thread(target=listen_hall, daemon=True)
    hall_thread.start()
 
    import time
    time.sleep(30)  # слушаем 30 секунд
 
    order_client.close()
    kitchen_client.close()