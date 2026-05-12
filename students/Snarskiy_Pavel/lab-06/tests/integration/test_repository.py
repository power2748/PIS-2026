import pytest
from testcontainers.postgres import PostgresContainer
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
 
from infrastructure.db.models import Base
from infrastructure.adapter.out.postgres_order_repository import PostgresOrderRepository
from domain.aggregates.order import Order
from domain.entities.order_item import OrderItem
from domain.value_objects.money import Money
from domain.value_objects.dish_station import DishStation
from domain.value_objects.table_number import TableNumber
from domain.value_objects.order_status import OrderStatus
 
 
# ── Фикстуры ──────────────────────────────────────────────────────
 
@pytest.fixture(scope="session")
def pg():
    with PostgresContainer("postgres:15-alpine") as container:
        yield container
 
@pytest.fixture(scope="session")
def engine(pg):
    eng = create_engine(pg.get_connection_url())
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
 
@pytest.fixture
def session(engine):
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.rollback()
    s.close()
 
@pytest.fixture
def repo(session):
    return PostgresOrderRepository(session)
 
 
def make_order(order_id="ORD-IT-001", table=5) -> Order:
    order = Order(order_id=order_id, table_number=TableNumber(table), guests=2)
    order.pull_events()
    item = OrderItem(
        item_id="item-001", dish_id="D-01", dish_name="Стейк Рибай",
        quantity=1, price=Money(1500.0), station=DishStation("GRILL"),
    )
    order.add_item(item)
    return order
 
 
# ── Тесты ─────────────────────────────────────────────────────────
 
class TestPostgresOrderRepository:
 
    def test_save_and_find_by_id(self, repo, session):
        """Сохранение агрегата → чтение из PostgreSQL → данные совпадают"""
        order = make_order("ORD-IT-001", table=5)
        repo.save(order)
        session.commit()
 
        restored = repo.find_by_id("ORD-IT-001")
 
        assert restored is not None
        assert restored.order_id == "ORD-IT-001"
        assert restored.table_number.value == 5
        assert restored.status.value == "NEW"
        assert restored.guests == 2
        assert len(restored.items) == 1
        assert restored.items[0].dish_name == "Стейк Рибай"
        assert restored.items[0].price == Money(1500.0)
        assert restored.items[0].station == DishStation("GRILL")
 
    def test_find_by_id_not_found_returns_none(self, repo):
        result = repo.find_by_id("ORD-NOT-EXIST")
        assert result is None
 
    def test_find_by_table_id_active_order(self, repo, session):
        order = make_order("ORD-IT-002", table=6)
        repo.save(order)
        session.commit()
 
        found = repo.find_by_table_id(6)
        assert found is not None
        assert found.order_id == "ORD-IT-002"
 
    def test_find_by_table_id_returns_none_for_paid(self, repo, session):
        order = make_order("ORD-IT-003", table=7)
        repo.save(order)
        session.execute(
            text("UPDATE orders SET status='PAID' WHERE order_id='ORD-IT-003'")
        )
        session.commit()
 
        result = repo.find_by_table_id(7)
        assert result is None
 
    def test_save_updates_status_after_send_to_kitchen(self, repo, session):
        """Обновление агрегата: статус меняется после send_to_kitchen"""
        order = make_order("ORD-IT-004", table=8)
        repo.save(order)
        session.commit()
 
        loaded = repo.find_by_id("ORD-IT-004")
        loaded.send_to_kitchen("KT-IT-001")
        repo.save(loaded)
        session.commit()
 
        updated = repo.find_by_id("ORD-IT-004")
        assert updated.status.value == "IN_PROGRESS"
        assert updated.kitchen_ticket is not None
        assert updated.kitchen_ticket.ticket_id == "KT-IT-001"
        assert updated.version == 2
 
    def test_idempotency_key_stored_and_retrieved(self, repo, session):
        order = make_order("ORD-IT-005", table=9)
        repo.save(order, idempotency_key="idem-key-abc")
        session.commit()
 
        found = repo.find_by_idempotency_key("idem-key-abc")
        assert found is not None
        assert found.order_id == "ORD-IT-005"
 
    def test_idempotency_key_not_found_returns_none(self, repo):
        result = repo.find_by_idempotency_key("nonexistent-key")
        assert result is None
 
    def test_find_by_statuses_pagination(self, repo, session):
        for i in range(4):
            o = make_order(f"ORD-PAGE-{i:02}", table=20 + i)
            repo.save(o)
        session.commit()
 
        page1 = repo.find_by_statuses({"NEW"}, offset=0, limit=2)
        page2 = repo.find_by_statuses({"NEW"}, offset=2, limit=2)
 
        assert len(page1) <= 2
        assert len(page2) <= 2
        ids1 = {o.order_id for o in page1}
        ids2 = {o.order_id for o in page2}
        assert ids1.isdisjoint(ids2)  # страницы не пересекаются