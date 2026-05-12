import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
 
from cqrs.read_model.orm_models import ReadBase, OrderViewModel, TableViewModel, KitchenDashboardViewModel, RevenueViewModel
from cqrs.projection.order_view_projection import OrderViewProjection
from cqrs.projection.table_view_projection import TableViewProjection
from cqrs.projection.kitchen_dashboard_projection import KitchenDashboardProjection
from cqrs.projection.revenue_projection import RevenueProjection
from domain.events.order_events import (
    OrderCreatedEvent, OrderSentToKitchenEvent,
    PaymentInitiatedEvent, PaymentCompletedEvent, OrderCancelledEvent,
)
from domain.aggregates.order import Order
from domain.entities.order_item import OrderItem
from domain.value_objects.money import Money
from domain.value_objects.dish_station import DishStation
from domain.value_objects.table_number import TableNumber
 
 
# ── Фикстуры ──────────────────────────────────────────────────────
 
@pytest.fixture(scope="session")
def engine():
    eng = create_engine("sqlite:///:memory:")
    ReadBase.metadata.create_all(eng)
    return eng
 
@pytest.fixture
def session(engine):
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.rollback()
    s.close()
 
def make_mock_write_repo(order_id="ORD-001", table=12):
    repo = MagicMock()
    order = MagicMock(spec=Order)
    order.order_id = order_id
    order.table_number = TableNumber(table)
    order._guests = 2
    item = MagicMock(spec=OrderItem)
    item.dish_id   = "D-01"
    item.dish_name = "Стейк"
    item.quantity  = 1
    item.price     = Money(1500.0)
    item.station   = DishStation("GRILL")
    item.comment   = None
    order.items = [item]
    order.calculate_total.return_value = Money(1500.0)
    repo.find_by_id.return_value = order
    return repo
 
def now():
    return datetime.now()
 
 
# ── OrderViewProjection ────────────────────────────────────────────
 
class TestOrderViewProjection:
 
    def test_on_order_created_inserts_view(self, session):
        repo = make_mock_write_repo("ORD-P-001", 12)
        proj = OrderViewProjection(session, repo)
 
        proj.on_order_created(OrderCreatedEvent("ORD-P-001", 12, 2, now()))
 
        view = session.get(OrderViewModel, "ORD-P-001")
        assert view is not None
        assert view.status == "NEW"
        assert view.table_id == 12
        assert view.items_count == 1
        assert view.total_amount == 1500.0
 
    def test_on_order_created_idempotent(self, session):
        repo = make_mock_write_repo("ORD-P-002", 13)
        proj = OrderViewProjection(session, repo)
        event = OrderCreatedEvent("ORD-P-002", 13, 2, now())
 
        proj.on_order_created(event)
        proj.on_order_created(event)  # повторное применение
 
        views = session.query(OrderViewModel).filter_by(order_id="ORD-P-002").all()
        assert len(views) == 1  # не создал дубликат
 
    def test_on_sent_to_kitchen_updates_status(self, session):
        repo = make_mock_write_repo("ORD-P-003", 14)
        proj = OrderViewProjection(session, repo)
        proj.on_order_created(OrderCreatedEvent("ORD-P-003", 14, 2, now()))
 
        proj.on_order_sent_to_kitchen(
            OrderSentToKitchenEvent("ORD-P-003", "KT-001", 14, now())
        )
 
        view = session.get(OrderViewModel, "ORD-P-003")
        assert view.status == "IN_PROGRESS"
        assert view.ticket_id == "KT-001"
        assert view.eta_minutes is not None
        assert view.version == 2
 
    def test_on_payment_initiated_updates_status(self, session):
        repo = make_mock_write_repo("ORD-P-004", 15)
        proj = OrderViewProjection(session, repo)
        proj.on_order_created(OrderCreatedEvent("ORD-P-004", 15, 2, now()))
 
        proj.on_payment_initiated(
            PaymentInitiatedEvent("ORD-P-004", "PAY-001", 1500.0, "RUB", now())
        )
 
        view = session.get(OrderViewModel, "ORD-P-004")
        assert view.status == "AWAITING_PAYMENT"
        assert view.payment_id == "PAY-001"
 
    def test_on_payment_completed_sets_paid(self, session):
        repo = make_mock_write_repo("ORD-P-005", 16)
        proj = OrderViewProjection(session, repo)
        proj.on_order_created(OrderCreatedEvent("ORD-P-005", 16, 2, now()))
        proj.on_payment_initiated(
            PaymentInitiatedEvent("ORD-P-005", "PAY-002", 1500.0, "RUB", now())
        )
        proj.on_payment_completed(
            PaymentCompletedEvent("ORD-P-005", "PAY-002", "txn-xyz", 16, now())
        )
 
        view = session.get(OrderViewModel, "ORD-P-005")
        assert view.status == "PAID"
        assert view.transaction_id == "txn-xyz"
 
    def test_on_order_cancelled_sets_cancelled(self, session):
        repo = make_mock_write_repo("ORD-P-006", 17)
        proj = OrderViewProjection(session, repo)
        proj.on_order_created(OrderCreatedEvent("ORD-P-006", 17, 2, now()))
        proj.on_order_cancelled(OrderCancelledEvent("ORD-P-006", "Гость ушёл", 17, now()))
 
        view = session.get(OrderViewModel, "ORD-P-006")
        assert view.status == "CANCELLED"
 
 
