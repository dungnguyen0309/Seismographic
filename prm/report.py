"""A one-page country brief as a PDF: score, pillars, risk since 2015, red flags and the real-life reading."""

from __future__ import annotations

import datetime as dt

import pandas as pd
from fpdf import FPDF
from fpdf.enums import XPos, YPos

from . import config, interpret

# The PDF uses the built-in Helvetica font, which only knows Latin-1 characters
_PLAIN = {"—": "-", "–": "-", "−": "-", "→": "->", "≥": ">=", "≤": "<=", "▲": "+", "▼": "-", "■": "=", "’": "'",
          "‘": "'", "“": '"', "”": '"', "…": "...", "•": "-", "⚑": "!", "✓": "", "✅": "", " ": " "}
INK, MUTED, RULE, ACCENT = (20, 20, 20), (110, 110, 105), (210, 210, 205), (232, 96, 88)


def _t(text) -> str:
    text = str(text)
    for a, b in _PLAIN.items():
        text = text.replace(a, b)
    return text.encode("latin-1", "replace").decode("latin-1")


def _rgb(hex_color: str) -> tuple[int, int, int]:
    n = int(hex_color.lstrip("#"), 16)
    return (n >> 16) & 255, (n >> 8) & 255, n & 255


class _Brief(FPDF):
    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*MUTED)
        self.cell(0, 4, _t(f"{config.APP_TITLE} - {config.APP_DESCRIPTION} General information, not investment, "
                          f"legal or security advice. Page {self.page_no()}"), align="C")


