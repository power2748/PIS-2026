import pytest
import httpx
import time
 
BASE_URL = "http://localhost:8000/api"
 
 
@pytest.fixture(scope="session")
def client():
    """HTTP-клиент для E2E тестов против живого приложения"""
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as c:
        # Ждём пока приложение поднимется
        for _ in range(10):
            try:
                c.get("/orders")
                break
            except httpx.ConnectError:
                time.sleep(1)
        yield c
 
 
# ── Сценарий 1: Полный жизненный цикл заказа ─────────────────────
 
class TestFullOrderLifecycle:
 
    def test_e2e_create_send_pay(self, client):
        """
        E2E: POST /orders → POST /orders/{id}/send → POST /orders/{id}/pay
        → GET /orders/{id} → status == AWAITING_PAYMENT
        """
 
        # ── Шаг 1: Создать заказ ──────────────────────────────────
        create_resp = client.post(
            "/orders",
            json={
                "table_id": 30,
                "guests": 2,
                "items": [
                    {"dish_id": "D-01", "dish_name": "Стейк Рибай",
                     "quantity": 1, "price": 1500.0, "station": "GRILL"},
                    {"dish_id": "D-12", "dish_name": "Тирамису",
                     "quantity": 2, "price": 400.0, "station": "DESSERT"},
                ],
                "comment": "Стейк medium",
            },
            headers={"Idempotency-Key": "e2e-test-lifecycle-001"},
        )
        assert create_resp.status_code == 201
        order_id = create_resp.json()["order_id"]
        assert order_id.startswith("ORD-")
 
        # ── Шаг 2: Проверить статус NEW ───────────────────────────
        get_resp = client.get(f"/orders/{order_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["status"] == "NEW"
        assert get_resp.json()["table_id"] == 30
 
        # ── Шаг 3: Отправить на кухню ─────────────────────────────
        send_resp = client.post(
            f"/orders/{order_id}/send",
            json={"waiter_id": "waiter-42"},
        )
        assert send_resp.status_code == 200
        ticket_id = send_resp.json()["ticket_id"]
        assert ticket_id.startswith("KT-")
 
        # ── Шаг 4: Проверить статус IN_PROGRESS ───────────────────
        get_resp2 = client.get(f"/orders/{order_id}")
        assert get_resp2.json()["status"] == "IN_PROGRESS"
        assert get_resp2.json()["kitchen_ticket"]["ticket_id"] == ticket_id
 
        # ── Шаг 5: Инициировать оплату ────────────────────────────
        # Сначала переводим заказ в READY через тестовый хелпер
        client.post(f"/orders/{order_id}/mark-ready")  # тестовый endpoint
 
        pay_resp = client.post(
            f"/orders/{order_id}/pay",
            json={"payment_method": "CARD", "tip": 230.0},
        )
        assert pay_resp.status_code == 200
        payment_id = pay_resp.json()["payment_id"]
        assert payment_id.startswith("PAY-")
 
        # ── Шаг 6: Проверить статус AWAITING_PAYMENT ──────────────
        get_resp3 = client.get(f"/orders/{order_id}")
        data = get_resp3.json()
        assert data["status"] == "AWAITING_PAYMENT"
        assert data["payment"]["payment_id"] == payment_id
        assert data["total"] == 2300.0
 
 
# ── Сценарий 2: Идемпотентность ───────────────────────────────────
 
class TestIdempotency:
 
    def test_duplicate_create_returns_same_order_id(self, client):
        """
        E2E: два одинаковых POST с Idempotency-Key → один и тот же order_id
        """
        payload = {
            "table_id": 31,
            "guests": 1,
            "items": [
                {"dish_id": "D-07", "dish_name": "Паста Карбонара",
                 "quantity": 1, "price": 800.0, "station": "PASTA"},
            ],
        }
        headers = {"Idempotency-Key": "e2e-idem-key-999"}
 
        resp1 = client.post("/orders", json=payload, headers=headers)
        resp2 = client.post("/orders", json=payload, headers=headers)
 
        assert resp1.status_code == 201
        assert resp2.status_code == 201
        assert resp1.json()["order_id"] == resp2.json()["order_id"]
 
 
# ── Сценарий 3: Ошибка — столик занят ────────────────────────────
 
class TestErrorCases:
 
    def test_create_order_on_occupied_table_returns_409(self, client):
        """
        E2E: создаём заказ → пытаемся создать ещё один на тот же столик → 409
        """
        payload = {
            "table_id": 32,
            "guests": 2,
            "items": [
                {"dish_id": "D-01", "dish_name": "Стейк",
                 "quantity": 1, "price": 1500.0, "station": "GRILL"},
            ],
        }
 
        first = client.post("/orders", json=payload,
                            headers={"Idempotency-Key": "e2e-occupied-001"})
        assert first.status_code == 201
 
        second = client.post("/orders", json=payload,
                             headers={"Idempotency-Key": "e2e-occupied-002"})
        assert second.status_code == 409
        assert "занят" in second.json()["detail"].lower()
 
    def test_get_nonexistent_order_returns_404(self, client):
        resp = client.get("/orders/ORD-NONEXISTENT")
        assert resp.status_code == 404
 
    def test_send_to_kitchen_already_sent_returns_409(self, client):
        """Повторная отправка на кухню → 409 Conflict"""
        create = client.post("/orders", json={
            "table_id": 33, "guests": 1,
            "items": [{"dish_id": "D-01", "dish_name": "Стейк",
                       "quantity": 1, "price": 1500.0, "station": "GRILL"}],
        }, headers={"Idempotency-Key": "e2e-double-send-001"})
        order_id = create.json()["order_id"]
 
        client.post(f"/orders/{order_id}/send", json={"waiter_id": "w-1"})
        second = client.post(f"/orders/{order_id}/send", json={"waiter_id": "w-1"})
 
        assert second.status_code == 409