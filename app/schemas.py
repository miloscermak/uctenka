"""Pydantic schemas for API request/response validation."""

from datetime import datetime
from pydantic import BaseModel, EmailStr
from typing import Optional

from .models import ReceiptCategory


# --- User schemas ---

class UserCreate(BaseModel):
    email: EmailStr
    name: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    email: str
    name: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# --- Tag schemas ---

class TagCreate(BaseModel):
    name: str
    color: Optional[str] = "#3B82F6"


class TagResponse(BaseModel):
    id: int
    name: str
    color: str

    class Config:
        from_attributes = True


# --- Receipt Item schemas ---

class ReceiptItemCreate(BaseModel):
    name: str
    quantity: Optional[float] = 1.0
    unit_price: Optional[float] = None
    total_price: Optional[float] = None
    vat_rate: Optional[float] = None
    vat_amount: Optional[float] = None
    price_without_vat: Optional[float] = None


class ReceiptItemResponse(BaseModel):
    id: int
    name: str
    quantity: float
    unit_price: Optional[float]
    total_price: Optional[float]
    vat_rate: Optional[float]
    vat_amount: Optional[float]
    price_without_vat: Optional[float]

    class Config:
        from_attributes = True


# --- Receipt schemas ---

class ReceiptCreate(BaseModel):
    date: Optional[datetime] = None
    total_amount: Optional[float] = None
    currency: Optional[str] = "CZK"
    seller_name: Optional[str] = None
    seller_tax_id: Optional[str] = None
    seller_business_id: Optional[str] = None
    seller_address: Optional[str] = None
    total_vat: Optional[float] = None
    total_without_vat: Optional[float] = None
    category: Optional[ReceiptCategory] = ReceiptCategory.PERSONAL
    note: Optional[str] = None
    items: list[ReceiptItemCreate] = []
    tag_ids: list[int] = []


class ReceiptUpdate(BaseModel):
    category: Optional[ReceiptCategory] = None
    note: Optional[str] = None
    tag_ids: Optional[list[int]] = None


class ReceiptResponse(BaseModel):
    id: int
    user_id: int
    date: Optional[datetime]
    total_amount: Optional[float]
    currency: str
    seller_name: Optional[str]
    seller_tax_id: Optional[str]
    seller_business_id: Optional[str]
    seller_address: Optional[str]
    total_vat: Optional[float]
    total_without_vat: Optional[float]
    category: ReceiptCategory
    note: Optional[str]
    image_path: Optional[str]
    created_at: datetime
    updated_at: datetime
    items: list[ReceiptItemResponse] = []
    tags: list[TagResponse] = []

    class Config:
        from_attributes = True


class ReceiptListResponse(BaseModel):
    id: int
    date: Optional[datetime]
    total_amount: Optional[float]
    currency: str
    seller_name: Optional[str]
    category: ReceiptCategory
    created_at: datetime
    tags: list[TagResponse] = []

    class Config:
        from_attributes = True


# --- Filter schemas ---

class ReceiptFilter(BaseModel):
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    category: Optional[ReceiptCategory] = None
    tag_ids: Optional[list[int]] = None
    seller_name: Optional[str] = None
    min_amount: Optional[float] = None
    max_amount: Optional[float] = None


# --- Export schemas ---

class ExportRequest(BaseModel):
    format: str = "json"  # json, csv
    filters: Optional[ReceiptFilter] = None
