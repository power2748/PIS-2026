import pytest
from unittest.mock import MagicMock, call
from application.command.create_order_command import CreateOrderCommand, OrderItemData
from application.command.handlers.create_order_handler import CreateOrderHandler
from application.port.out.order_repository import IOrderRepository
from application.port.out.menu_inventory_port import IMenuInventoryPort
from application.port.out.event_publisher import IEventPublisher
from domain.exceptions.domain_exception import TableOccupiedException, DishUnavailableException
from domain.events.order_events import OrderCreatedEvent
 
 
def make_command(**kwargs) -> CreateOrderCommand:
    defaults = dict(
        table_id=12,
        guests=2,
        items=[
            OrderItemData(dish_id="D-01", dish_name="Стейк", quantity=1,
                          price=1500.0, station="GRILL"),
            OrderItemData(dish_id="D-07", dish_name="Паста", quantity=1,
                          price=800.0, station="PASTA"),
        ],
        idempotency_key="waiter-1_table-12_test",
    )
    defaults.update(kwargs)
    return CreateOrderCommand(**defaults)
 
 
@pytest.fixture
def mock_repo():
    repo = MagicMock(spec=IOrderRepository)
    repo.find_by_idempotency_key.return_value = None   # нет дубликата
    repo.find_by_table_id.return_value = None           # столик свободен
    return repo
 
@pytest.fixture
def mock_menu():
    menu = MagicMock(spec=IMenuInventoryPort)
    menu.check_availability.return_value = {"D-01": True, "D-07": True}
    return menu
 
@pytest.fixture
def mock_publisher():
    return MagicMock(spec=IEventPublisher)
 
@pytest.fixture
def handler(mock_repo, mock_menu, mock_publisher):
    return CreateOrderHandler(mock_repo, mock_menu, mock_publisher)
 
 
class TestCreateOrderHandler:
 
    def test_create_order_success(self, handler, mock_repo, mock_menu, mock_publisher):
        """Успешное создание заказа: save вызван, событие опубликовано"""
        order_id = handler.handle(make_command())
 
        assert order_id.startswith("ORD-")
        mock_repo.save.assert_called_once()
        mock_menu.reserve_ingredients.assert_called_once()
        # Проверяем, что опубликован OrderCreatedEvent
        published_types = [type(c.args[0]) for c in mock_publisher.publish.call_args_list]
        assert OrderCreatedEvent in published_types
 
    def test_create_order_idempotent(self, handler, mock_repo):
        """Повторный запрос с тем же idempotency_key возвращает тот же order_id"""
        existing = MagicMock()
        existing.order_id = "ORD-2024-0042"
        mock_repo.find_by_idempotency_key.return_value = existing
 
        result = handler.handle(make_command())
        assert result == "ORD-2024-0042"
        mock_repo.save.assert_not_called()  # повторно не сохраняем
 
    def test_create_order_table_occupied(self, handler, mock_repo):
        """Исключение, если столик занят"""
        occupied = MagicMock()
        occupied.order_id = "ORD-2024-0001"
        mock_repo.find_by_table_id.return_value = occupied
 
        with pytest.raises(TableOccupiedException, match="Столик №12"):
            handler.handle(make_command())
        mock_repo.save.assert_not_called()
 
    def test_create_order_dish_unavailable(self, handler, mock_menu):
        """Исключение, если блюдо в стоп-листе"""
        mock_menu.check_availability.return_value = {"D-01": True, "D-07": False}
 
        with pytest.raises(DishUnavailableException, match="D-07"):
            handler.handle(make_command())
 
    def test_create_order_empty_items_raises(self):
        """Команда с пустым списком блюд не создаётся"""
        with pytest.raises(ValueError, match="пустым"):
            CreateOrderCommand(table_id=1, guests=1, items=[])
 
    def test_create_order_negative_guests_raises(self):
        """Команда с guests <= 0 не создаётся"""
        with pytest.raises(ValueError, match="guests"):
            CreateOrderCommand(table_id=1, guests=0, items=[
                OrderItemData("D-01", "Блюдо", 1, 100.0, "GRILL")
            ])