from abc import ABC, abstractmethod
from dataclasses import dataclass
 
@dataclass
class ProcessPaymentCommand:
    """DTO для команды проведения оплаты"""
    order_id: str
    payment_method: str     # CARD, CASH, QR
    amount: float
    tip: float = 0.0
 
class IProcessPaymentUseCase(ABC):
    """
    Входящий порт: проведение оплаты заказа.
    Вызывается REST-контроллером при POST /api/orders/{id}/pay.
    """
 
    @abstractmethod
    def process_payment(self, command: ProcessPaymentCommand) -> str:
        """
        Регистрирует платёж и инициирует списание через эквайринг.
        :param command: Данные для оплаты
        :return: ID платежа (например, 'PAY-0318')
        :raises InvalidOrderStateException: если заказ не готов к оплате
        """
        pass