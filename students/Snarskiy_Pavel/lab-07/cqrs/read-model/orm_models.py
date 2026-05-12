from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, Text, JSON
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime
 
 
class ReadBase(DeclarativeBase):
    pass
 
 
class OrderViewModel(ReadBase):
    """
    Read Model: денормализованная карточка заказа.
    Все данные в одной строке — никаких JOIN при чтении.
    Обновляется асинхронно через проекции при получении событий.
    """
    __tablename__ = "order_views"
 
    order_id         = Column(String(32), primary_key=True)
    table_id         = Column(Integer, nullable=False, index=True)
    table_label      = Column(String(32), nullable=False)      # "Столик №12"
    guests           = Column(Integer, nullable=False)
    status           = Column(String(20), nullable=False, index=True)
    status_label     = Column(String(64), nullable=False)      # "Готовится на кухне"
    comment          = Column(Text, nullable=True)
 
    # Позиции — денормализованы в JSON
    items_json       = Column(JSON, nullable=False)            # [{dish, qty, price, station}]
    items_count      = Column(Integer, nullable=False)
    total_amount     = Column(Float, nullable=False)
    currency         = Column(String(3), nullable=False, default="RUB")
 
    # Тикет кухни — денормализован
    ticket_id        = Column(String(32), nullable=True)
    ticket_status    = Column(String(20), nullable=True)
    kitchen_stations = Column(JSON, nullable=True)             # ["GRILL", "DESSERT"]
    eta_minutes      = Column(Integer, nullable=True)
 
    # Платёж — денормализован
    payment_id       = Column(String(32), nullable=True)
    payment_method   = Column(String(8), nullable=True)
    payment_status   = Column(String(20), nullable=True)
    payment_amount   = Column(Float, nullable=True)
    transaction_id   = Column(String(64), nullable=True)
 
    # Аудит
    waiter_id        = Column(String(32), nullable=True, index=True)
    created_at       = Column(DateTime, nullable=False, index=True)
    updated_at       = Column(DateTime, nullable=False)
    version          = Column(Integer, nullable=False, default=1)
 
 
class TableViewModel(ReadBase):
    """
    Read Model: состояние столика в зале.
    Обновляется при создании/оплате/отмене заказа.
    Используется для отображения карты зала.
    """
    __tablename__ = "table_views"
 
    table_id         = Column(Integer, primary_key=True)
    table_label      = Column(String(32), nullable=False)
    capacity         = Column(Integer, nullable=False)
    status           = Column(String(20), nullable=False)      # FREE, OCCUPIED, RESERVED
    active_order_id  = Column(String(32), nullable=True)
    active_order_status = Column(String(20), nullable=True)
    guests           = Column(Integer, nullable=True)
    occupied_since   = Column(DateTime, nullable=True)
    total_amount     = Column(Float, nullable=True)
    updated_at       = Column(DateTime, nullable=False)
 
 
class KitchenDashboardViewModel(ReadBase):
    """
    Read Model: очередь блюд для кухонного дисплея.
    Создаётся при OrderSentToKitchenEvent, удаляется при PaymentCompletedEvent.
    Один тикет = одна строка на каждой станции.
    """
    __tablename__ = "kitchen_dashboard_views"
 
    id               = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id        = Column(String(32), nullable=False, index=True)
    order_id         = Column(String(32), nullable=False)
    table_label      = Column(String(32), nullable=False)
    station          = Column(String(16), nullable=False, index=True)  # GRILL / PASTA...
    items_json       = Column(JSON, nullable=False)
    priority         = Column(Integer, nullable=False, default=0)      # выше = срочнее
    status           = Column(String(20), nullable=False, default="PENDING")
    created_at       = Column(DateTime, nullable=False)
    updated_at       = Column(DateTime, nullable=False)
 
 
class RevenueViewModel(ReadBase):
    """
    Read Model: выручка за смену с разбивкой по часам.
    Инкрементально обновляется при PaymentCompletedEvent.
    """
    __tablename__ = "revenue_views"
 
    id               = Column(Integer, primary_key=True, autoincrement=True)
    date             = Column(String(10), nullable=False, index=True)  # "2024-11-08"
    hour             = Column(Integer, nullable=False)                  # 0..23
    orders_count     = Column(Integer, nullable=False, default=0)
    total_amount     = Column(Float, nullable=False, default=0.0)
    avg_order_amount = Column(Float, nullable=False, default=0.0)
    currency         = Column(String(3), nullable=False, default="RUB")
    updated_at       = Column(DateTime, nullable=False)