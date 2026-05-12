import uuid
from datetime import datetime
 
from application.command.send_to_kitchen_command import SendToKitchenCommand
from application.port.out.order_repository import IOrderRepository
from application.port.out.event_publisher import IEventPublisher
from domain.exceptions.domain_exception import OrderNotFoundException
 
 
class SendToKitchenHandler:
    """
    Command Handler: отправка заказа на кухню.
    Загружает Order, вызывает send_to_kitchen(), сохраняет, публикует события.
    """
 
    def __init__(self, order_repository: IOrderRepository, event_publisher: IEventPublisher):
        self._repo = order_repository
        self._publisher = event_publisher
 
    def handle(self, command: SendToKitchenCommand) -> str:
        # ── Шаг 1: Загрузка агрегата ──────────────────────────────
        order = self._repo.find_by_id(command.order_id)
        if order is None:
            raise OrderNotFoundException(f"Заказ не найден: {command.order_id}")
 
        # ── Шаг 2: Вызов доменного метода (инварианты внутри) ─────
        ticket_id = self._generate_ticket_id()
        ticket = order.send_to_kitchen(ticket_id)   # InvalidOrderStateException если не NEW
 
        # ── Шаг 3: Сохранение обновлённого агрегата ───────────────
        self._repo.save(order)
 
        # ── Шаг 4: Публикация событий ─────────────────────────────
        for event in order.pull_events():
            self._publisher.publish(event)
 
        return ticket.ticket_id
 
    @staticmethod
    def _generate_ticket_id() -> str:
        now = datetime.now()
        seq = str(uuid.uuid4().int)[:3].zfill(3)
        return f"KT-{now.year}-{seq}"