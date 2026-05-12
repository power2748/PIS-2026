import pytest
from domain.aggregates.order import Order
from domain.entities.order_item import OrderItem
from domain.entities.kitchen_ticket import KitchenTicket, TicketItem
from domain.entities.payment import Payment
from domain.value_objects.money import Money
from domain.value_objects.order_status import OrderStatus
from domain.value_objects.dish_station import DishStation
from domain.value_objects.table_number import TableNumber
from domain.exceptions.domain_exception import (
    DomainException, InvalidOrderStateException,
)
from domain.events.order_events import (
    OrderCreatedEvent, OrderSentToKitchenEvent,
    PaymentInitiatedEvent, PaymentCompletedEvent, OrderCancelledEvent,
)
 
 
# ══════════════════════════════════════════════════════════════════
# VALUE OBJECTS
# ══════════════════════════════════════════════════════════════════
 
class TestMoney:
 
    def test_create_valid(self):
        m = Money(1500.0, "RUB")
        assert m.amount == 1500.0
        assert m.currency == "RUB"
 
    def test_negative_amount_raises(self):
        with pytest.raises(ValueError, match="отрицательной"):
            Money(-1.0)
 
    def test_invalid_currency_raises(self):
        with pytest.raises(ValueError, match="3 символа"):
            Money(100.0, "RUBLE")
 
    def test_immutable(self):
        m = Money(100.0)
        with pytest.raises(Exception):
            m.amount = 200.0  # FrozenInstanceError
 
    def test_add_same_currency(self):
        result = Money(1000.0, "RUB").add(Money(500.0, "RUB"))
        assert result == Money(1500.0, "RUB")
 
    def test_add_different_currency_raises(self):
        with pytest.raises(ValueError, match="разных валютах"):
            Money(100.0, "RUB").add(Money(100.0, "USD"))
 
    def test_multiply(self):
        assert Money(300.0).multiply(3) == Money(900.0)
 
    def test_equality_by_value(self):
        assert Money(100.0, "RUB") == Money(100.0, "RUB")
        assert Money(100.0, "RUB") != Money(200.0, "RUB")
 
 
class TestOrderStatus:
 
    def test_valid_statuses(self):
        for s in ("NEW", "IN_PROGRESS", "READY", "AWAITING_PAYMENT", "PAID", "CANCELLED"):
            assert OrderStatus(s).value == s
 
    def test_invalid_status_raises(self):
        with pytest.raises(ValueError, match="Недопустимый статус"):
            OrderStatus("COOKING")
 
    def test_valid_transition_new_to_in_progress(self):
        result = OrderStatus("NEW").transition_to(OrderStatus("IN_PROGRESS"))
        assert result.value == "IN_PROGRESS"
 
    def test_valid_transition_ready_to_paid(self):
        s = OrderStatus("READY").transition_to(OrderStatus("AWAITING_PAYMENT"))
        assert s.value == "AWAITING_PAYMENT"
 
    def test_invalid_transition_new_to_paid(self):
        with pytest.raises(ValueError, match="Недопустимый переход"):
            OrderStatus("NEW").transition_to(OrderStatus("PAID"))
 
    def test_paid_is_terminal(self):
        assert not OrderStatus("PAID").can_transition_to(OrderStatus("CANCELLED"))
 
    def test_immutable(self):
        s = OrderStatus("NEW")
        with pytest.raises(Exception):
            s.value = "PAID"
 
 
class TestTableNumber:
 
    def test_valid_range(self):
        assert TableNumber(1).value == 1
        assert TableNumber(999).value == 999
 
    def test_zero_raises(self):
        with pytest.raises(ValueError):
            TableNumber(0)
 
    def test_over_max_raises(self):
        with pytest.raises(ValueError):
            TableNumber(1000)
 
    def test_equality(self):
        assert TableNumber(12) == TableNumber(12)
        assert TableNumber(12) != TableNumber(13)
 
 
class TestDishStation:
 
    def test_valid_stations(self):
        for s in ("GRILL", "PASTA", "DESSERT", "BAR", "COLD"):
            assert DishStation(s).value == s
 
    def test_invalid_station_raises(self):
        with pytest.raises(ValueError, match="Неизвестная станция"):
            DishStation("OVEN")
 
    def test_immutable(self):
        d = DishStation("GRILL")
        with pytest.raises(Exception):
            d.value = "BAR"
 
 
