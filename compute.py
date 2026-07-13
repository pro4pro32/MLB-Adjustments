"""
compute.py – cała logika obliczeniowa
Dwie perspektywy:
  • Batter-centric:  aggregate wszystkich pitcherów → tygodniowy mix DO pałkarza
  • Matchup-level:   pitcher × batter × tydzień
"""
from __future__ import annotations

import time
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

from config import CAT_COLS, PITCH_CATEGORIES, PITCH_TYPES, ZONE_LOW
from data_layer import floor_to_monday, make_week_labels


# ─────────────────────────────────────────────────────────────────────────────
#  1.  BATTER-CENTRIC  (główna perspektywa)
# ─────────────────────────────────────────────────────────────────────────────

def _compute_batter_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """
    Agreguje WSZYSTKICH pitcherów → tygodniowy pitch mix DO danego battera.
    Kolumny wynikowe:
      batter_name, week_start, week_label, week_label_short, season,
      total, fb_pct, bb_pct, os_pct, z79_pct,
      n_fb, n_bb, n_os, n_z79
    """
    d = df.copy()
    d["week_start"] = floor_to_monday(d["game_date"])
    d["is_z79"]     = d["zone"].isin(ZONE_LOW).astype(int)

    # Baza: total + z79
    base = (
        d.groupby(["batter_name", "week_start", "season"])
         .agg(total=("pitch_type", "count"), n_z79=("is_z79", "sum"))
         .reset_index()
    )

    # Każda kategoria pitch
    for col, info in PITCH_CATEGORIES.items():
        if info["types"] is None:
            continue
        cnt_col = col.replace("_pct", "")          # "fb_pct" → "fb"
        sub = (
            d[d["pitch_type"].isin(info["types"])]
            .groupby(["batter_name", "week_start"])
            .size()
            .reset_index(name=f"n_{cnt_col}")
        )
        base = base.merge(sub, on=["batter_name", "week_start"], how="left")
        base[f"n_{cnt_col}"] = base[f"n_{cnt_col}"].fillna(0)
        base[col] = (base[f"n_{cnt_col}"] / base["total"] * 100).round(1)

    # Zone 7-9
    base["z79_pct"] = (base["n_z79"] / base["total"] * 100).round(1)

    labels = make_week_labels(base["week_start"])
    result = base.merge(labels, on="week_start")
    # Pre-konwersja daty – przyspiesza filtrowanie 2.8x (unika .dt.date per call)
    result["week_date"] = result["week_start"].dt.date
    return result


def _compute_batter_deltas(bw: pd.DataFrame, min_pitches: int = 1) -> pd.DataFrame:
    """
    Week-to-week delta per batter per kategoria.
    Kluczowe kolumny:
      d_fb, d_bb, d_os, d_z79  – delta pp
      adj_score                 – reliability-weighted średnia |delta|
    """
    w = (
        bw[bw["total"] >= min_pitches]
        .sort_values(["batter_name", "week_start"])
        .copy()
    )

    grp = "batter_name"
    for col in CAT_COLS:
        d_col = "d_" + col.replace("_pct", "")        # "d_fb", "d_bb", ...
        w[col + "_prev"]  = w.groupby(grp)[col].shift(1)
        w[d_col]          = (w[col] - w[col + "_prev"]).round(1)
        w["abs_" + d_col] = w[d_col].abs()

    w["total_prev"] = w.groupby(grp)["total"].shift(1)
    w["week_prev"]  = w.groupby(grp)["week_label"].shift(1)
    w = w.dropna(subset=["total_prev"]).copy()

    # Adjustment Score: mean(|delta|) × sqrt(min_pitches/10)
    abs_d_cols     = ["abs_d_fb", "abs_d_bb", "abs_d_os", "abs_d_z79"]
    min_total      = w[["total", "total_prev"]].min(axis=1)
    w["adj_score"] = (w[abs_d_cols].mean(axis=1) * np.sqrt(min_total / 10)).round(2)
    w["week_date"] = w["week_start"].dt.date

    return w.reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
#  2.  MATCHUP-LEVEL  (pitcher × batter)
# ─────────────────────────────────────────────────────────────────────────────

