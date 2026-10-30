"""Plotly figure builders.

Colour rules (black theme): risk magnitude uses one red ramp (dim = low, bright = high);
comparing countries uses their own fixed colours in a fixed order; a single
series takes its pillar's colour (governance, economy), otherwise the ink. Text
never carries the series colour. Marks are separated by a ring in the surface
colour (black).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.colors as pcolors
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from . import config
from .config import (
    FORECAST_GREY,
    NO_DATA_COLOR,
    OCEAN_COLOR,
    PILLAR_COLORS,
    COUNTRY_COLORS,
    INK,
    PILLARS,
    TIER_COLORS,
    TIER_ORDER,
    WGI_DIMENSIONS,
)

FONT = dict(family=config.MONO_FONT, size=12)
SURFACE = INK["bg"]
GRID = INK["line"]
MUTED = INK["faint"]
CI_FILL = "rgba(255,255,255,0.09)"  # neutral, so it sits under a line of any colour
WORSE = "#e66767"
BETTER = "#3987e5"
HOVER = dict(bgcolor=INK["hover"], bordercolor=INK["line-strong"], font=dict(color=INK["strong"], **FONT))


def _base(fig: go.Figure, height: int = 420, legend: bool = False) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=8, r=8, t=36, b=8),
        font=FONT,
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title=None),
        hoverlabel=HOVER,
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    return fig


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------
def choropleth(df: pd.DataFrame, value_col: str, colorbar_title: str, zoom_to_data: bool = False) -> go.Figure:
    """Flat world map of a 0-100 risk score. df needs iso3, name, tier, rank_label and value_col.

    The ISO3 code is the last customdata column, so a click on a country can open its profile.
    (The 3D globe lives in prm/globe.py.)
    """
    d = df.dropna(subset=[value_col])
    custom = np.column_stack(
        [d["name"].astype(str), d["tier"].fillna("—").astype(str), d["rank_label"].astype(str), d["iso3"].astype(str)]
    ) if len(d) else None
    fig = go.Figure(
        go.Choropleth(
            locations=d["iso3"],
            z=d[value_col],
            locationmode="ISO-3",
            zmin=0,
            zmax=100,
            colorscale=config.map_colorscale(value_col),
            marker_line_color=SURFACE,
            marker_line_width=0.6,
            colorbar=dict(
                title=dict(text=f"{colorbar_title} risk (0–100)", side="top"),
                orientation="h",
                x=0.5,
                xanchor="center",
                y=-0.02,
                yanchor="top",
                thickness=10,
                len=0.55,
                tickvals=[0, 20, 40, 60, 80, 100],
                outlinewidth=0,
            ),
            customdata=custom,
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>Score: %{z:.0f} / 100<br>"
                "Tier: %{customdata[1]}<br>Rank: %{customdata[2]}<br><i>Click to open the profile</i><extra></extra>"
            ),
        )
    )
    fig.update_geos(
        showframe=False,
        showcoastlines=False,
        showland=True,
        landcolor=NO_DATA_COLOR,
        showcountries=True,
        countrycolor=SURFACE,
        countrywidth=0.6,
        showocean=True,
        oceancolor=OCEAN_COLOR,
        showlakes=True,
        lakecolor=OCEAN_COLOR,
        bgcolor="rgba(0,0,0,0)",
        projection_type="natural earth",
    )
    if zoom_to_data and len(d):
        fig.update_geos(fitbounds="locations")
    else:
        fig.update_geos(lataxis_range=[-58, 84])
    fig.update_layout(
        height=520,
        margin=dict(l=0, r=0, t=0, b=0),
        font=FONT,
        geo=dict(bgcolor="rgba(0,0,0,0)"),
        hoverlabel=HOVER,
    )
    return fig


def risk_matrix(df: pd.DataFrame, x_key: str, y_key: str) -> go.Figure:
    """Scatter of two pillar scores; colour = tier, size = population."""
    x_label = config.PILLAR_BY_KEY[x_key].label
    y_label = config.PILLAR_BY_KEY[y_key].label
    d = df.dropna(subset=[x_key, y_key, "tier"]).copy()
    pop = d["population"].fillna(d["population"].median() if d["population"].notna().any() else 1e6)
    d["size"] = (np.sqrt(pop.clip(lower=1e5)) / np.sqrt(pop.clip(lower=1e5).max()) * 38).clip(lower=8)
    fig = go.Figure()
    for tier in TIER_ORDER:
        t = d[d["tier"] == tier]
        if t.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=t[x_key], y=t[y_key], mode="markers", name=tier,
                marker=dict(size=t["size"], color=TIER_COLORS[tier], line=dict(color=SURFACE, width=2), opacity=0.92),
                customdata=np.column_stack([t["name"], t["composite"].round(0), t["iso3"]]),
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>" + config.PILLAR_BY_KEY[x_key].short + ": %{x:.0f}<br>"
                    + config.PILLAR_BY_KEY[y_key].short + ": %{y:.0f}<br>Composite: %{customdata[1]}"
                    "<br><i>Click to open the profile</i><extra></extra>"
                ),
            )
        )
    # Soft quadrant tints: blue = lower risk on both axes, red = higher risk on both
    fig.add_shape(type="rect", x0=50, x1=103, y0=50, y1=103, fillcolor="rgba(230,103,103,0.10)", line_width=0, layer="below")
    fig.add_shape(type="rect", x0=-3, x1=50, y0=-3, y1=50, fillcolor="rgba(57,135,229,0.10)", line_width=0, layer="below")
    fig.add_annotation(x=101, y=101, text="Higher risk on both", showarrow=False, xanchor="right", yanchor="top",
                       font=dict(color="#fd8078", size=11))
    fig.add_annotation(x=-1, y=-1, text="Lower risk on both", showarrow=False, xanchor="left", yanchor="bottom",
                       font=dict(color="#74b1fe", size=11))
    for v in (50,):
        fig.add_vline(x=v, line=dict(color=MUTED, width=1, dash="dot"))
        fig.add_hline(y=v, line=dict(color=MUTED, width=1, dash="dot"))
    fig.update_xaxes(title=f"{x_label} risk →", range=[-3, 103])
    fig.update_yaxes(title=f"{y_label} risk →", range=[-3, 103])
    return _base(fig, height=470, legend=True)


def tier_distribution(df: pd.DataFrame) -> go.Figure:
    """Stacked bars: number of countries in each tier, by region."""
    d = df.dropna(subset=["tier"])
    counts = d.groupby(["region", "tier"]).size().unstack(fill_value=0).reindex(columns=TIER_ORDER, fill_value=0)
    order = (counts[["High", "Severe"]].sum(axis=1) / counts.sum(axis=1)).sort_values().index
    counts = counts.loc[order]
    labels = [config.region_short(r) for r in counts.index]
    fig = go.Figure()
    for tier in TIER_ORDER:
        fig.add_trace(
            go.Bar(
                y=labels, x=counts[tier], name=tier, orientation="h",
                marker=dict(color=TIER_COLORS[tier], line=dict(color=SURFACE, width=2)),
                hovertemplate="%{y}<br>" + tier + ": %{x} countries<extra></extra>",
            )
        )
    fig.update_layout(barmode="stack", bargap=0.35)
    fig.update_xaxes(title="Countries")
    fig.update_yaxes(title=None, automargin=True)
    return _base(fig, height=470, legend=True)


def movers(df: pd.DataFrame, n: int = 8) -> go.Figure:
    """Largest falls and rises in a WGI score (df: name, change)."""
    worst = df.nsmallest(n, "change")
    best = df.nlargest(n, "change")
    d = pd.concat([worst, best]).drop_duplicates("name").sort_values("change")
    colors = [WORSE if c < 0 else BETTER for c in d["change"]]
    fig = go.Figure(
        go.Bar(
            x=d["change"], y=d["name"], orientation="h",
            marker=dict(color=colors, line=dict(color=SURFACE, width=1)),
            customdata=np.column_stack([d["start"].round(1), d["end"].round(1), d["iso3"]]),
            text=[f"{c:+.1f}" for c in d["change"]], textposition="outside", cliponaxis=False,
            hovertemplate=(
                "<b>%{y}</b><br>Change: %{x:+.1f} pts<br>%{customdata[0]} → %{customdata[1]}"
                "<br><i>Click to open the profile</i><extra></extra>"
            ),
        )
    )
    fig.add_vline(x=0, line=dict(color=MUTED, width=1))
    fig.update_xaxes(title="Change in score (points)")
    fig.update_yaxes(title=None, automargin=True)
    return _base(fig, height=max(320, 26 * len(d) + 80))


# ---------------------------------------------------------------------------
# Country profile
# ---------------------------------------------------------------------------
def pillar_bars(row: pd.Series, regional_median: pd.Series) -> go.Figure:
    labels = [p.short for p in PILLARS][::-1]  # short names: the monospace font is wide
    keys = [p.key for p in PILLARS][::-1]
    vals = [row.get(k) for k in keys]
    meds = [regional_median.get(k) for k in keys]
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=vals, y=labels, orientation="h", name="Country", showlegend=False,
            marker=dict(color=[PILLAR_COLORS[k] for k in keys]),
            text=["—" if pd.isna(v) else f"{v:.0f}" for v in vals], textposition="outside", cliponaxis=False,
            hovertemplate="%{y}: %{x:.0f}<extra></extra>", width=0.55,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=meds, y=labels, mode="markers", name="Regional median",
            marker=dict(symbol="line-ns-open", size=26, color="#ffffff", line=dict(width=2.5)),
            hovertemplate="Regional median: %{x:.0f}<extra></extra>",
        )
    )
    fig.update_xaxes(range=[0, 108], title="Risk score (0 = lowest, 100 = highest)")
    fig.update_yaxes(title=None, automargin=True)
    return _base(fig, height=300, legend=True)


def risk_history(hist: pd.DataFrame) -> go.Figure:
    """One country's composite (bold, dots in tier colours) and pillar scores per year, over the tier bands."""
    fig = go.Figure()
    for tier, upper in zip(config.TIERS, [t.lower for t in config.TIERS[1:]] + [100]):
        fig.add_hrect(y0=tier.lower, y1=upper, fillcolor=tier.color, opacity=0.06, line_width=0, layer="below")
        fig.add_annotation(x=0, xref="paper", y=(tier.lower + upper) / 2, text=tier.label, showarrow=False,
                           xanchor="left", font=dict(color=MUTED, size=10))
    for p in PILLARS:
        fig.add_trace(go.Scatter(
            x=hist["year"], y=hist[p.key], name=p.short, mode="lines",
            line=dict(color=PILLAR_COLORS[p.key], width=1.5), opacity=0.85,
            hovertemplate=p.short + " %{x}: %{y:.0f}<extra></extra>",
        ))
    tiers = hist["tier"].fillna("—")
    fig.add_trace(go.Scatter(
        x=hist["year"], y=hist["composite"], name="Composite", mode="lines+markers",
        line=dict(color="#ffffff", width=3),
        marker=dict(size=9, color=[TIER_COLORS.get(t, MUTED) for t in tiers], line=dict(color=SURFACE, width=1.5)),
        customdata=np.column_stack([tiers, hist["rank"].fillna(0).astype(int)]),
        hovertemplate="<b>%{x}</b>: %{y:.0f} · %{customdata[0]} · rank %{customdata[1]}<extra></extra>",
    ))
    fig.update_yaxes(range=[0, 100], title="Risk score (0–100)")
    fig.update_xaxes(dtick=1, tickformat="d")
    fig.update_layout(hovermode="x unified")
    return _base(fig, height=380, legend=True)


