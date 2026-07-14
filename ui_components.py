"""
ui_components.py – reusable UI components: themed charts, KPIs, sidebar, export
"""
from __future__ import annotations

import io
from typing import Any, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from config import (
    AXIS_STYLE, CAT_COLS, CAT_COLORS, CAT_LABELS,
    AVAILABLE_SEASONS, BATTERS, PITCH_CATEGORIES,
    PITCH_COLORS, PITCH_TYPES, PLOTLY_BASE, LEGEND_DEFAULT,
)


# ─────────────────────────────────────────────────────────────────────────────
#  PLOTLY THEME HELPERS  (bez xaxis w update_layout → brak TypeError)
# ─────────────────────────────────────────────────────────────────────────────

# Klucze dict w PLOTLY_BASE – wszystkie wymagają merge zamiast nadpisania
_BASE_DICT_KEYS = {"font", "margin", "hoverlabel"}


def _apply_theme(fig: go.Figure, layout_kw: dict, x_angle: int | None = None) -> go.Figure:
    """
    Wewnętrzna funkcja aplikująca motyw.
    Bezpiecznie merguje WSZYSTKIE dict-type klucze z PLOTLY_BASE:
      font, margin, hoverlabel → merge zamiast TypeError
      legend                   → merge z LEGEND_DEFAULT
      xaxis / yaxis            → NIGDY w update_layout, zawsze update_xaxes/yaxes
    """
    base = dict(PLOTLY_BASE)

    # 1. Merge legend
    caller_legend  = layout_kw.pop("legend", {})
    base["legend"] = {**LEGEND_DEFAULT, **caller_legend}

    # 2. Merge pozostałych dict-type keys (margin, font, hoverlabel)
    for key in _BASE_DICT_KEYS:
        if key in layout_kw:
            base[key] = {**base.get(key, {}), **layout_kw.pop(key)}

    # 3. Upewnij się że title_font jest widoczny
    if "title" in layout_kw and isinstance(layout_kw["title"], str):
        layout_kw["title"] = dict(
            text=layout_kw["title"],
            font=dict(color="#e6edf3", size=13),
            x=0, xanchor="left",
        )

    fig.update_layout(**base, **layout_kw)

    ax = {**AXIS_STYLE}
    if x_angle is not None:
        ax["tickangle"] = x_angle
    fig.update_xaxes(**ax)
    fig.update_yaxes(**AXIS_STYLE)
    return fig


def themed(fig: go.Figure, **layout_kw: Any) -> go.Figure:
    """Aplikuje ciemny motyw bez konfliktu kluczy."""
    return _apply_theme(fig, layout_kw)


def themed_rot(fig: go.Figure, angle: int = -30, **layout_kw: Any) -> go.Figure:
    """Motyw + obrót etykiet X."""
    return _apply_theme(fig, layout_kw, x_angle=angle)


# ─────────────────────────────────────────────────────────────────────────────
#  SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────

