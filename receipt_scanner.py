#!/usr/bin/env python3
"""
Receipt Scanner - Aplikace pro čtení účtenek pomocí Claude API.

Použití:
    python receipt_scanner.py <cesta_k_obrazku> [vystupni_soubor.json]

Vyžaduje nastavení proměnné prostředí ANTHROPIC_API_KEY.
"""

import anthropic
import base64
import json
import sys
from pathlib import Path


def get_image_media_type(file_path: Path) -> str:
    """Určí MIME typ obrázku podle přípony."""
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
    """Načte obrázek a zakóduje ho do base64."""
    with open(file_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def analyze_receipt(image_path: Path) -> dict:
    """
    Analyzuje účtenku pomocí Claude API.

    Vrací slovník s následujícími klíči:
    - datum: datum nákupu
    - celkova_suma: celková částka
    - produkty: seznam produktů s cenami
    - dph: informace o DPH
    - prodejce: informace o prodejci (jméno, DIČ)
    """
    client = anthropic.Anthropic()

    image_data = load_image_as_base64(image_path)
    media_type = get_image_media_type(image_path)

    prompt = """Analyzuj tuto účtenku a extrahuj následující informace ve formátu JSON:

{
    "datum": "datum nákupu ve formátu YYYY-MM-DD, nebo původní formát pokud nelze převést",
    "celkova_suma": "celková částka včetně měny",
    "produkty": [
        {
            "nazev": "název produktu",
            "cena": "cena produktu",
            "mnozstvi": "množství (pokud je uvedeno)"
        }
    ],
    "dph": {
        "zaklad_dane": "základ daně",
        "sazba": "sazba DPH v %",
        "castka_dph": "částka DPH"
    },
    "prodejce": {
        "nazev": "název prodejce/obchodu",
        "dic": "DIČ prodejce",
        "ico": "IČO prodejce (pokud je uvedeno)",
        "adresa": "adresa prodejce (pokud je uvedena)"
    }
}

Pokud některá informace není na účtence dostupná, použij hodnotu null.
Vrať POUZE validní JSON bez dalšího textu."""

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
                    {
                        "type": "text",
                        "text": prompt,
                    },
                ],
            }
        ],
    )

    response_text = message.content[0].text

    # Pokus o extrakci JSON z odpovědi
    try:
        # Zkusíme najít JSON v odpovědi (někdy může být obalený v markdown)
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            response_text = response_text[json_start:json_end].strip()
        elif "```" in response_text:
            json_start = response_text.find("```") + 3
            json_end = response_text.find("```", json_start)
            response_text = response_text[json_start:json_end].strip()

        return json.loads(response_text)
    except json.JSONDecodeError as e:
        return {
            "error": f"Nepodařilo se parsovat odpověď jako JSON: {e}",
            "raw_response": response_text,
        }


def save_results(data: dict, output_path: Path) -> None:
    """Uloží výsledky do JSON souboru."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    if len(sys.argv) < 2:
        print("Použití: python receipt_scanner.py <cesta_k_obrazku> [vystupni_soubor.json]")
        print("\nPříklad:")
        print("  python receipt_scanner.py uctenka.jpg")
        print("  python receipt_scanner.py uctenka.jpg vysledek.json")
        sys.exit(1)

    image_path = Path(sys.argv[1])

    if not image_path.exists():
        print(f"Chyba: Soubor '{image_path}' neexistuje.")
        sys.exit(1)

    # Výstupní soubor - buď zadaný, nebo odvozený z názvu obrázku
    if len(sys.argv) >= 3:
        output_path = Path(sys.argv[2])
    else:
        output_path = image_path.with_suffix(".json")

    print(f"Analyzuji účtenku: {image_path}")

    try:
        result = analyze_receipt(image_path)
        save_results(result, output_path)
        print(f"Výsledky uloženy do: {output_path}")
        print("\nExtrahovaná data:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except anthropic.APIError as e:
        print(f"Chyba API: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
