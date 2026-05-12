import uuid
from datetime import datetime
 
from application.command.create_order_command import CreateOrderCommand
from application.port.out.order_repository import IOrderRepository
from application.port.out.menu_inventory_port import IMenuInventoryPort
from application.port.out.event_publisher import IEventPublisher
from domain.aggregates.order import Order
from domain.entities.order_item import OrderItem
from domain.value_objects.money import Money
from domain.value_objects.dish_station import DishStation
from domain.value_objects.table_number import TableNumber
from domain.exceptions.domain_exception import DishUnavailableException, TableOccupiedException
 
 
class CreateOrderHandler:
    """
    Command Handler: создание нового заказа.
    Оркестрирует: валидация → домен → репозиторий → события.
    Один handler — одна команда (SRP).
    """
 
    def __init__(
        self,
        order_repository: IOrderRepository,
        menu_inventory: IMenuInventoryPort,
        event_publisher: IEventPublisher,
    ):
        # Зависимости инжектируются через конструктор (DIP)
        self._repo = order_repository
        self._menu = menu_inventory
        self._publisher = event_publisher
 
    def handle(self, command: CreateOrderCommand) -> str:
        """
        Обрабатывает CreateOrderCommand.
        Возвращает order_id созданного заказа.
        """
 
        # ── Шаг 1: Идемпотентность ────────────────────────────────
        if command.idempotency_key:
            existing = self._repo.find_by_idempotency_key(command.idempotency_key)
            if existing:
                return existing.order_id  # повторный запрос — тот же ответ
 
        # ── Шаг 2: Валидация на уровне приложения ─────────────────
        # (примитивы уже проверены в команде; здесь — бизнес-контекст)
 
        # Проверяем, что столик свободен
        active_order = self._repo.find_by_table_id(command.table_id)
        if active_order is not None:
            raise TableOccupiedException(
                f"Столик №{command.table_id} уже занят заказом {active_order.order_id}"
            )
 
        # Проверяем доступность блюд (стоп-лист + остатки ингредиентов)
        dish_ids = [item.dish_id for item in command.items]
        availability = self._menu.check_availability(dish_ids)
        unavailable = [d for d, ok in availability.items() if not ok]
        if unavailable:
            raise DishUnavailableException(
                f"Блюда недоступны (стоп-лист): {unavailable}"
            )
 
        # ── Шаг 3: Создание агрегата (доменная логика) ────────────
        order_id = self._generate_order_id()
        order = Order(
            order_id=order_id,
            table_number=TableNumber(command.table_id),
            guests=command.guests,
        )
 
        for item_data in command.items:
            item = OrderItem(
                item_id=str(uuid.uuid4()),
                dish_id=item_data.dish_id,
                dish_name=item_data.dish_name,
                quantity=item_data.quantity,
                price=Money(item_data.price, "RUB"),
                station=DishStation(item_data.station),
                comment=item_data.comment,
            )
            order.add_item(item)  # инварианты проверяет агрегат
 
        if command.comment:
            order.set_comment(command.comment)
 
        # ── Шаг 4: Резервация ингредиентов ────────────────────────
        self._menu.reserve_ingredients(order_id, command.items)
 
        # ── Шаг 5: Сохранение (BEGIN → COMMIT внутри репозитория) ─
        self._repo.save(order, idempotency_key=command.idempotency_key)
 
        # ── Шаг 6: Публикация доменных событий ────────────────────
        # События извлекаются из агрегата ПОСЛЕ коммита транзакции
        events = order.pull_events()
        for event in events:
            self._publisher.publish(event)
 
        return order_id
 
    @staticmethod
    def _generate_order_id() -> str:
        now = datetime.now()
        seq = str(uuid.uuid4().int)[:4].zfill(4)
        return f"ORD-{now.year}-{seq}"