def _heading(pdf: FPDF, text: str) -> None:
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*ACCENT)
    pdf.cell(0, 6, _t(text.upper()), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(*INK)


def _bullets(pdf: FPDF, items: list[str], limit: int | None = None) -> None:
    pdf.set_font("Helvetica", "", 8.5)
    for item in items[:limit]:
        pdf.set_x(pdf.l_margin + 2)
        pdf.multi_cell(0, 4.2, _t(f"- {item}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _history_chart(pdf: FPDF, x: float, y: float, w: float, h: float, rows: pd.DataFrame) -> None:
    """Composite score per year, over faint tier bands."""
    for tier, upper in zip(config.TIERS, [t.lower for t in config.TIERS[1:]] + [100]):
        r, g, b = _rgb(tier.color)
        pdf.set_fill_color(int(255 - (255 - r) * 0.12), int(255 - (255 - g) * 0.12), int(255 - (255 - b) * 0.12))
        pdf.rect(x, y + h * (1 - upper / 100), w, h * (upper - tier.lower) / 100, style="F")
    pdf.set_draw_color(*RULE)
    pdf.rect(x, y, w, h)
    data = rows.dropna(subset=["composite"])
    if len(data) >= 2:
        years = data["year"].astype(int).tolist()
        lo, hi = min(years), max(years)
        pts = [(x + (yr - lo) / max(hi - lo, 1) * w, y + h * (1 - v / 100)) for yr, v in zip(years, data["composite"])]
        pdf.set_draw_color(*INK)
        pdf.set_line_width(0.6)
        pdf.polyline(pts)
        pdf.set_line_width(0.2)
        pdf.set_fill_color(*ACCENT)
        pdf.circle(pts[-1][0], pts[-1][1], 1.2, style="F")
        pdf.set_font("Helvetica", "", 7)
        pdf.set_text_color(*MUTED)
        pdf.text(x, y + h + 3.5, str(lo))
        pdf.text(x + w - 7, y + h + 3.5, str(hi))
        pdf.text(x - 6, y + 2, "100")
        pdf.text(x - 3, y + h, "0")
        pdf.set_text_color(*INK)


def country_pdf(reading: interpret.Reading, row: pd.Series, rows: pd.DataFrame, flags: list[dict], year: int,
                weights_label: str = "") -> bytes:
    """The brief for one country. `row` is its line of ui.master_table, `rows` its history (one row per year);
    `weights_label` names the pillar weights when they are not the defaults."""
    pdf = _Brief(format="A4")
    pdf.set_margins(16, 14, 16)
    pdf.set_auto_page_break(True, margin=16)
    pdf.add_page()
    width = pdf.w - pdf.l_margin - pdf.r_margin

    # Masthead
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*ACCENT)
    pdf.cell(width / 2, 5, _t(f"{config.APP_TITLE.upper()}  |  COUNTRY RISK BRIEF"))
    pdf.set_text_color(*MUTED)
    pdf.cell(width / 2, 5, _t(dt.date.today().strftime("%d %B %Y")), align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_draw_color(*ACCENT)
    pdf.set_line_width(0.6)
    pdf.line(pdf.l_margin, pdf.get_y() + 1, pdf.l_margin + width, pdf.get_y() + 1)
    pdf.set_line_width(0.2)
    pdf.ln(4)

    # Title
    pdf.set_text_color(*INK)
    pdf.set_font("Helvetica", "B", 22)
    pdf.cell(0, 10, _t(reading.name), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 5, _t(f"{row.get('region', '')} - {row.get('income', '')} - index for {year}"),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if weights_label:
        pdf.cell(0, 5, _t(f"Scored with custom pillar weights: {weights_label}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)

    # Score block (left) and risk since HISTORY_START (right)
    top = pdf.get_y()
    score = row.get("composite")
    pdf.set_text_color(*INK)
    pdf.set_font("Helvetica", "B", 30)
    pdf.cell(20 if pd.notna(score) and score < 100 else 26, 13, "-" if pd.isna(score) else f"{score:.0f}")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*MUTED)
    pdf.cell(14, 13, "/ 100")
    tier = row.get("tier")
    if isinstance(tier, str) and tier in config.TIER_COLORS:
        pdf.set_fill_color(*_rgb(config.TIER_COLORS[tier]))
        text_on = next(t.text_on for t in config.TIERS if t.label == tier)
        pdf.set_text_color(*_rgb(text_on))
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_xy(pdf.l_margin, top + 14)
        pdf.cell(26, 6, _t(tier), align="C", fill=True)
    pdf.set_text_color(*INK)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(pdf.l_margin, top + 22)
    rank = row.get("rank_label", "")
    change = row.get("delta_1y")
    pdf.multi_cell(80, 4.6, _t(f"Global rank: {rank}\nChange vs {year - 1}: "
                               + ("-" if pd.isna(change) else f"{change:+.1f} points")),
                   new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # Pillar bars
    pdf.set_xy(pdf.l_margin, top + 34)
    for p in config.PILLARS:
        v = row.get(p.key)
        y = pdf.get_y()
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*INK)
        pdf.cell(24, 5, _t(p.short))
        pdf.set_fill_color(235, 235, 230)
        pdf.rect(pdf.l_margin + 24, y + 1, 46, 3, style="F")
        if not pd.isna(v):
            pdf.set_fill_color(*_rgb(config.PILLAR_COLORS[p.key]))
            pdf.rect(pdf.l_margin + 24, y + 1, 46 * float(v) / 100, 3, style="F")
        pdf.set_xy(pdf.l_margin + 72, y)
        pdf.cell(10, 5, "-" if pd.isna(v) else f"{v:.0f}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    left_bottom = pdf.get_y()

    chart_x = pdf.l_margin + 96
    pdf.set_xy(chart_x, top)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 4, _t(f"Composite risk score, {config.HISTORY_START}-{year}"))
    _history_chart(pdf, chart_x + 6, top + 6, width - 102, 42, rows)
    pdf.set_xy(pdf.l_margin, max(left_bottom, top + 54) + 2)

    # Red flags
    _heading(pdf, "Red flags")
    if flags:
        _bullets(pdf, [f"{config.SEVERITY_LABEL[f['severity']]}: {f['label']}" for f in flags])
    else:
        _bullets(pdf, ["None: no absolute warning threshold is crossed."])

    # The reading
    _heading(pdf, "What it means in real life")
    pdf.set_font("Helvetica", "B", 9)
    pdf.multi_cell(0, 4.6, _t(reading.headline), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 8.5)
    pdf.multi_cell(0, 4.2, _t(reading.ground), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    if reading.warnings:
        _heading(pdf, "Warning signs right now")
        _bullets(pdf, [f"{w['label']}. {w['meaning']}" for w in reading.warnings], limit=4)
    if reading.direction:
        _heading(pdf, "Direction")
        _bullets(pdf, reading.direction, limit=3)
    if reading.events:
        _heading(pdf, "Coming up")
        _bullets(pdf, reading.events, limit=3)
    if reading.actions:
        _heading(pdf, "What to do")
        for key, label in interpret.AUDIENCES.items():
            items = reading.actions.get(key) or []
            if items:
                pdf.set_font("Helvetica", "B", 8.5)
                pdf.cell(0, 4.6, _t(label), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
                _bullets(pdf, items, limit=2)

    # Sources
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(0, 3.6, _t(
        "Sources: World Bank Worldwide Governance Indicators and World Development Indicators; IMF World Economic "
        "Outlook; UNHCR; Uppsala Conflict Data Program; IFES ElectionGuide. Scores are relative (0 = lowest risk in "
        "the sample, 100 = highest) and describe the latest data, which can lag events. " + " ".join(reading.caveats)),
        new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    return bytes(pdf.output())
