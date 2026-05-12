from abc import ABC, abstractmethod
 
class ISendToKitchenUseCase(ABC):
    """
    Входящий порт: отправка заказа на кухню.
    Вызывается REST-контроллером при POST /api/orders/{id}/send.
    """
 
    @abstractmethod
    def send_to_kitchen(self, order_id: str) -> str:
        """
        Создаёт тикет кухни и отправляет заказ по станциям.
        :param order_id: ID заказа
        :return: ID созданного тикета кухни (например, 'KT-318')
        :raises InvalidOrderStateException: если заказ не в статусе NEW
        """
        pass