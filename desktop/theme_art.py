"""Original vector artwork for desktop themes, drawn at the native display scale.

Every theme paints its own scene, and every page gets a different subject:
a reward chest (overview), a route (queue), a gem (campaigns), a trophy (history),
a pulse (activity) and a gear (settings). Backdrops vary per page from a fixed
seed, so each page/theme pair is a distinct, repeatable image. Nothing here is
traced from or reproduces any game's art, logos or characters.
"""

from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPolygonF,
    QRadialGradient,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

from desktop.themes import Theme, theme


PAGES = ("overview", "queue", "campaigns", "history", "activity", "settings")


def _color(value: str, alpha: int | None = None) -> QColor:
    color = QColor(value)
    if alpha is not None:
        color.setAlpha(alpha)
    return color


def _seed(theme_key: str, page: str) -> random.Random:
    # Stable across runs (unlike hash()), so each image is always the same.
    return random.Random(sum((i + 1) * ord(ch) for i, ch in enumerate(f"{theme_key}:{page}")))


# --- Page subjects, centred on (0, 0) and sized to fit a square of side 2*s. ---

def motif_path(page: str, s: float) -> QPainterPath:
    path = QPainterPath()
    if page == "overview":  # Reward chest.
        path.addRoundedRect(QRectF(-0.9 * s, -0.42 * s, 1.8 * s, 1.22 * s), 0.16 * s, 0.16 * s)
        path.addRoundedRect(QRectF(-1.0 * s, -0.78 * s, 2.0 * s, 0.46 * s), 0.12 * s, 0.12 * s)
    elif page == "queue":  # Ordered list with a play marker on the first row.
        play = QPolygonF([QPointF(-0.95 * s, -0.78 * s), QPointF(-0.5 * s, -0.5 * s), QPointF(-0.95 * s, -0.22 * s)])
        path.addPolygon(play)
        path.closeSubpath()
        for index, length in enumerate((1.3, 1.05, 0.8)):
            top = (-0.66 + index * 0.6) * s
            path.addRoundedRect(QRectF(-0.3 * s, top, length * s, 0.32 * s), 0.16 * s, 0.16 * s)
        for index in (1, 2):
            path.addEllipse(QPointF(-0.72 * s, (-0.5 + index * 0.6) * s), 0.16 * s, 0.16 * s)
    elif page == "campaigns":  # Faceted gem.
        path.addPolygon(QPolygonF([
            QPointF(-0.55 * s, -0.7 * s), QPointF(0.55 * s, -0.7 * s), QPointF(0.98 * s, -0.22 * s),
            QPointF(0, 0.92 * s), QPointF(-0.98 * s, -0.22 * s),
        ]))
        path.closeSubpath()
    elif page == "history":  # Trophy.
        path.moveTo(-0.62 * s, -0.82 * s)
        path.lineTo(0.62 * s, -0.82 * s)
        path.cubicTo(0.62 * s, 0.05 * s, 0.32 * s, 0.32 * s, 0, 0.32 * s)
        path.cubicTo(-0.32 * s, 0.32 * s, -0.62 * s, 0.05 * s, -0.62 * s, -0.82 * s)
        path.closeSubpath()
        path.addRect(QRectF(-0.1 * s, 0.3 * s, 0.2 * s, 0.32 * s))
        path.addRoundedRect(QRectF(-0.48 * s, 0.6 * s, 0.96 * s, 0.24 * s), 0.06 * s, 0.06 * s)
    elif page == "activity":  # Signal disc.
        path.addEllipse(QPointF(0, 0), 0.92 * s, 0.92 * s)
    else:  # Settings gear.
        teeth = 8
        points = []
        for index in range(teeth * 2):
            angle = math.pi * index / teeth
            radius = (0.95 if index % 2 == 0 else 0.74) * s
            for offset in (-0.17, 0.17):
                a = angle + offset * (math.pi / teeth) * 2
                points.append(QPointF(math.cos(a) * radius, math.sin(a) * radius))
        path.addPolygon(QPolygonF(points))
        path.closeSubpath()
        hole = QPainterPath()
        hole.addEllipse(QPointF(0, 0), 0.32 * s, 0.32 * s)
        path = path.subtracted(hole)
    return path


