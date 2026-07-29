#!/usr/bin/env python3
"""Composite IqbalAI marketing art onto the blank two-panel background.

LEFT panel  = ambient glow/grid only. The Authentik form card (sidebar_left +
              custom.css) floats here as a compact glass card — never paint
              form-shaped UI into this panel (fluid CSS width ≠ fixed art %).
RIGHT panel = premium SaaS marketing copy (kicker, headline, body, bullets).

Run:  python infrastructure/authentik/make_login_bg.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
RAW = HERE / "login-bg-raw.png"
OUT = HERE / "login-bg.png"

_FONT_CANDIDATES = [
    (Path(r"C:\Windows\Fonts\arialbd.ttf"), Path(r"C:\Windows\Fonts\arial.ttf")),
    (
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    ),
    (
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/DejaVuSans.ttf"),
    ),
]

INK = (18, 48, 22)
MUTED = (70, 100, 74)
BODY = (55, 85, 60)
GREEN = (46, 125, 50)
GREEN_BRIGHT = (67, 160, 71)
GREEN_SOFT = (102, 187, 106)
GREEN_DEEP = (27, 94, 32)
GREEN_WASH = (236, 248, 238)
WHITE = (255, 255, 255)
CARD_BORDER = (185, 220, 188)


def resolve_fonts() -> tuple[Path, Path]:
    for bold, regular in _FONT_CANDIDATES:
        if bold.is_file() and regular.is_file():
            return bold, regular
    print("ERROR: no usable fonts found", file=sys.stderr)
    raise SystemExit(1)


def load_font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size)


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=fnt)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def center_text(draw, cx, y, text, fnt, fill) -> int:
    tw, th = text_size(draw, text, fnt)
    draw.text((cx - tw / 2, y), text, font=fnt, fill=fill)
    return th


def wrap_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    fnt: ImageFont.FreeTypeFont,
    max_width: float,
) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        tw, _ = text_size(draw, test, fnt)
        if tw <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def glow_ellipse(base, box, color, alpha, blur) -> None:
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse(box, fill=(*color, alpha))
    base.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)))


def soft_shadow_rect(base, box, radius, blur=14, alpha=48) -> None:
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(
        [box[0] + 3, box[1] + 5, box[2] + 3, box[3] + 7],
        radius=radius,
        fill=(20, 60, 25, alpha),
    )
    base.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)))


def star(draw, x, y, size, fill) -> None:
    pts = []
    for i in range(8):
        ang = math.pi / 2 * i / 2 - math.pi / 2
        r = size if i % 2 == 0 else size * 0.38
        pts.append((x + r * math.cos(ang), y + r * math.sin(ang)))
    draw.polygon(pts, fill=fill)


def ring(draw, cx, cy, r, width, fill) -> None:
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=fill, width=width)


def paint_panel_glass(base: Image.Image, box: tuple[float, float, float, float]) -> None:
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle(box, radius=36, fill=(*GREEN_WASH, 220))
    d.rounded_rectangle(
        [box[0] + 10, box[1] + 10, box[2] - 10, box[3] - 10],
        radius=28,
        outline=(*CARD_BORDER, 180),
        width=2,
    )
    base.alpha_composite(layer)


def draw_grid(draw, box, step=28, color=(255, 255, 255, 55)) -> None:
    x0, y0, x1, y1 = box
    x = x0 + step
    while x < x1:
        draw.line([x, y0, x, y1], fill=color, width=1)
        x += step
    y = y0 + step
    while y < y1:
        draw.line([x0, y, x1, y], fill=color, width=1)
        y += step


def draw_check(draw, x, y, size=14) -> None:
    """Filled green circle with a simple white checkmark."""
    r = size / 2
    draw.ellipse([x, y, x + size, y + size], fill=GREEN)
    # check stroke
    cx, cy = x + r, y + r
    draw.line([(cx - 3.5, cy), (cx - 1, cy + 3), (cx + 4, cy - 3.5)], fill=WHITE, width=2)


def main() -> None:
    bold_path, regular_path = resolve_fonts()
    img = Image.open(RAW).convert("RGBA")
    w, h = img.size

    lp = (0.055 * w, 0.08 * h, 0.48 * w, 0.92 * h)
    rp = (0.517 * w, 0.08 * h, 0.945 * w, 0.92 * h)
    rcx = (rp[0] + rp[2]) / 2
    content_w = (rp[2] - rp[0]) * 0.78
    content_x = rcx - content_w / 2

    glow_ellipse(img, (0.05 * w, 0.05 * h, 0.45 * w, 0.55 * h), GREEN_SOFT, 45, 45)
    glow_ellipse(img, (0.55 * w, 0.15 * h, 0.95 * w, 0.55 * h), GREEN_BRIGHT, 50, 40)
    glow_ellipse(img, (0.15 * w, 0.55 * h, 0.55 * w, 0.95 * h), GREEN_DEEP, 30, 50)
    glow_ellipse(img, (0.55 * w, 0.55 * h, 0.95 * w, 0.95 * h), GREEN, 35, 45)

    # Right panel glass frame for marketing; left stays ambient (form card is CSS).
    paint_panel_glass(img, rp)

    draw = ImageDraw.Draw(img)
    draw_grid(draw, [lp[0] + 24, lp[1] + 24, lp[2] - 24, lp[3] - 24], step=36, color=(255, 255, 255, 40))
    draw_grid(draw, [rp[0] + 24, rp[1] + 24, rp[2] - 24, rp[3] - 24], step=36, color=(255, 255, 255, 45))

    # Sparse accents only — reduce clutter
    ring(draw, rp[0] + 48, 0.18 * h, 18, 2, (*GREEN_SOFT, 140))
    star(draw, rp[2] - 48, 0.16 * h, 9, GREEN_BRIGHT)
    ring(draw, rp[2] - 56, 0.84 * h, 22, 2, (*GREEN, 90))

    f_kicker = load_font(bold_path, 12)
    f_title = load_font(bold_path, 40)
    f_tag = load_font(regular_path, 17)
    f_body = load_font(regular_path, 14)
    f_bullet = load_font(regular_path, 14)

    # --- Vertically centered marketing block ---
    # Estimate block height, then start so the block sits mid-panel.
    body_copy = (
        "Iqbal AI helps teachers, students and schools create personalized "
        "learning experiences, automate routine tasks, and gain meaningful "
        "educational insights through AI-powered tools."
    )
    bullets = [
        "AI-powered lesson planning",
        "Personalized student learning",
        "School analytics & reporting",
    ]

    # Measure wrapped body
    body_lines = wrap_lines(draw, body_copy, f_body, content_w)
    body_line_h = text_size(draw, "Ag", f_body)[1] + 6
    body_block_h = len(body_lines) * body_line_h
    bullet_block_h = len(bullets) * 32
    # kicker(~34) + gap + title(~48) + gap + tag(~24) + gap + divider(~20) + gap + body + gap + bullets
    block_h = 34 + 22 + 48 + 14 + 24 + 22 + 20 + 18 + body_block_h + 22 + bullet_block_h
    y = ((rp[1] + rp[3]) / 2) - block_h / 2

    # Kicker pill
    kicker = "POWERED BY AI"
    kw, kh = text_size(draw, kicker, f_kicker)
    pad_x, pad_y = 18, 8
    pill = (
        rcx - (kw + 2 * pad_x) / 2,
        y,
        rcx + (kw + 2 * pad_x) / 2,
        y + kh + 2 * pad_y,
    )
    soft_shadow_rect(img, pill, radius=18, blur=8, alpha=28)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(pill, radius=18, fill=GREEN)
    draw.text((rcx - kw / 2, y + pad_y - 1), kicker, font=f_kicker, fill=WHITE)
    y = pill[3] + 22

    # Title
    th = center_text(draw, rcx, y, "Welcome to Iqbal AI", f_title, INK)
    y += th + 14

    # Tagline
    th = center_text(draw, rcx, y, "Smarter learning for modern classrooms.", f_tag, MUTED)
    y += th + 22

    # Divider
    draw.line([rcx - 70, y, rcx - 10, y], fill=GREEN, width=2)
    draw.line([rcx + 10, y, rcx + 70, y], fill=GREEN, width=2)
    draw.polygon([(rcx, y - 5), (rcx + 5, y), (rcx, y + 5), (rcx - 5, y)], fill=GREEN_BRIGHT)
    y += 20

    # Body (left-aligned within content column for SaaS readability)
    for line in body_lines:
        draw.text((content_x, y), line, font=f_body, fill=BODY)
        y += body_line_h
    y += 18

    # Feature bullets
    for item in bullets:
        draw_check(draw, content_x, y + 2, size=16)
        draw.text((content_x + 26, y + 1), item, font=f_bullet, fill=INK)
        y += 32

    img.convert("RGB").save(OUT, quality=95)
    print(f"WROTE {OUT} ({w}x{h})")


if __name__ == "__main__":
    main()
