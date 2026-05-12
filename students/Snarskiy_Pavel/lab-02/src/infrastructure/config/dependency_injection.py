from infrastructure.adapter.out.in_memory_order_repository import InMemoryOrderRepository
from infrastructure.adapter.out.stripe_payment_gateway import StripePaymentGateway
from infrastructure.adapter.out.console_notification_service import ConsoleNotificationService
from application.service.order_service import OrderService
 
class DependencyContainer:
    """
    DI-контейнер: связывает порты с адаптерами.
    Ключевой принцип: OrderService не создаёт зависимости сам —
    они передаются через конструктор (Dependency Inversion Principle).
    """
 
    def __init__(self):
        # 1. Создаём исходящие адаптеры (реализации портов)
        self.order_repository = InMemoryOrderRepository()
        self.payment_gateway = StripePaymentGateway()
        self.kitchen_notification = ConsoleNotificationService()
        self.menu_inventory = InMemoryMenuInventoryAdapter()
 
        # 2. Создаём application service с инжекцией зависимостей
        self.order_service = OrderService(
            order_repository=self.order_repository,
            menu_inventory_port=self.menu_inventory,
            payment_gateway=self.payment_gateway,
            kitchen_notification_port=self.kitchen_notification,
        )
 
    def get_order_service(self) -> OrderService:
        return self.order_service
 
# Точка входа
container = DependencyContainer()