from flask import Flask, request, jsonify
 
app = Flask(__name__)
 
class OrderController:
    """
    Входящий адаптер: REST API для управления заказами.
    Преобразует HTTP-запросы в команды для use-cases.
    Зависит от входящих портов (интерфейсов), не от реализаций.
    """
 
    def __init__(self, create_order_use_case, send_to_kitchen_use_case, process_payment_use_case):
        self._create_order = create_order_use_case
        self._send_to_kitchen = send_to_kitchen_use_case
        self._process_payment = process_payment_use_case
 
    def create_order(self):
        """POST /api/orders — создание нового заказа"""
        data = request.get_json()
        command = CreateOrderCommand(
            table_id=data["table_id"],
            guests=data["guests"],
            items=[OrderItemCommand(**item) for item in data["items"]],
            comment=data.get("comment"),
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
        order_id = self._create_order.create_order(command)
        return jsonify({"order_id": order_id}), 201
 
    def send_to_kitchen(self, order_id: str):
        """POST /api/orders/{id}/send — отправка на кухню"""
        ticket_id = self._send_to_kitchen.send_to_kitchen(order_id)
        return jsonify({"ticket_id": ticket_id}), 200
 
    def process_payment(self, order_id: str):
        """POST /api/orders/{id}/pay — проведение оплаты"""
        data = request.get_json()
        command = ProcessPaymentCommand(
            order_id=order_id,
            payment_method=data["payment_method"],
            amount=data["amount"],
            tip=data.get("tip", 0.0),
        )
        payment_id = self._process_payment.process_payment(command)
        return jsonify({"payment_id": payment_id}), 200