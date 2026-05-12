class OrderService(ICreateOrderUseCase, ISendToKitchenUseCase, IProcessPaymentUseCase):
    """
    Оркестратор use-cases для управления заказами.
    Реализует входящие порты и использует исходящие порты.
    Не зависит от конкретных реализаций адаптеров.
    """
 
    def __init__(
        self,
        order_repository: IOrderRepository,
        menu_inventory_port: IMenuInventoryPort,
        payment_gateway: IPaymentGateway,
        kitchen_notification_port: IKitchenNotificationPort,
    ):
        # Зависимости инжектируются через конструктор (DIP)
        self._order_repository = order_repository
        self._menu_inventory = menu_inventory_port
        self._payment_gateway = payment_gateway
        self._kitchen_notification = kitchen_notification_port
 
    def create_order(self, command: CreateOrderCommand) -> str:
        # TODO: реализовать в Lab #4
        # 1. Проверить idempotency_key (не дубликат ли?)
        # 2. Проверить что столик свободен (find_by_table_id)
        # 3. Проверить доступность блюд (menu_inventory_port.check_availability)
        # 4. Создать Order aggregate (domain)
        # 5. Добавить OrderItem-ы
        # 6. Зарезервировать ингредиенты (menu_inventory_port.reserve_ingredients)
        # 7. Сохранить заказ (order_repository.save)
        # 8. Вернуть order.id
        raise NotImplementedError("Будет реализовано в Lab #4")
 
    def send_to_kitchen(self, order_id: str) -> str:
        # TODO: реализовать в Lab #4
        # 1. Загрузить заказ (order_repository.find_by_id)
        # 2. Вызвать order.send_to_kitchen() (domain logic)
        # 3. Создать KitchenTicket, распределить по станциям
        # 4. Сохранить обновлённый заказ и тикет
        # 5. Асинхронно уведомить KDS (kitchen_notification_port.send_ticket)
        # 6. Вернуть ticket.id
        raise NotImplementedError("Будет реализовано в Lab #4")
 
    def process_payment(self, command: ProcessPaymentCommand) -> str:
        # TODO: реализовать в Lab #4
        # 1. Загрузить заказ (order_repository.find_by_id)
        # 2. Вызвать order.initiate_payment() (domain logic)
        # 3. Создать Payment запись (статус PENDING)
        # 4. Сохранить в БД (order_repository.save)
        # 5. Вызвать payment_gateway.charge() — outbox pattern
        # 6. При успехе: order.complete_payment(), освободить столик
        # 7. Вернуть payment.id
        raise NotImplementedError("Будет реализовано в Lab #4")