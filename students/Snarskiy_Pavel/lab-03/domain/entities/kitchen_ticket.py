from typing import List, Optional
from datetime import datetime
 
class KitchenTicket:
    """
    Entity: Тикет кухни.
    Создаётся при отправке заказа на кухню.
    Хранит состояние приготовления блюд по станциям.
    Идентифицируется по ticket_id.
    """

    VALID_STATUSES = {"PENDING", "IN_PROGRESS", "DONE", "CANCELLED"}

    def __init__(self, ticket_id: str, order_id: str, items: List["TicketItem"]):
        if not ticket_id:
            raise ValueError("ticket_id не может быть пустым")
        if not order_id:
            raise ValueError("order_id не может быть пустым")
        if not items:
            raise ValueError("Тикет не может быть создан без позиций")

        self._ticket_id = ticket_id
        self._order_id = order_id
        self._items: List["TicketItem"] = list(items)
        self._status = "PENDING"
        self._created_at = datetime.now()
        self._updated_at = datetime.now()

    @property
    def ticket_id(self) -> str:
        return self._ticket_id

    @property
    def order_id(self) -> str:
        return self._order_id

    @property
    def status(self) -> str:
        return self._status

    @property
    def items(self) -> List["TicketItem"]:
        return list(self._items)  # защитная копия

    def start_cooking(self) -> None:
        """Кухня начала готовить"""
        if self._status != "PENDING":
            raise ValueError(
                f"Нельзя начать готовить тикет в статусе {self._status}"
            )
        self._status = "IN_PROGRESS"
        self._updated_at = datetime.now()

    def mark_item_done(self, dish_id: str) -> None:
        """Пометить блюдо как приготовленное"""
        item = self._find_item(dish_id)
        if item is None:
            raise ValueError(f"Блюдо {dish_id} не найдено в тикете {self._ticket_id}")
        item.mark_done()

    def complete(self) -> None:
        """Закрыть тикет — все блюда готовы"""
        pending_items = [i for i in self._items if not i.is_done]
        if pending_items:
            names = [i.dish_name for i in pending_items]
            raise ValueError(
                f"Нельзя закрыть тикет: не готовы блюда: {names}"
            )
        if self._status == "CANCELLED":
            raise ValueError("Нельзя закрыть отменённый тикет")
        self._status = "DONE"
        self._updated_at = datetime.now()

    def cancel(self) -> None:
        """Отменить тикет"""
        if self._status == "DONE":
            raise ValueError("Нельзя отменить уже выполненный тикет")
        self._status = "CANCELLED"
        self._updated_at = datetime.now()
 
    def _find_item(self, dish_id: str) -> Optional["TicketItem"]:
        return next((i for i in self._items if i.dish_id == dish_id), None)
 
    # Identity-based equality
    def __eq__(self, other) -> bool:
        if not isinstance(other, KitchenTicket):
            return False
        return self._ticket_id == other._ticket_id
 
    def __hash__(self) -> int:
        return hash(self._ticket_id)
 
    def __repr__(self) -> str:
        return f"KitchenTicket(id={self._ticket_id}, order={self._order_id}, status={self._status})"
 
 
class TicketItem:
    """Позиция тикета кухни (не самостоятельная сущность, живёт внутри KitchenTicket)"""
 
    def __init__(self, dish_id: str, dish_name: str, quantity: int, station: str):
        self.dish_id = dish_id
        self.dish_name = dish_name
        self.quantity = quantity
        self.station = station
        self.is_done = False
 
    def mark_done(self) -> None:
        self.is_done = True