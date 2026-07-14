"""
app.py – Pitch Mix Dashboard v4
Analiza pitch mix rzucanego DO pałkarzy w ujęciu tygodniowym.

Uruchomienie:
    pip install streamlit pandas numpy plotly
    streamlit run app.py

Struktura:
    config.py        – stałe, kolory, CSS
    data_layer.py    – ładowanie danych (parquet / pybaseball / syntetyczne)
    compute.py       – agregacja batter-centric + matchup-level, delty, insights
    ui_components.py – reusable charts, KPI, sidebar, export
    app.py           – entry point, 5 tabów
"""
from __future__ import annotations

import time as _time

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ── Lokalne moduły ─────────────────────────────────────────────────────────
from config import (
    APP_CSS, AVAILABLE_SEASONS, CAT_COLS, CAT_COLORS, CAT_LABELS,
    PITCH_CATEGORIES, PITCH_COLORS, PITCH_TYPES,
)
from data_layer import load_data
from compute import (
    precompute_all,
    filter_batter_weekly, filter_batter_delta,
    filter_matchup_weekly, filter_matchup_delta,
    generate_batter_insights,
)
from ui_components import (
    SidebarFilters,
    themed, themed_rot,
    render_kpis, section, empty, insight_box, export_csv,
    chart_batter_trend, chart_batter_delta_bars, chart_batter_heatmap,
    chart_adj_score_ranking, chart_comparison,
    chart_matchup_line, chart_matchup_heatmap,
    chart_biggest_changes,
)