def case_history(hist: pd.DataFrame, event_date: str, label: str) -> go.Figure:
    """A country's risk over time with the year before the event shaded and the event marked."""
    fig = risk_history(hist)
    when = pd.Timestamp(event_date)
    x = when.year + (when.dayofyear - 1) / 365
    fig.add_vrect(x0=when.year - 1.5, x1=when.year - 0.5, fillcolor="#fd8078", opacity=0.08, line_width=0, layer="below")
    fig.add_vline(x=x, line=dict(color="#fd8078", dash="dash", width=1.5))
    fig.add_annotation(x=x, y=100, yref="y", text=label, showarrow=False, xanchor="left", yanchor="top",
                       font=dict(color="#fd8078", **FONT), bgcolor="rgba(0,0,0,0.6)")
    return fig


def whatif_pillars(base: pd.Series, scenario: pd.Series) -> go.Figure:
    """Pillar scores today (grey) against the what-if scenario (pillar colours)."""
    keys = [p.key for p in PILLARS][::-1]
    labels = [p.short for p in PILLARS][::-1]
    before = [base.get(k) for k in keys]
    after = [scenario.get(k) for k in keys]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=before, y=labels, orientation="h", name="Today", marker=dict(color="#5a5955"),
        hovertemplate="%{y} today: %{x:.0f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=after, y=labels, orientation="h", name="Scenario",
        marker=dict(color=[PILLAR_COLORS[k] for k in keys], line=dict(color=SURFACE, width=1)),
        text=[
            "—" if pd.isna(a) else f"{a:.0f}" + ("" if pd.isna(b) or round(a - b) == 0 else f" ({a - b:+.0f})")
            for a, b in zip(after, before)
        ],
        textposition="outside", cliponaxis=False,
        hovertemplate="%{y} in scenario: %{x:.0f}<extra></extra>",
    ))
    fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.08)
    fig.update_xaxes(range=[0, 112], title="Risk score (0 = lowest, 100 = highest)")
    fig.update_yaxes(title=None, automargin=True)
    return _base(fig, height=320, legend=True)


