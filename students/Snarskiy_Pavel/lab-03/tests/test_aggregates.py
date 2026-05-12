import pytest
from domain.aggregates.order import Order
from domain.entities.order_item import OrderItem
from domain.value_objects.money import Money
from domain.value_objects.table_number import TableNumber
from domain.value_objects.dish_station import DishStation
from domain.exceptions.domain_exception import InvalidOrderStateException, DomainException
from domain.events.order_events import (
    OrderCreatedEvent, OrderSentToKitchenEvent,
    PaymentInitiatedEvent, PaymentCompletedEvent,
)
 
 
def make_order(order_id="ORD-001", table=12, guests=2) -> Order:
    return Order(
        order_id=order_id,
        table_number=TableNumber(table),
        guests=guests,
    )
 
def make_item(dish_id="D-01", price=500.0, qty=1) -> OrderItem:
    return OrderItem(
        item_id=f"item-{dish_id}",
        dish_id=dish_id,
        dish_name="Стейк Рибай",
        quantity=qty,
        price=Money(price, "RUB"),
        station=DishStation("GRILL"),
    )
 
 
class TestOrderCreation:
    def test_order_created_event_registered(self):
        order = make_order()
        events = order.pull_events()
        assert len(events) == 1
        assert isinstance(events[0], OrderCreatedEvent)
 
    def test_initial_status_is_new(self):
        order = make_order()
        assert order.status.value == "NEW"
 
    def test_invalid_guests_raises(self):
        with pytest.raises(ValueError, match="гостей"):
            Order(order_id="ORD-X", table_number=TableNumber(1), guests=0)
 
 
class TestAddItem:
    def test_add_item_success(self):
        order = make_order()
        order.add_item(make_item())
        assert len(order.items) == 1
 
    def test_cannot_add_item_after_send_to_kitchen(self):
        order = make_order()
        order.add_item(make_item())
        order.send_to_kitchen("KT-001")
        with pytest.raises(InvalidOrderStateException):
            order.add_item(make_item("D-02"))
 
    def test_cannot_exceed_max_items(self):
        order = make_order()
        for i in range(Order.MAX_ITEMS):
            order.add_item(make_item(f"D-{i:02}"))
        with pytest.raises(DomainException, match="лимит"):
            order.add_item(make_item("D-99"))
 
 
class TestSendToKitchen:
    def test_send_to_kitchen_success(self):
        order = make_order()
        order.add_item(make_item())
        ticket = order.send_to_kitchen("KT-001")
        assert ticket.ticket_id == "KT-001"
        assert order.status.value == "IN_PROGRESS"
 
    def test_cannot_send_empty_order(self):
        order = make_order()
        with pytest.raises(DomainException, match="пустой"):
            order.send_to_kitchen("KT-001")
 
    def test_cannot_send_twice(self):
        order = make_order()
        order.add_item(make_item())
        order.send_to_kitchen("KT-001")
        with pytest.raises(InvalidOrderStateException):
            order.send_to_kitchen("KT-002")
 
    def test_send_to_kitchen_event_registered(self):
        order = make_order()
        order.add_item(make_item())
        order.pull_events()  # очищаем OrderCreatedEvent
        order.send_to_kitchen("KT-001")
        events = order.pull_events()
        assert any(isinstance(e, OrderSentToKitchenEvent) for e in events)
 
    def test_version_increments(self):
        order = make_order()
        v_before = order.version
        order.add_item(make_item())
        order.send_to_kitchen("KT-001")
        assert order.version == v_before + 1
 
 
class TestPayment:
    def _ready_order(self) -> Order:
        order = make_order()
        order.add_item(make_item(price=1000.0, qty=2))
        order.send_to_kitchen("KT-001")
        order.mark_ready()
        return order
 
    def test_initiate_payment_success(self):
        order = self._ready_order()
        payment = order.initiate_payment("PAY-001", "CARD")
        assert payment.payment_id == "PAY-001"
        assert order.status.value == "AWAITING_PAYMENT"
 
    def test_cannot_pay_non_ready_order(self):
        order = make_order()
        order.add_item(make_item())
        order.send_to_kitchen("KT-001")
        with pytest.raises(InvalidOrderStateException):
            order.initiate_payment("PAY-001", "CARD")
 
    def test_complete_payment_success(self):
        order = self._ready_order()
        order.initiate_payment("PAY-001", "CARD")
        order.complete_payment("txn-abc123")
        assert order.status.value == "PAID"
 
    def test_payment_completed_event_registered(self):
        order = self._ready_order()
        order.initiate_payment("PAY-001", "CARD")
        order.pull_events()
        order.complete_payment("txn-abc123")
        events = order.pull_events()
        assert any(isinstance(e, PaymentCompletedEvent) for e in events)
 
    def test_calculate_total(self):
        order = make_order()
        order.add_item(make_item("D-01", price=500.0, qty=2))
        order.add_item(make_item("D-02", price=300.0, qty=1))
        assert order.calculate_total() == Money(1300.0, "RUB")
 
    def test_cancel_paid_order_raises(self):
        order = self._ready_order()
        order.initiate_payment("PAY-001", "CARD")
        order.complete_payment("txn-abc123")
        with pytest.raises(InvalidOrderStateException, match="оплаченный"):
            order.cancel()