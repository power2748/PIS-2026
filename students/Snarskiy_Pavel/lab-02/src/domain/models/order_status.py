class OrderStatus:
    """
    Value Object: Статус заказа.
    Неизменяемый объект, описывающий состояние заказа.
    """
 
    NEW = "NEW"
    IN_PROGRESS = "IN_PROGRESS"
    READY = "READY"
    AWAITING_PAYMENT = "AWAITING_PAYMENT"
    PAID = "PAID"
    CANCELLED = "CANCELLED"
 
    TRANSITIONS = {
        NEW: [IN_PROGRESS, CANCELLED],
        IN_PROGRESS: [READY, CANCELLED],
        READY: [AWAITING_PAYMENT],
        AWAITING_PAYMENT: [PAID, READY],  # READY — при неудаче оплаты
        PAID: [],
        CANCELLED: [],
    }
 
    @staticmethod
    def can_transition(from_status: str, to_status: str) -> bool:
        return to_status in OrderStatus.TRANSITIONS.get(from_status, [])