from __future__ import annotations

import io
import math
import textwrap
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .schemas import GeneratePosterRequest


FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/msyh.ttc",
]


def render_mock_background(size: tuple[int, int], seed_text: str) -> Image.Image:
    width, height = size
    image = Image.new("RGB", size)
    draw = ImageDraw.Draw(image)
    seed = sum(ord(char) for char in seed_text)
    start = ((seed * 3) % 180 + 35, (seed * 7) % 140 + 45, (seed * 11) % 120 + 65)
    end = ((seed * 13) % 100 + 110, (seed * 17) % 120 + 80, (seed * 19) % 130 + 70)
    for y in range(height):
        ratio = y / max(height - 1, 1)
        color = tuple(int(start[i] * (1 - ratio) + end[i] * ratio) for i in range(3))
        draw.line([(0, y), (width, y)], fill=color)
    for i in range(9):
        radius = int(width * (0.16 + (i % 3) * 0.06))
        x = int((seed * (i + 5) * 37) % width)
        y = int(height * (0.12 + i * 0.09))
        overlay = Image.new("RGBA", size, (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        odraw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=(255, 255, 255, 22))
        image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    return image.filter(ImageFilter.GaussianBlur(radius=0.4))


def compose_poster(background_bytes: bytes | None, request: GeneratePosterRequest) -> Image.Image:
    size = parse_size(request.size)
    if background_bytes:
        image = Image.open(io.BytesIO(background_bytes)).convert("RGB")
        image = cover_resize(image, size)
    else:
        image = render_mock_background(size, request.brief.theme)
    if request.overlay_text:
        image = overlay_text(image, request)
    return image


def cover_resize(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    source_w, source_h = image.size
    scale = max(target_w / source_w, target_h / source_h)
    resized = image.resize((math.ceil(source_w * scale), math.ceil(source_h * scale)), Image.Resampling.LANCZOS)
    left = (resized.width - target_w) // 2
    top = (resized.height - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def overlay_text(image: Image.Image, request: GeneratePosterRequest) -> Image.Image:
    width, height = image.size
    canvas = image.convert("RGBA")
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    title = request.brief.main_title or request.brief.theme
    subtitle = request.brief.subtitle or ""
    bullets = request.brief.selling_points[:3]

    bottom_h = int(height * 0.36)
    draw.rounded_rectangle(
        (int(width * 0.06), height - bottom_h - int(height * 0.04), int(width * 0.94), int(height * 0.94)),
        radius=28,
        fill=(0, 0, 0, 118),
    )
    x = int(width * 0.105)
    y = height - bottom_h + int(height * 0.015)
    max_text_width = int(width * 0.79)

    title_font = font_for_size(int(width * 0.082), bold=True)
    body_font = font_for_size(int(width * 0.034), bold=False)
    bullet_font = font_for_size(int(width * 0.037), bold=True)

    y = draw_wrapped(draw, title, title_font, x, y, max_text_width, fill=(255, 255, 255, 255), line_gap=10)
    if subtitle:
        y += int(height * 0.018)
        y = draw_wrapped(draw, subtitle, body_font, x, y, max_text_width, fill=(238, 244, 255, 235), line_gap=8)
    if bullets:
        y += int(height * 0.022)
        for bullet in bullets:
            y = draw_wrapped(draw, f"• {bullet}", bullet_font, x, y, max_text_width, fill=(255, 245, 210, 245), line_gap=7)
            y += 7
    return Image.alpha_composite(canvas, overlay).convert("RGB")


def draw_wrapped(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, x: int, y: int, max_width: int, fill: tuple[int, int, int, int], line_gap: int) -> int:
    for line in wrap_for_width(draw, text, font, max_width):
        draw.text((x, y), line, font=font, fill=fill)
        bbox = draw.textbbox((x, y), line, font=font)
        y = bbox[3] + line_gap
    return y


def wrap_for_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> Iterable[str]:
    if not text:
        return []
    lines: list[str] = []
    current = ""
    for char in text:
        candidate = current + char
        if draw.textlength(candidate, font=font) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = char
    if current:
        lines.append(current)
    return lines


def font_for_size(size: int, bold: bool) -> ImageFont.FreeTypeFont:
    candidates = FONT_CANDIDATES if bold else FONT_CANDIDATES[1:] + FONT_CANDIDATES[:1]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default(size=size)


def parse_size(value: str) -> tuple[int, int]:
    width, height = value.lower().split("x", 1)
    return int(width), int(height)
