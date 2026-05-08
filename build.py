"""
Generates a standalone feiras_map.html with all fair data embedded.
Libraries are loaded from CDN — requires internet for both map tiles and scripts.

Run with:  uv run python build.py
"""

import json
from pathlib import Path

DATA_PATH   = Path(__file__).parent / "feiras.json"
OUTPUT_PATH = Path(__file__).parent / "feiras_map.html"


def main() -> None:
    if not DATA_PATH.exists():
        print("feiras.json not found — run extract.py first.")
        return

    with open(DATA_PATH, encoding="utf-8") as f:
        feiras = json.load(f)

    geocoded = [f for f in feiras if f.get("lat") is not None]
    print(f"Embedding {len(geocoded)}/{len(feiras)} fairs …")

    data_js = json.dumps(geocoded, ensure_ascii=False)
    html = build_html(data_js)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    kb = OUTPUT_PATH.stat().st_size // 1024
    print(f"Done → {OUTPUT_PATH.name}  ({kb} KB)")


def build_html(data_js: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0" />
  <title>Feiras Livres — São Paulo</title>

  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css" />

  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      display: flex;
      flex-direction: column;
      height: 100dvh;
      background: #111827;
      color: #f3f4f6;
    }}

    #toolbar {{
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 8px 14px;
      background: #1f2937;
      border-bottom: 1px solid #374151;
      flex-shrink: 0;
      flex-wrap: wrap;
    }}

    #toolbar h1 {{
      font-size: 0.95rem;
      font-weight: 700;
      color: #f9a825;
      white-space: nowrap;
    }}

    #day-filters {{
      display: flex;
      gap: 5px;
      flex-wrap: wrap;
      align-items: center;
    }}

    .day-btn {{
      padding: 3px 11px;
      border: 2px solid;
      border-radius: 999px;
      cursor: pointer;
      font-size: 0.72rem;
      font-weight: 600;
      transition: opacity 0.15s, transform 0.1s;
      background: transparent;
      color: #f3f4f6;
      -webkit-tap-highlight-color: transparent;
    }}
    .day-btn.active {{ opacity: 1; }}
    .day-btn:not(.active) {{ opacity: 0.28; }}
    .day-btn:active {{ transform: scale(0.95); }}

    #stats {{
      margin-left: auto;
      font-size: 0.75rem;
      color: #9ca3af;
      white-space: nowrap;
    }}

    #map {{ flex: 1; }}

    .leaflet-tooltip.feira-tip {{
      background: #1f2937;
      border: 1px solid #4b5563;
      color: #f3f4f6;
      border-radius: 8px;
      padding: 9px 13px;
      font-size: 0.78rem;
      line-height: 1.55;
      max-width: 280px;
      box-shadow: 0 6px 20px rgba(0,0,0,0.6);
      pointer-events: none;
    }}
    .leaflet-tooltip.feira-tip::before {{ display: none; }}

    .tip-name {{ font-weight: 700; font-size: 0.88rem; margin-bottom: 5px; }}
    .tip-row  {{ color: #9ca3af; }}
    .tip-row b {{ color: #e5e7eb; }}
    .tip-day  {{ display: inline-block; padding: 1px 7px; border-radius: 999px;
                font-size: 0.68rem; font-weight: 700; margin-bottom: 5px; }}

    /* Popup used on touch/mobile (tap) */
    .leaflet-popup-content-wrapper {{
      background: #1f2937;
      border: 1px solid #4b5563;
      color: #f3f4f6;
      border-radius: 10px;
      box-shadow: 0 6px 20px rgba(0,0,0,0.6);
    }}
    .leaflet-popup-content {{
      font-size: 0.82rem;
      line-height: 1.55;
      margin: 12px 14px;
    }}
    .leaflet-popup-tip {{ background: #1f2937; }}
    .leaflet-popup-close-button {{ color: #9ca3af !important; font-size: 1.1rem !important; }}
  </style>
</head>
<body>

<div id="toolbar">
  <h1>Feiras Livres — SP</h1>
  <div id="day-filters">
    <button class="day-btn active" id="btn-all"
            style="border-color:#6b7280;color:#d1d5db;">Todos</button>
  </div>
  <div id="stats"></div>
</div>

<div id="map"></div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
<script>
const FEIRAS = {data_js};

const DAY_ORDER  = ['SEG','TER','QUA','QUI','SEX','SAB','DOM'];
const DAY_LABELS = {{SEG:'Seg',TER:'Ter',QUA:'Qua',QUI:'Qui',SEX:'Sex',SAB:'Sáb',DOM:'Dom'}};
const DAY_COLORS = {{
  SEG:'#ef4444',TER:'#f97316',QUA:'#eab308',
  QUI:'#22c55e',SEX:'#06b6d4',SAB:'#3b82f6',DOM:'#a855f7'
}};

const isTouchDevice = () => window.matchMedia('(pointer: coarse)').matches;

// Map
const map = L.map('map').setView([-23.5505, -46.6333], 12);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
  attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
  maxZoom: 19,
}}).addTo(map);

// Cluster groups
const clusterGroups = {{}};
DAY_ORDER.forEach(day => {{
  const color = DAY_COLORS[day];
  clusterGroups[day] = L.markerClusterGroup({{
    maxClusterRadius: 50,
    iconCreateFunction(cluster) {{
      const n = cluster.getChildCount();
      const sz = n > 99 ? 38 : n > 9 ? 32 : 26;
      return L.divIcon({{
        html: `<div style="width:${{sz}}px;height:${{sz}}px;border-radius:50%;
          background:${{color}};border:2px solid rgba(255,255,255,0.8);
          display:flex;align-items:center;justify-content:center;
          font-weight:700;font-size:${{sz>30?12:10}}px;color:#fff;
          box-shadow:0 2px 6px rgba(0,0,0,0.5);">${{n}}</div>`,
        className:'', iconSize:[sz,sz], iconAnchor:[sz/2,sz/2],
      }});
    }},
  }});
}});

function esc(s) {{
  return String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}}

function makeContent(f) {{
  const color = DAY_COLORS[f.dia] || '#888';
  return `
    <div class="tip-name">${{esc(f.nome)}}</div>
    <span class="tip-day" style="background:${{color}}20;color:${{color}};border:1px solid ${{color}}40">${{esc(f.dia_nome)}}</span>
    <div class="tip-row"><b>Endereço:</b> ${{esc(f.endereco)}}</div>
    <div class="tip-row"><b>Bairro:</b> ${{esc(f.bairro)}}</div>
    <div class="tip-row"><b>Categoria:</b> ${{esc(f.categoria)}}</div>
    <div class="tip-row"><b>Feirantes:</b> ${{esc(f.qnt_feirantes)}}</div>
    ${{f.regiao ? `<div class="tip-row"><b>Região:</b> ${{esc(f.regiao)}}</div>` : ''}}
  `;
}}

// Build markers
FEIRAS.forEach(f => {{
  if (!clusterGroups[f.dia]) return;
  const color = DAY_COLORS[f.dia] || '#888';
  const marker = L.circleMarker([f.lat, f.lng], {{
    radius: 6, fillColor: color,
    color: 'rgba(255,255,255,0.7)', weight: 1.5,
    opacity: 1, fillOpacity: 0.9,
  }});

  const content = makeContent(f);

  if (isTouchDevice()) {{
    marker.bindPopup(content, {{ maxWidth: 280 }});
  }} else {{
    marker.bindTooltip(content, {{
      className: 'feira-tip', sticky: true, direction: 'top', offset: [0,-6],
    }});
  }}

  clusterGroups[f.dia].addLayer(marker);
}});

DAY_ORDER.forEach(day => clusterGroups[day].addTo(map));

// Day filter buttons
let activeDays = new Set(DAY_ORDER);
const container = document.getElementById('day-filters');
DAY_ORDER.forEach(day => {{
  const color = DAY_COLORS[day];
  const btn = document.createElement('button');
  btn.className = 'day-btn active';
  btn.dataset.day = day;
  btn.textContent = DAY_LABELS[day];
  btn.style.borderColor = color;
  btn.style.color = color;
  btn.addEventListener('click', () => {{
    if (activeDays.has(day)) {{
      activeDays.delete(day);
      map.removeLayer(clusterGroups[day]);
      btn.classList.remove('active');
    }} else {{
      activeDays.add(day);
      clusterGroups[day].addTo(map);
      btn.classList.add('active');
    }}
    document.getElementById('btn-all').classList.toggle('active', activeDays.size === DAY_ORDER.length);
    updateStats();
  }});
  container.appendChild(btn);
}});

document.getElementById('btn-all').addEventListener('click', () => {{
  const allOn = activeDays.size === DAY_ORDER.length;
  DAY_ORDER.forEach(day => {{
    if (allOn) {{ activeDays.delete(day); map.removeLayer(clusterGroups[day]); }}
    else        {{ activeDays.add(day);    clusterGroups[day].addTo(map); }}
  }});
  document.querySelectorAll('.day-btn[data-day]').forEach(b =>
    b.classList.toggle('active', !allOn));
  document.getElementById('btn-all').classList.toggle('active', !allOn);
  updateStats();
}});

function updateStats() {{
  const visible = DAY_ORDER.filter(d => activeDays.has(d))
    .reduce((n,d) => n + clusterGroups[d].getLayers().length, 0);
  document.getElementById('stats').textContent = visible + ' feiras';
}}
updateStats();
</script>
</body>
</html>"""


if __name__ == "__main__":
    main()
