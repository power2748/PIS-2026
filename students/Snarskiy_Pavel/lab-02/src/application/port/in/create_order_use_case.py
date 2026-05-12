from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List
 
@dataclass
class OrderItemCommand:
    """DTO: одна позиция в команде создания заказа"""
    dish_id: str
    quantity: int
    comment: str = None
 
@dataclass
class CreateOrderCommand:
    """DTO для команды создания заказа"""
    table_id: int
    guests: int
    items: List[OrderItemCommand]
    comment: str = None
    idempotency_key: str = None
 
class ICreateOrderUseCase(ABC):
    """
    Входящий порт: создание нового заказа.
    Вызывается REST-контроллером при POST /api/orders.
    """
 
    @abstractmethod
    def create_order(self, command: CreateOrderCommand) -> str:
        """
        Создаёт заказ и возвращает его ID.
        :param command: Данные для создания заказа
        :return: ID созданного заказа (например, 'ORD-2024-0318')
        :raises DishUnavailableException: если блюдо в стоп-листе
        :raises TableOccupiedException: если столик уже занят
        """
        pass