def wgi_small_multiples(series: dict[str, pd.DataFrame], ci: dict[str, pd.DataFrame], iso3: str) -> go.Figure:
    dims = list(WGI_DIMENSIONS.items())
    fig = make_subplots(
        rows=2, cols=3, subplot_titles=[label for _, label in dims], shared_yaxes=True,
        vertical_spacing=0.2, horizontal_spacing=0.04,
    )
    for i, (dim, label) in enumerate(dims):
        r, c = i // 3 + 1, i % 3 + 1
        s = _country(series.get(f"wgi_{dim}"), iso3)
        lb = _country(ci.get(f"wgi_{dim}_lb"), iso3)
        ub = _country(ci.get(f"wgi_{dim}_ub"), iso3)
        if not lb.empty and not ub.empty:
            band = lb.merge(ub, on="year", suffixes=("_lb", "_ub"))
            fig.add_trace(go.Scatter(x=band["year"], y=band["value_ub"], mode="lines", line=dict(width=0),
                                     hoverinfo="skip", showlegend=False), r, c)
            fig.add_trace(go.Scatter(x=band["year"], y=band["value_lb"], mode="lines", line=dict(width=0),
                                     fill="tonexty", fillcolor=CI_FILL, hoverinfo="skip",
                                     name="90% confidence interval", showlegend=(i == 0)), r, c)
        fig.add_trace(go.Scatter(x=s["year"], y=s["value"], mode="lines", line=dict(color=PILLAR_COLORS["governance"], width=2),
                                 name="Score", showlegend=(i == 0),
                                 hovertemplate=label + "<br>%{x}: %{y:.1f}<extra></extra>"), r, c)
    fig.update_yaxes(range=[0, 100], gridcolor=GRID)
    fig.update_xaxes(gridcolor=GRID)
    fig.update_annotations(font=dict(size=13))
    return _base(fig, height=520, legend=True)


MACRO_PANELS = [
    ("gdp_growth", "Real GDP growth (%)", True),
    ("inflation", "Inflation (%)", False),
    ("gov_debt", "Public debt (% of GDP)", False),
    ("fiscal_balance", "Fiscal balance (% of GDP)", True),
    ("current_account", "Current account (% of GDP)", True),
    ("unemployment_imf", "Unemployment (%)", False),
]