# ══════════════════════════════════════════════════════════════════
# ENTITIES
# ══════════════════════════════════════════════════════════════════
 
class TestKitchenTicket:
 
    def _make_ticket(self, ticket_id="KT-001") -> KitchenTicket:
        items = [TicketItem("D-01", "Стейк", 1, "GRILL")]
        return KitchenTicket(ticket_id=ticket_id, order_id="ORD-001", items=items)
 
    def test_create_valid(self):
        ticket = self._make_ticket()
        assert ticket.ticket_id == "KT-001"
        assert ticket.status == "PENDING"
 
    def test_create_without_items_raises(self):
        with pytest.raises(ValueError, match="без позиций"):
            KitchenTicket("KT-X", "ORD-X", [])
 
    def test_start_cooking(self):
        ticket = self._make_ticket()
        ticket.start_cooking()
        assert ticket.status == "IN_PROGRESS"
 
    def test_start_cooking_twice_raises(self):
        ticket = self._make_ticket()
        ticket.start_cooking()
        with pytest.raises(ValueError):
            ticket.start_cooking()
 
    def test_complete_with_undone_items_raises(self):
        ticket = self._make_ticket()
        with pytest.raises(ValueError, match="не готовы"):
            ticket.complete()
 
    def test_complete_after_all_done(self):
        ticket = self._make_ticket()
        ticket.mark_item_done("D-01")
        ticket.complete()
        assert ticket.status == "DONE"
 
    def test_cancel_done_ticket_raises(self):
        ticket = self._make_ticket()
        ticket.mark_item_done("D-01")
        ticket.complete()
        with pytest.raises(ValueError, match="выполненный"):
            ticket.cancel()
 
    def test_equality_by_id(self):
        t1 = self._make_ticket("KT-001")
        t2 = self._make_ticket("KT-001")
        assert t1 == t2
 
 
class TestPayment:
 
    def _make_payment(self) -> Payment:
        return Payment("PAY-001", "ORD-001", Money(5000.0), "CARD")
 
    def test_create_valid(self):
        p = self._make_payment()
        assert p.status == "PENDING"
        assert p.retry_count == 0
 
    def test_zero_amount_raises(self):
        with pytest.raises(ValueError, match="> 0"):
            Payment("PAY-X", "ORD-X", Money(0.0), "CARD")
 
    def test_invalid_method_raises(self):
        with pytest.raises(ValueError, match="метод оплаты"):
            Payment("PAY-X", "ORD-X", Money(100.0), "BITCOIN")
 
    def test_mark_retry_pending(self):
        p = self._make_payment()
        p.mark_retry_pending()
        assert p.status == "RETRY_PENDING"
        assert p.retry_count == 1
 
    def test_max_retries_raises(self):
        p = self._make_payment()
        for _ in range(Payment.MAX_RETRIES):
            p.mark_retry_pending()
        with pytest.raises(ValueError, match="попыток"):
            p.mark_retry_pending()
 
    def test_complete_success(self):
        p = self._make_payment()
        p.complete("txn-abc123")
        assert p.status == "COMPLETED"
 
    def test_complete_already_completed_raises(self):
        p = self._make_payment()
        p.complete("txn-1")
        with pytest.raises(ValueError):
            p.complete("txn-2")
 
    def test_fail_completed_raises(self):
        p = self._make_payment()
        p.complete("txn-1")
        with pytest.raises(ValueError, match="завершённый"):
            p.fail()
 
 
# ══════════════════════════════════════════════════════════════════
# AGGREGATE ROOT: ORDER
# ══════════════════════════════════════════════════════════════════
 
def make_order(order_id="ORD-001", table=12, guests=2) -> Order:
    order = Order(order_id=order_id, table_number=TableNumber(table), guests=guests)
    order.pull_events()  # очищаем OrderCreatedEvent
    return order
 
def make_item(dish_id="D-01", price=500.0, qty=1) -> OrderItem:
    return OrderItem(
        item_id=f"item-{dish_id}",
        dish_id=dish_id,
        dish_name="Тестовое блюдо",
        quantity=qty,
        price=Money(price),
        station=DishStation("GRILL"),
    )
 
 
