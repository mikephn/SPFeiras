"""
One-time script: parse "Endereços das Feiras Livres.pdf" → geocode → save feiras.json

Run with:  uv run python extract.py

If interrupted, re-running will resume geocoding from where it stopped.
"""

import json
import os
import time
import re
from pathlib import Path
from typing import Optional

import googlemaps
import pdfplumber
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

PDF_PATH = Path(__file__).parent / "Endereços das Feiras Livres.pdf"
OUTPUT_PATH = Path(__file__).parent / "feiras.json"

DAYS = {"SEG", "TER", "QUA", "QUI", "SEX", "SAB", "DOM"}

DAY_NAMES = {
    "SEG": "Segunda-feira",
    "TER": "Terça-feira",
    "QUA": "Quarta-feira",
    "QUI": "Quinta-feira",
    "SEX": "Sexta-feira",
    "SAB": "Sábado",
    "DOM": "Domingo",
}

STREET_PREFIX = {
    "AV": "Avenida",
    "RUA": "Rua",
    "PC": "Praça",
    "PCA": "Praça",
    "ES": "Estrada",
    "EST": "Estrada",
    "AL": "Alameda",
    "TRAV": "Travessa",
    "TV": "Travessa",
    "VD": "Viaduto",
    "LRG": "Largo",
    "ROD": "Rodovia",
    "ACESSO": "Acesso",
    "EX": "Avenida",   # Exalto — rare but present
}

# Mid-street honorific / title abbreviations
TITLE_ABBREVS = {
    "PROF": "Professor",
    "PROFA": "Professora",
    "DR": "Doutor",
    "DRA": "Doutora",
    "ENG": "Engenheiro",
    "ENGA": "Engenheira",
    "GAL": "General",
    "GEN": "General",
    "MAL": "Marechal",
    "CEL": "Coronel",
    "TEN": "Tenente",
    "CAP": "Capitão",
    "SGT": "Sargento",
    "AL": "Almirante",
    "COMEN": "Comendador",
    "COM": "Comendador",
    "MONS": "Monsenhor",
    "CARD": "Cardeal",
    "DOM": "Dom",
    "FRE": "Frei",
    "FR": "Frei",
    "PDE": "Padre",
    "PE": "Padre",
    "PADRE": "Padre",
    "PRES": "Presidente",
    "MIN": "Ministro",
    "DEP": "Deputado",
    "SEN": "Senador",
    "VER": "Vereador",
    "GOV": "Governador",
    "PREF": "Prefeito",
    "ARQ": "Arquiteto",
    "ADM": "Almirante",
    "BRIG": "Brigadeiro",
    "MJ": "Major",
    "BARON": "Barão",
    "COND": "Conde",
    "VIS": "Visconde",
    "CONS": "Conselheiro",
}

BAIRRO_PREFIX = {
    "VL": "Vila",
    "JD": "Jardim",
    "JDE": "Jardim",
    "PQ": "Parque",
    "CID": "Cidade",
    "PCA": "Praça",
    "PC": "Praça",
}

# Bounding box for São Paulo municipality (lat_min, lat_max, lng_min, lng_max)
SP_BOUNDS = (-24.01, -23.35, -47.0, -46.35)


def expand_titles(text: str) -> str:
    """Expand honorific abbreviations anywhere in a string and title-case the rest."""
    parts = text.split()
    expanded = []
    for part in parts:
        key = re.sub(r"[^A-Z]", "", part.upper())
        if key in TITLE_ABBREVS:
            expanded.append(TITLE_ABBREVS[key])
        else:
            # Title-case non-abbreviation words (keep prepositions lowercase)
            low = part.lower()
            if low in ("de", "da", "do", "dos", "das", "e", "a", "o", "em", "na", "no"):
                expanded.append(low)
            else:
                expanded.append(part.title())
    return " ".join(expanded)


def expand_street(raw: str) -> str:
    parts = raw.split()
    if not parts:
        return raw
    key = parts[0].upper()
    if key in STREET_PREFIX:
        parts[0] = STREET_PREFIX[key]
    return expand_titles(" ".join(parts))