def motif_details(p: QPainter, page: str, s: float, pen: QPen) -> None:
    """Inner lines that make each subject readable at small sizes."""
    p.save()
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    if page == "overview":
        p.drawRoundedRect(QRectF(-0.13 * s, -0.5 * s, 0.26 * s, 0.5 * s), 0.07 * s, 0.07 * s)
    elif page == "queue":
        pass  # The list reads clearly without inner lines.
    elif page == "campaigns":
        p.drawLine(QPointF(-0.98 * s, -0.22 * s), QPointF(0.98 * s, -0.22 * s))
        p.drawLine(QPointF(-0.3 * s, -0.7 * s), QPointF(-0.42 * s, -0.22 * s))
        p.drawLine(QPointF(0.3 * s, -0.7 * s), QPointF(0.42 * s, -0.22 * s))
        p.drawLine(QPointF(-0.42 * s, -0.22 * s), QPointF(0, 0.92 * s))
        p.drawLine(QPointF(0.42 * s, -0.22 * s), QPointF(0, 0.92 * s))
    elif page == "history":
        p.drawArc(QRectF(-0.95 * s, -0.7 * s, 0.6 * s, 0.6 * s), 90 * 16, 180 * 16)
        p.drawArc(QRectF(0.35 * s, -0.7 * s, 0.6 * s, 0.6 * s), 270 * 16, 180 * 16)
    elif page == "activity":
        line = QPolygonF([QPointF(x * s, y * s) for x, y in (
            (-0.75, 0.05), (-0.38, 0.05), (-0.22, -0.42), (0.0, 0.45), (0.18, -0.2), (0.32, 0.05), (0.75, 0.05))])
        p.drawPolyline(line)
    else:
        p.drawEllipse(QPointF(0, 0), 0.5 * s, 0.5 * s)
    p.restore()


def _panel(p: QPainter, rect: QRectF, radius: float, brush) -> None:
    clip = QPainterPath()
    clip.addRoundedRect(rect, radius, radius)
    p.setClipPath(clip)
    p.fillRect(rect, brush)


def _gradient(rect: QRectF, top: str, bottom: str, *, horizontal=False) -> QLinearGradient:
    end = rect.topRight() if horizontal else rect.bottomLeft()
    gradient = QLinearGradient(rect.topLeft(), end)
    gradient.setColorAt(0, QColor(top))
    gradient.setColorAt(1, QColor(bottom))
    return gradient


def _sparkle(p: QPainter, x: float, y: float, size: float, color: QColor) -> None:
    path = QPainterPath()
    path.moveTo(x, y - size)
    path.quadTo(x, y, x + size, y)
    path.quadTo(x, y, x, y + size)
    path.quadTo(x, y, x - size, y)
    path.quadTo(x, y, x, y - size)
    p.fillPath(path, color)


# --- Theme scenes. Each receives the full widget rect. ---

def _midnight(p: QPainter, rect: QRectF, page: str, t: Theme, rng: random.Random) -> None:
    a = t.art
    cx, cy = rect.center().x(), rect.center().y()
    s = min(rect.width(), rect.height()) * 0.235  # Outer ring (1.95 s) and sparkles stay inside.
    if rect.width() > rect.height() * 1.6:
        cx = rect.right() - rect.height() * 0.62
    p.setPen(QPen(_color(a["line"]), 1))
    p.setBrush(Qt.BrushStyle.NoBrush)
    for factor in (1.95, 1.48):
        p.drawEllipse(QPointF(cx, cy), s * factor, s * factor)
    p.setPen(Qt.PenStyle.NoPen)
    for _ in range(5):
        angle = rng.uniform(0, math.tau)
        radius = s * rng.choice((1.48, 1.95))
        size = rng.uniform(2.2, 4.2)
        p.setBrush(_color(a["glow"]))
        p.drawEllipse(QPointF(cx + math.cos(angle) * radius, cy + math.sin(angle) * radius), size, size)
    if rect.width() > rect.height() * 1.6:  # Wide headers get a soft trail of dots.
        for index in range(9):
            x = rect.left() + rect.width() * 0.08 + index * rect.width() * 0.055
            y = cy + math.sin(index * 0.9 + rng.uniform(0, 1)) * rect.height() * 0.18
            p.setBrush(_color(a["glow"], 40 + index * 18))
            p.drawEllipse(QPointF(x, y), 2.2, 2.2)
    p.save()
    p.translate(cx, cy)
    p.rotate(-10 if page == "overview" else rng.uniform(-12, 12))
    gradient = QLinearGradient(-s, -s, s, s)
    gradient.setColorAt(0, _color(a["a"]))
    gradient.setColorAt(1, _color(a["b"]))
    p.setBrush(gradient)
    p.drawPath(motif_path(page, s))
    if page == "overview":
        p.setBrush(_color(a["c"]))
        p.drawRoundedRect(QRectF(-1.0 * s, -0.78 * s, 2.0 * s, 0.46 * s), 0.12 * s, 0.12 * s)
        p.setBrush(_color(a["d"]))
        p.drawRoundedRect(QRectF(-0.13 * s, -0.5 * s, 0.26 * s, 0.5 * s), 0.07 * s, 0.07 * s)
    else:
        motif_details(p, page, s, QPen(_color(a["c"], 200), max(1.5, s * 0.06)))
    p.restore()
    pen = QPen(_color(a["c"]), 2)
    p.setPen(pen)
    for dx, dy in ((-1.6, 1.65), (1.85, -1.45)):
        x, y = cx + dx * s, cy + dy * s
        p.drawLine(QPointF(x - 5, y), QPointF(x + 5, y))
        p.drawLine(QPointF(x, y - 5), QPointF(x, y + 5))