class TestOrderCreation:
 
    def test_initial_status_new(self):
        order = Order("ORD-X", TableNumber(1), guests=1)
        assert order.status.value == "NEW"
 
    def test_order_created_event_registered(self):
        order = Order("ORD-X", TableNumber(1), guests=1)
        events = order.pull_events()
        assert len(events) == 1
        assert isinstance(events[0], OrderCreatedEvent)
        assert events[0].order_id == "ORD-X"
 
    def test_invalid_guests_raises(self):
        with pytest.raises(ValueError, match="гостей"):
            Order("ORD-X", TableNumber(1), guests=0)
 
    def test_pull_events_clears_list(self):
        order = Order("ORD-X", TableNumber(1), guests=1)
        order.pull_events()
        assert order.pull_events() == []
 
 
class TestOrderAddItem:
 
    def test_add_item_success(self):
        order = make_order()
        order.add_item(make_item())
        assert len(order.items) == 1
 
    def test_add_multiple_items(self):
        order = make_order()
        order.add_item(make_item("D-01"))
        order.add_item(make_item("D-02"))
        assert len(order.items) == 2
 
    def test_cannot_add_item_after_send_to_kitchen(self):
        order = make_order()
        order.add_item(make_item())
        order.send_to_kitchen("KT-001")
        with pytest.raises(InvalidOrderStateException):
            order.add_item(make_item("D-02"))
 
    def test_items_returns_copy(self):
        order = make_order()
        order.add_item(make_item())
        items = order.items
        items.clear()
        assert len(order.items) == 1  # оригинал не изменился
 
 
class TestOrderSendToKitchen:
 
    def test_send_success(self):
        order = make_order()
        order.add_item(make_item())
        ticket = order.send_to_kitchen("KT-001")
        assert order.status.value == "IN_PROGRESS"
        assert ticket.ticket_id == "KT-001"
 
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
 
    def test_version_increments(self):
        order = make_order()
        v = order.version
        order.add_item(make_item())
        order.send_to_kitchen("KT-001")
        assert order.version == v + 1
 
    def test_event_registered(self):
        order = make_order()
        order.add_item(make_item())
        order.send_to_kitchen("KT-001")
        events = order.pull_events()
        assert any(isinstance(e, OrderSentToKitchenEvent) for e in events)
 
 
class TestOrderPayment:
 
    def _ready_order(self) -> Order:
        order = make_order()
        order.add_item(make_item(price=1500.0, qty=2))
        order.send_to_kitchen("KT-001")
        order.mark_ready()
        order.pull_events()
        return order
 
    def test_calculate_total(self):
        order = make_order()
        order.add_item(make_item("D-01", price=1500.0, qty=2))
        order.add_item(make_item("D-02", price=800.0, qty=1))
        assert order.calculate_total() == Money(3800.0)
 
    def test_initiate_payment_success(self):
        order = self._ready_order()
        payment = order.initiate_payment("PAY-001", "CARD")
        assert payment.payment_id == "PAY-001"
        assert order.status.value == "AWAITING_PAYMENT"
 
    def test_cannot_pay_not_ready_order(self):
        order = make_order()
        order.add_item(make_item())
        order.send_to_kitchen("KT-001")  # IN_PROGRESS, не READY
        with pytest.raises(InvalidOrderStateException):
            order.initiate_payment("PAY-001", "CARD")
 
    def test_complete_payment(self):
        order = self._ready_order()
        order.initiate_payment("PAY-001", "CARD")
        order.complete_payment("txn-xyz")
        assert order.status.value == "PAID"
 
    def test_complete_payment_event(self):
        order = self._ready_order()
        order.initiate_payment("PAY-001", "CARD")
        order.complete_payment("txn-xyz")
        events = order.pull_events()
        assert any(isinstance(e, PaymentCompletedEvent) for e in events)
 
    def test_cancel_paid_raises(self):
        order = self._ready_order()
        order.initiate_payment("PAY-001", "CARD")
        order.complete_payment("txn-xyz")
        with pytest.raises(InvalidOrderStateException, match="оплаченный"):
            order.cancel()
 
    def test_cancel_event_registered(self):
        order = make_order()
        order.add_item(make_item())
        order.cancel(reason="Гость передумал")
        events = order.pull_events()
        assert any(isinstance(e, OrderCancelledEvent) for e in events)