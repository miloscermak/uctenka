"""Export functionality for receipts."""

import csv
import json
import io
from datetime import datetime

from . import models


def receipts_to_json(receipts: list[models.Receipt]) -> str:
    """Export receipts to JSON format."""
    data = []
    for receipt in receipts:
        receipt_data = {
            "id": receipt.id,
            "datum": receipt.date.isoformat() if receipt.date else None,
            "celkova_suma": receipt.total_amount,
            "mena": receipt.currency,
            "prodejce": {
                "nazev": receipt.seller_name,
                "dic": receipt.seller_tax_id,
                "ico": receipt.seller_business_id,
                "adresa": receipt.seller_address,
            },
            "dph_celkem": receipt.total_vat,
            "cena_bez_dph": receipt.total_without_vat,
            "kategorie": receipt.category.value if receipt.category else None,
            "poznamka": receipt.note,
            "tagy": [tag.name for tag in receipt.tags],
            "polozky": [
                {
                    "nazev": item.name,
                    "mnozstvi": item.quantity,
                    "cena_za_kus": item.unit_price,
                    "cena_celkem": item.total_price,
                    "sazba_dph": item.vat_rate,
                    "dph": item.vat_amount,
                    "cena_bez_dph": item.price_without_vat,
                }
                for item in receipt.items
            ],
            "vytvoreno": receipt.created_at.isoformat() if receipt.created_at else None,
        }
        data.append(receipt_data)

    return json.dumps(data, ensure_ascii=False, indent=2)


def receipts_to_csv(receipts: list[models.Receipt]) -> str:
    """Export receipts to CSV format (summary view)."""
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "ID",
        "Datum",
        "Prodejce",
        "DIČ",
        "Celková suma",
        "Měna",
        "DPH",
        "Cena bez DPH",
        "Kategorie",
        "Tagy",
        "Poznámka",
    ])

    # Data rows
    for receipt in receipts:
        writer.writerow([
            receipt.id,
            receipt.date.strftime("%Y-%m-%d") if receipt.date else "",
            receipt.seller_name or "",
            receipt.seller_tax_id or "",
            receipt.total_amount or "",
            receipt.currency,
            receipt.total_vat or "",
            receipt.total_without_vat or "",
            receipt.category.value if receipt.category else "",
            ", ".join(tag.name for tag in receipt.tags),
            receipt.note or "",
        ])

    return output.getvalue()


def receipts_to_csv_detailed(receipts: list[models.Receipt]) -> str:
    """Export receipts to CSV format with item details (one row per item)."""
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "ID účtenky",
        "Datum",
        "Prodejce",
        "DIČ",
        "Kategorie",
        "Položka",
        "Množství",
        "Cena/ks",
        "Cena celkem",
        "Sazba DPH %",
        "DPH",
        "Cena bez DPH",
        "Měna",
    ])

    # Data rows
    for receipt in receipts:
        if receipt.items:
            for item in receipt.items:
                writer.writerow([
                    receipt.id,
                    receipt.date.strftime("%Y-%m-%d") if receipt.date else "",
                    receipt.seller_name or "",
                    receipt.seller_tax_id or "",
                    receipt.category.value if receipt.category else "",
                    item.name,
                    item.quantity,
                    item.unit_price or "",
                    item.total_price or "",
                    item.vat_rate or "",
                    item.vat_amount or "",
                    item.price_without_vat or "",
                    receipt.currency,
                ])
        else:
            # Receipt without items - still include summary row
            writer.writerow([
                receipt.id,
                receipt.date.strftime("%Y-%m-%d") if receipt.date else "",
                receipt.seller_name or "",
                receipt.seller_tax_id or "",
                receipt.category.value if receipt.category else "",
                "(bez položek)",
                "",
                "",
                receipt.total_amount or "",
                "",
                receipt.total_vat or "",
                receipt.total_without_vat or "",
                receipt.currency,
            ])

    return output.getvalue()