def macro_small_multiples(series: dict[str, pd.DataFrame], iso3: str, year: int, history: int = 12, ahead: int = 5) -> go.Figure:
    fig = make_subplots(rows=2, cols=3, subplot_titles=[t for _, t, _ in MACRO_PANELS],
                        vertical_spacing=0.2, horizontal_spacing=0.07)
    for i, (key, title, zero_line) in enumerate(MACRO_PANELS):
        r, c = i // 3 + 1, i % 3 + 1
        s = _country(series.get(key), iso3)
        s = s[(s["year"] >= year - history) & (s["year"] <= year + ahead)]
        actual = s[s["year"] <= year - 1]
        projected = s[s["year"] >= year - 1]
        fig.add_trace(go.Scatter(x=actual["year"], y=actual["value"], mode="lines", line=dict(color=PILLAR_COLORS["economic"], width=2),
                                 name="Reported / estimated", showlegend=(i == 0),
                                 hovertemplate=title + "<br>%{x}: %{y:.1f}<extra></extra>"), r, c)
        fig.add_trace(go.Scatter(x=projected["year"], y=projected["value"], mode="lines",
                                 line=dict(color=FORECAST_GREY, width=2, dash="dash"),
                                 name="IMF projection", showlegend=(i == 0),
                                 hovertemplate=title + " (projection)<br>%{x}: %{y:.1f}<extra></extra>"), r, c)
        if zero_line:
            fig.add_hline(y=0, line=dict(color=MUTED, width=1), row=r, col=c)
    fig.update_annotations(font=dict(size=13))
    return _base(fig, height=520, legend=True)


def tone_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Scatter(x=df["date"], y=df["tone"], mode="lines", line=dict(color=INK["text"], width=2),
                               hovertemplate="%{x|%d %b %Y}<br>Average tone: %{y:.2f}<extra></extra>"))
    fig.add_hline(y=0, line=dict(color=MUTED, width=1))
    fig.update_yaxes(title="Average tone (negative = more negative coverage)")
    return _base(fig, height=300)


def protest_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Scatter(x=df["date"], y=df["share"], mode="lines", line=dict(color="#fd8078", width=2),
                               fill="tozeroy", fillcolor="rgba(253,128,120,0.12)",
                               hovertemplate="%{x|%d %b %Y}<br>%{y:.3f}% of monitored coverage<extra></extra>"))
    fig.update_yaxes(title="Share of world news coverage (%)", rangemode="tozero")
    return _base(fig, height=300)


# ---------------------------------------------------------------------------
# Compare
# ---------------------------------------------------------------------------
def radar(scores: pd.DataFrame, names: dict[str, str]) -> go.Figure:
    labels = [p.short for p in PILLARS]
    fig = go.Figure()
    for i, iso3 in enumerate(scores.index):
        vals = [scores.loc[iso3, p.key] for p in PILLARS]
        vals = [0 if pd.isna(v) else v for v in vals]
        fig.add_trace(go.Scatterpolar(
            r=vals + vals[:1], theta=labels + labels[:1], name=names.get(iso3, iso3), mode="lines+markers",
            line=dict(color=COUNTRY_COLORS[i], width=2), marker=dict(size=8),
            hovertemplate="%{theta}: %{r:.0f}<extra>" + names.get(iso3, iso3) + "</extra>",
        ))
    fig.update_layout(polar=dict(radialaxis=dict(range=[0, 100], tickvals=[20, 40, 60, 80], gridcolor=GRID),
                                 angularaxis=dict(gridcolor=GRID), bgcolor="rgba(0,0,0,0)"))
    fig = _base(fig, height=440, legend=True)
    fig.update_layout(margin=dict(l=84, r=84, t=48, b=24))  # the pillar names sit outside the circle
    return fig


def compare_lines(series: dict[str, pd.DataFrame], key: str, iso3s: list[str], names: dict[str, str], title: str,
                  start_year: int | None = None, end_year: int | None = None,
                  projected_from: int | None = None) -> go.Figure:
    fig = go.Figure()
    if projected_from is not None:  # shade the years that are estimates or projections
        fig.add_vrect(x0=projected_from - 0.5, x1=(end_year or projected_from + 5) + 0.5, fillcolor=FORECAST_GREY,
                      opacity=0.12, line_width=0, annotation_text="IMF estimates & projections",
                      annotation_position="top left", annotation_font=dict(color=MUTED, **FONT))
    for i, iso3 in enumerate(iso3s):
        s = _country(series.get(key), iso3)
        if start_year:
            s = s[s["year"] >= start_year]
        if end_year:
            s = s[s["year"] <= end_year]
        fig.add_trace(go.Scatter(x=s["year"], y=s["value"], mode="lines", name=names.get(iso3, iso3),
                                 line=dict(color=COUNTRY_COLORS[i], width=2),
                                 hovertemplate=names.get(iso3, iso3) + "<br>%{x}: %{y:.1f}<extra></extra>"))
    fig.update_yaxes(title=title)
    fig.update_layout(hovermode="x unified")
    return _base(fig, height=400, legend=True)


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------
SIGNIFICANCE_COLORS = {"Low": "#c42d31", "Medium": "#e94f4d", "High": "#feb5ae"}


