"""
POS Service — Database Models.
Defines all tables for the POS system: Products, Cash Sessions, Sales, and Tourist Orders.
"""
import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, Index
)
from sqlalchemy.orm import relationship, DeclarativeBase
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class Product(Base):
    """Товар в магазине. Синхронизируется из Google Sheets."""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    category = Column(String(100), default="Other")
    cost_price = Column(Float, default=0)
    sale_price = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
    image_url = Column(String(500), nullable=True)  # For future product images
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_products_category", "category"),
        Index("ix_products_active", "is_active"),
    )


class CashSession(Base):
    """Кассовая смена. Привязана к конкретному пирсу и менеджеру."""
    __tablename__ = "cash_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pier = Column(String(50), nullable=False, index=True)
    manager_id = Column(Integer, nullable=False)  # Telegram user ID of the manager
    manager_name = Column(String(200), nullable=True)
    status = Column(String(20), default="open")  # "open" | "closed"
    opened_at = Column(DateTime(timezone=True), server_default=func.now())
    closed_at = Column(DateTime(timezone=True), nullable=True)

    sales = relationship("Sale", back_populates="session", lazy="selectin")

    __table_args__ = (
        Index("ix_sessions_pier_status", "pier", "status"),
    )


class Sale(Base):
    """Отдельная продажа (транзакция) в рамках кассовой смены."""
    __tablename__ = "sales"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("cash_sessions.id"), nullable=True)
    pier = Column(String(50), nullable=False, index=True)
    manager_id = Column(Integer, nullable=False)
    total_amount = Column(Float, default=0)
    payment_type = Column(String(20), default="cash")  # "cash" | "online"
    status = Column(String(20), default="completed")  # "completed" | "cancelled"
    payment_reference = Column(String(200), nullable=True, index=True)
    payment_link = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("CashSession", back_populates="sales")
    items = relationship("SaleItem", back_populates="sale", lazy="selectin", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_sales_pier_date", "pier", "created_at"),
    )


class SaleItem(Base):
    """Отдельная позиция в продаже."""
    __tablename__ = "sale_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sale_id = Column(Integer, ForeignKey("sales.id", ondelete="CASCADE"), nullable=False)
    product_name = Column(String(255), nullable=False)
    quantity = Column(Integer, default=1)
    price_per_unit = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)

    sale = relationship("Sale", back_populates="items")


class TouristOrder(Base):
    """Онлайн-заказ от туриста (оплата через NSPK)."""
    __tablename__ = "tourist_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(Integer, nullable=True)
    pier = Column(String(50), default="Online")
    total_amount = Column(Float, nullable=False)
    total_rub = Column(Float, nullable=True)
    rate = Column(Float, nullable=True)
    status = Column(String(20), default="pending")  # "pending" | "paid" | "cancelled"
    payment_reference = Column(String(200), nullable=True, unique=True)
    payment_link = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    items = relationship("TouristOrderItem", back_populates="order", lazy="selectin", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_tourist_orders_status", "status"),
    )


class TouristOrderItem(Base):
    """Позиция в онлайн-заказе."""
    __tablename__ = "tourist_order_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("tourist_orders.id", ondelete="CASCADE"), nullable=False)
    product_name = Column(String(255), nullable=False)
    quantity = Column(Integer, default=1)
    price_per_unit = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)

    order = relationship("TouristOrder", back_populates="items")


class POSSetting(Base):
    """Dynamic key-value settings for the POS service.
    Allows runtime configuration changes without service restart."""
    __tablename__ = "pos_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False, default="")
    description = Column(String(500), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
