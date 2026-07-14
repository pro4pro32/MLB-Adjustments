"""
config.py – stałe, kolory, profile, CSS, motyw Plotly
"""
from __future__ import annotations

# ── Pitch types ──────────────────────────────────────────────────────────────
PITCH_TYPES: dict[str, str] = {
    "FF": "Four-Seam Fastball",
    "SI": "Sinker",
    "FC": "Cutter",
    "SL": "Slider",
    "CU": "Curveball",
    "KC": "Knuckle-Curve",
    "ST": "Sweeper",
    "CH": "Changeup",
    "FS": "Splitter",
}

PITCH_COLORS: dict[str, str] = {
    "FF": "#ff6b35",
    "SI": "#ff9a3c",
    "FC": "#ffd166",
    "SL": "#06d6a0",
    "CU": "#118ab2",
    "KC": "#4cc9f0",
    "ST": "#38b000",
    "CH": "#bc8cff",
    "FS": "#f72585",
}

# ── Kategorie agregowane ─────────────────────────────────────────────────────
PITCH_CATEGORIES: dict[str, dict] = {
    "fb_pct":  {"label": "Fastball %",      "short": "FB%",   "types": ["FF", "SI", "FC"], "color": "#ff6b35"},
    "bb_pct":  {"label": "Breaking Ball %", "short": "BB%",   "types": ["SL", "CU", "KC", "ST"], "color": "#58a6ff"},
    "os_pct":  {"label": "Offspeed %",      "short": "OS%",   "types": ["CH", "FS"],       "color": "#bc8cff"},
    "z79_pct": {"label": "Zone 7-9 %",      "short": "Z79%",  "types": None,               "color": "#39d353"},
}

CAT_COLS   = list(PITCH_CATEGORIES.keys())                    # ["fb_pct", "bb_pct", "os_pct", "z79_pct"]
CAT_LABELS = {k: v["short"] for k, v in PITCH_CATEGORIES.items()}  # {"fb_pct": "FB%", ...}
CAT_COLORS = {k: v["color"] for k, v in PITCH_CATEGORIES.items()}

# ── Strefy Statcast ──────────────────────────────────────────────────────────
ALL_ZONES     = list(range(1, 10)) + list(range(11, 15))
ZONE_LOW      = [7, 8, 9]   # Zone 7-9 = dolny rząd

# Wagi stref per pitch type [top, middle, low, outside]
ZONE_WEIGHTS: dict[str, list[float]] = {
    "FF": [0.20, 0.35, 0.25, 0.20],
    "SI": [0.08, 0.22, 0.45, 0.25],
    "FC": [0.15, 0.35, 0.25, 0.25],
    "SL": [0.12, 0.25, 0.33, 0.30],
    "CU": [0.08, 0.15, 0.42, 0.35],
    "KC": [0.08, 0.15, 0.42, 0.35],
    "ST": [0.08, 0.18, 0.38, 0.36],
    "CH": [0.08, 0.22, 0.38, 0.32],
    "FS": [0.08, 0.18, 0.42, 0.32],
}

# ── Profile pitcherów ────────────────────────────────────────────────────────
PITCHER_PROFILES: dict[str, dict] = {
    "Gerrit Cole":      {"primary": "FF", "secondary": ["SL", "CH", "KC"]},
    "Sandy Alcantara":  {"primary": "SI", "secondary": ["SL", "CH", "FF"]},
    "Spencer Strider":  {"primary": "FF", "secondary": ["SL"]},
    "Zack Wheeler":     {"primary": "FF", "secondary": ["SL", "CU", "CH"]},
    "Kevin Gausman":    {"primary": "FC", "secondary": ["FS", "FF", "SL"]},
    "Pablo Lopez":      {"primary": "CH", "secondary": ["FF", "SI", "SL"]},
    "Corbin Burnes":    {"primary": "FC", "secondary": ["SL", "CU", "SI"]},
    "Framber Valdez":   {"primary": "SI", "secondary": ["CU", "CH", "FF"]},
    "Logan Gilbert":    {"primary": "FF", "secondary": ["SL", "CU", "CH"]},
    "Luis Castillo":    {"primary": "FF", "secondary": ["SL", "CH", "SI"]},
    "Yu Darvish":       {"primary": "SL", "secondary": ["FF", "CU", "CH", "FC"]},
    "Max Fried":        {"primary": "FF", "secondary": ["SL", "CU", "CH"]},
    "Dylan Cease":      {"primary": "SL", "secondary": ["FF", "CU", "CH"]},
    "Shane Bieber":     {"primary": "FF", "secondary": ["SL", "CU", "CH"]},
    "Shohei Ohtani":    {"primary": "FF", "secondary": ["SL", "CU", "FS"]},
    "Kodai Senga":      {"primary": "FS", "secondary": ["FF", "CU", "ST"]},
    "Tarik Skubal":     {"primary": "FF", "secondary": ["CH", "SL", "CU"]},
    "Chris Sale":       {"primary": "FF", "secondary": ["SL", "CH", "CU"]},
}

