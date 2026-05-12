import unittest
from unittest.mock import MagicMock, call
 
class TestOrderService(unittest.TestCase):
    """Юнит-тесты для OrderService с mock-объектами вместо реальных адаптеров"""
 
    def setUp(self):
        # Создаём моки для всех исходящих портов
        self.mock_repository = MagicMock(spec=IOrderRepository)
        self.mock_menu_inventory = MagicMock(spec=IMenuInventoryPort)
        self.mock_payment_gateway = MagicMock(spec=IPaymentGateway)
        self.mock_kitchen_notification = MagicMock(spec=IKitchenNotificationPort)
 
        self.service = OrderService(
            order_repository=self.mock_repository,
            menu_inventory_port=self.mock_menu_inventory,
            payment_gateway=self.mock_payment_gateway,
            kitchen_notification_port=self.mock_kitchen_notification,
        )
 
    def test_create_order_success(self):
        """Успешное создание заказа"""
        # Arrange
        self.mock_repository.find_by_table_id.return_value = None  # столик свободен
        self.mock_menu_inventory.check_availability.return_value = {"D-01": True, "D-07": True}
        command = CreateOrderCommand(table_id=12, guests=2, items=[
            OrderItemCommand(dish_id="D-01", quantity=1),
            OrderItemCommand(dish_id="D-07", quantity=1),
        ])
 
        # Act — раскомментировать после реализации в Lab #4
        # order_id = self.service.create_order(command)
 
        # Assert
        # self.assertIsNotNone(order_id)
        # self.assertTrue(order_id.startswith("ORD-"))
        # self.mock_repository.save.assert_called_once()
        # self.mock_menu_inventory.reserve_ingredients.assert_called_once()
        pass  # TODO: раскомментировать в Lab #4
 
    def test_create_order_fails_if_table_occupied(self):
        """Создание заказа падает, если столик занят"""
        # Arrange
        existing_order = MagicMock()
        existing_order.id = "ORD-2024-0301"
        self.mock_repository.find_by_table_id.return_value = existing_order
 
        command = CreateOrderCommand(table_id=12, guests=2, items=[
            OrderItemCommand(dish_id="D-01", quantity=1)
        ])
 
        # Act & Assert — раскомментировать после реализации в Lab #4
        # with self.assertRaises(TableOccupiedException):
        #     self.service.create_order(command)
        # self.mock_repository.save.assert_not_called()
        pass  # TODO: раскомментировать в Lab #4
 
    def test_create_order_fails_if_dish_in_stoplist(self):
        """Создание заказа падает, если блюдо в стоп-листе"""
        # Arrange
        self.mock_repository.find_by_table_id.return_value = None
        self.mock_menu_inventory.check_availability.return_value = {
            "D-01": True,
            "D-99": False,  # В стоп-листе
        }
        command = CreateOrderCommand(table_id=5, guests=1, items=[
            OrderItemCommand(dish_id="D-01", quantity=1),
            OrderItemCommand(dish_id="D-99", quantity=1),
        ])
 
        # Act & Assert — раскомментировать после реализации в Lab #4
        # with self.assertRaises(DishUnavailableException):
        #     self.service.create_order(command)
        pass  # TODO: раскомментировать в Lab #4
 
if __name__ == "__main__":
    unittest.main()