def events_timeline(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for level in ["Low", "Medium", "High"]:
        d = df[df["significance"].str.title() == level]
        if d.empty:
            continue
        fig.add_trace(go.Scatter(
            x=d["date"], y=d["country"], mode="markers", name=f"{level} significance",
            marker=dict(size={"Low": 10, "Medium": 14, "High": 18}[level], color=SIGNIFICANCE_COLORS[level],
                        line=dict(color=SURFACE, width=2)),
            customdata=np.column_stack([d["event"], d["category"]]),
            hovertemplate="<b>%{y}</b> · %{x|%d %b %Y}<br>%{customdata[0]}<br><i>%{customdata[1]}</i><extra></extra>",
        ))
    fig.add_vline(x=pd.Timestamp.today().strftime("%Y-%m-%d"), line=dict(color=MUTED, width=1, dash="dot"))
    fig.update_yaxes(title=None, automargin=True)
    return _base(fig, height=max(280, 34 * df["country"].nunique() + 120), legend=True)


# ---------------------------------------------------------------------------
# Briefing pages (Score changes, Regions, Conflict & displacement, Economic stress)
# ---------------------------------------------------------------------------
def change_bars(df: pd.DataFrame, n: int = 10) -> go.Figure:
    """Largest rises (red) and falls (blue) in the composite vs last year. df: iso3, name, delta_1y."""
    valid = df.dropna(subset=["delta_1y"])
    d = pd.concat([valid.nsmallest(n, "delta_1y"), valid.nlargest(n, "delta_1y")]).drop_duplicates("iso3")
    d = d.sort_values("delta_1y")
    fig = go.Figure(go.Bar(
        x=d["delta_1y"], y=d["name"], orientation="h",
        marker=dict(color=[WORSE if c > 0 else BETTER for c in d["delta_1y"]], line=dict(color=SURFACE, width=1)),
        text=[f"{c:+.1f}" for c in d["delta_1y"]], textposition="outside", cliponaxis=False,
        customdata=np.column_stack([d["prev_composite"].round(0), d["composite"].round(0), d["iso3"]]),
        hovertemplate="<b>%{y}</b><br>%{customdata[0]} → %{customdata[1]} (%{x:+.1f})"
                      "<br><i>Click to open the profile</i><extra></extra>",
    ))
    fig.add_vline(x=0, line=dict(color=MUTED, width=1))
    fig.update_xaxes(title="Change in composite score vs last year (points)")
    fig.update_yaxes(title=None, automargin=True)
    return _base(fig, height=max(320, 24 * len(d) + 90))


def tier_mix(hist: pd.DataFrame) -> go.Figure:
    """Number of countries in each tier, per year (stacked)."""
    counts = hist.dropna(subset=["tier"]).groupby(["year", "tier"]).size().unstack(fill_value=0)
    counts = counts.reindex(columns=TIER_ORDER, fill_value=0)
    fig = go.Figure()
    for tier in TIER_ORDER:
        fig.add_trace(go.Bar(x=counts.index, y=counts[tier], name=tier,
                             marker=dict(color=TIER_COLORS[tier], line=dict(color=SURFACE, width=1)),
                             hovertemplate="%{x} · " + tier + ": %{y} countries<extra></extra>"))
    fig.update_layout(barmode="stack", bargap=0.25)
    fig.update_xaxes(dtick=2, tickformat="d", tickangle=0)  # every other year: fits a half-width column
    fig.update_yaxes(title="Countries")
    return _base(fig, height=380, legend=True)


def yearly_bars(years, values, title: str, color: str, hover: str) -> go.Figure:
    """A single series per year (e.g. battle deaths worldwide)."""
    fig = go.Figure(go.Bar(x=years, y=values, marker=dict(color=color, line=dict(color=SURFACE, width=1)),
                           hovertemplate="%{x}: %{y:,.0f} " + hover + "<extra></extra>"))
    fig.update_xaxes(tickformat="d")
    fig.update_yaxes(title=title)
    return _base(fig, height=340)


FIFTHS = ["Safest fifth", "2nd fifth", "Middle fifth", "4th fifth", "Riskiest fifth"]


def onset_fifths(by_fifth: pd.DataFrame, base_rate: float, color: str) -> go.Figure:
    """Share of countries at peace where armed conflict started the next year, by fifth of the risk score."""
    rate = by_fifth["mean"].fillna(0) * 100
    fig = go.Figure(go.Bar(
        x=FIFTHS, y=rate, marker=dict(color=color, opacity=[0.35, 0.5, 0.65, 0.82, 1.0], line=dict(color=SURFACE, width=1)),
        text=[f"{r:.1f}%" for r in rate], textposition="outside", textfont=dict(color="#c3c2b7", **FONT),
        customdata=by_fifth[["sum", "size"]].fillna(0).astype(int).to_numpy(),
        hovertemplate="%{x}: conflict started in %{customdata[0]} of %{customdata[1]} cases (%{y:.1f}%)<extra></extra>",
    ))
    fig.add_hline(y=base_rate * 100, line=dict(color=MUTED, dash="dash", width=1),
                  annotation_text=f"average {base_rate * 100:.1f}%", annotation_position="top left",
                  annotation_font=dict(color=MUTED, **FONT))
    fig.update_yaxes(title="Conflict started the next year (%)", rangemode="tozero")
    fig.update_xaxes(title="Risk score the year before")
    return _base(fig, height=360)


def outlook_drivers(coefficients: pd.Series, labels: dict[str, str]) -> go.Figure:
    """How much each factor multiplies the odds of new conflict, per typical (one standard deviation) difference."""
    odds = np.exp(coefficients).sort_values()
    fig = go.Figure(go.Bar(
        x=odds.to_numpy(), y=[labels.get(k, k) for k in odds.index], orientation="h",
        marker=dict(color=[WORSE if v > 1 else BETTER for v in odds], line=dict(color=SURFACE, width=1)),
        text=[f"×{v:.2f}" for v in odds], textposition="outside", textfont=dict(color="#c3c2b7", **FONT),
        hovertemplate="%{y}: odds ×%{x:.2f} per typical difference<extra></extra>",
    ))
    fig.add_vline(x=1, line=dict(color=MUTED, dash="dash", width=1))
    fig.update_xaxes(title="Change in the odds of new conflict (1 = no effect)", rangemode="tozero")
    return _base(fig, height=300)


def calibration_bars(cal: pd.DataFrame) -> go.Figure:
    """Out-of-time test: predicted chance against what happened, in fifths of the prediction."""
    labels = [FIFTHS[int(f) - 1].replace("Safest", "Lowest").replace("Riskiest", "Highest") for f in cal["fifth"]]
    fig = go.Figure([
        go.Bar(name="Predicted", x=labels, y=cal["predicted"] * 100, marker=dict(color=FORECAST_GREY),
               hovertemplate="%{x}: predicted %{y:.1f}%<extra></extra>"),
        go.Bar(name="What happened", x=labels, y=cal["observed"] * 100, marker=dict(color="#fd8078"),
               hovertemplate="%{x}: conflict began in %{y:.1f}% of cases<extra></extra>"),
    ])
    fig.update_layout(barmode="group")
    fig.update_yaxes(title="New armed conflict next year (%)", rangemode="tozero")
    return _base(fig, height=320, legend=True)


def tier_shift(before: pd.Series, after: pd.Series) -> go.Figure:
    """Stress test: number of countries in each tier today and under stress."""
    today = before.value_counts().reindex(TIER_ORDER, fill_value=0)
    stressed = after.value_counts().reindex(TIER_ORDER, fill_value=0)
    fig = go.Figure([
        go.Bar(name="Today", x=TIER_ORDER, y=today, marker=dict(color="#4a4a47", line=dict(color=SURFACE, width=1)),
               text=today, textposition="outside", textfont=dict(color=MUTED, **FONT),
               hovertemplate="%{x} today: %{y} countries<extra></extra>"),
        go.Bar(name="Under stress", x=TIER_ORDER, y=stressed,
               marker=dict(color=[TIER_COLORS[t] for t in TIER_ORDER], line=dict(color=SURFACE, width=1)),
               text=stressed, textposition="outside", textfont=dict(color="#c3c2b7", **FONT),
               hovertemplate="%{x} under stress: %{y} countries<extra></extra>"),
    ])
    fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.08)
    fig.update_yaxes(title="Countries", rangemode="tozero")
    return _base(fig, height=320, legend=True)