BATTERS: list[str] = [
    # Aktywni gracze 2024-2026
    "Freddie Freeman", "Mookie Betts", "Ronald Acuna Jr.", "Corey Seager",
    "Trea Turner", "Jose Ramirez", "Yordan Alvarez", "Kyle Tucker",
    "Juan Soto", "Pete Alonso", "Michael Harris II", "Austin Riley",
    "Nolan Arenado", "Paul Goldschmidt", "William Contreras",
    "Bo Bichette", "Vladimir Guerrero Jr.", "Matt Olson",
    "Gunnar Henderson", "Adley Rutschman", "Julio Rodriguez",
    "Steven Kwan", "Elly De La Cruz", "Jackson Merrill",
    "Jackson Chourio", "Francisco Lindor", "Bryce Harper",
    "CJ Abrams", "Spencer Torkelson", "Adolis Garcia",
]

# Gracze nieaktywni (zawieszeni, kontuzja długoterminowa, emerytura) per sezon
# Klucz = rok, wartość = set nazwisk do wykluczenia z generatora
INACTIVE_BY_SEASON: dict[int, set[str]] = {
    2024: {"Wander Franco"},            # zawieszony bezterminowo od VIII 2023
    2025: {"Wander Franco"},
    2026: {"Wander Franco"},
}

AVAILABLE_SEASONS: list[int] = [2022, 2023, 2024, 2025, 2026]

# ── Plotly – motyw bazowy (BEZ xaxis/yaxis – to powoduje błąd!) ──────────────
PLOTLY_BASE: dict = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", color="#c9d1d9", size=12),
    margin=dict(l=20, r=20, t=48, b=20),
    hoverlabel=dict(
        bgcolor="#161b22",
        bordercolor="#30363d",
        font=dict(color="#e6edf3", size=12),
    ),
)

# Domyślny legend – stosowany przez themed(), nadpisywalny per-chart
LEGEND_DEFAULT: dict = dict(
    bgcolor="rgba(22,27,34,0.9)",
    bordercolor="#30363d",
    borderwidth=1,
    font=dict(size=11),
)

AXIS_STYLE: dict = dict(
    gridcolor="#21262d",
    linecolor="#30363d",
    tickfont=dict(size=11, color="#c9d1d9"),
    title_font=dict(size=12, color="#c9d1d9"),
    zeroline=False,
    automargin=True,        # prevents label clipping
)

# ── CSS ───────────────────────────────────────────────────────────────────────
APP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