def expand_bairro(raw: str) -> str:
    parts = raw.split()
    if not parts:
        return raw
    key = parts[0].upper()
    if key in BAIRRO_PREFIX:
        parts[0] = BAIRRO_PREFIX[key]
    # title-case remaining parts
    result = [parts[0]] + [p.title() for p in parts[1:]]
    return " ".join(result)


def build_geocode_candidates(prefix: str, rest: str, bairro: str) -> list[str]:
    """Return address strings to try from most to least specific."""
    full_street = f"{prefix} {rest}".strip()

    # Normalise "X C/ Y" (corner notation) — keep both parts as "street1, street2"
    corner_match = re.match(r"^(.+?)\s+C/\s+(.+)$", full_street, re.IGNORECASE)
    if corner_match:
        main_street = corner_match.group(1).strip()
        cross_street = corner_match.group(2).strip()
    else:
        main_street = full_street
        cross_street = None

    exp_full  = expand_street(full_street).replace(" C/ ", " e ")
    exp_main  = expand_street(main_street)
    exp_bairro = expand_bairro(bairro)

    candidates = [
        f"{exp_full}, {exp_bairro}, São Paulo, SP, Brasil",
        f"{exp_full}, São Paulo, SP, Brasil",
        f"{exp_main}, {exp_bairro}, São Paulo, SP, Brasil",
        f"{exp_main}, São Paulo, SP, Brasil",
    ]
    if cross_street:
        exp_cross = expand_street(cross_street)
        candidates.append(f"{exp_cross}, {exp_bairro}, São Paulo, SP, Brasil")
        candidates.append(f"{exp_cross}, São Paulo, SP, Brasil")

    candidates.append(f"{exp_bairro}, São Paulo, SP, Brasil")
    return candidates


def _in_sp(lat: float, lng: float) -> bool:
    return SP_BOUNDS[0] <= lat <= SP_BOUNDS[1] and SP_BOUNDS[2] <= lng <= SP_BOUNDS[3]


def geocode_google(gmaps: googlemaps.Client, address: str) -> Optional[tuple[float, float]]:
    try:
        results = gmaps.geocode(address, region="br")
        if results:
            loc = results[0]["geometry"]["location"]
            lat, lng = loc["lat"], loc["lng"]
            if _in_sp(lat, lng):
                return lat, lng
    except Exception as exc:
        print(f"    google error: {exc}")
    return None


def geocode_nominatim(geolocator: Nominatim, address: str) -> Optional[tuple[float, float]]:
    try:
        time.sleep(1.1)  # Nominatim: max 1 req/sec
        loc = geolocator.geocode(address, timeout=15)
        if loc:
            lat, lng = loc.latitude, loc.longitude
            if _in_sp(lat, lng):
                return lat, lng
    except (GeocoderTimedOut, GeocoderServiceError) as exc:
        print(f"    nominatim error: {exc}")
        time.sleep(3)
    return None


def geocode_feira(
    gmaps: Optional[googlemaps.Client],
    geolocator: Nominatim,
    feira: dict,
) -> tuple[Optional[float], Optional[float]]:
    candidates = build_geocode_candidates(
        feira["endereco_prefix"],
        feira["endereco_rest"],
        feira["bairro"],
    )
    for addr in candidates:
        if gmaps:
            result = geocode_google(gmaps, addr)
            if result:
                return result
        result = geocode_nominatim(geolocator, addr)
        if result:
            return result
    return None, None


def is_section_row(row: list) -> bool:
    """A section header row has only the first cell non-empty."""
    non_empty = [c for c in row if c and str(c).strip()]
    return len(non_empty) == 1 and str(row[0]).strip().upper() == str(row[0]).strip()


def is_column_header_row(row: list) -> bool:
    text = " ".join(str(c) for c in row if c).upper()
    return "DIA" in text and "CATEGORIA" in text


