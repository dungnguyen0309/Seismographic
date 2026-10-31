"""Seismographic brand assets: the mark, the wordmark and the banner wave (SVGs in assets/)."""

from __future__ import annotations

from functools import cache
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"


@cache
def svg(name: str) -> str:
    """The SVG markup of assets/<name>.svg (icon, logo or wave)."""
    return (ASSETS / f"{name}.svg").read_text(encoding="utf-8")

