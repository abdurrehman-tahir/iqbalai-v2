#!/usr/bin/env python3
"""Composite the IqbalAI "Join us for free" panel onto the blank two-panel
background, producing the Authentik flow background.

Input : infrastructure/authentik/login-bg-raw.png   (blank two-panel green art)
Output: infrastructure/authentik/login-bg.png        (right panel filled in)

Run:  api/.venv/bin/python infrastructure/authentik/make_login_bg.py
Re-run safe — always regenerates from the raw art.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
RAW = HERE / "login-bg-raw.png"
OUT = HERE / "login-bg.png"

ARIAL = "/System/Library/Fonts/Supplemental/Arial.ttf"
ARIAL_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

INK = (22, 52, 26)          # dark green text
MUTED = (75, 107, 80)
GREEN = (46, 125, 50)       # brand green button
PILL_BG = (255, 255, 255)
PILL_BORDER = (198, 230, 200)

# Brand mark colors for the little social glyphs
GOOGLE = (66, 133, 244)
FACEBOOK = (24, 119, 242)
GITHUB = (36, 41, 46)


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def center_text(draw, cx, y, text, fnt, fill):
    w = draw.textbbox((0, 0), text, font=fnt)[2]
    draw.text((cx - w / 2, y), text, font=fnt, fill=fill)


def social_pill(draw, cx, cy, w, h, glyph, glyph_color, label, fnt, glyph_fnt):
    """A rounded white pill: colored circle glyph + label, centered on (cx, cy)."""
    x0, y0 = cx - w / 2, cy - h / 2
    draw.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=h / 2.6,
                           fill=PILL_BG, outline=PILL_BORDER, width=2)
    # icon circle
    r = h * 0.30
    icx = x0 + h * 0.55
    draw.ellipse([icx - r, cy - r, icx + r, cy + r], fill=glyph_color)
    gw = draw.textbbox((0, 0), glyph, font=glyph_fnt)[2]
    gh = draw.textbbox((0, 0), glyph, font=glyph_fnt)[3]
    draw.text((icx - gw / 2, cy - gh / 2 - 2), glyph, font=glyph_fnt, fill="white")
    # label
    lw = draw.textbbox((0, 0), label, font=fnt)[2]
    draw.text((icx + r + 12, cy - fnt.size * 0.62), label, font=fnt, fill=INK)


def main() -> None:
    img = Image.open(RAW).convert("RGB")
    W, H = img.size
    draw = ImageDraw.Draw(img)

    # Right panel bounds (measured from the art, relative to size).
    rp_left, rp_right = 0.517 * W, 0.945 * W
    cx = (rp_left + rp_right) / 2

    f_title = font(ARIAL_BOLD, 46)
    f_sub = font(ARIAL, 24)
    f_pill = font(ARIAL_BOLD, 17)
    f_glyph = font(ARIAL_BOLD, 15)
    f_or = font(ARIAL, 18)
    f_btn = font(ARIAL_BOLD, 19)
    f_trial = font(ARIAL, 16)

    center_text(draw, cx, 0.42 * H, "Join us for free", f_title, INK)
    center_text(draw, cx, 0.51 * H, "Create account with", f_sub, INK)

    # Row of three social pills
    pill_w, pill_h, gap = 148, 44, 16
    row_y = 0.60 * H
    start = cx - (3 * pill_w + 2 * gap) / 2 + pill_w / 2
    social_pill(draw, start, row_y, pill_w, pill_h, "G", GOOGLE, "Google", f_pill, f_glyph)
    social_pill(draw, start + pill_w + gap, row_y, pill_w, pill_h, "f", FACEBOOK, "Facebook", f_pill, f_glyph)
    social_pill(draw, start + 2 * (pill_w + gap), row_y, pill_w, pill_h, "GH", GITHUB, "GitHub", f_pill, f_glyph)

    # "or" divider with lines
    or_y = 0.675 * H
    center_text(draw, cx, or_y, "or", f_or, MUTED)
    draw.line([cx - 130, or_y + 12, cx - 34, or_y + 12], fill=PILL_BORDER, width=2)
    draw.line([cx + 34, or_y + 12, cx + 130, or_y + 12], fill=PILL_BORDER, width=2)

    # CREATE ACCOUNT button
    btn_w, btn_h = 230, 46
    by = 0.735 * H
    draw.rounded_rectangle([cx - btn_w / 2, by, cx + btn_w / 2, by + btn_h],
                           radius=btn_h / 2, fill=GREEN)
    bt = "CREATE ACCOUNT"
    bw = draw.textbbox((0, 0), bt, font=f_btn)[2]
    draw.text((cx - bw / 2, by + btn_h / 2 - f_btn.size * 0.62), bt, font=f_btn, fill="white")

    center_text(draw, cx, 0.82 * H, "Enjoy 14-day trial with premium content for free", f_trial, MUTED)

    img.save(OUT)
    print(f"WROTE {OUT} ({img.size[0]}x{img.size[1]})")


if __name__ == "__main__":
    main()
