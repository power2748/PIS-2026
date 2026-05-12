import pytest
from domain.value_objects.money import Money
from domain.value_objects.order_status import OrderStatus
from domain.value_objects.dish_station import DishStation
from domain.value_objects.table_number import TableNumber
 
 
class TestMoney:
    def test_valid_money_creation(self):
        m = Money(amount=100.0, currency="RUB")
        assert m.amount == 100.0
        assert m.currency == "RUB"
 
    def test_money_is_immutable(self):
        m = Money(amount=100.0)
        with pytest.raises(Exception):  # frozen=True → FrozenInstanceError
            m.amount = 200.0
 
    def test_negative_amount_raises(self):
        with pytest.raises(ValueError, match="отрицательной"):
            Money(amount=-1.0)
 
    def test_invalid_currency_raises(self):
        with pytest.raises(ValueError, match="3 символа"):
            Money(amount=100.0, currency="RUBLES")
 
    def test_add_same_currency(self):
        a = Money(500.0, "RUB")
        b = Money(250.0, "RUB")
        assert a.add(b) == Money(750.0, "RUB")
 
    def test_add_different_currency_raises(self):
        with pytest.raises(ValueError, match="разных валютах"):
            Money(100.0, "RUB").add(Money(100.0, "USD"))
 
    def test_multiply(self):
        m = Money(200.0, "RUB")
        assert m.multiply(3) == Money(600.0, "RUB")
 
    def test_equality_by_value(self):
        assert Money(100.0, "RUB") == Money(100.0, "RUB")
        assert Money(100.0, "RUB") != Money(200.0, "RUB")
 
 
class TestOrderStatus:
    def test_valid_status(self):
        s = OrderStatus("NEW")
        assert s.value == "NEW"
 
    def test_invalid_status_raises(self):
        with pytest.raises(ValueError, match="Недопустимый статус"):
            OrderStatus("COOKING")
 
    def test_valid_transition(self):
        s = OrderStatus("NEW")
        next_s = s.transition_to(OrderStatus("IN_PROGRESS"))
        assert next_s.value == "IN_PROGRESS"
 
    def test_invalid_transition_raises(self):
        with pytest.raises(ValueError, match="Недопустимый переход"):
            OrderStatus("NEW").transition_to(OrderStatus("PAID"))
 
    def test_paid_has_no_transitions(self):
        s = OrderStatus("PAID")
        assert not s.can_transition_to(OrderStatus("CANCELLED"))
 
 
class TestTableNumber:
    def test_valid_table(self):
        t = TableNumber(12)
        assert t.value == 12
 
    def test_zero_raises(self):
        with pytest.raises(ValueError):
            TableNumber(0)
 
    def test_over_max_raises(self):
        with pytest.raises(ValueError):
            TableNumber(1000)
 
    def test_immutable(self):
        t = TableNumber(5)
        with pytest.raises(Exception):
            t.value = 10