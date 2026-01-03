"""FastAPI application for Receipt Scanner."""

import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from . import crud, models, schemas, export
from .database import engine, get_db
from .scanner import scan_receipt

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Receipt Scanner API",
    description="API pro skenování a správu účtenek",
    version="1.0.0",
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

STATIC_DIR = Path(__file__).parent.parent / "static"


# --- User endpoints ---

@app.post("/users", response_model=schemas.UserResponse, tags=["users"])
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """Create a new user."""
    existing = crud.get_user_by_email(db, user.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db, user)


@app.get("/users/{user_id}", response_model=schemas.UserResponse, tags=["users"])
def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get user by ID."""
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# --- Tag endpoints ---

@app.get("/users/{user_id}/tags", response_model=list[schemas.TagResponse], tags=["tags"])
def get_tags(user_id: int, db: Session = Depends(get_db)):
    """Get all tags for a user."""
    return crud.get_tags(db, user_id)


@app.post("/users/{user_id}/tags", response_model=schemas.TagResponse, tags=["tags"])
def create_tag(user_id: int, tag: schemas.TagCreate, db: Session = Depends(get_db)):
    """Create a new tag for a user."""
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return crud.create_tag(db, user_id, tag)


@app.delete("/tags/{tag_id}", tags=["tags"])
def delete_tag(tag_id: int, db: Session = Depends(get_db)):
    """Delete a tag."""
    if not crud.delete_tag(db, tag_id):
        raise HTTPException(status_code=404, detail="Tag not found")
    return {"status": "deleted"}


# --- Receipt endpoints ---

@app.post("/users/{user_id}/receipts/scan", response_model=schemas.ReceiptResponse, tags=["receipts"])
async def scan_and_create_receipt(
    user_id: int,
    file: UploadFile = File(...),
    category: models.ReceiptCategory = Query(default=models.ReceiptCategory.PERSONAL),
    db: Session = Depends(get_db),
):
    """
    Upload a receipt image, scan it with AI, and save to database.
    """
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate file type
    allowed_types = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_types)}"
        )

    # Save uploaded file
    file_extension = Path(file.filename).suffix or ".jpg"
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = UPLOAD_DIR / unique_filename

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # Scan receipt
        receipt_data, raw_json = scan_receipt(file_path)
        receipt_data["category"] = category

        # Create receipt in database
        receipt = crud.create_receipt(
            db,
            user_id=user_id,
            receipt_data=receipt_data,
            image_path=str(file_path),
            raw_json=raw_json,
        )

        return receipt

    except Exception as e:
        # Clean up file on error
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Error scanning receipt: {str(e)}")


@app.get("/users/{user_id}/receipts", response_model=list[schemas.ReceiptListResponse], tags=["receipts"])
def get_receipts(
    user_id: int,
    date_from: datetime = None,
    date_to: datetime = None,
    category: models.ReceiptCategory = None,
    seller_name: str = None,
    min_amount: float = None,
    max_amount: float = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Get all receipts for a user with optional filters."""
    filters = schemas.ReceiptFilter(
        date_from=date_from,
        date_to=date_to,
        category=category,
        seller_name=seller_name,
        min_amount=min_amount,
        max_amount=max_amount,
    )
    return crud.get_receipts(db, user_id, filters, skip, limit)


@app.get("/receipts/{receipt_id}", response_model=schemas.ReceiptResponse, tags=["receipts"])
def get_receipt(receipt_id: int, db: Session = Depends(get_db)):
    """Get a specific receipt with all details."""
    receipt = crud.get_receipt(db, receipt_id)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return receipt


@app.patch("/receipts/{receipt_id}", response_model=schemas.ReceiptResponse, tags=["receipts"])
def update_receipt(
    receipt_id: int,
    update_data: schemas.ReceiptUpdate,
    db: Session = Depends(get_db),
):
    """Update receipt category, note, or tags."""
    receipt = crud.update_receipt(db, receipt_id, update_data)
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return receipt


@app.delete("/receipts/{receipt_id}", tags=["receipts"])
def delete_receipt(receipt_id: int, db: Session = Depends(get_db)):
    """Delete a receipt."""
    receipt = crud.get_receipt(db, receipt_id)
    if receipt and receipt.image_path:
        Path(receipt.image_path).unlink(missing_ok=True)

    if not crud.delete_receipt(db, receipt_id):
        raise HTTPException(status_code=404, detail="Receipt not found")
    return {"status": "deleted"}


# --- Export endpoints ---

@app.get("/users/{user_id}/receipts/export", tags=["export"])
def export_receipts(
    user_id: int,
    format: str = Query(default="json", regex="^(json|csv|csv_detailed)$"),
    date_from: datetime = None,
    date_to: datetime = None,
    category: models.ReceiptCategory = None,
    seller_name: str = None,
    min_amount: float = None,
    max_amount: float = None,
    db: Session = Depends(get_db),
):
    """
    Export receipts in JSON or CSV format.

    Formats:
    - json: Full JSON export
    - csv: Summary CSV (one row per receipt)
    - csv_detailed: Detailed CSV (one row per item)
    """
    filters = schemas.ReceiptFilter(
        date_from=date_from,
        date_to=date_to,
        category=category,
        seller_name=seller_name,
        min_amount=min_amount,
        max_amount=max_amount,
    )

    receipts = crud.get_receipts(db, user_id, filters, skip=0, limit=10000)

    if format == "json":
        content = export.receipts_to_json(receipts)
        media_type = "application/json"
        filename = "uctenky.json"
    elif format == "csv":
        content = export.receipts_to_csv(receipts)
        media_type = "text/csv"
        filename = "uctenky.csv"
    else:  # csv_detailed
        content = export.receipts_to_csv_detailed(receipts)
        media_type = "text/csv"
        filename = "uctenky_detail.csv"

    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# --- Health check ---

@app.get("/health", tags=["system"])
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# --- Static files and frontend ---

@app.get("/", include_in_schema=False)
def serve_frontend():
    """Serve the main frontend page."""
    return FileResponse(STATIC_DIR / "index.html")


# Mount static files (must be after all routes)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
