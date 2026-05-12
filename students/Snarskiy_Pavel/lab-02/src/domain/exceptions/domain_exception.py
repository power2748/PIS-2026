class DomainException(Exception):
    """Базовое доменное исключение"""
    pass
 
# domain/exceptions/dish_unavailable_exception.py
class DishUnavailableException(DomainException):
    """Блюдо недоступно (стоп-лист или нехватка ингредиентов)"""
    pass
 
# domain/exceptions/table_occupied_exception.py
class TableOccupiedException(DomainException):
    """Столик уже занят другим активным заказом"""
    pass
 
# domain/exceptions/invalid_order_state_exception.py
class InvalidOrderStateException(DomainException):
    """Попытка выполнить недопустимый переход состояния заказа"""
    pass