import pytest
import grpc
import threading
import time
from concurrent import futures
from unittest.mock import MagicMock, patch
 
from grpc.generated import order_service_pb2 as pb
from grpc.generated import order_service_pb2_grpc as pb_grpc
from grpc.generated import kitchen_service_pb2 as kitchen_pb
from grpc.generated import kitchen_service_pb2_grpc as kitchen_pb_grpc
 
from grpc.server import OrderServicer, KitchenServicer
from grpc.client import OrderServiceClient, KitchenServiceClient
 
 
# ── Фикстуры: поднимаем тестовые gRPC-серверы ─────────────────────
 
@pytest.fixture(scope="session")
def order_grpc_server():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    pb_grpc.add_OrderServiceServicer_to_server(OrderServicer(), server)
    port = server.add_insecure_port("[::]:0")   # случайный порт
    server.start()
    yield port
    server.stop(grace=1)
 
@pytest.fixture(scope="session")
def kitchen_grpc_server():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    kitchen_pb_grpc.add_KitchenServiceServicer_to_server(KitchenServicer(), server)
    port = server.add_insecure_port("[::]:0")
    server.start()
    yield port
    server.stop(grace=1)
 
@pytest.fixture(scope="session")
def order_client(order_grpc_server):
    client = OrderServiceClient("localhost", order_grpc_server)
    yield client
    client.close()
 
@pytest.fixture(scope="session")
def kitchen_client(kitchen_grpc_server):
    client = KitchenServiceClient("localhost", kitchen_grpc_server)
    yield client
    client.close()
 
 
# ── Unary тесты ───────────────────────────────────────────────────
 
class TestOrderServiceUnary:
 
    @patch("grpc.server.build_create_order_handler")
    def test_create_order_returns_order_id(self, mock_build, order_client):
        mock_handler = MagicMock()
        mock_handler.handle.return_value = "ORD-TEST-001"
        mock_build.return_value = mock_handler
 
        resp = order_client.create_order(
            table_id=5, guests=2,
            items=[{"dish_id": "D-01", "dish_name": "Блюдо",
                    "quantity": 1, "price": 500.0, "station": "GRILL"}],
            idempotency_key="test-key-001",
        )
 
        assert resp.order_id == "ORD-TEST-001"
        assert resp.status == "NEW"
        assert resp.currency == "RUB"
 
    @patch("grpc.server.build_get_order_by_id_handler")
    def test_get_order_returns_dto(self, mock_build, order_client):
        mock_dto = MagicMock()
        mock_dto.order_id  = "ORD-001"
        mock_dto.table_id  = 5
        mock_dto.guests    = 2
        mock_dto.status    = "NEW"
        mock_dto.total     = 500.0
        mock_dto.currency  = "RUB"
        mock_dto.version   = 1
        mock_dto.comment   = None
        mock_dto.items     = []
        mock_dto.kitchen_ticket = None
        mock_dto.payment   = None
        from datetime import datetime
        mock_dto.created_at = datetime.now().isoformat()
        mock_dto.updated_at = datetime.now().isoformat()
 
        mock_handler = MagicMock()
        mock_handler.handle.return_value = mock_dto
        mock_build.return_value = mock_handler
 
        dto = order_client.get_order("ORD-001")
 
        assert dto.order_id == "ORD-001"
        assert dto.table_id == 5
        assert dto.status == "NEW"
 
    @patch("grpc.server.build_get_order_by_id_handler")
    def test_get_nonexistent_order_raises_not_found(self, mock_build, order_client):
        mock_handler = MagicMock()
        mock_handler.handle.side_effect = Exception("Заказ не найден")
        mock_build.return_value = mock_handler
 
        with pytest.raises(grpc.RpcError) as exc_info:
            order_client.get_order("ORD-GHOST")
 
        assert exc_info.value.code() == grpc.StatusCode.NOT_FOUND
 
 
class TestKitchenServiceUnary:
 
    @patch("grpc.server.build_create_ticket_handler")
    def test_create_ticket_returns_ticket_id(self, mock_build, kitchen_client):
        mock_handler = MagicMock()
        mock_build.return_value = mock_handler
 
        resp = kitchen_client.create_ticket(
            ticket_id="KT-001",
            order_id="ORD-001",
            table_number=5,
            items=[{"dish_id": "D-01", "dish_name": "Стейк",
                    "quantity": 1, "station": "GRILL", "comment": ""}],
        )
 
        assert resp.ticket_id == "KT-001"
        assert resp.status == "PENDING"
        assert resp.eta_minutes == 20  # GRILL = 20 мин
 
 
# ── Streaming тесты ───────────────────────────────────────────────
 
class TestServerSideStreaming:
 
    @patch("grpc.server.build_list_active_orders_handler")
    @patch("grpc.server.build_get_order_by_id_handler")
    def test_stream_active_orders_receives_initial_state(
        self, mock_get_build, mock_list_build, order_client
    ):
        """
        Streaming: первые сообщения содержат текущее состояние активных заказов.
        """
        mock_list_handler = MagicMock()
        summary = MagicMock()
        summary.order_id = "ORD-001"
        mock_list_handler.handle.return_value = [summary]
        mock_list_build.return_value = mock_list_handler
 
        mock_dto = MagicMock()
        mock_dto.order_id = "ORD-001"
        mock_dto.table_id = 5
        mock_dto.guests = 2
        mock_dto.status = "IN_PROGRESS"
        mock_dto.total = 1500.0
        mock_dto.currency = "RUB"
        mock_dto.version = 2
        mock_dto.comment = None
        mock_dto.items = []
        mock_dto.kitchen_ticket = None
        mock_dto.payment = None
        from datetime import datetime
        mock_dto.created_at = datetime.now().isoformat()
        mock_dto.updated_at = datetime.now().isoformat()
 
        mock_get_handler = MagicMock()
        mock_get_handler.handle.return_value = mock_dto
        mock_get_build.return_value = mock_get_handler
 
        received = []
        def collect():
            for dto in order_client.stream_active_orders(page_size=10):
                received.append(dto)
                if len(received) >= 1:
                    break  # берём только первое сообщение
 
        t = threading.Thread(target=collect)
        t.start()
        t.join(timeout=5.0)
 
        assert len(received) >= 1
        assert received[0].order_id == "ORD-001"
        assert received[0].status == "IN_PROGRESS"
 
    @patch("grpc.server.build_create_ticket_handler")
    def test_stream_station_updates_receives_ticket_created(
        self, mock_build, kitchen_client
    ):
        """
        Streaming: после создания тикета KDS получает TICKET_CREATED событие.
        """
        mock_build.return_value = MagicMock()
 
        received_events = []
 
        def listen():
            for event in kitchen_client.stream_station_updates("GRILL"):
                received_events.append(event)
                break  # берём первое событие и выходим
 
        listener = threading.Thread(target=listen, daemon=True)
        listener.start()
 
        time.sleep(0.2)  # даём клиенту зарегистрироваться
 
        # Создаём тикет — должен триггернуть событие на GRILL
        kitchen_client.create_ticket(
            ticket_id="KT-STREAM-001",
            order_id="ORD-STREAM-001",
            table_number=7,
            items=[{"dish_id": "D-01", "dish_name": "Стейк",
                    "quantity": 1, "station": "GRILL", "comment": ""}],
        )
 
        listener.join(timeout=3.0)
 
        assert len(received_events) == 1
        assert received_events[0].event_type == "TICKET_CREATED"
        assert received_events[0].ticket_id == "KT-STREAM-001"
        assert received_events[0].table_number == 7