# ── TableViewProjection ────────────────────────────────────────────
 
class TestTableViewProjection:
 
    def test_on_order_created_occupies_table(self, session):
        proj = TableViewProjection(session)
        proj.on_order_created(OrderCreatedEvent("ORD-T-001", 20, 3, now()))
 
        view = session.get(TableViewModel, 20)
        assert view.status == "OCCUPIED"
        assert view.active_order_id == "ORD-T-001"
        assert view.guests == 3
 
    def test_on_payment_completed_frees_table(self, session):
        proj = TableViewProjection(session)
        proj.on_order_created(OrderCreatedEvent("ORD-T-002", 21, 2, now()))
        proj.on_payment_completed(
            PaymentCompletedEvent("ORD-T-002", "PAY-T", "txn-t", 21, now())
        )
 
        view = session.get(TableViewModel, 21)
        assert view.status == "FREE"
        assert view.active_order_id is None
 
    def test_on_order_cancelled_frees_table(self, session):
        proj = TableViewProjection(session)
        proj.on_order_created(OrderCreatedEvent("ORD-T-003", 22, 1, now()))
        proj.on_order_cancelled(OrderCancelledEvent("ORD-T-003", "Отмена", 22, now()))
 
        view = session.get(TableViewModel, 22)
        assert view.status == "FREE"
 
 
# ── KitchenDashboardProjection ─────────────────────────────────────
 
class TestKitchenDashboardProjection:
 
    def test_on_sent_creates_rows_per_station(self, session):
        repo = make_mock_write_repo("ORD-K-001", 30)
        proj = KitchenDashboardProjection(session, repo)
 
        proj.on_order_sent_to_kitchen(
            OrderSentToKitchenEvent("ORD-K-001", "KT-K-001", 30, now())
        )
 
        rows = session.query(KitchenDashboardViewModel).filter_by(
            ticket_id="KT-K-001"
        ).all()
        assert len(rows) >= 1
        assert rows[0].station == "GRILL"
 
    def test_on_payment_completed_removes_ticket(self, session):
        repo = make_mock_write_repo("ORD-K-002", 31)
        proj = KitchenDashboardProjection(session, repo)
        proj.on_order_sent_to_kitchen(
            OrderSentToKitchenEvent("ORD-K-002", "KT-K-002", 31, now())
        )
        proj.on_payment_completed(
            PaymentCompletedEvent("ORD-K-002", "PAY-K", "txn-k", 31, now())
        )
 
        rows = session.query(KitchenDashboardViewModel).filter_by(
            order_id="ORD-K-002"
        ).all()
        assert len(rows) == 0
 
 
# ── RevenueProjection ──────────────────────────────────────────────
 
class TestRevenueProjection:
 
    def test_first_payment_creates_row(self, session):
        proj = RevenueProjection(session)
        event = PaymentCompletedEvent("ORD-R-001", "PAY-R-001", "txn-r1", 5,
                                      datetime(2024, 11, 8, 19, 30))
        event_with_amount = MagicMock(**{
            "order_id": "ORD-R-001", "payment_id": "PAY-R-001",
            "transaction_id": "txn-r1", "table_number": 5,
            "occurred_at": datetime(2024, 11, 8, 19, 30),
            "amount": 2300.0, "currency": "RUB",
        })
        proj.on_payment_completed(event_with_amount)
 
        view = session.query(RevenueViewModel).filter_by(
            date="2024-11-08", hour=19
        ).first()
        assert view is not None
        assert view.orders_count == 1
        assert view.total_amount == 2300.0
 
    def test_second_payment_increments(self, session):
        proj = RevenueProjection(session)
        for i in range(2):
            event = MagicMock(**{
                "order_id": f"ORD-R-00{i+2}", "payment_id": f"PAY-R-{i}",
                "transaction_id": f"txn-{i}", "table_number": i,
                "occurred_at": datetime(2024, 11, 8, 20, 0),
                "amount": 1000.0, "currency": "RUB",
            })
            proj.on_payment_completed(event)
 
        view = session.query(RevenueViewModel).filter_by(
            date="2024-11-08", hour=20
        ).first()
        assert view.orders_count == 2
        assert view.total_amount == 2000.0
        assert view.avg_order_amount == 1000.0