def benchmark_scatter(df: pd.DataFrame, year: int) -> go.Figure:
    """Seismographic's composite against the Fragile States Index, one dot per country, in tier colours."""
    fig = go.Figure(go.Scatter(
        x=df["fsi"], y=df["score"], mode="markers",
        marker=dict(size=8, color=[TIER_COLORS.get(t, MUTED) for t in df["tier"].fillna("—")],
                    line=dict(color=SURFACE, width=1), opacity=0.9),
        customdata=df[["name"]].to_numpy(),
        hovertemplate="<b>%{customdata[0]}</b><br>Fragile States Index %{x:.1f}<br>Seismographic %{y:.0f}<extra></extra>",
    ))
    fig.update_xaxes(title=f"Fragile States Index {year} (higher = more fragile)")
    fig.update_yaxes(title=f"Seismographic {year} (0–100)", range=[0, 100])
    return _base(fig, height=420)


def ranked_bars(df: pd.DataFrame, value: str, label: str, color: str, hover: str, fmt: str = ",.0f") -> go.Figure:
    """Horizontal bars, largest on top; clickable when df has iso3."""
    d = df.sort_values(value)
    fig = go.Figure(go.Bar(
        x=d[value], y=d[label], orientation="h", marker=dict(color=color, line=dict(color=SURFACE, width=1)),
        text=[f"{v:{fmt}}" for v in d[value]], textposition="outside", cliponaxis=False,
        customdata=np.column_stack([d["iso3"]]) if "iso3" in d else None,
        hovertemplate="<b>%{y}</b><br>%{x:" + fmt + "} " + hover + "<extra></extra>",
    ))
    fig.update_yaxes(title=None, automargin=True)
    top = float(d[value].max()) if len(d) else 1.0
    fig.update_xaxes(showticklabels=False, range=[0, top * 1.18 if top > 0 else 1])  # room for the value labels
    return _base(fig, height=max(300, 28 * len(d) + 60))