class SidebarFilters:
    """Renderuje sidebar i przechowuje wartości filtrów."""

    def __init__(self, raw_df: pd.DataFrame) -> None:
        self._render(raw_df)

    def _render(self, raw_df: pd.DataFrame) -> None:
        with st.sidebar:
            st.markdown("### ⚾ Pitch Mix Analyzer")

            # ── Sezony ──────────────────────────────────────────────────────
            st.markdown("### 📅 Sezony")
            self.seasons: list[int] = st.multiselect(
                "Sezony", AVAILABLE_SEASONS, default=[2025, 2026],
                label_visibility="collapsed",
            )
            if not self.seasons:
                self.seasons = [2026]

            # ── Presets dat ─────────────────────────────────────────────────
            st.markdown("### 📆 Zakres dat")
            min_d = raw_df["game_date"].min().date()
            max_d = raw_df["game_date"].max().date()

            preset = st.radio(
                "Preset", ["Bieżący miesiąc", "Ostatnie 8 tyg.", "Pełny sezon", "Własny"],
                horizontal=False, label_visibility="collapsed",
                index=3,
            )
            import datetime
            today = max_d
            if preset == "Bieżący miesiąc":
                d_s = today.replace(day=1)
                d_e = today
            elif preset == "Ostatnie 8 tyg.":
                d_s = today - datetime.timedelta(weeks=8)
                d_e = today
            elif preset == "Pełny sezon":
                d_s = min_d
                d_e = max_d
            else:
                cols = st.columns(2)
                with cols[0]:
                    d_s = st.date_input("Od", value=min_d, min_value=min_d,
                                        max_value=max_d, label_visibility="visible")
                with cols[1]:
                    d_e = st.date_input("Do", value=max_d, min_value=min_d,
                                        max_value=max_d, label_visibility="visible")

            self.d_start = max(d_s, min_d)
            self.d_end   = min(d_e, max_d)
            if self.d_start > self.d_end:
                self.d_start, self.d_end = self.d_end, self.d_start

            # ── Progi ───────────────────────────────────────────────────────
            st.markdown("### 🎯 Progi")
            self.min_pitches: int = st.slider(
                "Min. narzutów / tydzień",    5, 80, 15, 5)
            self.min_prev: int    = st.slider(
                "Min. narzutów poprz. tydz.", 5, 80, 10, 5)

            # ── Pitcher / Batter search ──────────────────────────────────────
            st.markdown("### 🔍 Filtruj graczy")
            all_pitchers = sorted(raw_df["pitcher_name"].dropna().unique())
            all_batters  = sorted(raw_df["batter_name"].dropna().unique())

            pitcher_q = st.text_input("Szukaj pitcher", placeholder="np. Cole…",
                                      label_visibility="collapsed")
            filt_p = [p for p in all_pitchers if pitcher_q.lower() in p.lower()] \
                     if pitcher_q else all_pitchers
            self.sel_pitchers: list[str] = st.multiselect(
                "Pitcher", filt_p, placeholder="Wszyscy",
                label_visibility="collapsed", key="sb_pitchers",
            )

            batter_q = st.text_input("Szukaj batter", placeholder="np. Alvarez…",
                                     label_visibility="collapsed")
            filt_b = [b for b in all_batters if batter_q.lower() in b.lower()] \
                     if batter_q else all_batters
            self.sel_batters: list[str] = st.multiselect(
                "Batter", filt_b, placeholder="Wszyscy",
                label_visibility="collapsed", key="sb_batters",
            )

            # ── Pitch type ──────────────────────────────────────────────────
            st.markdown("### 🎳 Pitch type")
            avail_pt = sorted(raw_df["pitch_type"].dropna().unique())
            self.sel_pt: list[str] = st.multiselect(
                "Pitch type", avail_pt,
                format_func=lambda x: f"{x} – {PITCH_TYPES.get(x, x)}",
                placeholder="Wszystkie", label_visibility="collapsed",
            )

            st.divider()
            st.caption("Demo: dane syntetyczne.\nPodmień na `data/pitch_mix_RRRR.parquet`.")


# ─────────────────────────────────────────────────────────────────────────────
#  KPI CARDS
# ─────────────────────────────────────────────────────────────────────────────

def render_kpis(cards: list[dict]) -> None:
    """
    cards = [{"label": str, "value": str, "sub": str, "highlight": bool}, ...]
    """
    parts = []
    for c in cards:
        hl = " highlight" if c.get("highlight") else ""
        parts.append(
            f'<div class="kpi-card{hl}">'
            f'<div class="kpi-label">{c["label"]}</div>'
            f'<div class="kpi-value">{c["value"]}</div>'
            f'<div class="kpi-sub">{c.get("sub", "")}</div>'
            f'</div>'
        )
    st.markdown(
        f'<div class="kpi-row">{"".join(parts)}</div>',
        unsafe_allow_html=True,
    )


def section(title: str) -> None:
    st.markdown(f'<div class="section-hdr">{title}</div>', unsafe_allow_html=True)


def empty(msg: str = "Brak danych dla wybranych filtrów.") -> None:
    st.markdown(
        f'<div class="empty-state"><span class="icon">⚾</span>{msg}</div>',
        unsafe_allow_html=True,
    )


