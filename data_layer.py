"""
data_layer.py – ładowanie danych (parquet / pybaseball / syntetyczne)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st
from datetime import timedelta
from pathlib import Path
from typing import Optional

from config import PITCHER_PROFILES, BATTERS, ZONE_WEIGHTS, ALL_ZONES, ZONE_LOW, INACTIVE_BY_SEASON


# ── Helpers ───────────────────────────────────────────────────────────────────

def floor_to_monday(dates: pd.Series) -> pd.Series:
    """Wektoryzowany floor do poniedziałku — 8 ms vs 1700 ms dla apply(lambda)."""
    return dates.dt.normalize() - pd.to_timedelta(dates.dt.dayofweek, unit="D")


def make_week_labels(week_starts: pd.Series) -> pd.DataFrame:
    """Buduje tabelę label dla unikalnych week_start."""
    uw = week_starts.drop_duplicates().sort_values()
    return pd.DataFrame({
        "week_start":       uw.values,
        "week_label":       uw.dt.strftime("W%V %Y · %d %b").values,
        "week_label_short": uw.dt.strftime("W%V '%y").values,
    })


# ── Generowanie syntetycznych danych ─────────────────────────────────────────

def _gen_season(year: int) -> pd.DataFrame:
    """Generuje pitch-by-pitch dla jednego sezonu z realistycznymi wzorcami."""
    rng = np.random.default_rng(year * 17 + 3)

    # 2026 = sezon w toku (do połowy lipca)
    end_mo, end_dy = (7, 15) if year >= 2026 else (10, 1)
    start = pd.Timestamp(f"{year}-04-01")
    end   = pd.Timestamp(f"{year}-{end_mo:02d}-{end_dy:02d}")

    # Wykluczamy zawieszonych / nieaktywnych graczy
    inactive   = INACTIVE_BY_SEASON.get(year, set())
    active_bats = [b for b in BATTERS if b not in inactive]

    rows: list[dict] = []
    pitchers = list(PITCHER_PROFILES.keys())

    # Każdy pitcher ma wolno dryfujące tendencje w sezonie (adjustment factor)
    pitcher_drift: dict[str, np.ndarray] = {
        p: rng.uniform(-0.08, 0.08, size=4) for p in pitchers
    }

    for week_start in pd.date_range(start, end, freq="W-MON"):
        week_num = int((week_start - start).days // 7)
        for pitcher in pitchers:
            prof = PITCHER_PROFILES[pitcher]
            nb   = rng.integers(5, 12)
            bats = rng.choice(active_bats, size=min(nb, len(active_bats)), replace=False)

            for batter in bats:
                n_p       = int(rng.integers(10, 38))
                game_date = week_start + timedelta(days=int(rng.integers(0, 6)))
                if game_date > end:
                    continue

                all_types    = [prof["primary"]] + prof["secondary"]
                base_w       = np.array([0.42] + [0.58 / len(prof["secondary"])] * len(prof["secondary"]))
                # Powolny drift wg matchup-specific random walk
                drift_factor = np.ones(len(all_types))
                drift_factor[0] += pitcher_drift[pitcher][week_num % 4] * 0.5
                drift_factor   = np.abs(drift_factor)
                noise          = rng.dirichlet(base_w * 12)
                weights        = 0.68 * base_w * drift_factor + 0.32 * noise
                weights       /= weights.sum()

                for pt in rng.choice(all_types, size=n_p, p=weights):
                    zw_raw = ZONE_WEIGHTS.get(pt, [0.25, 0.25, 0.25, 0.25])
                    # Rozwiń na 14 stref
                    zone_prob = (
                        [zw_raw[0] / 3] * 3 +
                        [zw_raw[1] / 3] * 3 +
                        [zw_raw[2] / 3] * 3 +
                        [zw_raw[3] / 4] * 4
                    )
                    zone = int(rng.choice(ALL_ZONES, p=zone_prob))
                    rows.append({
                        "game_date":    game_date,
                        "pitcher_name": pitcher,
                        "batter_name":  batter,
                        "pitch_type":   pt,
                        "zone":         zone,
                        "season":       year,
                    })

    df = pd.DataFrame(rows)
    df["game_date"] = pd.to_datetime(df["game_date"])
    return df


# ── Ładowanie danych ──────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False, ttl=3600)
def load_data(seasons: tuple[int, ...]) -> tuple[pd.DataFrame, str]:
    """
    Wczytuje dane dla wybranych sezonów.
    Priorytety:
      1. data/pitch_mix_RRRR.parquet  (z data_pipeline.ipynb)
      2. pybaseball Statcast
      3. Dane syntetyczne (zawsze dostępne)

    Zwraca: (DataFrame, source_info_string)
    """
    frames: list[pd.DataFrame] = []
    source = "syntetyczne"

    # ── 1. Lokalny parquet ──
    for year in sorted(seasons):
        p = Path(f"data/pitch_mix_{year}.parquet")
        if p.exists():
            try:
                df_p = pd.read_parquet(p)
                df_p["game_date"] = pd.to_datetime(df_p["game_date"])
                if "season" not in df_p.columns:
                    df_p["season"] = year
                if "zone" not in df_p.columns:
                    df_p["zone"] = 5  # środek strefy jako fallback
                frames.append(df_p)
                source = "parquet"
            except Exception as e:
                st.warning(f"Nie można wczytać {p}: {e}")

    if frames and len(frames) == len(seasons):
        return pd.concat(frames, ignore_index=True), source

    # ── 2. pybaseball ──
    missing = [y for y in seasons if not Path(f"data/pitch_mix_{y}.parquet").exists()]
    if missing:
        try:
            from pybaseball import statcast  # type: ignore
            pb_frames: list[pd.DataFrame] = []
            for year in missing:
                end_mo = "07-15" if year >= 2026 else "10-01"
                df_pb  = statcast(start_dt=f"{year}-04-01", end_dt=f"{year}-{end_mo}")
                cols   = ["game_date", "player_name", "batter", "pitch_type", "zone"]
                df_pb  = df_pb[[c for c in cols if c in df_pb.columns]].dropna(subset=["pitch_type"])
                df_pb["game_date"] = pd.to_datetime(df_pb["game_date"])
                df_pb["pitcher_name"] = df_pb["player_name"].apply(
                    lambda n: f"{n.split(',')[1].strip()} {n.split(',')[0].strip()}"
                    if isinstance(n, str) and "," in n else str(n)
                )
                df_pb["batter_name"] = "Batter #" + df_pb["batter"].astype("Int64").astype(str)
                df_pb["season"] = year
                if "zone" not in df_pb.columns:
                    df_pb["zone"] = 5
                pb_frames.append(df_pb[["game_date", "pitcher_name", "batter_name", "pitch_type", "zone", "season"]])
            frames.extend(pb_frames)
            source = "Statcast"
        except Exception:
            pass  # fallback do syntetycznych

    # ── 3. Syntetyczne dla brakujących sezonów ──
    have_seasons = {int(f["season"].iloc[0]) for f in frames} if frames else set()
    for year in sorted(seasons):
        if year not in have_seasons:
            frames.append(_gen_season(year))

    df_out = pd.concat(frames, ignore_index=True)

    # Normalizacja kolumn
    required = {"game_date", "pitcher_name", "batter_name", "pitch_type", "zone", "season"}
    for col in required:
        if col not in df_out.columns:
            df_out[col] = 5 if col == "zone" else None

    df_out["zone"] = pd.to_numeric(df_out["zone"], errors="coerce").fillna(5).astype(int)
    df_out = df_out.dropna(subset=["pitcher_name", "batter_name", "pitch_type"])

    return df_out, source
