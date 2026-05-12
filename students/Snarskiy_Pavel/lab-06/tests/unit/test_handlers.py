import pytest
from unittest.mock import MagicMock, patch, call
from application.command.create_order_command import CreateOrderCommand, OrderItemData
from application.command.send_to_kitchen_command import SendToKitchenCommand
from application.command.initiate_payment_command import InitiatePaymentCommand
from application.command.handlers.create_order_handler import CreateOrderHandler
from application.command.handlers.send_to_kitchen_handler import SendToKitchenHandler
from application.command.handlers.initiate_payment_handler import InitiatePaymentHandler
from application.query.get_order_by_id_query import GetOrderByIdQuery
from application.query.handlers.get_order_by_id_handler import GetOrderByIdHandler
from application.port.out.order_repository import IOrderRepository
from application.port.out.menu_inventory_port import IMenuInventoryPort
from application.port.out.event_publisher import IEventPublisher
from domain.aggregates.order import Order
from domain.value_objects.table_number import TableNumber
from domain.value_objects.order_status import OrderStatus
from domain.value_objects.money import Money
from domain.exceptions.domain_exception import (
    TableOccupiedException, DishUnavailableException,
    OrderNotFoundException, InvalidOrderStateException,
)
from domain.events.order_events import OrderCreatedEvent, OrderSentToKitchenEvent
 
 
# ── Фикстуры ──────────────────────────────────────────────────────
 
@pytest.fixture
def mock_repo():
    repo = MagicMock(spec=IOrderRepository)
    repo.find_by_idempotency_key.return_value = None
    repo.find_by_table_id.return_value = None
    return repo
 
@pytest.fixture
def mock_menu():
    menu = MagicMock(spec=IMenuInventoryPort)
    menu.check_availability.return_value = {"D-01": True, "D-07": True}
    return menu
 
@pytest.fixture
def mock_publisher():
    return MagicMock(spec=IEventPublisher)
 
def make_create_command(**kwargs) -> CreateOrderCommand:
    defaults = dict(
        table_id=12, guests=2,
        items=[
            OrderItemData("D-01", "Стейк", 1, 1500.0, "GRILL"),
            OrderItemData("D-07", "Паста", 1, 800.0, "PASTA"),
        ],
        idempotency_key="key-001",
    )
    defaults.update(kwargs)
    return CreateOrderCommand(**defaults)
 
def make_mock_order(order_id="ORD-001", status="NEW") -> Order:
    order = MagicMock(spec=Order)
    order.order_id = order_id
    order.table_number = TableNumber(12)
    order.status = OrderStatus(status)
    order.version = 1
    order.items = []
    order.kitchen_ticket = None
    order.payment = None
    order._guests = 2
    order._comment = None
    from datetime import datetime
    order._created_at = datetime.now()
    order._updated_at = datetime.now()
    order.calculate_total.return_value = Money(2300.0)
    order.pull_events.return_value = [OrderCreatedEvent("ORD-001", 12, 2)]
    return order
 
 
# ── CreateOrderHandler ────────────────────────────────────────────
 
class TestCreateOrderHandler:
 
    @pytest.fixture
    def handler(self, mock_repo, mock_menu, mock_publisher):
        return CreateOrderHandler(mock_repo, mock_menu, mock_publisher)
 
    def test_happy_path_returns_order_id(self, handler, mock_repo):
        order_id = handler.handle(make_create_command())
        assert order_id.startswith("ORD-")
        mock_repo.save.assert_called_once()
 
    def test_publishes_order_created_event(self, handler, mock_publisher):
        handler.handle(make_create_command())
        published = [type(c.args[0]) for c in mock_publisher.publish.call_args_list]
        assert OrderCreatedEvent in published
 
    def test_reserves_ingredients(self, handler, mock_menu):
        handler.handle(make_create_command())
        mock_menu.reserve_ingredients.assert_called_once()
 
    def test_idempotent_returns_existing_order_id(self, handler, mock_repo):
        existing = MagicMock()
        existing.order_id = "ORD-EXISTING"
        mock_repo.find_by_idempotency_key.return_value = existing
 
        result = handler.handle(make_create_command())
 
        assert result == "ORD-EXISTING"
        mock_repo.save.assert_not_called()
 
    def test_table_occupied_raises(self, handler, mock_repo):
        occupied = MagicMock()
        occupied.order_id = "ORD-999"
        mock_repo.find_by_table_id.return_value = occupied
 
        with pytest.raises(TableOccupiedException, match="Столик №12"):
            handler.handle(make_create_command())
        mock_repo.save.assert_not_called()
 
    def test_dish_in_stoplist_raises(self, handler, mock_menu):
        mock_menu.check_availability.return_value = {"D-01": True, "D-07": False}
        with pytest.raises(DishUnavailableException, match="D-07"):
            handler.handle(make_create_command())
 
    def test_does_not_save_on_validation_error(self, handler, mock_repo, mock_menu):
        mock_menu.check_availability.return_value = {"D-01": False, "D-07": False}
        with pytest.raises(DishUnavailableException):
            handler.handle(make_create_command())
        mock_repo.save.assert_not_called()
 
    def test_command_validates_empty_items(self):
        with pytest.raises(ValueError, match="пустым"):
            CreateOrderCommand(table_id=1, guests=1, items=[])
 
    def test_command_validates_negative_guests(self):
        with pytest.raises(ValueError):
            CreateOrderCommand(table_id=1, guests=-1, items=[
                OrderItemData("D-01", "Блюдо", 1, 100.0, "GRILL")
            ])
 
 