def refugee_sankey(flows: pd.DataFrame, names: dict[str, str], n: int = 25) -> go.Figure:
    """The largest refugee corridors: origins (left) to host countries (right)."""
    top = flows[flows["origin"].isin(names) & flows["host"].isin(names)].nlargest(n, "value")
    origins = list(dict.fromkeys(top["origin"]))
    hosts = list(dict.fromkeys(top["host"]))
    labels = [names[o] for o in origins] + [names[h] for h in hosts]
    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(label=labels, pad=10, thickness=14, line=dict(color=SURFACE, width=0.5),
                  color=[WORSE] * len(origins) + [BETTER] * len(hosts),
                  hovertemplate="<b>%{label}</b><br>%{value:,.0f} people<extra></extra>"),
        link=dict(source=[origins.index(o) for o in top["origin"]],
                  target=[len(origins) + hosts.index(h) for h in top["host"]],
                  value=top["value"], color="rgba(116,177,254,0.28)",
                  hovertemplate="%{source.label} → %{target.label}<br>%{value:,.0f} people<extra></extra>"),
    ))
    fig.update_layout(height=max(420, 22 * max(len(origins), len(hosts)) + 80), margin=dict(l=8, r=8, t=16, b=8),
                      font=FONT, hoverlabel=HOVER)
    return fig


ECON_COLUMNS = [  # (indicator key, short label) for the economic heatmap
    ("inflation", "Inflation"), ("gdp_growth", "Growth"), ("gov_debt", "Debt"),
    ("fiscal_balance", "Fiscal bal."), ("current_account", "Current acc."), ("reserves_months", "Reserves"),
]


def _text_on(rgb: str) -> str:
    """Black or white text, whichever reads better on this background colour ('rgb(r, g, b)' or '#rrggbb')."""
    if rgb.startswith("#"):
        r, g, b = (int(rgb[i:i + 2], 16) for i in (1, 3, 5))
    else:
        r, g, b = (float(v) for v in rgb[rgb.index("(") + 1:rgb.index(")")].split(",")[:3])
    lum = 0.2126 * (r / 255) ** 2.2 + 0.7152 * (g / 255) ** 2.2 + 0.0722 * (b / 255) ** 2.2
    return "#0b0b0b" if lum > 0.22 else "#f4f4f4"


def econ_heatmap(df: pd.DataFrame) -> go.Figure:
    """Rows = countries, columns = economic indicators; colour = risk score, text = the actual value."""
    keys = [k for k, _ in ECON_COLUMNS]
    z = df[[f"n_{k}" for k in keys]].to_numpy(dtype=float)
    text = [[config.INDICATOR_BY_KEY[k].fmt(row[k]) for k in keys] for _, row in df.iterrows()]
    units = [config.INDICATOR_BY_KEY[k].unit for k in keys]
    labels = [label for _, label in ECON_COLUMNS]
    scale = config.map_colorscale("economic")
    fig = go.Figure(go.Heatmap(
        z=z, x=labels, y=df["name"], zmin=0, zmax=100, colorscale=scale, xgap=2, ygap=2, text=text,
        customdata=np.array([[units[j] for j in range(len(keys))] for _ in range(len(df))]),
        colorbar=dict(title=dict(text="Risk", side="right"), thickness=10, len=0.6, tickvals=[0, 50, 100]),
        hovertemplate="<b>%{y}</b> · %{x}<br>Value: %{text} %{customdata}<br>Risk score: %{z:.0f}/100<extra></extra>",
    ))
    # The values, each in dark or light text depending on how bright its cell is
    xs, ys, ts, cs = [], [], [], []
    for i, name in enumerate(df["name"]):
        for j, label in enumerate(labels):
            xs.append(label); ys.append(name); ts.append(text[i][j])
            cs.append(MUTED if np.isnan(z[i, j]) else _text_on(pcolors.sample_colorscale(scale, [z[i, j] / 100])[0]))
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="text", text=ts, textfont=dict(size=11, color=cs), hoverinfo="skip",
                             showlegend=False))
    # fixed ranges: the text layer would otherwise pad the axes and open a gap above the first row
    fig.update_yaxes(range=[len(df) - 0.5, -0.5], automargin=True)
    fig.update_xaxes(side="top", range=[-0.5, len(labels) - 0.5])
    return _base(fig, height=max(320, 24 * len(df) + 90))


def stagflation_scatter(df: pd.DataFrame, cap: float = 60.0) -> go.Figure:
    """Growth vs inflation; bubble = population, colour = economic pillar risk. Inflation above `cap` is pinned."""
    d = df.dropna(subset=["gdp_growth", "inflation"]).copy()
    d["y"] = d["inflation"].clip(upper=cap)
    pop = d["population"].fillna(d["population"].median())
    d["size"] = (np.sqrt(pop.clip(lower=1e5)) / np.sqrt(pop.clip(lower=1e5).max()) * 34).clip(lower=7)
    fig = go.Figure(go.Scatter(
        x=d["gdp_growth"], y=d["y"], mode="markers",
        marker=dict(size=d["size"], color=d["economic"], colorscale=config.map_colorscale("economic"), cmin=0, cmax=100,
                    symbol=["triangle-up" if v > cap else "circle" for v in d["inflation"]],
                    line=dict(color=SURFACE, width=1.5), opacity=0.92,
                    colorbar=dict(title=dict(text="Economy risk", side="right"), thickness=10, len=0.6)),
        customdata=np.column_stack([d["name"], d["inflation"].round(1), d["iso3"]]),
        hovertemplate="<b>%{customdata[0]}</b><br>Growth %{x:.1f}% · inflation %{customdata[1]}%"
                      "<br><i>Click to open the profile</i><extra></extra>",
    ))
    fig.add_shape(type="rect", x0=-15, x1=0, y0=20, y1=cap + 3, fillcolor="rgba(230,103,103,0.10)", line_width=0,
                  layer="below")
    fig.add_annotation(x=-14.5, y=cap + 2, text="Stagflation zone", showarrow=False, xanchor="left",
                       font=dict(color="#fd8078", size=11))
    fig.add_vline(x=0, line=dict(color=MUTED, width=1, dash="dot"))
    fig.add_hline(y=20, line=dict(color=MUTED, width=1, dash="dot"))
    fig.update_xaxes(title="Real GDP growth (%)", range=[-15, 15])
    fig.update_yaxes(title=f"Inflation (%, ▲ = above {cap:.0f})", range=[-5, cap + 3])
    return _base(fig, height=460)


