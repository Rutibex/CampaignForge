from __future__ import annotations

from typing import Tuple, Optional
from PySide6.QtGui import QImage, QColor, QPainter, QPen
from PySide6.QtCore import Qt

from .generator import (
    ContinentModel,
    BIOME_OCEAN, BIOME_BEACH, BIOME_TUNDRA, BIOME_TAIGA, BIOME_TEMPERATE_FOREST,
    BIOME_GRASSLAND, BIOME_DESERT, BIOME_SAVANNA, BIOME_TROPICAL_FOREST,
    BIOME_MOUNTAIN, BIOME_SNOW_PEAK
)

def _biome_color(code: int) -> Tuple[int, int, int]:
    # Keep it readable. You can swap to theme packs later.
    if code == BIOME_OCEAN: return (30, 60, 120)
    if code == BIOME_BEACH: return (210, 200, 140)
    if code == BIOME_TUNDRA: return (180, 190, 190)
    if code == BIOME_TAIGA: return (70, 110, 80)
    if code == BIOME_TEMPERATE_FOREST: return (50, 120, 70)
    if code == BIOME_GRASSLAND: return (120, 170, 90)
    if code == BIOME_DESERT: return (220, 200, 120)
    if code == BIOME_SAVANNA: return (190, 185, 95)
    if code == BIOME_TROPICAL_FOREST: return (40, 140, 90)
    if code == BIOME_MOUNTAIN: return (120, 120, 120)
    if code == BIOME_SNOW_PEAK: return (235, 235, 240)
    return (255, 0, 255)

def render_base(model: ContinentModel, *, show_rivers: bool = True, show_capitals: bool = True) -> QImage:
    img = QImage(model.w, model.h, QImage.Format.Format_ARGB32)
    img.fill(QColor(0, 0, 0, 0))

    # Paint pixels
    for y in range(model.h):
        row = y * model.w
        for x in range(model.w):
            i = row + x
            r, g, b = _biome_color(model.biome[i])

            # gentle shading by elevation (land only)
            if model.land[i]:
                e = model.elev[i]
                shade = int((e - 0.5) * 55)
                r = max(0, min(255, r + shade))
                g = max(0, min(255, g + shade))
                b = max(0, min(255, b + shade))

            img.setPixelColor(x, y, QColor(r, g, b, 255))

    if show_rivers:
        p = QPainter(img)
        p.setPen(QPen(QColor(120, 170, 255, 220), 1))
        for y in range(model.h):
            row = y * model.w
            for x in range(model.w):
                i = row + x
                if model.river[i] and model.land[i]:
                    p.drawPoint(x, y)
        p.end()

    if show_capitals and model.factions:
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        for f in model.factions:
            x, y = f.capital
            # black outline + white dot
            p.setPen(QPen(QColor(0, 0, 0, 220), 2))
            p.drawPoint(x, y)
            p.setPen(QPen(QColor(250, 250, 250, 230), 1))
            p.drawPoint(x, y)
        p.end()

    return img

def render_factions_overlay(model: ContinentModel, *, opacity: float = 0.45, show_borders: bool = True, show_contested: bool = True) -> QImage:
    """
    Returns an ARGB overlay (transparent elsewhere).
    """
    img = QImage(model.w, model.h, QImage.Format.Format_ARGB32)
    img.fill(QColor(0, 0, 0, 0))

    alpha = max(0, min(255, int(255 * float(opacity))))

    # Fill faction ownership
    for y in range(model.h):
        row = y * model.w
        for x in range(model.w):
            i = row + x
            fid = model.faction[i]
            if fid < 0:
                continue
            if fid >= len(model.factions):
                continue
            fr, fg, fb = model.factions[fid].color
            img.setPixelColor(x, y, QColor(fr, fg, fb, alpha))

    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)

    if show_contested:
        # darken contested a bit
        for y in range(model.h):
            row = y * model.w
            for x in range(model.w):
                i = row + x
                if model.contested[i] and model.faction[i] >= 0:
                    c = img.pixelColor(x, y)
                    img.setPixelColor(x, y, QColor(max(0, c.red() - 25), max(0, c.green() - 25), max(0, c.blue() - 25), c.alpha()))

    if show_borders:
        # draw borders where neighbor faction differs
        p.setPen(QPen(QColor(10, 10, 10, min(255, alpha + 40)), 1))
        w, h = model.w, model.h
        for y in range(h):
            for x in range(w):
                i = y * w + x
                fid = model.faction[i]
                if fid < 0:
                    continue
                if x + 1 < w and model.faction[i + 1] != fid:
                    p.drawPoint(x, y)
                if y + 1 < h and model.faction[i + w] != fid:
                    p.drawPoint(x, y)

    p.end()
    return img

def compose(base: QImage, overlay: Optional[QImage]) -> QImage:
    if overlay is None:
        return base
    img = QImage(base)  # copy
    p = QPainter(img)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
    p.drawImage(0, 0, overlay)
    p.end()
    return img
