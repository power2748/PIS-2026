from sqlalchemy import (
    Column, String, Integer, Float, DateTime,
    ForeignKey, Text, Enum as SAEnum
)
from sqlalchemy.orm import DeclarativeBase, relationship
from datetime import datetime
 
 
class Base(DeclarativeBase):
    pass
 
 
class OrderModel(Base):
    """ORM-модель таблицы orders"""
    __tablename__ = "orders"
 
    order_id        = Column(String(32), primary_key=True)
    table_id        = Column(Integer, nullable=False, index=True)
    guests          = Column(Integer, nullable=False)
    status          = Column(String(20), nullable=False, default="NEW", index=True)
    comment         = Column(Text, nullable=True)
    version         = Column(Integer, nullable=False, default=1)
    idempotency_key = Column(String(128), nullable=True, unique=True, index=True)
    created_at      = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at      = Column(DateTime, nullable=False, default=datetime.utcnow,
                             onupdate=datetime.utcnow)
 
    items           = relationship("OrderItemModel", back_populates="order",
                                   cascade="all, delete-orphan")
    kitchen_ticket  = relationship("KitchenTicketModel", back_populates="order",
                                   uselist=False, cascade="all, delete-orphan")
    payment         = relationship("PaymentModel", back_populates="order",
                                   uselist=False, cascade="all, delete-orphan")
 
 
class OrderItemModel(Base):
    """ORM-модель таблицы order_items"""
    __tablename__ = "order_items"
 
    item_id   = Column(String(36), primary_key=True)
    order_id  = Column(String(32), ForeignKey("orders.order_id"), nullable=False)
    dish_id   = Column(String(32), nullable=False)
    dish_name = Column(String(128), nullable=False)
    quantity  = Column(Integer, nullable=False)
    price     = Column(Float, nullable=False)
    station   = Column(String(16), nullable=False)  # GRILL, PASTA, DESSERT, BAR, COLD
    comment   = Column(Text, nullable=True)
 
    order     = relationship("OrderModel", back_populates="items")
 
 
class KitchenTicketModel(Base):
    """ORM-модель таблицы kitchen_tickets"""
    __tablename__ = "kitchen_tickets"
 
    ticket_id  = Column(String(32), primary_key=True)
    order_id   = Column(String(32), ForeignKey("orders.order_id"), nullable=False, unique=True)
    status     = Column(String(20), nullable=False, default="PENDING")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow,
                        onupdate=datetime.utcnow)
 
    order      = relationship("OrderModel", back_populates="kitchen_ticket")
    items      = relationship("TicketItemModel", back_populates="ticket",
                              cascade="all, delete-orphan")
 
 
class TicketItemModel(Base):
    __tablename__ = "ticket_items"
 
    id        = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(String(32), ForeignKey("kitchen_tickets.ticket_id"), nullable=False)
    dish_id   = Column(String(32), nullable=False)
    dish_name = Column(String(128), nullable=False)
    quantity  = Column(Integer, nullable=False)
    station   = Column(String(16), nullable=False)
    is_done   = Column(Integer, nullable=False, default=0)  # 0/1
 
    ticket    = relationship("KitchenTicketModel", back_populates="items")
 
 
class PaymentModel(Base):
    """ORM-модель таблицы payments"""
    __tablename__ = "payments"
 
    payment_id     = Column(String(32), primary_key=True)
    order_id       = Column(String(32), ForeignKey("orders.order_id"), nullable=False, unique=True)
    amount         = Column(Float, nullable=False)
    currency       = Column(String(3), nullable=False, default="RUB")
    method         = Column(String(8), nullable=False)       # CARD, CASH, QR
    status         = Column(String(20), nullable=False, default="PENDING")
    retry_count    = Column(Integer, nullable=False, default=0)
    transaction_id = Column(String(64), nullable=True)
    created_at     = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at     = Column(DateTime, nullable=False, default=datetime.utcnow,
                            onupdate=datetime.utcnow)
 
    order          = relationship("OrderModel", back_populates="payment")
 
 
class IdempotentRequestModel(Base):
    """ORM-модель таблицы idempotent_requests"""
    __tablename__ = "idempotent_requests"
 
    idempotency_key = Column(String(128), primary_key=True)
    order_id        = Column(String(32), nullable=False)
    created_at      = Column(DateTime, nullable=False, default=datetime.utcnow)