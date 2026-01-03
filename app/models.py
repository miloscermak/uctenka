"""SQLAlchemy database models."""

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Text, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
import enum

from .database import Base


class ReceiptCategory(str, enum.Enum):
    """Receipt category enum."""
    PERSONAL = "personal"
    WORK = "work"


class User(Base):
    """User model."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    receipts = relationship("Receipt", back_populates="user")
    tags = relationship("Tag", back_populates="user")


class Tag(Base):
    """Custom tag for receipts."""
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    color = Column(String(7), default="#3B82F6")  # Hex color

    user = relationship("User", back_populates="tags")
    receipts = relationship("Receipt", secondary="receipt_tags", back_populates="tags")


class Receipt(Base):
    """Receipt model."""
    __tablename__ = "receipts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Receipt data
    date = Column(DateTime, nullable=True)
    total_amount = Column(Float, nullable=True)
    currency = Column(String(3), default="CZK")

    # Seller info
    seller_name = Column(String(255), nullable=True)
    seller_tax_id = Column(String(50), nullable=True)  # DIČ
    seller_business_id = Column(String(50), nullable=True)  # IČO
    seller_address = Column(Text, nullable=True)

    # VAT totals
    total_vat = Column(Float, nullable=True)
    total_without_vat = Column(Float, nullable=True)

    # Category and metadata
    category = Column(SQLEnum(ReceiptCategory), default=ReceiptCategory.PERSONAL)
    note = Column(Text, nullable=True)
    image_path = Column(String(500), nullable=True)
    raw_json = Column(Text, nullable=True)  # Original Claude response

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="receipts")
    items = relationship("ReceiptItem", back_populates="receipt", cascade="all, delete-orphan")
    tags = relationship("Tag", secondary="receipt_tags", back_populates="receipts")


class ReceiptItem(Base):
    """Individual item on a receipt."""
    __tablename__ = "receipt_items"

    id = Column(Integer, primary_key=True, index=True)
    receipt_id = Column(Integer, ForeignKey("receipts.id"), nullable=False)

    name = Column(String(255), nullable=False)
    quantity = Column(Float, default=1.0)
    unit_price = Column(Float, nullable=True)
    total_price = Column(Float, nullable=True)

    vat_rate = Column(Float, nullable=True)  # e.g., 21.0 for 21%
    vat_amount = Column(Float, nullable=True)
    price_without_vat = Column(Float, nullable=True)

    receipt = relationship("Receipt", back_populates="items")


class ReceiptTag(Base):
    """Many-to-many relationship between receipts and tags."""
    __tablename__ = "receipt_tags"

    receipt_id = Column(Integer, ForeignKey("receipts.id"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id"), primary_key=True)