def _resonant_tide(p: QPainter, rect: QRectF, page: str, t: Theme, rng: random.Random) -> None:
    a = t.art
    _panel(p, rect, t.radius, _gradient(rect, a["sky1"], a["sky2"]))
    wide = rect.width() > rect.height() * 1.6
    s = rect.height() * (0.26 if wide else 0.24)
    cx = rect.right() - rect.height() * 0.7 if wide else rect.center().x()
    cy = rect.center().y() - (0 if wide else rect.height() * 0.06)
    # A moon-like halo of pale light behind the subject.
    halo = QRadialGradient(QPointF(cx, cy), s * 2.6)
    halo.setColorAt(0, _color(a["foam"], 70))
    halo.setColorAt(1, _color(a["foam"], 0))
    p.fillRect(rect, halo)
    # Flowing waves across the panel; phase differs per page.
    phase = rng.uniform(0, math.tau)
    for layer in range(5):
        y0 = rect.top() + rect.height() * (0.58 + layer * 0.09)
        path = QPainterPath(QPointF(rect.left(), y0))
        steps = 40
        for index in range(steps + 1):
            x = rect.left() + rect.width() * index / steps
            y = y0 + math.sin(index / steps * math.tau * (1.2 + layer * 0.25) + phase + layer) * rect.height() * 0.035
            path.lineTo(x, y)
        path.lineTo(rect.right(), rect.bottom())
        path.lineTo(rect.left(), rect.bottom())
        path.closeSubpath()
        p.fillPath(path, _color(a["deep"], 90 + layer * 25))
        p.setPen(QPen(_color(a["wave"], 70 + layer * 25), 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
    # Resonance ripples: arcs radiating from the subject.
    p.setBrush(Qt.BrushStyle.NoBrush)
    for index in range(4):
        radius = s * (1.35 + index * 0.42)
        pen = QPen(_color(a["wave"], 150 - index * 32), 1.4)
        pen.setDashPattern([6, 4] if index % 2 else [1, 0])
        p.setPen(pen)
        start = rng.randint(10, 60)
        p.drawArc(QRectF(cx - radius, cy - radius, radius * 2, radius * 2), start * 16, (180 + rng.randint(30, 90)) * 16)
    # Tuning ticks on the inner ring.
    p.setPen(QPen(_color(a["gold"], 200), 1.4))
    for index in range(24):
        angle = math.tau * index / 24
        inner, outer = s * 1.2, s * (1.29 if index % 3 else 1.36)
        p.drawLine(QPointF(cx + math.cos(angle) * inner, cy + math.sin(angle) * inner),
                   QPointF(cx + math.cos(angle) * outer, cy + math.sin(angle) * outer))
    # Floating gold shards.
    for _ in range(7):
        x = rng.uniform(rect.left() + 10, rect.right() - 10)
        y = rng.uniform(rect.top() + 8, rect.top() + rect.height() * 0.55)
        _sparkle(p, x, y, rng.uniform(2, 4.5), _color(a["gold"], rng.randint(120, 230)))
    p.save()
    p.translate(cx, cy)
    gradient = QLinearGradient(0, -s, 0, s)
    gradient.setColorAt(0, _color(a["foam"]))
    gradient.setColorAt(1, _color(a["wave"]))
    p.setPen(QPen(_color(a["gold"]), max(1.5, s * 0.05)))
    p.setBrush(gradient)
    p.drawPath(motif_path(page, s))
    motif_details(p, page, s, QPen(_color(a["deep"], 220), max(1.4, s * 0.06)))
    p.restore()


def _neon_hollow(p: QPainter, rect: QRectF, page: str, t: Theme, rng: random.Random) -> None:
    a = t.art
    _panel(p, rect, t.radius, _color(a["ink"]))
    wide = rect.width() > rect.height() * 1.6
    # Halftone dots fading across the panel.
    p.setPen(Qt.PenStyle.NoPen)
    step = 9
    for row in range(int(rect.height() / step) + 1):
        for column in range(int(rect.width() / step) + 1):
            x = rect.left() + column * step + (step / 2 if row % 2 else 0)
            y = rect.top() + row * step
            weight = (column * step) / max(1.0, rect.width())
            radius = 0.4 + 2.4 * weight
            p.setBrush(_color(a["yellow"], 40))
            p.drawEllipse(QPointF(x, y), radius, radius)
    # Diagonal hazard band.
    band = QPainterPath()
    height = rect.height() * 0.2
    offset = rng.uniform(0.25, 0.45) * rect.height()
    band.addRect(QRectF(rect.left() - rect.width(), rect.top() + offset, rect.width() * 3, height))
    p.save()
    p.translate(rect.center())
    p.rotate(rng.choice((-14, -10, 10, 14)))
    p.translate(-rect.center())
    p.fillPath(band, _color(a["yellow"]))
    p.setClipPath(band, Qt.ClipOperation.IntersectClip)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_color(a["ink"]))
    for index in range(-20, 60):
        x = rect.left() + index * 18
        stripe = QPolygonF([QPointF(x, rect.top() + offset), QPointF(x + 9, rect.top() + offset),
                            QPointF(x + 9 - height, rect.top() + offset + height), QPointF(x - height, rect.top() + offset + height)])
        p.drawPolygon(stripe)
    p.restore()
    clip = QPainterPath()
    clip.addRoundedRect(rect, t.radius, t.radius)
    p.setClipPath(clip)
    # CRT screen holding the subject.
    side = rect.height() * (0.74 if wide else 0.56)
    sx = rect.right() - side - rect.height() * 0.22 if wide else rect.center().x() - side / 2
    sy = rect.center().y() - side / 2 - (0 if wide else rect.height() * 0.04)
    screen = QRectF(sx, sy, side, side * 0.86)
    p.setPen(QPen(_color(a["paper"]), 3))
    p.setBrush(_color(a["screen"]))
    p.drawRoundedRect(screen, side * 0.12, side * 0.12)
    p.setPen(QPen(_color(a["yellow"], 26), 1))
    y = screen.top() + 4
    while y < screen.bottom() - 2:
        p.drawLine(QPointF(screen.left() + 6, y), QPointF(screen.right() - 6, y))
        y += 3
    # Little antenna and dial.
    p.setPen(QPen(_color(a["paper"]), 2.5))
    top = QPointF(screen.center().x(), screen.top())
    p.drawLine(top, QPointF(top.x() - side * 0.2, top.y() - side * 0.18))
    p.drawLine(top, QPointF(top.x() + side * 0.18, top.y() - side * 0.2))
    s = side * 0.27
    p.save()
    p.translate(screen.center())
    p.translate(2.5, 2.5)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_color(a["pink"]))
    p.drawPath(motif_path(page, s))
    p.translate(-2.5, -2.5)
    p.setBrush(_color(a["yellow"]))
    p.drawPath(motif_path(page, s))
    motif_details(p, page, s, QPen(_color(a["ink"]), max(1.6, s * 0.08)))
    p.restore()
    # Stickers: a tilted tag with a page number and a starburst.
    tag_x = rect.left() + rect.width() * (0.08 if wide else 0.06)
    tag_y = rect.top() + rect.height() * (0.14 if wide else 0.08)
    p.save()
    p.translate(tag_x, tag_y)
    p.rotate(-8)
    p.setPen(QPen(_color(a["ink"]), 2))
    p.setBrush(_color(a["paper"]))
    p.drawRect(QRectF(0, 0, 62, 22))
    font = p.font()
    font.setBold(True)
    font.setPixelSize(12)
    p.setFont(font)
    p.setPen(_color(a["ink"]))
    p.drawText(QRectF(0, 0, 62, 22), Qt.AlignmentFlag.AlignCenter, f"No.0{PAGES.index(page) + 1}")
    p.restore()
    burst = QPolygonF()
    bx = rect.left() + rect.width() * (0.42 if wide else 0.18)
    by = rect.bottom() - rect.height() * 0.2
    for index in range(16):
        angle = math.tau * index / 16
        radius = 13 if index % 2 == 0 else 6
        burst.append(QPointF(bx + math.cos(angle) * radius, by + math.sin(angle) * radius))
    p.setPen(QPen(_color(a["ink"]), 1.5))
    p.setBrush(_color(a["teal"]))
    p.drawPolygon(burst)