def _compute_matchup_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """Tygodniowy pitch mix per pitcher × batter."""
    d = df.copy()
    d["week_start"] = floor_to_monday(d["game_date"])

    grp = (
        d.groupby(["pitcher_name", "batter_name", "week_start", "pitch_type", "season"])
         .size()
         .reset_index(name="n")
    )
    grp["total"] = grp.groupby(
        ["pitcher_name", "batter_name", "week_start"]
    )["n"].transform("sum")
    grp["pitch_pct"] = (grp["n"] / grp["total"] * 100).round(1)

    labels = make_week_labels(grp["week_start"])
    result = grp.merge(labels, on="week_start")
    result["week_date"] = result["week_start"].dt.date
    return result


def _compute_matchup_deltas(mw: pd.DataFrame) -> pd.DataFrame:
    """Week-to-week delta per pitcher × batter × pitch_type."""
    GRP = ["pitcher_name", "batter_name", "pitch_type"]
    w   = mw.sort_values(GRP + ["week_start"]).copy()

    w["pct_prev"]   = w.groupby(GRP)["pitch_pct"].shift(1)
    w["total_prev"] = w.groupby(GRP)["total"].shift(1)
    w["week_prev"]  = w.groupby(GRP)["week_label"].shift(1)

    w = w.dropna(subset=["pct_prev"]).copy()
    w["delta"]     = (w["pitch_pct"] - w["pct_prev"]).round(1)
    w["abs_delta"] = w["delta"].abs()
    w["pitch_name"] = w["pitch_type"].map(PITCH_TYPES).fillna(w["pitch_type"])

    result = w.rename(columns={
        "pitcher_name": "Pitcher",
        "batter_name":  "Batter",
        "week_label":   "Week",
        "week_prev":    "Prev Week",
        "pitch_type":   "PT",
        "pitch_name":   "Pitch Name",
        "pitch_pct":    "Now %",
        "pct_prev":     "Prev %",
        "delta":        "Δ pp",
        "abs_delta":    "Abs Δ",
        "total":        "Pitches",
        "total_prev":   "Prev Pitches",
    }).reset_index(drop=True)
    result["week_date"] = result["week_start"].dt.date
    return result


