class OrderItem:
    """
    Доменная модель: Позиция заказа.
    Представляет одно блюдо в составе заказа.
    """
 
    def __init__(self, dish_id: str, dish_name: str, quantity: int, price: float):
        if quantity <= 0:
            raise ValueError("Количество должно быть больше нуля")
        if price < 0:
            raise ValueError("Цена не может быть отрицательной")
        self.dish_id = dish_id
        self.dish_name = dish_name
        self.quantity = quantity
        self.price = price
        self.comment = None
        self.station = None     # GRILL, PASTA, DESSERT, BAR — заполняется при отправке на кухню