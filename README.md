# Feiras Livres — São Paulo

Interactive map of all 822 street fairs (*feiras livres*) in the city of São Paulo, extracted from the official PDF published by the municipal government.

**[→ Open the map](https://mikephn.github.io/SPFeiras/feiras_map.html)**

## Features

- All 822 fairs plotted on a map of São Paulo
- Filter by day of the week
- Hover (desktop) or tap (mobile) a marker to see the fair name, address, neighbourhood, category, number of vendors, and district
- Markers are clustered at lower zoom levels for readability

## How it works

1. `extract.py` — parses the PDF, geocodes each address using the Google Maps API (with Nominatim as fallback), and saves the results to `feiras.json`
2. `build.py` — reads `feiras.json` and generates the self-contained `feiras_map.html`
3. `main.py` — runs a local Flask server for development (`uv run python main.py`)

## Running locally

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv run python main.py
# open http://localhost:5000
```

To re-extract from a new PDF:

```bash
export GOOGLE_MAPS_API_KEY="your-key"
uv run python extract.py
uv run python build.py
```
