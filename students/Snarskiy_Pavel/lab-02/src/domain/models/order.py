from domain.exceptions.domain_exception import DomainException
 
class Order:
    """
    Доменная модель: Заказ (Aggregate Root).
    Управляет жизненным циклом заказа в ресторане.
    Не зависит от фреймворков, БД и внешних сервисов.
    """
 
    ALLOWED_STATUSES = ["NEW", "IN_PROGRESS", "READY", "AWAITING_PAYMENT", "PAID", "CANCELLED"]
 
    def __init__(self, order_id: str, table_id: int, guests: int):
        self.id = order_id
        self.table_id = table_id
        self.guests = guests
        self.items = []         # List[OrderItem]
        self.status = "NEW"
        self.comment = None
        self.version = 1        # Для optimistic locking
 
    def add_item(self, item):
        """Добавить позицию в заказ"""
        if self.status != "NEW":
            raise DomainException(f"Нельзя изменить заказ в статусе {self.status}")
        self.items.append(item)
 
    def send_to_kitchen(self):
        """Отправить заказ на кухню"""
        if not self.items:
            raise DomainException("Нельзя отправить пустой заказ на кухню")
        if self.status != "NEW":
            raise DomainException(f"Заказ уже отправлен (статус: {self.status})")
        self.status = "IN_PROGRESS"
        self.version += 1
 
    def mark_ready(self):
        """Пометить заказ как выполненный кухней"""
        if self.status != "IN_PROGRESS":
            raise DomainException("Заказ ещё не готовится")
        self.status = "READY"
 
    def initiate_payment(self):
        """Инициировать оплату"""
        if self.status != "READY":
            raise DomainException("Заказ ещё не готов к оплате")
        self.status = "AWAITING_PAYMENT"
 
    def complete_payment(self):
        """Завершить оплату"""
        if self.status != "AWAITING_PAYMENT":
            raise DomainException("Оплата не была инициирована")
        self.status = "PAID"
 
    def calculate_total(self) -> float:
        """Вычислить итоговую сумму заказа"""
        return sum(item.price * item.quantity for item in self.items)