def imf_outlook(series: pd.DataFrame, year: int, title: str, start: int, end: int) -> go.Figure:
    """Median across countries with the middle-half band; dashed after the last full year (IMF projections)."""
    d = series[(series["year"] >= start) & (series["year"] <= end)]
    q = d.groupby("year")["value"].quantile([0.25, 0.5, 0.75]).unstack()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=q.index, y=q[0.75], mode="lines", line=dict(width=0), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=q.index, y=q[0.25], mode="lines", line=dict(width=0), fill="tonexty",
                             fillcolor=CI_FILL, name="Middle half of countries", hoverinfo="skip"))
    actual, projected = q[q.index <= year - 1], q[q.index >= year - 1]
    fig.add_trace(go.Scatter(x=actual.index, y=actual[0.5], mode="lines", name="Median", line=dict(color=PILLAR_COLORS["economic"], width=2.5),
                             hovertemplate="%{x}: %{y:.1f}%<extra>median</extra>"))
    fig.add_trace(go.Scatter(x=projected.index, y=projected[0.5], mode="lines", name="IMF projection",
                             line=dict(color=FORECAST_GREY, width=2.5, dash="dash"),
                             hovertemplate="%{x}: %{y:.1f}%<extra>projection</extra>"))
    fig.update_xaxes(tickformat="d")
    fig.update_yaxes(title=title)
    return _base(fig, height=340, legend=True)


def distribution(values: pd.Series, title: str, color: str, log: bool = False) -> go.Figure:
    """Histogram of one indicator across countries, with the median marked."""
    v = pd.to_numeric(values, errors="coerce").dropna()
    x = np.log10(v.clip(lower=0) + 1) if log else v
    fig = go.Figure(go.Histogram(x=x, nbinsx=40, marker=dict(color=color, line=dict(color=SURFACE, width=1)),
                                 hovertemplate="%{y} countries<extra></extra>"))
    if len(v):
        median = float(np.log10(max(v.median(), 0) + 1)) if log else float(v.median())
        fig.add_vline(x=median, line=dict(color="#ffffff", width=1.5, dash="dot"),
                      annotation_text=f"median {v.median():,.1f}", annotation_font_color="#ffffff")
    fig.update_xaxes(title=title + (" (log scale: log10(1 + x))" if log else ""))
    fig.update_yaxes(title="Countries")
    fig.update_layout(bargap=0.05)
    return _base(fig, height=320)


def peer_strip(country: pd.Series, peers: pd.DataFrame, name: str) -> go.Figure:
    """Each row a score; grey dots = peers, white tick = peer median, big dot = this country."""
    rows = [("composite", "Composite")] + [(p.key, p.short) for p in PILLARS]
    rng = np.random.default_rng(7)
    fig = go.Figure()
    for i, (key, label) in enumerate(rows):
        vals = peers[["name", key]].dropna()
        fig.add_trace(go.Scatter(
            x=vals[key], y=i + rng.uniform(-0.18, 0.18, len(vals)), mode="markers", showlegend=i == 0, name="Peers",
            marker=dict(size=7, color="#5a5955", line=dict(color=SURFACE, width=1)), text=vals["name"],
            hovertemplate="%{text}: %{x:.0f}<extra>" + label + "</extra>",
        ))
        if len(vals):
            fig.add_trace(go.Scatter(x=[vals[key].median()], y=[i], mode="markers", showlegend=i == 0, name="Peer median",
                                     marker=dict(symbol="line-ns-open", size=24, color="#ffffff", line=dict(width=2.5)),
                                     hovertemplate="Peer median: %{x:.0f}<extra>" + label + "</extra>"))
        value = country.get(key)
        if pd.notna(value):
            color = TIER_COLORS.get(country.get("tier"), MUTED) if key == "composite" else PILLAR_COLORS[key]
            fig.add_trace(go.Scatter(x=[value], y=[i], mode="markers+text", showlegend=False, text=[f"{value:.0f}"],
                                     textposition="top center", textfont=dict(color="#ffffff"),
                                     marker=dict(size=16, color=color, line=dict(color="#ffffff", width=2)),
                                     hovertemplate=name + ": %{x:.0f}<extra>" + label + "</extra>"))
    fig.update_yaxes(tickvals=list(range(len(rows))), ticktext=[label for _, label in rows], autorange="reversed",
                     showgrid=False)
    fig.update_xaxes(range=[-2, 102], title="Risk score (0 = lowest, 100 = highest)")
    return _base(fig, height=360, legend=True)


def _country(df: pd.DataFrame | None, iso3: str) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["year", "value"])
    return df[df["iso3"] == iso3][["year", "value"]].sort_values("year")
