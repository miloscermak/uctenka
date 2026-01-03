"""Receipt scanner using Claude API."""

import anthropic
import base64
import json
from datetime import datetime
from pathlib import Path


def get_image_media_type(file_path: Path) -> str:
    """Determine MIME type from file extension."""
    suffix = file_path.suffix.lower()
    media_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    return media_types.get(suffix, "image/jpeg")


def load_image_as_base64(file_path: Path) -> str:
    """Load image and encode to base64."""
    with open(file_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def parse_date(date_str: str | None) -> datetime | None:
    """Try to parse date string to datetime."""
    if not date_str:
        return None

    formats = [
        "%Y-%m-%d",
        "%d.%m.%Y",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y/%m/%d",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    return None


def parse_amount(amount_str: str | None) -> tuple[float | None, str]:
    """Parse amount string to float and currency."""
    if not amount_str:
        return None, "CZK"

    # Remove whitespace
    amount_str = amount_str.strip()

    # Detect currency
    currency = "CZK"
    currency_symbols = {
        "€": "EUR", "EUR": "EUR",
        "Kč": "CZK", "CZK": "CZK",
        "$": "USD", "USD": "USD",
        "£": "GBP", "GBP": "GBP",
    }

    for symbol, curr in currency_symbols.items():
        if symbol in amount_str:
            currency = curr
            amount_str = amount_str.replace(symbol, "")
            break

    # Clean and parse number
    amount_str = amount_str.strip().replace(" ", "").replace(",", ".")

    try:
        return float(amount_str), currency
    except ValueError:
        return None, currency


def scan_receipt(image_path: Path) -> dict:
    """
    Scan a receipt image using Claude API.

    Returns parsed receipt data ready for database insertion.
    """
    client = anthropic.Anthropic()

    image_data = load_image_as_base64(image_path)
    media_type = get_image_media_type(image_path)

    prompt = """Analyzuj tuto účtenku a extrahuj následující informace ve formátu JSON:

{
    "datum": "datum nákupu ve formátu YYYY-MM-DD",
    "celkova_suma": "celková částka jako číslo",
    "mena": "měna (CZK, EUR, USD, atd.)",
    "produkty": [
        {
            "nazev": "název produktu",
            "mnozstvi": 1,
            "cena_za_kus": 0.00,
            "cena_celkem": 0.00,
            "sazba_dph": 21,
            "dph": 0.00,
            "cena_bez_dph": 0.00
        }
    ],
    "celkove_dph": 0.00,
    "cena_bez_dph": 0.00,
    "prodejce": {
        "nazev": "název prodejce/obchodu",
        "dic": "DIČ prodejce",
        "ico": "IČO prodejce",
        "adresa": "adresa prodejce"
    }
}

Pravidla:
- Všechny částky jako čísla (ne stringy)
- Datum ve formátu YYYY-MM-DD
- Pokud informace není dostupná, použij null
- U DPH dopočítej hodnoty pokud je známá sazba
- Vrať POUZE validní JSON bez dalšího textu"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )

    response_text = message.content[0].text

    # Extract JSON from response
    if "```json" in response_text:
        json_start = response_text.find("```json") + 7
        json_end = response_text.find("```", json_start)
        response_text = response_text[json_start:json_end].strip()
    elif "```" in response_text:
        json_start = response_text.find("```") + 3
        json_end = response_text.find("```", json_start)
        response_text = response_text[json_start:json_end].strip()

    raw_data = json.loads(response_text)

    # Transform to database format
    return transform_to_db_format(raw_data), response_text


def transform_to_db_format(raw_data: dict) -> dict:
    """Transform Claude response to database-ready format."""
    # Parse date
    date = parse_date(raw_data.get("datum"))

    # Get seller info
    seller = raw_data.get("prodejce", {}) or {}

    # Build receipt data
    receipt_data = {
        "date": date,
        "total_amount": raw_data.get("celkova_suma"),
        "currency": raw_data.get("mena", "CZK"),
        "seller_name": seller.get("nazev"),
        "seller_tax_id": seller.get("dic"),
        "seller_business_id": seller.get("ico"),
        "seller_address": seller.get("adresa"),
        "total_vat": raw_data.get("celkove_dph"),
        "total_without_vat": raw_data.get("cena_bez_dph"),
        "items": [],
    }

    # Transform items
    for item in raw_data.get("produkty", []):
        receipt_data["items"].append({
            "name": item.get("nazev", "Neznámá položka"),
            "quantity": item.get("mnozstvi", 1),
            "unit_price": item.get("cena_za_kus"),
            "total_price": item.get("cena_celkem"),
            "vat_rate": item.get("sazba_dph"),
            "vat_amount": item.get("dph"),
            "price_without_vat": item.get("cena_bez_dph"),
        })

    return receipt_data