# ─────────────────────────────────────────────────────────────────────────────
#  3.  GŁÓWNA FUNKCJA CACHE  (precompute raz → filtruj tanio)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False, max_entries=8)
def precompute_all(df: pd.DataFrame) -> dict[str, Any]:
    """
    Jeden punkt wejścia – liczy wszystko na pełnym df, wynik w cache.
    Filtry sidebar aplikowane jako tanie maski pandas (~5 ms per interakcja).

    Zwraca słownik:
      batter_weekly  – bw:  batter × week (kategorie FB/BB/OS/Z79)
      batter_delta   – bd:  tygodniowe delty per batter
      matchup_weekly – mw:  pitcher × batter × week (per pitch type)
      matchup_delta  – md:  delty matchup
      perf_ms        – int: czas obliczenia w ms
    """
    t0 = time.perf_counter()

    bw = _compute_batter_weekly(df)
    bd = _compute_batter_deltas(bw, min_pitches=1)
    mw = _compute_matchup_weekly(df)
    md = _compute_matchup_deltas(mw)

    perf_ms = round((time.perf_counter() - t0) * 1000)
    return {
        "batter_weekly":  bw,
        "batter_delta":   bd,
        "matchup_weekly": mw,
        "matchup_delta":  md,
        "perf_ms":        perf_ms,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  4.  FILTROWANIE  (inline, bez cache)
# ─────────────────────────────────────────────────────────────────────────────

def filter_batter_weekly(
    bw: pd.DataFrame,
    d_start, d_end,
    sel_batters: list[str],
    sel_seasons: list[int],
) -> pd.DataFrame:
    col = "week_date" if "week_date" in bw.columns else None
    if col:
        m = (bw[col] >= d_start) & (bw[col] <= d_end)
    else:
        m = (bw["week_start"].dt.date >= d_start) & (bw["week_start"].dt.date <= d_end)
    if sel_batters:  m &= bw["batter_name"].isin(sel_batters)
    if sel_seasons:  m &= bw["season"].isin(sel_seasons)
    return bw[m].copy()


def filter_batter_delta(
    bd: pd.DataFrame,
    d_start, d_end,
    sel_batters: list[str],
    sel_seasons: list[int],
    min_pitches: int,
    min_prev: int,
) -> pd.DataFrame:
    col = "week_date" if "week_date" in bd.columns else None
    if col:
        m = (bd[col] >= d_start) & (bd[col] <= d_end)
    else:
        m = (bd["week_start"].dt.date >= d_start) & (bd["week_start"].dt.date <= d_end)
    m &= (bd["total"] >= min_pitches) & (bd["total_prev"] >= min_prev)
    if sel_batters: m &= bd["batter_name"].isin(sel_batters)
    if sel_seasons: m &= bd["season"].isin(sel_seasons)
    return bd[m].sort_values("adj_score", ascending=False).reset_index(drop=True)


def filter_matchup_weekly(
    mw: pd.DataFrame,
    d_start, d_end,
    sel_pitchers: list[str],
    sel_batters: list[str],
    sel_pt: list[str],
    sel_seasons: list[int],
) -> pd.DataFrame:
    col = "week_date" if "week_date" in mw.columns else None
    if col:
        m = (mw[col] >= d_start) & (mw[col] <= d_end)
    else:
        m = (mw["week_start"].dt.date >= d_start) & (mw["week_start"].dt.date <= d_end)
    if sel_pitchers: m &= mw["pitcher_name"].isin(sel_pitchers)
    if sel_batters:  m &= mw["batter_name"].isin(sel_batters)
    if sel_pt:       m &= mw["pitch_type"].isin(sel_pt)
    if sel_seasons:  m &= mw["season"].isin(sel_seasons)
    return mw[m].copy()


def filter_matchup_delta(
    md: pd.DataFrame,
    d_start, d_end,
    sel_pitchers: list[str],
    sel_batters: list[str],
    sel_pt: list[str],
    sel_seasons: list[int],
    min_pitches: int,
    min_prev: int,
) -> pd.DataFrame:
    col = "week_date" if "week_date" in md.columns else None
    if col:
        m = (md[col] >= d_start) & (md[col] <= d_end)
    else:
        m = (md["week_start"].dt.date >= d_start) & (md["week_start"].dt.date <= d_end)
    m &= (md["Pitches"] >= min_pitches) & (md["Prev Pitches"] >= min_prev)
    if sel_pitchers: m &= md["Pitcher"].isin(sel_pitchers)
    if sel_batters:  m &= md["Batter"].isin(sel_batters)
    if sel_pt:       m &= md["PT"].isin(sel_pt)
    if sel_seasons:  m &= md["season"].isin(sel_seasons)
    return md[m].sort_values("Abs Δ", ascending=False).reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
#  5.  INSIGHTS  (auto-generated text)
# ─────────────────────────────────────────────────────────────────────────────

def generate_batter_insights(bd_batter: pd.DataFrame, batter: str) -> list[str]:
    """Zwraca listę zdań-insightów dla wybranego battera."""
    if bd_batter.empty:
        return []

    from config import CAT_COLS, PITCH_CATEGORIES

    insights: list[str] = []

    # Najwyższy adj_score
    top = bd_batter.loc[bd_batter["adj_score"].idxmax()]
    if top["adj_score"] > 0:
        wl = top["week_label"].replace("\n", " ").replace("·", "")
        insights.append(
            f"🔥 Największe dostosowanie w **{wl.strip()}** "
            f"(Adjustment Score = **{top['adj_score']:.1f}**)"
        )

    # Streak wzrostu FB%
    bd_s = bd_batter.sort_values("week_start")
    fb_d = bd_s["d_fb"].dropna().values
    if len(fb_d) >= 3:
        streak = 0
        for v in reversed(fb_d):
            if v > 0:
                streak += 1
            else:
                break
        if streak >= 3:
            total_rise = round(bd_s["d_fb"].tail(streak).sum(), 1)
            insights.append(
                f"📈 FB% rośnie **{streak} tygodnie z rzędu** "
                f"(łącznie **+{total_rise} pp**)"
            )

    # Największy jednorazowy skok
    for col in CAT_COLS:
        d_col = "d_" + col.replace("_pct", "")
        label = PITCH_CATEGORIES[col]["short"]
        if d_col not in bd_batter.columns:
            continue
        max_idx = bd_batter[d_col].abs().idxmax()
        val     = bd_batter.loc[max_idx, d_col]
        wk      = bd_batter.loc[max_idx, "week_label"].replace("\n", " ").replace("·","").strip()
        if abs(val) >= 15:
            sign = "+" if val > 0 else ""
            insights.append(
                f"⚡ Rekordowa jednorazowa zmiana **{label}**: "
                f"**{sign}{val:.1f} pp** w tygodniu {wk}"
            )

    return insights[:4]  # max 4 insights
