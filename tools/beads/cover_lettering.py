"""Licensed, readable character-name lettering for bead presentation covers."""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from reportlab.pdfbase.ttfonts import TTFont, TTFError

FONT_ROOT = Path(__file__).resolve().parents[2]/"skills/codex/pixel-art-to-beads/assets/fonts"
DEFAULT_NAME_FONT = FONT_ROOT/"LXGWWenKaiLite-Regular.ttf"


@lru_cache(maxsize=8)
def font_info(path, stamp, length):
    path = Path(path)
    try:
        parsed = TTFont("CoverName", str(path))
    except (OSError, TTFError) as error:
        raise ValueError("Name font must be a readable TrueType font") from error
    info = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "license": "user-supplied; verify permission separately"}
    if path == DEFAULT_NAME_FONT.resolve():
        source = json.loads((FONT_ROOT/"source.json").read_text())
        if source["sha256"] != info["sha256"]:
            raise ValueError("Bundled name font differs from its licensed source record")
        info.update(family=source["family"], license=source["license"],
                    source=source["font_url"], license_path=str(FONT_ROOT/"OFL.txt"))
    return frozenset(parsed.face.charToGlyph), info


def lettering_mask(text, font, tracking):
    positions, boxes, cursor = [], [], 0.0
    for char in text:
        left, top, right, bottom = font.getbbox(char)
        positions.append(cursor)
        boxes.append((cursor+left, top, cursor+right, bottom))
        cursor += font.getlength(char)+tracking
    left = math.floor(min(b[0] for b in boxes))
    top = min(b[1] for b in boxes)
    right = math.ceil(max(b[2] for b in boxes))
    bottom = max(b[3] for b in boxes)
    if right <= left or bottom <= top:
        raise ValueError("Character name has no visible glyphs")
    mask = Image.new("L", (right-left, bottom-top))
    draw = ImageDraw.Draw(mask)
    for char, cursor in zip(text, positions):
        draw.text((cursor-left, -top), char, font=font, fill=255)
    return mask


def render_name(cover, text, subject_bottom, *, font_path=None, size_fraction=0.078):
    """Place warm calligraphic lettering below the subject, with safe fitting."""
    if (not isinstance(text, str) or not text.strip() or len(text) > 80
            or any(ord(char) < 32 for char in text)):
        raise ValueError("Character name must be a visible single line of at most 80 characters")
    if not math.isfinite(size_fraction) or not 0.025 <= size_fraction <= 0.12:
        raise ValueError("Name size must be 0.025-0.12 of canvas width")
    text = text.strip()
    path = Path(font_path or DEFAULT_NAME_FONT).resolve()
    stat = path.stat()
    glyphs, provenance = font_info(str(path), stat.st_mtime_ns, stat.st_size)
    missing = [char for char in text if ord(char) not in glyphs]
    if missing:
        raise ValueError("Name font lacks glyphs: " + "".join(dict.fromkeys(missing)))
    width, height = cover.size
    font_size = max(12, round(width*size_fraction))
    minimum = max(10, round(width*0.025))
    while True:
        font = ImageFont.truetype(str(path), font_size)
        tracking = max(1, round(font_size*0.10))
        mask = lettering_mask(text, font, tracking)
        if mask.width <= width*0.78:
            break
        font_size -= 1
        if font_size < minimum:
            raise ValueError("Character name is too long; use a shorter reviewed name")
    stroke = max(1, round(width*0.0015))
    softness = max(1, width*0.003)
    offset = max(1, round(width*0.003))
    padding = math.ceil(softness*3)+stroke+offset
    x, y = round((width-mask.width)/2), subject_bottom+round(height*0.055)
    if x-padding < 0 or x+mask.width+padding > width or y+mask.height+padding > height:
        raise ValueError("Name would be clipped; move the subject up, reduce its size or use --no-name")
    alpha = Image.new("L", cover.size)
    alpha.paste(mask, (x, y))
    shadow_alpha = Image.new("L", cover.size)
    shadow_alpha.paste(mask, (x+offset, y+offset))
    shadow_alpha = shadow_alpha.filter(ImageFilter.GaussianBlur(softness)).point(lambda v: round(v*0.65))
    shadow = Image.new("RGBA", cover.size, (27, 25, 38, 0))
    shadow.putalpha(shadow_alpha)
    result = cover.convert("RGBA")
    result.alpha_composite(shadow)
    outline = Image.new("RGBA", cover.size, (56, 44, 51, 0))
    outline.putalpha(alpha.filter(ImageFilter.MaxFilter(stroke*2+1)).point(lambda v: round(v*0.70)))
    result.alpha_composite(outline)
    top, bottom = (255, 248, 235), (226, 205, 170)
    gradient = Image.new("RGBA", (1, mask.height))
    for row in range(mask.height):
        fraction = row/max(1, mask.height-1)
        gradient.putpixel((0, row), tuple(round(a+(b-a)*fraction) for a, b in zip(top, bottom))+(255,))
    ink = Image.new("RGBA", cover.size)
    ink.paste(gradient.resize(mask.size), (x, y))
    ink.putalpha(alpha)
    result.alpha_composite(ink)
    return result, {"text": text, "style": "warm_calligraphic", "font": dict(provenance),
                    "font_pixels": font_size, "tracking_pixels": tracking,
                    "ink_bbox": [x, y, x+mask.width, y+mask.height],
                    "effect_bbox": [x-padding, y-padding, x+mask.width+padding, y+mask.height+padding],
                    "fill_top": top, "fill_bottom": bottom, "stroke_pixels": stroke}