# ─────────────────────────────────────────────────────────────────────────────
#  PAGE CONFIG  (musi być przed jakimkolwiek st.*)
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="⚾ Pitch Mix Dashboard",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(APP_CSS, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
#  HEADER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="dash-header">
    <h1>⚾ Pitch Mix Dashboard</h1>
    <p class="subtitle">
        Jak zmienia się pitch mix rzucany DO pałkarza tydzień po tygodniu?
        FB% · BB% · OS% · Zone 7-9% · Adjustment Score
    </p>
    <span class="badge">v4 · batter-centric · multi-season 2022-2026</span>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
#  SIDEBAR + LOAD DATA
# ─────────────────────────────────────────────────────────────────────────────

# Renderujemy sidebar tymczasowo żeby pobrać sezony przed load_data
with st.sidebar:
    st.markdown("### ⚾ Pitch Mix Analyzer")
    st.markdown("### 📅 Sezony")
    _seasons_sel = st.multiselect(
        "Sezony", AVAILABLE_SEASONS, default=[2025, 2026],
        label_visibility="collapsed", key="_seasons_pre",
    )
    if not _seasons_sel:
        _seasons_sel = [2026]

with st.spinner("⚾ Ładowanie danych…"):
    raw_df, data_source = load_data(tuple(sorted(_seasons_sel)))

raw_df["game_date"] = pd.to_datetime(raw_df["game_date"])

# Renderuj pełny sidebar
filters = SidebarFilters(raw_df)
# Nadpisz sezony wybranymi wcześniej (unikamy podwójnego widgetu)
filters.seasons = _seasons_sel

# ─────────────────────────────────────────────────────────────────────────────
#  PRECOMPUTE
# ─────────────────────────────────────────────────────────────────────────────
with st.spinner("📊 Obliczanie statystyk (cache po pierwszym uruchomieniu)…"):
    pc = precompute_all(raw_df)

bw_all = pc["batter_weekly"]
bd_all = pc["batter_delta"]
mw_all = pc["matchup_weekly"]
md_all = pc["matchup_delta"]
pc_ms  = pc["perf_ms"]

# Perf pill
season_str = ", ".join(str(y) for y in sorted(filters.seasons))
src_icon   = "📂" if data_source == "parquet" else ("🌐" if data_source == "Statcast" else "🎲")
st.markdown(
    f'<span class="perf-pill">'
    f'{src_icon} {data_source} · sezony {season_str} · '
    f'precompute {pc_ms} ms · filtr ~5 ms'
    f'</span>',
    unsafe_allow_html=True,
)
st.markdown("")

# ─────────────────────────────────────────────────────────────────────────────
#  FILTROWANIE  (~5 ms per interakcja)
# ─────────────────────────────────────────────────────────────────────────────
_tf = _time.perf_counter()

bw = filter_batter_weekly(
    bw_all,
    filters.d_start, filters.d_end,
    filters.sel_batters, filters.seasons,
)
bd = filter_batter_delta(
    bd_all,
    filters.d_start, filters.d_end,
    filters.sel_batters, filters.seasons,
    filters.min_pitches, filters.min_prev,
)
mw = filter_matchup_weekly(
    mw_all,
    filters.d_start, filters.d_end,
    filters.sel_pitchers, filters.sel_batters, filters.sel_pt, filters.seasons,
)
md = filter_matchup_delta(
    md_all,
    filters.d_start, filters.d_end,
    filters.sel_pitchers, filters.sel_batters, filters.sel_pt, filters.seasons,
    filters.min_pitches, filters.min_prev,
)
_tf_ms = round((_time.perf_counter() - _tf) * 1000, 1)

if bw.empty and mw.empty:
    st.warning("⚠️ Brak danych dla wybranych filtrów — zmień kryteria w sidebarze.")
    st.stop()

# ─────────────────────────────────────────────────────────────────────────────
#  GLOBAL KPIs
# ─────────────────────────────────────────────────────────────────────────────
n_batters_f  = bw["batter_name"].nunique()
n_pitchers_f = mw["pitcher_name"].nunique() if not mw.empty else 0
n_pitches_f  = int(bw["total"].sum()) if not bw.empty else 0
n_matchups_f = mw.groupby(["pitcher_name", "batter_name"]).ngroups if not mw.empty else 0
n_weeks_f    = bw["week_start"].nunique() if not bw.empty else 0
avg_adj      = round(bd["adj_score"].mean(), 1) if not bd.empty else 0

render_kpis([
    {"label": "Pitches do battera", "value": f"{n_pitches_f:,}",
     "sub": "łącznie w filtrze"},
    {"label": "Tygodnie",           "value": str(n_weeks_f),
     "sub": "zakresu analizy"},
    {"label": "Batters",            "value": str(n_batters_f),
     "sub": "pałkarzy"},
    {"label": "Pitchers",           "value": str(n_pitchers_f),
     "sub": "miotaczy"},
    {"label": "Matchups",           "value": f"{n_matchups_f:,}",
     "sub": "par pitcher-batter"},
    {"label": "Avg Adj.Score",      "value": str(avg_adj),
     "sub": "średnie dostosowanie",  "highlight": True},
    {"label": "Filtr",              "value": str(_tf_ms),
     "sub": "ms per interakcja"},
])

# ─────────────────────────────────────────────────────────────────────────────
#  TABY
# ─────────────────────────────────────────────────────────────────────────────
tab_profile, tab_compare, tab_changes, tab_matchup, tab_ranking = st.tabs([
    "🏏 Profil Pałkarza",
    "🆚 Porównanie",
    "📊 Zmiany Matchup",
    "🔍 Szczegóły Matchupu",
    "📈 Rankingi",
])


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 1 – PROFIL PAŁKARZA  (główna funkcja – batter-centric aggregation)
# ══════════════════════════════════════════════════════════════════════════════
with tab_profile:
    st.markdown("""
    > **Jak czytać tę zakładkę:** dla każdego tygodnia liczymy WSZYSTKIE pitche
    > rzucone do wybranego battera (przez wszystkich pitcherów łącznie)
    > i pokazujemy jak zmieniał się ich mix FB%/BB%/OS%/Zone 7-9%.
    """)

    if bw.empty:
        empty("Brak danych batter-weekly. Zmień filtry.")
        st.stop()

    avail_batters = sorted(bw["batter_name"].unique())
    col_sel, col_info = st.columns([2, 3])
    with col_sel:
        sel_batter = st.selectbox(
            "🏏 Wybierz pałkarza", avail_batters,
            key="profile_batter",
        )

    bw_b = bw[bw["batter_name"] == sel_batter].sort_values("week_start")
    bd_b = bd[bd["batter_name"] == sel_batter].sort_values("week_start")

    with col_info:
        if not bw_b.empty:
            total_px   = int(bw_b["total"].sum())
            n_wk       = len(bw_b)
            avg_fb     = round(bw_b["fb_pct"].mean(), 1)
            top_adj_wk = (bd_b.loc[bd_b["adj_score"].idxmax(), "week_label"].replace("\n", " ").replace("·", "").strip()
                          if not bd_b.empty else "—")
            render_kpis([
                {"label": "Pitchy do niego",   "value": f"{total_px:,}",
                 "sub": "w wybranym okresie"},
                {"label": "Tygodnie",           "value": str(n_wk),
                 "sub": "obserwacji"},
                {"label": "Śr. FB%",            "value": f"{avg_fb}%",
                 "sub": "fastballe"},
                {"label": "Max adj. tydzień",   "value": top_adj_wk,
                 "sub": "największe dostosowanie", "highlight": True},
            ])

    # ── Insights ─────────────────────────────────────────────────────────────
    if not bd_b.empty:
        for ins in generate_batter_insights(bd_b, sel_batter):
            insight_box(ins)

    # ── Trend wykres ─────────────────────────────────────────────────────────
    section("📊 Tygodniowy Mix — Wszystkie Pitch Types Razem")
    st.caption(
        "Każdy punkt = ile % pitchy danej kategorii rzucono do tego battera "
        "w tym tygodniu (suma wszystkich pitcherów)."
    )

    if bw_b.empty:
        empty(f"Brak danych tygodniowych dla {sel_batter}.")
    else:
        st.plotly_chart(chart_batter_trend(bw, sel_batter),
                        use_container_width=True)

        # ── Delta bary ───────────────────────────────────────────────────────
        section("📉 Zmiany Tydzień do Tygodnia")
        if bd_b.empty:
            st.info("Za mało tygodni / pitchy by policzyć deltę — obniż progi w sidebarze.")
        else:
            st.plotly_chart(chart_batter_delta_bars(bd, sel_batter),
                            use_container_width=True)

        # ── Heatmapa + tabela ────────────────────────────────────────────────
        col_ht, col_tbl = st.columns([3, 2])
        with col_ht:
            section("🗓️ Heatmapa (tygodnie × kategorie)")
            st.plotly_chart(chart_batter_heatmap(bw, sel_batter),
                            use_container_width=True)

        with col_tbl:
            section("📋 Tabela delt")
            if not bd_b.empty:
                disp_cols = {
                    "week_label_short": "Tydzień",
                    "fb_pct":  "FB%", "fb_pct_prev": "FB% poprz.",
                    "bb_pct":  "BB%", "bb_pct_prev": "BB% poprz.",
                    "os_pct":  "OS%", "z79_pct": "Z79%",
                    "d_fb": "ΔFB", "d_bb": "ΔBB", "d_os": "ΔOS", "d_z79": "ΔZ79",
                    "adj_score": "Adj.Score",
                    "total": "Pitchy",
                }
                cols_avail = [c for c in disp_cols if c in bd_b.columns]
                tbl = bd_b[cols_avail].rename(columns=disp_cols)

                fmt = {}
                for c in tbl.columns:
                    if "%" in c and "Δ" not in c:
                        fmt[c] = "{:.1f}%"
                    elif "Δ" in c:
                        fmt[c] = "{:+.1f}"
                    elif c == "Adj.Score":
                        fmt[c] = "{:.1f}"

                st.dataframe(
                    tbl.style
                       .background_gradient(subset=["Adj.Score"] if "Adj.Score" in tbl.columns else [],
                                            cmap="YlOrRd")
                       .format(fmt, na_rep="—"),
                    use_container_width=True,
                    height=320,
                )
                export_csv(bd_b, f"batter_delta_{sel_batter.replace(' ','_')}.csv",
                           "⬇ Pobierz CSV")

        # ── Breakdown per pitch type ─────────────────────────────────────────
        with st.expander("📊 Szczegóły per pitch type (każdy typ osobno)"):
            import plotly.graph_objects as go

            sub_mw = mw[mw["batter_name"] == sel_batter].sort_values("week_start")
            if sub_mw.empty:
                st.info("Brak danych matchup-level dla tego battera.")
            else:
                # Agreguj per batter × week × pitch_type (wszyscy pitcherzy)
                agg_pt = (
                    sub_mw.groupby(["week_label_short", "week_start", "pitch_type"])["n"]
                    .sum().reset_index()
                )
                tot_week = agg_pt.groupby("week_start")["n"].transform("sum")
                agg_pt["pct"] = (agg_pt["n"] / tot_week * 100).round(1)
                agg_pt = agg_pt.sort_values("week_start")

                fig_pt = go.Figure()
                for pt in sorted(agg_pt["pitch_type"].unique()):
                    ptd = agg_pt[agg_pt["pitch_type"] == pt]
                    fig_pt.add_trace(go.Scatter(
                        x=ptd["week_label_short"], y=ptd["pct"],
                        mode="lines+markers",
                        name=f"{pt} – {PITCH_TYPES.get(pt, pt)}",
                        line=dict(color=PITCH_COLORS.get(pt, "#aaa"), width=2),
                        marker=dict(size=6),
                        hovertemplate=(
                            f"<b>{pt}</b><br>Tydzień: %{{x}}<br>"
                            "%: %{y:.1f}%<extra></extra>"
                        ),
                    ))
                themed(fig_pt,
                       height=340,
                       title=f"Pitch type breakdown (wszyscy pitcherzy) → {sel_batter}",
                       xaxis_title="Tydzień", yaxis_title="%",
                       hovermode="x unified")
                st.plotly_chart(fig_pt, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 2 – PORÓWNANIE  (2-3 batters na jednym wykresie)
# ══════════════════════════════════════════════════════════════════════════════
with tab_compare:
    section("🆚 Porównanie pałkarzy — pitch mix do nich")
    st.caption("Wybierz 2-4 pałkarzy i kategorię aby zobaczyć jak różni się pitch mix rzucany do każdego.")

    if bw.empty:
        empty()
    else:
        avail_cmp = sorted(bw["batter_name"].unique())
        c1, c2 = st.columns([3, 1])
        with c1:
            cmp_batters = st.multiselect(
                "Wybierz pałkarzy (2-4)", avail_cmp,
                default=avail_cmp[:3] if len(avail_cmp) >= 3 else avail_cmp,
                max_selections=4,
                key="cmp_batters",
            )
        with c2:
            cmp_mode = st.radio("Tryb", ["Wszystkie kategorie", "Jedna kategoria"],
                                key="cmp_mode")

        if not cmp_batters:
            empty("Wybierz co najmniej jednego pałkarza.")
        elif cmp_mode == "Jedna kategoria":
            sel_cat_cmp = st.selectbox(
                "Kategoria",
                CAT_COLS,
                format_func=lambda x: PITCH_CATEGORIES[x]["label"],
                key="cmp_cat",
            )
            st.plotly_chart(
                chart_comparison(bw, cmp_batters, sel_cat_cmp),
                use_container_width=True,
            )
        else:
            # 2×2 grid
            cols_grid = [CAT_COLS[:2], CAT_COLS[2:]]
            for row in cols_grid:
                grid_cols = st.columns(len(row))
                for ci, col_cat in enumerate(row):
                    with grid_cols[ci]:
                        st.plotly_chart(
                            chart_comparison(bw, cmp_batters, col_cat),
                            use_container_width=True,
                        )

        # Tabela porównawcza — średnie
        section("📋 Tabela średnich")
        if cmp_batters and not bw.empty:
            bw_cmp = bw[bw["batter_name"].isin(cmp_batters)]
            avg_tbl = (
                bw_cmp.groupby("batter_name")[CAT_COLS]
                      .mean().round(1).reset_index()
            )
            avg_tbl.columns = ["Batter"] + [PITCH_CATEGORIES[c]["short"] for c in CAT_COLS]
            st.dataframe(
                avg_tbl.style
                       .background_gradient(cmap="RdYlGn", subset=avg_tbl.columns[1:].tolist())
                       .format({c: "{:.1f}%" for c in avg_tbl.columns[1:]}),
                use_container_width=True,
            )
            export_csv(avg_tbl, "comparison_avg.csv", "⬇ CSV")


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 3 – ZMIANY MATCHUP  (pitcher × batter × pitch_type)
# ══════════════════════════════════════════════════════════════════════════════
with tab_changes:
    section("📊 Największe zmiany pitch mix (pitcher → batter)")
    st.caption("Delta per pitcher × batter × pitch type. Każdy wiersz = konkretny pitcher zmienił podejście do konkretnego battera.")

    if md.empty:
        empty("Brak danych delt. Obniż progi lub rozszerz zakres dat.")
    else:
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            pt_f = st.multiselect(
                "Pitch type", sorted(md["PT"].unique()),
                format_func=lambda x: f"{x} – {PITCH_TYPES.get(x, x)}",
                key="chg_pt",
            )
        with c2:
            direction = st.radio("Kierunek", ["Oba", "↑ Wzrost", "↓ Spadek"],
                                 horizontal=True, key="chg_dir")
        with c3:
            top_n = st.slider("Top N", 10, 100, 25, 5, key="chg_n")

        tbl_md = md.copy()
        if pt_f:                        tbl_md = tbl_md[tbl_md["PT"].isin(pt_f)]
        if direction == "↑ Wzrost":     tbl_md = tbl_md[tbl_md["Δ pp"] > 0]
        elif direction == "↓ Spadek":   tbl_md = tbl_md[tbl_md["Δ pp"] < 0]
        tbl_md = tbl_md.head(top_n)

        st.dataframe(
            tbl_md[["Pitcher","Batter","Week","Prev Week","Pitch Name",
                    "Now %","Prev %","Δ pp","Pitches"]]
            .style
            .background_gradient(subset=["Δ pp"], cmap="RdYlGn", vmin=-30, vmax=30)
            .format({"Now %": "{:.1f}%", "Prev %": "{:.1f}%", "Δ pp": "{:+.1f} pp"}),
            use_container_width=True,
            height=420,
        )

        col_dl, _ = st.columns([1, 4])
        with col_dl:
            export_csv(tbl_md, "biggest_changes.csv", "⬇ CSV")

        section("Top 20 zmian – wykres")
        st.plotly_chart(chart_biggest_changes(md, top_n=min(top_n, 25)),
                        use_container_width=True)

        # Scatter: Prev% vs Now%
        section("Scatter: poprzednio vs teraz")
        sel_pt_sc = st.selectbox(
            "Pitch type dla scattera",
            ["Wszystkie"] + sorted(md["PT"].unique()),
            key="chg_sc_pt",
        )
        sc_data = md if sel_pt_sc == "Wszystkie" else md[md["PT"] == sel_pt_sc]
        if not sc_data.empty:
            import plotly.express as px
            fig_sc = px.scatter(
                sc_data.head(500),
                x="Prev %", y="Now %",
                color="Δ pp",
                size="Pitches",
                size_max=18,
                color_continuous_scale="RdYlGn",
                range_color=[-35, 35],
                hover_data={"Pitcher": True, "Batter": True,
                            "Pitch Name": True, "Δ pp": ":.1f"},
                title=f"Scatter: % poprzednio vs % teraz ({sel_pt_sc})",
            )
            fig_sc.add_shape(type="line", x0=0, y0=0, x1=100, y1=100,
                             line=dict(color="#30363d", dash="dash", width=1))
            themed(fig_sc, height=420,
                   xaxis_title="% w poprzednim tygodniu",
                   yaxis_title="% w bieżącym tygodniu")
            st.plotly_chart(fig_sc, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 4 – SZCZEGÓŁY MATCHUPU  (pitcher × batter trend)
# ══════════════════════════════════════════════════════════════════════════════
with tab_matchup:
    section("🔍 Szczegóły matchupu pitcher → batter")

    if mw.empty:
        empty("Brak danych matchup. Zmień filtry.")
    else:
        avail_p = sorted(mw["pitcher_name"].unique())
        c1, c2 = st.columns(2)
        with c1:
            sel_p = st.selectbox("🎯 Pitcher", avail_p, key="mq_p")
        with c2:
            faced = sorted(mw[mw["pitcher_name"] == sel_p]["batter_name"].unique())
            sel_b = st.selectbox("🏏 Batter", faced, key="mq_b")

        mw_mb = mw[(mw["pitcher_name"] == sel_p) & (mw["batter_name"] == sel_b)]
        md_mb = md[(md["Pitcher"] == sel_p) & (md["Batter"] == sel_b)]

        if mw_mb.empty:
            empty("Brak danych dla tego matchupu.")
        else:
            # KPI matchupu
            render_kpis([
                {"label": "Tygodni razem",  "value": str(mw_mb["week_start"].nunique()),
                 "sub": "obserwacji"},
                {"label": "Łącznie pitchy", "value": str(int(mw_mb.groupby("week_start")["n"].sum().sum())),
                 "sub": "przez cały okres"},
                {"label": "Pitch types",    "value": str(mw_mb["pitch_type"].nunique()),
                 "sub": "różnych typów"},
                {"label": "Max Δ pp",       "value": f"{md_mb['Abs Δ'].max():.1f}" if not md_mb.empty else "—",
                 "sub": "największa zmiana", "highlight": True},
            ])

            st.plotly_chart(chart_matchup_line(mw, sel_p, sel_b),
                            use_container_width=True)

            c_ht, c_tbl = st.columns([3, 2])
            with c_ht:
                section("Heatmapa pitch type × tydzień")
                st.plotly_chart(chart_matchup_heatmap(mw, sel_p, sel_b),
                                use_container_width=True)
            with c_tbl:
                section("Delty dla tego matchupu")
                if md_mb.empty:
                    st.info("Za mało tygodni by policzyć deltę.")
                else:
                    show_md = md_mb[["Week", "Pitch Name", "Now %", "Prev %", "Δ pp", "Pitches"]].head(20)
                    st.dataframe(
                        show_md.style
                               .background_gradient(subset=["Δ pp"], cmap="RdYlGn",
                                                    vmin=-30, vmax=30)
                               .format({"Now %": "{:.1f}%", "Prev %": "{:.1f}%",
                                        "Δ pp": "{:+.1f} pp"}),
                        use_container_width=True,
                        height=280,
                    )
                    export_csv(md_mb, f"matchup_{sel_p.split()[-1]}_{sel_b.split()[-1]}.csv",
                               "⬇ CSV")


# ══════════════════════════════════════════════════════════════════════════════
#  TAB 5 – RANKINGI  (Adj. Score, kategorie)
# ══════════════════════════════════════════════════════════════════════════════
with tab_ranking:
    section("📈 Ranking pałkarzy — Adjustment Score")
    st.caption(
        "**Adjustment Score** = mean(|ΔFB%|, |ΔBB%|, |ΔOS%|, |ΔZ79%|) × √(min_pitches/10). "
        "Im wyższy, tym bardziej pitcherzy zmieniali swoje podejście do tego battera."
    )

    if bd.empty:
        empty()
    else:
        c1, c2 = st.columns([1, 3])
        with c1:
            top_n_rank = st.slider("Top N", 5, 30, 15, key="rank_n")
        with c2:
            st.plotly_chart(chart_adj_score_ranking(bd, top_n_rank),
                            use_container_width=True)

        # Tabela rankingowa
        rank_tbl = (
            bd.groupby("batter_name")
              .agg(
                  Max_Adj=("adj_score",     "max"),
                  Avg_Adj=("adj_score",     "mean"),
                  N_Weeks=("adj_score",     "count"),
                  Avg_FB =("fb_pct",        "mean"),
                  Avg_BB =("bb_pct",        "mean"),
                  Avg_OS =("os_pct",        "mean"),
                  Avg_Z79=("z79_pct",       "mean"),
              )
              .round(1)
              .sort_values("Max_Adj", ascending=False)
              .head(top_n_rank)
              .reset_index()
        )
        rank_tbl.columns = [
            "Batter", "Max Adj.", "Avg Adj.", "Tygodni",
            "Śr. FB%", "Śr. BB%", "Śr. OS%", "Śr. Z79%",
        ]
        st.dataframe(
            rank_tbl.style
                    .background_gradient(subset=["Max Adj.", "Avg Adj."], cmap="YlOrRd")
                    .format({c: "{:.1f}" for c in rank_tbl.columns if c != "Batter" and c != "Tygodni"}),
            use_container_width=True,
        )
        export_csv(rank_tbl, "adj_score_ranking.csv", "⬇ CSV rankingu")

        # ── Ranking per kategoria ─────────────────────────────────────────────
        section("Ranking per kategoria (max |delta| per batter)")

        cat_cols_ui = st.columns(4)
        for ci, col_cat in enumerate(CAT_COLS):
            with cat_cols_ui[ci]:
                label = PITCH_CATEGORIES[col_cat]["short"]
                color = PITCH_CATEGORIES[col_cat]["color"]
                d_col = "d_" + col_cat.replace("_pct", "")
                abs_col = "abs_" + d_col

                if abs_col not in bd.columns:
                    st.caption(f"{label}: brak danych")
                    continue

                cat_rank = (
                    bd.groupby("batter_name")[abs_col]
                      .max()
                      .sort_values(ascending=False)
                      .head(10)
                      .reset_index()
                )
                cat_rank.columns = ["Batter", f"Max |Δ| {label}"]

                fig_cr = go.Figure(go.Bar(
                    y=cat_rank["Batter"],
                    x=cat_rank[f"Max |Δ| {label}"],
                    orientation="h",
                    marker_color=color,
                    text=cat_rank[f"Max |Δ| {label}"].round(1),
                    texttemplate="  %{text:.1f}",
                    textposition="outside",
                    cliponaxis=False,
                    textfont=dict(color="#c9d1d9", size=10),
                ))
                themed(fig_cr,
                       height=320,
                       title=f"Top {label}",
                       xaxis_title="pp",
                       yaxis_title="",
                       margin=dict(l=10, r=60, t=40, b=10))
                fig_cr.update_yaxes(autorange="reversed")
                st.plotly_chart(fig_cr, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
#  FOOTER
# ─────────────────────────────────────────────────────────────────────────────
st.divider()
st.markdown("""
<div style="text-align:center; color:#7d8590; font-size:.76rem; padding:8px 0">
    ⚾ Pitch Mix Dashboard v4 &nbsp;·&nbsp;
    <a href="https://baseballsavant.mlb.com" style="color:#58a6ff">Baseball Savant</a>
    &nbsp;·&nbsp;
    <a href="https://github.com/jldbc/pybaseball" style="color:#58a6ff">pybaseball</a>
    &nbsp;·&nbsp; Streamlit + Plotly + pandas
</div>
""", unsafe_allow_html=True)