:root {
    --bg:      #0d1117;  --bg2:    #161b22;  --bg3:    #21262d;
    --border:  #30363d;  --green:  #39d353;  --red:    #f85149;
    --yellow:  #e3b341;  --blue:   #58a6ff;  --purple: #bc8cff;
    --text:    #e6edf3;  --muted:  #7d8590;  --accent: #ff6b35;
    --accent2: #ffd166;
}
html, body, [class*="css"] {
    background-color: var(--bg) !important;
    color: var(--text) !important;
    font-family: 'Inter', sans-serif;
}
/* Sidebar */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d1117 0%, #111820 100%) !important;
    border-right: 1px solid var(--border);
}
section[data-testid="stSidebar"] * { color: var(--text) !important; }
section[data-testid="stSidebar"] .stMarkdown h3 {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 1rem;
    letter-spacing: 2px;
    color: var(--accent) !important;
    border-bottom: 1px solid var(--border);
    padding-bottom: 4px;
    margin: 16px 0 8px 0;
}
/* Inputs */
div[data-testid="stSelectbox"] > div,
div[data-testid="stMultiSelect"] > div,
div[data-testid="stTextInput"] > div > div {
    background-color: var(--bg3) !important;
    border-color: var(--border) !important;
    border-radius: 8px !important;
}
div[data-testid="stSlider"] > div { color: var(--text) !important; }
/* Tabs */
div[data-testid="stTabs"] > div > div > button {
    font-family: 'Inter', sans-serif;
    font-weight: 600;
    font-size: 0.82rem;
    color: var(--muted) !important;
    border-radius: 6px 6px 0 0;
    padding: 8px 16px;
}
div[data-testid="stTabs"] > div > div > button[aria-selected="true"] {
    color: var(--accent) !important;
    border-bottom: 2px solid var(--accent) !important;
    background: var(--bg2) !important;
}
/* DataFrames */
div[data-testid="stDataFrame"] {
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    overflow: hidden !important;
}
/* Info/Warning */
div[data-testid="stInfo"]    { background: #0d2137 !important; border-color: var(--blue) !important; }
div[data-testid="stWarning"] { background: #2d1f00 !important; border-color: var(--yellow) !important; }
div[data-testid="stError"]   { background: #2d0f0f !important; border-color: var(--red) !important; }
/* Custom classes */
.dash-header {
    background: linear-gradient(135deg, #1a0800 0%, #0d1117 40%, #001510 100%);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 28px 36px;
    margin-bottom: 24px;
    position: relative;
    overflow: hidden;
}
.dash-header::after {
    content: '⚾';
    position: absolute;
    right: 28px; top: 50%;
    transform: translateY(-50%);
    font-size: 96px;
    opacity: 0.06;
    pointer-events: none;
}
.dash-header h1 {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 2.6rem;
    letter-spacing: 4px;
    color: var(--accent) !important;
    margin: 0 0 6px 0;
    line-height: 1;
}
.dash-header .subtitle { color: var(--muted) !important; font-size: 0.88rem; margin: 0; }
.dash-header .badge {
    display: inline-block;
    background: rgba(255,107,53,0.15);
    border: 1px solid rgba(255,107,53,0.4);
    border-radius: 20px;
    padding: 3px 12px;
    font-size: 0.72rem;
    color: var(--accent) !important;
    font-family: 'JetBrains Mono', monospace;
    margin-top: 10px;
}
.kpi-row { display: flex; gap: 12px; margin: 0 0 24px 0; flex-wrap: wrap; }
.kpi-card {
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 16px 20px;
    flex: 1; min-width: 130px;
    transition: border-color 0.2s;
}
.kpi-card:hover { border-color: #444d56; }
.kpi-card .kpi-label {
    font-size: 0.68rem; color: var(--muted);
    text-transform: uppercase; letter-spacing: 1.2px;
    margin-bottom: 4px;
}
.kpi-card .kpi-value {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 2rem; color: var(--accent); line-height: 1.05;
}
.kpi-card .kpi-sub { font-size: 0.7rem; color: var(--muted); margin-top: 2px; }
.kpi-card.highlight { border-color: rgba(255,107,53,0.5); background: rgba(255,107,53,0.06); }
.section-hdr {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 1.2rem; letter-spacing: 2px;
    color: var(--yellow);
    border-bottom: 1px solid var(--border);
    padding-bottom: 6px;
    margin: 24px 0 14px 0;
}
.insight-box {
    background: linear-gradient(135deg, #0d2137, #111820);
    border: 1px solid #1a3a5c;
    border-left: 3px solid var(--blue);
    border-radius: 8px;
    padding: 12px 16px;
    margin: 12px 0;
    font-size: 0.84rem;
    color: var(--text) !important;
}
.insight-box .icon { font-size: 1.1rem; margin-right: 6px; }
.trend-up   { color: var(--green) !important; font-family: 'JetBrains Mono', monospace; font-weight: 600; }
.trend-down { color: var(--red)   !important; font-family: 'JetBrains Mono', monospace; font-weight: 600; }
.trend-neu  { color: var(--muted) !important; font-family: 'JetBrains Mono', monospace; }
.perf-pill {
    display: inline-block;
    background: #0d2137; border: 1px solid #1a3a5c;
    border-radius: 20px; padding: 4px 14px;
    font-size: 0.72rem; color: var(--blue);
    font-family: 'JetBrains Mono', monospace;
}
.cat-chip {
    display: inline-block; padding: 3px 10px;
    border-radius: 12px; font-size: 0.72rem;
    font-weight: 600; margin: 2px;
    font-family: 'JetBrains Mono', monospace;
}
.chip-fb  { background:#2d1a0a; color:#ff6b35; border:1px solid #ff6b35; }
.chip-bb  { background:#0a1a2d; color:#58a6ff; border:1px solid #58a6ff; }
.chip-os  { background:#1a0a2d; color:#bc8cff; border:1px solid #bc8cff; }
.chip-z79 { background:#0a2d1a; color:#39d353; border:1px solid #39d353; }
.empty-state {
    text-align: center; padding: 48px 24px;
    color: var(--muted); font-size: 0.9rem;
}
.empty-state .icon { font-size: 2.5rem; display: block; margin-bottom: 12px; }
</style>
"""