def _office(p: QPainter, rect: QRectF, page: str, t: Theme, rng: random.Random) -> None:
    a = t.art
    _panel(p, rect, t.radius, _gradient(rect, a["sky"], a["paper"], horizontal=True))
    wide = rect.width() > rect.height() * 1.6
    p.setPen(QPen(_color(a["line"], 120), 1))
    grid = 14
    x = rect.left()
    while x < rect.right():
        p.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
        x += grid
    y = rect.top()
    while y < rect.bottom():
        p.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
        y += grid

    def document(x: float, y: float, w: float, h: float, tilt: float) -> None:
        p.save()
        p.translate(x + w / 2, y + h / 2)
        p.rotate(tilt)
        body = QRectF(-w / 2, -h / 2, w, h)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_color(a["ink"], 28))
        p.drawRoundedRect(body.translated(2, 3), 4, 4)
        p.setPen(QPen(_color(a["line"]), 1))
        p.setBrush(_color(a["paper"]))
        p.drawRoundedRect(body, 4, 4)
        p.setPen(QPen(_color(a["line"]), 2))
        for index in range(4):
            yy = -h / 2 + h * (0.22 + index * 0.17)
            p.drawLine(QPointF(-w * 0.34, yy), QPointF(w * (0.34 - 0.12 * (index % 2)), yy))
        p.restore()

    def chart(x: float, y: float, w: float, h: float) -> None:
        """A small card whose content matches the page."""
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_color(a["ink"], 28))
        p.drawRoundedRect(QRectF(x + 2, y + 3, w, h), 5, 5)
        p.setPen(QPen(_color(a["line"]), 1))
        p.setBrush(_color(a["paper"]))
        p.drawRoundedRect(QRectF(x, y, w, h), 5, 5)
        palette = (a["blue"], a["green"], a["orange"])
        inner = QRectF(x + w * 0.1, y + h * 0.16, w * 0.8, h * 0.7)
        if page == "queue":  # Checklist.
            for index in range(3):
                row = inner.top() + index * inner.height() / 3 + inner.height() / 6
                done = index == 0
                p.setPen(QPen(_color(a["blue"] if done else a["line"]), 1.5))
                p.setBrush(_color(a["blue"]) if done else _color(a["paper"]))
                p.drawRoundedRect(QRectF(inner.left(), row - 5, 10, 10), 2, 2)
                p.setPen(QPen(_color(a["line"]), 2.5))
                p.drawLine(QPointF(inner.left() + 16, row), QPointF(inner.right() - index * inner.width() * 0.15, row))
        elif page == "campaigns":  # Calendar with highlighted days.
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(_color(a["blue"]))
            p.drawRect(QRectF(x, y, w, h * 0.18))
            for row in range(3):
                for column in range(6):
                    cell = QRectF(inner.left() + column * inner.width() / 6 + 1, inner.top() + h * 0.08 + row * inner.height() / 3.4,
                                  inner.width() / 6 - 3, inner.height() / 4.2)
                    highlighted = (row * 6 + column) % 5 == rng.randint(0, 4)
                    p.setBrush(_color(a["orange"] if highlighted else a["sky"]))
                    p.drawRoundedRect(cell, 2, 2)
        elif page == "history":  # Pie chart.
            radius = min(inner.width(), inner.height()) / 2
            centre = QPointF(inner.left() + radius, inner.center().y())
            start = 90 * 16
            for index, share in enumerate((0.45, 0.33, 0.22)):
                span = int(share * 360 * 16)
                p.setPen(QPen(_color(a["paper"]), 1.5))
                p.setBrush(_color(palette[index]))
                p.drawPie(QRectF(centre.x() - radius, centre.y() - radius, radius * 2, radius * 2), start, span)
                start += span
            p.setPen(QPen(_color(a["line"]), 2.5))
            for index in range(3):
                yy = inner.top() + inner.height() * (0.25 + index * 0.25)
                p.drawLine(QPointF(centre.x() + radius + 8, yy), QPointF(inner.right(), yy))
        elif page == "activity":  # Line chart.
            p.setPen(QPen(_color(a["line"]), 1))
            p.drawLine(inner.bottomLeft(), inner.bottomRight())
            dots = [QPointF(inner.left() + inner.width() * index / 6,
                            inner.bottom() - inner.height() * rng.uniform(0.15, 0.95)) for index in range(7)]
            p.setPen(QPen(_color(a["green"]), 2.2))
            p.drawPolyline(QPolygonF(dots))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(_color(a["green"]))
            for point in dots:
                p.drawEllipse(point, 2.2, 2.2)
        elif page == "settings":  # Toggle switches.
            for index in range(3):
                row = inner.top() + index * inner.height() / 3 + inner.height() / 6
                on = index != 1
                track = QRectF(inner.right() - 22, row - 6, 22, 12)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(_color(a["blue"] if on else a["line"]))
                p.drawRoundedRect(track, 6, 6)
                p.setBrush(_color(a["paper"]))
                p.drawEllipse(QPointF(track.right() - 6 if on else track.left() + 6, row), 4.5, 4.5)
                p.setPen(QPen(_color(a["line"]), 2.5))
                p.drawLine(QPointF(inner.left(), row), QPointF(inner.right() - 32, row))
        else:  # Bar chart on the overview.
            bars = [rng.uniform(0.3, 0.9) for _ in range(5)]
            p.setPen(Qt.PenStyle.NoPen)
            for index, value in enumerate(bars):
                bw = w / 8
                bx = x + w * 0.12 + index * bw * 1.35
                p.setBrush(_color(palette[index % 3]))
                p.drawRoundedRect(QRectF(bx, y + h * 0.88 - h * 0.7 * value, bw, h * 0.7 * value), 2, 2)

    if wide:
        document(rect.left() + rect.width() * 0.08, rect.top() + rect.height() * 0.2, rect.height() * 0.48,
                 rect.height() * 0.62, rng.uniform(-8, -3))
        chart(rect.left() + rect.width() * 0.3, rect.top() + rect.height() * 0.24, rect.height() * 0.95,
              rect.height() * 0.56)
    else:
        document(rect.left() + rect.width() * 0.1, rect.top() + rect.height() * 0.12, rect.width() * 0.3,
                 rect.width() * 0.38, rng.uniform(-9, -4))
        chart(rect.left() + rect.width() * 0.12, rect.bottom() - rect.height() * 0.36, rect.width() * 0.46,
              rect.height() * 0.24)
    # Sticky note.
    note = rect.height() * (0.3 if wide else 0.17)
    nx = rect.right() - rect.height() * (1.45 if wide else 0.4) - note
    ny = rect.top() + rect.height() * (0.12 if wide else 0.62)
    p.save()
    p.translate(nx + note / 2, ny + note / 2)
    p.rotate(rng.uniform(4, 9))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_color("#fff1a6"))
    p.drawRect(QRectF(-note / 2, -note / 2, note, note))
    p.setPen(QPen(_color("#d3b54a"), 1.5))
    p.drawLine(QPointF(-note * 0.3, -note * 0.1), QPointF(note * 0.3, -note * 0.1))
    p.drawLine(QPointF(-note * 0.3, note * 0.15), QPointF(note * 0.15, note * 0.15))
    p.restore()
    # App tile with the subject.
    tile = rect.height() * (0.66 if wide else 0.42)
    tx = rect.right() - tile - rect.height() * (0.2 if wide else 0.14)
    ty = rect.center().y() - tile / 2 - (0 if wide else rect.height() * 0.1)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_color(a["ink"], 40))
    p.drawRoundedRect(QRectF(tx + 2, ty + 4, tile, tile), tile * 0.18, tile * 0.18)
    p.setBrush(_gradient(QRectF(tx, ty, tile, tile), "#3d82e8", a["blue"]))
    p.drawRoundedRect(QRectF(tx, ty, tile, tile), tile * 0.18, tile * 0.18)
    s = tile * 0.28
    p.save()
    p.translate(tx + tile / 2, ty + tile / 2)
    p.setBrush(_color("#ffffff"))
    p.drawPath(motif_path(page, s))
    motif_details(p, page, s, QPen(_color(a["blue"]), max(1.4, s * 0.08)))
    p.restore()


