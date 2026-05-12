import pytest
from unittest.mock import MagicMock
from application.query.get_order_by_id_query import GetOrderByIdQuery
from application.query.handlers.get_order_by_id_handler import GetOrderByIdHandler
from application.port.out.order_repository import IOrderRepository
from domain.exceptions.domain_exception import OrderNotFoundException
from domain.aggregates.order import Order
from domain.value_objects.table_number import TableNumber
from domain.value_objects.order_status import OrderStatus
 
 
def make_mock_order(order_id="ORD-001", table=5, status="NEW"):
    order = MagicMock(spec=Order)
    order.order_id = order_id
    order.table_number = TableNumber(table)
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
    order.calculate_total.return_value = MagicMock(amount=0.0, currency="RUB")
    return order
 
 
class TestGetOrderByIdHandler:
 
    def test_returns_dto_for_existing_order(self):
        repo = MagicMock(spec=IOrderRepository)
        repo.find_by_id.return_value = make_mock_order("ORD-001")
        handler = GetOrderByIdHandler(repo)
 
        dto = handler.handle(GetOrderByIdQuery(order_id="ORD-001"))
 
        assert dto.order_id == "ORD-001"
        assert dto.table_id == 5
        assert dto.status == "NEW"
 
    def test_raises_if_not_found(self):
        repo = MagicMock(spec=IOrderRepository)
        repo.find_by_id.return_value = None
        handler = GetOrderByIdHandler(repo)
 
        with pytest.raises(OrderNotFoundException, match="ORD-999"):
            handler.handle(GetOrderByIdQuery(order_id="ORD-999"))
 
    def test_query_does_not_call_save(self):
        """Query не должен изменять состояние"""
        repo = MagicMock(spec=IOrderRepository)
        repo.find_by_id.return_value = make_mock_order()
        handler = GetOrderByIdHandler(repo)
 
        handler.handle(GetOrderByIdQuery(order_id="ORD-001"))
 
        repo.save.assert_not_called()  # ключевая проверка для Query