def parse_row(row: list, section: str) -> Optional[dict]:
    cells = [str(c).strip() if c else "" for c in row]
    if not any(cells):
        return None
    if is_column_header_row(cells):
        return None
    if cells[0].upper() not in DAYS:
        return None

    # Table has 7 columns: Dia | Categoria | Qnt | Nome | Prefix | AddressRest | Bairro
    while len(cells) < 7:
        cells.append("")

    return {
        "dia": cells[0].upper(),
        "dia_nome": DAY_NAMES.get(cells[0].upper(), cells[0]),
        "categoria": cells[1],
        "qnt_feirantes": cells[2],
        "nome": cells[3],
        "endereco_prefix": cells[4],
        "endereco_rest": cells[5],
        "endereco": f"{cells[4]} {cells[5]}".strip(),
        "bairro": cells[6],
        "regiao": section,
        "lat": None,
        "lng": None,
    }


def extract_from_pdf() -> list[dict]:
    feiras = []
    current_section = ""

    print(f"Opening {PDF_PATH.name} …")
    with pdfplumber.open(PDF_PATH) as pdf:
        print(f"  {len(pdf.pages)} pages")
        for page_num, page in enumerate(pdf.pages, 1):
            tables = page.extract_tables()
            if not tables:
                print(f"  Page {page_num}: no tables")
                continue

            for table in tables:
                for row in (table or []):
                    if not row:
                        continue
                    if is_section_row(row):
                        current_section = str(row[0]).strip()
                        continue
                    feira = parse_row(row, current_section)
                    if feira:
                        feiras.append(feira)

            print(f"  Page {page_num}: {sum(len(t) for t in tables)} rows → {len(feiras)} fairs so far")

    return feiras


def run_geocoding(feiras: list[dict]) -> None:
    # geocode anything without coordinates (new or previously failed)
    to_geocode = [f for f in feiras if f.get("lat") is None and f.get("endereco")]
    if not to_geocode:
        print("All fairs already geocoded.")
        return

    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    gmaps = googlemaps.Client(key=api_key) if api_key else None
    geolocator = Nominatim(user_agent="feiras_livres_sp_extractor_v1")

    if gmaps:
        print(f"\nGeocoding {len(to_geocode)} addresses (Google Maps primary, Nominatim fallback) …")
    else:
        print(f"\nGeocoding {len(to_geocode)} addresses via Nominatim only (set GOOGLE_MAPS_API_KEY for better results) …")

    for i, feira in enumerate(to_geocode, 1):
        print(f"  [{i}/{len(to_geocode)}] {feira['nome']}  —  {feira['endereco']}")
        lat, lng = geocode_feira(gmaps, geolocator, feira)
        feira["lat"] = lat
        feira["lng"] = lng
        if lat:
            print(f"    ✓ {lat:.5f}, {lng:.5f}")
        else:
            print(f"    ✗ not found")

        if i % 10 == 0:
            _save(feiras)
            print(f"    [saved checkpoint]")

    _save(feiras)


def _save(feiras: list[dict]) -> None:
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(feiras, f, ensure_ascii=False, indent=2)


def main() -> None:
    if OUTPUT_PATH.exists():
        print(f"Loading existing data from {OUTPUT_PATH.name} …")
        with open(OUTPUT_PATH, encoding="utf-8") as f:
            feiras = json.load(f)
        missing = sum(1 for f in feiras if f.get("lat") is None and f.get("endereco"))
        print(f"  {len(feiras)} fairs total, {missing} still need geocoding")
        if missing == 0:
            print("Nothing to do. Delete feiras.json to re-extract from PDF.")
            return
    else:
        feiras = extract_from_pdf()
        print(f"\nExtracted {len(feiras)} fairs.")
        if not feiras:
            print("ERROR: no fairs found — check PDF parsing output above.")
            return
        _save(feiras)
        print(f"Raw data saved to {OUTPUT_PATH.name}")

    run_geocoding(feiras)

    geocoded = sum(1 for f in feiras if f.get("lat") is not None)
    print(f"\nDone. {geocoded}/{len(feiras)} fairs geocoded.")
    print(f"Saved to {OUTPUT_PATH}")
    print("\nNow run:  uv run python main.py")


if __name__ == "__main__":
    main()
