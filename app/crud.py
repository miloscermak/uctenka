"""CRUD operations for database models."""

from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_

from . import models, schemas


# --- User operations ---

def get_user(db: Session, user_id: int) -> models.User | None:
    return db.query(models.User).filter(models.User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> models.User | None:
    return db.query(models.User).filter(models.User.email == email).first()


def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    db_user = models.User(email=user.email, name=user.name)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def get_or_create_user(db: Session, email: str, name: str = None) -> models.User:
    user = get_user_by_email(db, email)
    if not user:
        user = create_user(db, schemas.UserCreate(email=email, name=name))
    return user


# --- Tag operations ---

def get_tags(db: Session, user_id: int) -> list[models.Tag]:
    return db.query(models.Tag).filter(models.Tag.user_id == user_id).all()


def get_tag(db: Session, tag_id: int) -> models.Tag | None:
    return db.query(models.Tag).filter(models.Tag.id == tag_id).first()


def create_tag(db: Session, user_id: int, tag: schemas.TagCreate) -> models.Tag:
    db_tag = models.Tag(user_id=user_id, name=tag.name, color=tag.color)
    db.add(db_tag)
    db.commit()
    db.refresh(db_tag)
    return db_tag


def delete_tag(db: Session, tag_id: int) -> bool:
    tag = get_tag(db, tag_id)
    if tag:
        db.delete(tag)
        db.commit()
        return True
    return False


# --- Receipt operations ---

def get_receipt(db: Session, receipt_id: int) -> models.Receipt | None:
    return db.query(models.Receipt).filter(models.Receipt.id == receipt_id).first()


def get_receipts(
    db: Session,
    user_id: int,
    filters: schemas.ReceiptFilter = None,
    skip: int = 0,
    limit: int = 100
) -> list[models.Receipt]:
    query = db.query(models.Receipt).filter(models.Receipt.user_id == user_id)

    if filters:
        if filters.date_from:
            query = query.filter(models.Receipt.date >= filters.date_from)
        if filters.date_to:
            query = query.filter(models.Receipt.date <= filters.date_to)
        if filters.category:
            query = query.filter(models.Receipt.category == filters.category)
        if filters.seller_name:
            query = query.filter(
                models.Receipt.seller_name.ilike(f"%{filters.seller_name}%")
            )
        if filters.min_amount is not None:
            query = query.filter(models.Receipt.total_amount >= filters.min_amount)
        if filters.max_amount is not None:
            query = query.filter(models.Receipt.total_amount <= filters.max_amount)
        if filters.tag_ids:
            query = query.join(models.Receipt.tags).filter(
                models.Tag.id.in_(filters.tag_ids)
            )

    return query.order_by(models.Receipt.date.desc()).offset(skip).limit(limit).all()


def create_receipt(
    db: Session,
    user_id: int,
    receipt_data: dict,
    image_path: str = None,
    raw_json: str = None
) -> models.Receipt:
    """Create a receipt from scanned data."""
    # Extract items if present
    items_data = receipt_data.pop("items", [])
    tag_ids = receipt_data.pop("tag_ids", [])

    # Create receipt
    db_receipt = models.Receipt(
        user_id=user_id,
        image_path=image_path,
        raw_json=raw_json,
        **receipt_data
    )
    db.add(db_receipt)
    db.flush()  # Get the receipt ID

    # Add items
    for item_data in items_data:
        db_item = models.ReceiptItem(receipt_id=db_receipt.id, **item_data)
        db.add(db_item)

    # Add tags
    if tag_ids:
        tags = db.query(models.Tag).filter(models.Tag.id.in_(tag_ids)).all()
        db_receipt.tags = tags

    db.commit()
    db.refresh(db_receipt)
    return db_receipt


def update_receipt(
    db: Session,
    receipt_id: int,
    update_data: schemas.ReceiptUpdate
) -> models.Receipt | None:
    receipt = get_receipt(db, receipt_id)
    if not receipt:
        return None

    if update_data.category is not None:
        receipt.category = update_data.category
    if update_data.note is not None:
        receipt.note = update_data.note
    if update_data.tag_ids is not None:
        tags = db.query(models.Tag).filter(
            models.Tag.id.in_(update_data.tag_ids)
        ).all()
        receipt.tags = tags

    receipt.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(receipt)
    return receipt


def delete_receipt(db: Session, receipt_id: int) -> bool:
    receipt = get_receipt(db, receipt_id)
    if receipt:
        db.delete(receipt)
        db.commit()
        return True
    return False
