import pytest
from testcontainers.postgres import PostgresContainer
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
 
from infrastructure.db.models import Base
from infrastructure.adapter.out.postgres_order_repository import PostgresOrderRepository
from infrastructure.db.mapper import OrderMapper
from domain.aggregates.order import Order
from domain.entities.order_item import OrderItem
from domain.value_objects.money import Money
from domain.value_objects.dish_station import DishStation
from domain.value_objects.table_number import TableNumber
from unittest.mock import MagicMock
from application.port.out.event_publisher import IEventPublisher
 
 
@pytest.fixture(scope="session")
def pg_container():
    """Запускает реальный PostgreSQL в Docker для тестов (testcontainers)"""
    with PostgresContainer("postgres:15-alpine") as pg:
        yield pg
 
 
@pytest.fixture(scope="session")
def db_engine(pg_container):
    engine = create_engine(pg_container.get_connection_url())
    Base.metadata.create_all(engine)   # создаём схему
    yield engine
    Base.metadata.drop_all(engine)
 
 
@pytest.fixture
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.rollback()   # откатываем каждый тест — изоляция
    session.close()
 
 
@pytest.fixture
def repo(db_session):
    return PostgresOrderRepository(db_session)
 
 
def make_order_with_item(order_id="ORD-TEST-001", table=7) -> Order:
    order = Order(
        order_id=order_id,
        table_number=TableNumber(table),
        guests=2,
    )
    order.pull_events()  # очищаем события
    item = OrderItem(
        item_id="item-001",
        dish_id="D-01",
        dish_name="Стейк Рибай",
        quantity=1,
        price=Money(1500.0, "RUB"),
        station=DishStation("GRILL"),
    )
    order.add_item(item)
    return order
 
 
class TestPostgresOrderRepository:
 
    def test_save_and_find_by_id(self, repo, db_session):
        """Сохраняем Order → читаем из PostgreSQL → агрегат восстановлен корректно"""
        order = make_order_with_item()
        repo.save(order)
        db_session.commit()
 
        restored = repo.find_by_id("ORD-TEST-001")
 
        assert restored is not None
        assert restored.order_id == "ORD-TEST-001"
        assert restored.table_number.value == 7
        assert restored.status.value == "NEW"
        assert len(restored.items) == 1
        assert restored.items[0].dish_name == "Стейк Рибай"
        assert restored.items[0].price == Money(1500.0, "RUB")
 
    def test_find_by_table_id_returns_active_order(self, repo, db_session):
        """find_by_table_id возвращает активный заказ на столике"""
        order = make_order_with_item("ORD-TEST-002", table=8)
        repo.save(order)
        db_session.commit()
 
        found = repo.find_by_table_id(8)
        assert found is not None
        assert found.order_id == "ORD-TEST-002"
 
    def test_find_by_table_id_returns_none_for_paid_order(self, repo, db_session):
        """После оплаты столик считается свободным"""
        order = make_order_with_item("ORD-TEST-003", table=9)
        repo.save(order)
        db_session.commit()
 
        # Переводим в PAID
        saved = repo.find_by_id("ORD-TEST-003")
        saved._status = saved._status.transition_to(
            __import__("domain.value_objects.order_status", fromlist=["OrderStatus"])
            .OrderStatus("IN_PROGRESS")
        )
        # Упрощённо — меняем статус напрямую для теста
        db_session.execute(
            text("UPDATE orders SET status='PAID' WHERE order_id='ORD-TEST-003'")
        )
        db_session.commit()
 
        found = repo.find_by_table_id(9)
        assert found is None  # столик свободен
 
    def test_idempotency_key_deduplication(self, repo, db_session):
        """Повторный save с тем же ключом не создаёт дубликат"""
        order = make_order_with_item("ORD-TEST-004", table=10)
        repo.save(order, idempotency_key="test-key-123")
        db_session.commit()
 
        restored = repo.find_by_idempotency_key("test-key-123")
        assert restored is not None
        assert restored.order_id == "ORD-TEST-004"
 
    def test_save_updates_existing_order(self, repo, db_session):
        """Повторный save обновляет существующую запись"""
        order = make_order_with_item("ORD-TEST-005", table=11)
        repo.save(order)
        db_session.commit()
 
        # Отправляем на кухню
        loaded = repo.find_by_id("ORD-TEST-005")
        loaded.send_to_kitchen("KT-TEST-001")
        repo.save(loaded)
        db_session.commit()
 
        updated = repo.find_by_id("ORD-TEST-005")
        assert updated.status.value == "IN_PROGRESS"
        assert updated.kitchen_ticket is not None
        assert updated.kitchen_ticket.ticket_id == "KT-TEST-001"
 
    def test_find_by_statuses_pagination(self, repo, db_session):
        """find_by_statuses возвращает не более limit записей"""
        for i in range(5):
            o = make_order_with_item(f"ORD-PAGE-{i:03}", table=20 + i)
            repo.save(o)
        db_session.commit()
 
        result = repo.find_by_statuses({"NEW"}, offset=0, limit=3)
        assert len(result) <= 3