def _starlit_rail(p: QPainter, rect: QRectF, page: str, t: Theme, rng: random.Random) -> None:
    a = t.art
    _panel(p, rect, t.radius, _gradient(rect, a["sky1"], a["sky2"]))
    wide = rect.width() > rect.height() * 1.6
    nebula = QRadialGradient(QPointF(rect.left() + rect.width() * rng.uniform(0.2, 0.5), rect.top()), rect.width() * 0.6)
    nebula.setColorAt(0, _color(a["violet"], 70))
    nebula.setColorAt(1, _color(a["violet"], 0))
    p.fillRect(rect, nebula)
    p.setPen(Qt.PenStyle.NoPen)
    for _ in range(int(rect.width() * rect.height() / 260)):
        x, y = rng.uniform(rect.left(), rect.right()), rng.uniform(rect.top(), rect.bottom())
        size = rng.choice((0.6, 0.8, 1.0, 1.4))
        p.setBrush(_color(a["star"], rng.randint(90, 230)))
        p.drawEllipse(QPointF(x, y), size, size)
    # Rails converging to a horizon point beneath the subject.
    s = rect.height() * (0.24 if wide else 0.22)
    cx = rect.right() - rect.height() * 0.75 if wide else rect.center().x()
    cy = rect.center().y() - rect.height() * (0.08 if wide else 0.12)
    horizon = QPointF(cx, cy + s * 1.15)
    p.setPen(QPen(_color(a["rail"], 220), 1.6))
    spread = rect.width() * (0.5 if wide else 0.7)
    for side in (-1, 1):
        p.drawLine(horizon, QPointF(horizon.x() + side * spread, rect.bottom() + 4))
    for index in range(1, 7):
        progress = (index / 7) ** 1.8
        y = horizon.y() + (rect.bottom() - horizon.y()) * progress
        half = spread * progress
        p.setPen(QPen(_color(a["rail"], 70 + index * 22), 1 + progress * 2))
        p.drawLine(QPointF(horizon.x() - half * 0.9, y), QPointF(horizon.x() + half * 0.9, y))
    # A small constellation in the open sky.
    points = []
    base_x = rect.left() + rect.width() * (0.08 if wide else 0.1)
    for index in range(5):
        points.append(QPointF(base_x + index * rect.width() * (0.07 if wide else 0.15) + rng.uniform(-6, 6),
                              rect.top() + rect.height() * rng.uniform(0.18, 0.5)))
    p.setPen(QPen(_color(a["gold"], 120), 1))
    p.drawPolyline(QPolygonF(points))
    for point in points:
        _sparkle(p, point.x(), point.y(), 4, _color(a["star"]))
    # Orbit rings and the subject.
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(_color(a["gold"], 160), 1.2))
    p.drawEllipse(QPointF(cx, cy), s * 1.45, s * 1.45)
    p.save()
    p.translate(cx, cy)
    p.rotate(-18)
    p.setPen(QPen(_color(a["gold"], 110), 1))
    p.drawEllipse(QPointF(0, 0), s * 1.95, s * 0.7)
    p.restore()
    glow = QRadialGradient(QPointF(cx, cy), s * 1.4)
    glow.setColorAt(0, _color(a["gold"], 70))
    glow.setColorAt(1, _color(a["gold"], 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(glow)
    p.drawEllipse(QPointF(cx, cy), s * 1.4, s * 1.4)
    p.save()
    p.translate(cx, cy)
    gradient = QLinearGradient(0, -s, 0, s)
    gradient.setColorAt(0, _color(a["star"]))
    gradient.setColorAt(1, _color(a["gold"]))
    p.setPen(QPen(_color(a["sky2"]), max(1.2, s * 0.05)))
    p.setBrush(gradient)
    p.drawPath(motif_path(page, s))
    motif_details(p, page, s, QPen(_color(a["sky1"]), max(1.4, s * 0.07)))
    p.restore()
    _sparkle(p, cx + s * 1.05, cy - s * 1.1, 7, _color(a["star"]))


def _anomaly_city(p: QPainter, rect: QRectF, page: str, t: Theme, rng: random.Random) -> None:
    a = t.art
    _panel(p, rect, t.radius, _gradient(rect, a["night1"], a["night2"]))
    wide = rect.width() > rect.height() * 1.6
    s = rect.height() * (0.22 if wide else 0.2)
    cx = rect.right() - rect.height() * 0.75 if wide else rect.center().x()
    cy = rect.top() + rect.height() * (0.42 if wide else 0.36)
    # The rift: a tall glowing tear in the sky.
    rift = QRadialGradient(QPointF(cx, cy), s * 2.4)
    rift.setColorAt(0, _color(a["violet"], 160))
    rift.setColorAt(0.5, _color(a["pink"], 60))
    rift.setColorAt(1, _color(a["pink"], 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(rift)
    p.drawEllipse(QPointF(cx, cy), s * 2.4, s * 2.4)
    # Thin rift arcs circling the subject, opening at a different angle on each page.
    p.setBrush(Qt.BrushStyle.NoBrush)
    opening = rng.randint(0, 359)
    for index, (radius, color) in enumerate(((1.5, a["cyan"]), (1.75, a["pink"]), (2.0, a["violet"]))):
        pen = QPen(_color(color, 200 - index * 45), 1.6 - index * 0.3)
        p.setPen(pen)
        p.drawArc(QRectF(cx - s * radius, cy - s * radius, s * radius * 2, s * radius * 2),
                  (opening + index * 40) * 16, (230 - index * 30) * 16)
    # Skyline with lit windows; heights vary per page.
    x = rect.left() - 4
    while x < rect.right():
        width = rng.uniform(16, 34)
        height = rect.height() * rng.uniform(0.2, 0.48)
        building = QRectF(x, rect.bottom() - height, width, height + 2)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_color("#07050c"))
        p.drawRect(building)
        p.setPen(QPen(_color(rng.choice((a["pink"], a["cyan"])), 120), 1))
        p.drawLine(building.topLeft(), building.topRight())
        p.setPen(Qt.PenStyle.NoPen)
        for wy in range(int(building.top() + 6), int(rect.bottom() - 4), 7):
            for wx in range(int(building.left() + 4), int(building.right() - 4), 6):
                if rng.random() < 0.22:
                    p.setBrush(_color(rng.choice((a["window"], a["cyan"], a["pink"])), rng.randint(110, 220)))
                    p.drawRect(QRectF(wx, wy, 2.5, 3))
        x += width + rng.uniform(1, 5)
    # Glitch blocks.
    for _ in range(6):
        gw, gh = rng.uniform(14, 46), rng.uniform(2, 5)
        gx = rng.uniform(rect.left(), rect.right() - gw)
        gy = rng.uniform(rect.top() + 6, rect.top() + rect.height() * 0.6)
        p.setBrush(_color(rng.choice((a["pink"], a["cyan"])), rng.randint(90, 180)))
        p.drawRect(QRectF(gx, gy, gw, gh))
    # Subject with chromatic split.
    p.save()
    p.translate(cx, cy)
    p.setPen(Qt.PenStyle.NoPen)
    for dx, color in ((-3, a["cyan"]), (3, a["pink"])):
        p.translate(dx, 0)
        p.setBrush(_color(color, 210))
        p.drawPath(motif_path(page, s))
        p.translate(-dx, 0)
    p.setBrush(_color("#fbf3ff"))
    p.drawPath(motif_path(page, s))
    motif_details(p, page, s, QPen(_color(a["violet"]), max(1.4, s * 0.08)))
    p.restore()


_PAINTERS = {
    "midnight": _midnight,
    "resonant_tide": _resonant_tide,
    "neon_hollow": _neon_hollow,
    "office": _office,
    "starlit_rail": _starlit_rail,
    "anomaly_city": _anomaly_city,
}


def paint(p: QPainter, rect: QRectF, page: str, t: Theme) -> None:
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    _PAINTERS[t.key](p, rect, page, t, _seed(t.key, page))
    p.restore()


class ThemeArt(QWidget):
    """Decorative page artwork that follows the active theme."""

    def __init__(self, page: str, width: int, height: int, parent=None):
        super().__init__(parent)
        if page not in PAGES:
            raise ValueError(page)
        self.page = page
        self.theme = theme(None)
        self.setFixedSize(width, height)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setAccessibleName("Decorative artwork")

    def set_theme(self, value: Theme) -> None:
        self.theme = value
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        paint(painter, QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), self.page, self.theme)
        painter.end()


__all__ = ["PAGES", "ThemeArt", "motif_path", "paint"]