# ── SendToKitchenHandler ──────────────────────────────────────────
 
class TestSendToKitchenHandler:
 
    @pytest.fixture
    def handler(self, mock_repo, mock_publisher):
        return SendToKitchenHandler(mock_repo, mock_publisher)
 
    def test_happy_path_returns_ticket_id(self, handler, mock_repo):
        order = make_mock_order("ORD-001", "NEW")
        ticket = MagicMock()
        ticket.ticket_id = "KT-001"
        order.send_to_kitchen.return_value = ticket
        order.pull_events.return_value = [OrderSentToKitchenEvent("ORD-001", "KT-001", 12)]
        mock_repo.find_by_id.return_value = order
 
        result = handler.handle(SendToKitchenCommand("ORD-001", "waiter-42"))
 
        assert result == "KT-001"
        mock_repo.save.assert_called_once_with(order)
 
    def test_not_found_raises(self, handler, mock_repo):
        mock_repo.find_by_id.return_value = None
        with pytest.raises(OrderNotFoundException):
            handler.handle(SendToKitchenCommand("ORD-GHOST", "waiter-1"))
 
    def test_publishes_event(self, handler, mock_repo, mock_publisher):
        order = make_mock_order()
        ticket = MagicMock(ticket_id="KT-001")
        order.send_to_kitchen.return_value = ticket
        order.pull_events.return_value = [OrderSentToKitchenEvent("ORD-001", "KT-001", 12)]
        mock_repo.find_by_id.return_value = order
 
        handler.handle(SendToKitchenCommand("ORD-001", "waiter-1"))
 
        mock_publisher.publish.assert_called_once()
 
 
# ── InitiatePaymentHandler ────────────────────────────────────────
 
class TestInitiatePaymentHandler:
 
    @pytest.fixture
    def handler(self, mock_repo, mock_publisher):
        return InitiatePaymentHandler(mock_repo, mock_publisher)
 
    def test_happy_path_returns_payment_id(self, handler, mock_repo):
        order = make_mock_order("ORD-001", "READY")
        payment = MagicMock()
        payment.payment_id = "PAY-001"
        order.initiate_payment.return_value = payment
        mock_repo.find_by_id.return_value = order
 
        result = handler.handle(InitiatePaymentCommand("ORD-001", "CARD", tip=200.0))
 
        assert result == "PAY-001"
        mock_repo.save.assert_called_once()
 
    def test_not_found_raises(self, handler, mock_repo):
        mock_repo.find_by_id.return_value = None
        with pytest.raises(OrderNotFoundException):
            handler.handle(InitiatePaymentCommand("ORD-GHOST", "CARD"))
 
    def test_command_invalid_method_raises(self):
        with pytest.raises(ValueError, match="метод оплаты"):
            InitiatePaymentCommand("ORD-001", "CRYPTO")
 
    def test_command_negative_tip_raises(self):
        with pytest.raises(ValueError, match="tip"):
            InitiatePaymentCommand("ORD-001", "CARD", tip=-10.0)
 
 
# ── GetOrderByIdHandler ───────────────────────────────────────────
 
class TestGetOrderByIdHandler:
 
    @pytest.fixture
    def handler(self, mock_repo):
        return GetOrderByIdHandler(mock_repo)
 
    def test_returns_dto_for_existing_order(self, handler, mock_repo):
        mock_repo.find_by_id.return_value = make_mock_order("ORD-001")
        dto = handler.handle(GetOrderByIdQuery("ORD-001"))
        assert dto.order_id == "ORD-001"
 
    def test_not_found_raises(self, handler, mock_repo):
        mock_repo.find_by_id.return_value = None
        with pytest.raises(OrderNotFoundException, match="ORD-GHOST"):
            handler.handle(GetOrderByIdQuery("ORD-GHOST"))
 
    def test_does_not_call_save(self, handler, mock_repo):
        """Query не должен изменять состояние — ключевая гарантия CQRS"""
        mock_repo.find_by_id.return_value = make_mock_order()
        handler.handle(GetOrderByIdQuery("ORD-001"))
        mock_repo.save.assert_not_called()
 
    def test_query_empty_id_raises(self):
        with pytest.raises(ValueError):
            GetOrderByIdQuery(order_id="")