def insight_box(text: str) -> None:
    st.markdown(
        f'<div class="insight-box">{text}</div>',
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  EXPORT
# ─────────────────────────────────────────────────────────────────────────────

def export_csv(df: pd.DataFrame, filename: str, label: str = "⬇ CSV") -> None:
    st.download_button(
        label=label,
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
        use_container_width=False,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  CHART: Category trend (główny wykres profilu pałkarza)
# ─────────────────────────────────────────────────────────────────────────────

def chart_batter_trend(bw: pd.DataFrame, batter: str) -> go.Figure:
    """
    Line chart: FB%/BB%/OS%/Z79% per week dla jednego battera.
    """
    sub = bw[bw["batter_name"] == batter].sort_values("week_start")

    fig = go.Figure()
    for col in CAT_COLS:
        label = PITCH_CATEGORIES[col]["short"]
        full  = PITCH_CATEGORIES[col]["label"]
        color = CAT_COLORS[col]

        fig.add_trace(go.Scatter(
            x=sub["week_label_short"],
            y=sub[col],
            mode="lines+markers",
            name=label,
            line=dict(color=color, width=2.5),
            marker=dict(size=7, color=color,
                        line=dict(color="#0d1117", width=1.5)),
            customdata=sub[["week_label", "total"]].values,
            hovertemplate=(
                f"<b>{full}</b><br>"
                "Tydzień: %{customdata[0]}<br>"
                "<b>%{y:.1f}%</b> pitchy do battera<br>"
                "Łącznie pitchy: %{customdata[1]}"
                "<extra></extra>"
            ),
        ))

    return themed(
        fig,
        height=380,
        title=f"Tygodniowy mix rzucony do: {batter}",
        xaxis_title="Tydzień",
        yaxis_title="Udział (%)",
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.04,
            xanchor="left", x=0,
            font=dict(size=11, color="#c9d1d9"),
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
#  CHART: Delta bar (zmiany tygodniowe)
# ─────────────────────────────────────────────────────────────────────────────

def chart_batter_delta_bars(bd: pd.DataFrame, batter: str) -> go.Figure:
    """Grouped bar chart: zmiana każdej kategorii tydzień do tygodnia."""
    sub = bd[bd["batter_name"] == batter].sort_values("week_start")
    if sub.empty:
        return go.Figure()

    fig = go.Figure()
    d_map = {
        "d_fb":  ("FB%",  CAT_COLORS["fb_pct"]),
        "d_bb":  ("BB%",  CAT_COLORS["bb_pct"]),
        "d_os":  ("OS%",  CAT_COLORS["os_pct"]),
        "d_z79": ("Z79%", CAT_COLORS["z79_pct"]),
    }
    for col, (lbl, color) in d_map.items():
        if col not in sub.columns:
            continue
        fig.add_trace(go.Bar(
            name=lbl,
            x=sub["week_label_short"],
            y=sub[col],
            marker_color=color,
            opacity=0.85,
            hovertemplate=(
                f"<b>{lbl} Δ</b><br>"
                "Tydzień: %{x}<br>"
                "Zmiana: <b>%{y:+.1f} pp</b>"
                "<extra></extra>"
            ),
        ))

    return themed(
        fig,
        height=300,
        barmode="group",
        title=f"Zmiany tydzień-do-tygodnia · {batter}",
        xaxis_title="Tydzień",
        yaxis_title="Δ (pp)",
        bargap=0.15,
        bargroupgap=0.05,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  CHART: Heatmap kategorii (week × category)
# ─────────────────────────────────────────────────────────────────────────────

def chart_batter_heatmap(bw: pd.DataFrame, batter: str) -> go.Figure:
    """Heatmapa tygodnie × kategorie, kolor = % wartości."""
    sub = bw[bw["batter_name"] == batter].sort_values("week_start")
    if sub.empty:
        return go.Figure()

    z_data    = sub[CAT_COLS].T.values
    x_labels  = sub["week_label_short"].tolist()
    y_labels  = [PITCH_CATEGORIES[c]["short"] for c in CAT_COLS]
    text_data = np.round(z_data, 1)

    fig = go.Figure(go.Heatmap(
        z=z_data,
        x=x_labels,
        y=y_labels,
        colorscale=[
            [0.0, "#0d1117"], [0.2, "#1a2a1a"],
            [0.5, "#ff6b35"], [0.8, "#ffd166"],
            [1.0, "#ffffff"],
        ],
        zmin=0, zmax=80,
        text=text_data,
        texttemplate="%{text:.1f}%",
        textfont=dict(size=11, family="JetBrains Mono"),
        hovertemplate="Kategoria: %{y}<br>Tydzień: %{x}<br>%: %{z:.1f}%<extra></extra>",
        showscale=True,
        colorbar=dict(
            title="%",
            tickfont=dict(color="#7d8590"),
            title_font=dict(color="#7d8590"),
            thickness=12, len=0.8,
        ),
    ))
    themed_rot(fig, angle=-30,
               height=220,
               title=f"Heatmapa pitch mix · {batter}",
               xaxis_title="", yaxis_title="")
    return fig


# ─────────────────────────────────────────────────────────────────────────────
#  CHART: Adjustment Score ranking
# ─────────────────────────────────────────────────────────────────────────────

def chart_adj_score_ranking(bd: pd.DataFrame, top_n: int = 15) -> go.Figure:
    """Ranking pałkarzy wg max Adjustment Score."""
    rank = (
        bd.groupby("batter_name")["adj_score"]
          .max()
          .sort_values(ascending=True)
          .tail(top_n)
          .reset_index()
    )
    q75 = rank["adj_score"].quantile(0.75)
    q50 = rank["adj_score"].quantile(0.50)
    colors = [
        "#ff6b35" if v >= q75 else "#ffd166" if v >= q50 else "#4cc9f0"
        for v in rank["adj_score"]
    ]
    fig = go.Figure(go.Bar(
        x=rank["adj_score"],
        y=rank["batter_name"],
        orientation="h",
        marker_color=colors,
        text=rank["adj_score"].round(1),
        texttemplate="  %{text:.1f}",
        textposition="outside",
        cliponaxis=False,
        textfont=dict(color="#c9d1d9", size=11),
        hovertemplate="<b>%{y}</b><br>Adj. Score: %{x:.1f}<extra></extra>",
    ))
    return themed(
        fig,
        height=max(340, top_n * 30),
        title="Ranking: Adjustment Score",
        xaxis_title="Adjustment Score",
        yaxis_title="",
        margin=dict(r=80),   # miejsce na etykiety
    )


# ─────────────────────────────────────────────────────────────────────────────
#  CHART: Comparison – kategorie dla 2-3 batters
# ─────────────────────────────────────────────────────────────────────────────

def chart_comparison(bw: pd.DataFrame, batters: list[str], cat_col: str) -> go.Figure:
    """Overlay line chart dla wybranych batters, jedna kategoria."""
    label = PITCH_CATEGORIES[cat_col]["short"]
    full  = PITCH_CATEGORIES[cat_col]["label"]
    colors_comp = ["#ff6b35", "#4cc9f0", "#39d353", "#bc8cff"]

    fig = go.Figure()
    for i, b in enumerate(batters):
        sub = bw[bw["batter_name"] == b].sort_values("week_start")
        if sub.empty:
            continue
        fig.add_trace(go.Scatter(
            x=sub["week_label_short"],
            y=sub[cat_col],
            mode="lines+markers",
            name=b,
            line=dict(color=colors_comp[i % len(colors_comp)], width=2.5),
            marker=dict(size=7),
            hovertemplate=f"<b>{b}</b><br>Tydzień: %{{x}}<br>{label}: %{{y:.1f}}%<extra></extra>",
        ))

    themed(fig,
           height=340,
           title=f"Porównanie: {full}",
           xaxis_title="Tydzień",
           yaxis_title=f"{label} (%)",
           hovermode="x unified")
    return fig


# ─────────────────────────────────────────────────────────────────────────────
#  CHART: Matchup line + heatmap
# ─────────────────────────────────────────────────────────────────────────────

def chart_matchup_line(mw: pd.DataFrame, pitcher: str, batter: str) -> go.Figure:
    """Trend per pitch type dla jednego matchupu pitcher × batter."""
    sub = mw[
        (mw["pitcher_name"] == pitcher) & (mw["batter_name"] == batter)
    ].sort_values("week_start")

    fig = go.Figure()
    for pt in sorted(sub["pitch_type"].unique()):
        ptd = sub[sub["pitch_type"] == pt]
        fig.add_trace(go.Scatter(
            x=ptd["week_label_short"],
            y=ptd["pitch_pct"],
            mode="lines+markers",
            name=f"{pt} – {PITCH_TYPES.get(pt, pt)}",
            line=dict(color=PITCH_COLORS.get(pt, "#aaa"), width=2.5),
            marker=dict(size=7),
            customdata=ptd[["week_label", "pitch_pct", "total"]].values,
            hovertemplate=(
                f"<b>{pt}</b><br>"
                "Tydzień: %{customdata[0]}<br>"
                "%: %{y:.1f}%<br>"
                "Total pitchy: %{customdata[2]}<extra></extra>"
            ),
        ))

    themed(fig,
           height=360,
           title=f"{pitcher} → {batter}: pitch mix per tydzień",
           xaxis_title="Tydzień",
           yaxis_title="Udział (%)",
           hovermode="x unified")
    return fig


def chart_matchup_heatmap(mw: pd.DataFrame, pitcher: str, batter: str) -> go.Figure:
    """Heatmapa pitch types × tygodnie dla jednego matchupu."""
    sub = mw[
        (mw["pitcher_name"] == pitcher) & (mw["batter_name"] == batter)
    ].sort_values("week_start")

    pivot = (
        sub.pivot_table(index="pitch_type", columns="week_label_short",
                        values="pitch_pct", aggfunc="sum")
           .fillna(0)
    )
    pivot = pivot.loc[pivot.mean(axis=1).sort_values(ascending=False).index]
    pivot.index = [f"{pt} – {PITCH_TYPES.get(pt, pt)}" for pt in pivot.index]

    fig = go.Figure(go.Heatmap(
        z=pivot.values,
        x=list(pivot.columns),
        y=pivot.index.tolist(),
        colorscale=[
            [0, "#0d1117"], [0.25, "#1a3a5c"],
            [0.55, "#ff6b35"], [0.8, "#ffd166"], [1, "#fff"],
        ],
        zmin=0, zmax=80,
        text=np.round(pivot.values, 1),
        texttemplate="%{text:.1f}%",
        textfont=dict(size=10, family="JetBrains Mono"),
        hovertemplate="Pitch: %{y}<br>Tydzień: %{x}<br>%: %{z:.1f}%<extra></extra>",
        showscale=True,
        colorbar=dict(thickness=10, title="%",
                      tickfont=dict(color="#7d8590"),
                      title_font=dict(color="#7d8590")),
    ))
    themed_rot(fig, angle=-30,
               height=max(240, len(pivot) * 48 + 80),
               title=f"Heatmapa: {pitcher} → {batter}",
               xaxis_title="", yaxis_title="")
    return fig


# ─────────────────────────────────────────────────────────────────────────────
#  CHART: Biggest matchup changes (Tab Zmiany)
# ─────────────────────────────────────────────────────────────────────────────

def chart_biggest_changes(md: pd.DataFrame, top_n: int = 20) -> go.Figure:
    if md.empty:
        return go.Figure()
    bar = md.head(top_n).copy()
    bar["label"] = bar["Pitcher"] + " → " + bar["Batter"]
    bar["color"] = bar["Δ pp"].apply(lambda x: "#39d353" if x > 0 else "#f85149")

    fig = go.Figure(go.Bar(
        x=bar["Δ pp"],
        y=bar["label"],
        orientation="h",
        marker_color=bar["color"],
        text=bar.apply(lambda r: f"{r['Pitch Name']} {r['Δ pp']:+.1f}pp", axis=1),
        textposition="outside",
        cliponaxis=False,
        textfont=dict(color="#c9d1d9", size=10),
        customdata=np.stack([
            bar["Pitch Name"], bar["Now %"], bar["Prev %"],
            bar["Pitches"], bar["Week"].str.split("\n").str[0],
        ], axis=-1),
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Pitch: %{customdata[0]}<br>"
            "Teraz: %{customdata[1]:.1f}% · Poprzednio: %{customdata[2]:.1f}%<br>"
            "Δ: <b>%{x:+.1f} pp</b><br>"
            "Pitchy: %{customdata[3]} · Tydzień: %{customdata[4]}"
            "<extra></extra>"
        ),
    ))
    return themed(
        fig,
        height=max(420, top_n * 27),
        title=f"Top {top_n} zmian pitch mix (pitcher → batter)",
        xaxis_title="Δ (pp)",
        yaxis_title="",
        margin=dict(r=160),
    )
