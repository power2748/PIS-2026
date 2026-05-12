import uuid
from datetime import datetime
 
from application.command.initiate_payment_command import InitiatePaymentCommand
from application.port.out.order_repository import IOrderRepository
from application.port.out.event_publisher import IEventPublisher
from domain.exceptions.domain_exception import OrderNotFoundException
 
 
class InitiatePaymentHandler:
    """
    Command Handler: инициирование оплаты заказа.
    Регистрирует платёж в БД (outbox pattern) — фактическое
    списание через эквайринг выполнит асинхронный PaymentWorker.
    """
 
    def __init__(self, order_repository: IOrderRepository, event_publisher: IEventPublisher):
        self._repo = order_repository
        self._publisher = event_publisher
 
    def handle(self, command: InitiatePaymentCommand) -> str:
        # ── Шаг 1: Загрузка агрегата ──────────────────────────────
        order = self._repo.find_by_id(command.order_id)
        if order is None:
            raise OrderNotFoundException(f"Заказ не найден: {command.order_id}")
 
        # ── Шаг 2: Вычисляем итог с чаевыми ──────────────────────
        total = order.calculate_total()
        # Чаевые добавляются на уровне приложения, не домена
        tip_amount = command.tip
 
        # ── Шаг 3: Доменный метод ─────────────────────────────────
        payment_id = self._generate_payment_id()
        payment = order.initiate_payment(payment_id, command.payment_method)
 
        # ── Шаг 4: Сохранение ─────────────────────────────────────
        self._repo.save(order)
 
        # ── Шаг 5: Публикация событий ─────────────────────────────
        for event in order.pull_events():
            self._publisher.publish(event)
 
        return payment.payment_id
 
    @staticmethod
    def _generate_payment_id() -> str:
        seq = str(uuid.uuid4().int)[:4].zfill(4)
        return f"PAY-{seq}"