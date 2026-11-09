"""Licensed, readable character-name lettering for bead presentation covers."""
from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import subprocess

from fontTools.ttLib import TTCollection, TTFont, TTLibError
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_ROOT = Path(__file__).resolve().parents[2]/"skills/codex/pixel-art-to-beads/assets/fonts"
DEFAULT_NAME_FONT = FONT_ROOT/"LXGWWenKaiLite-Regular.ttf"
PINGFANG_POSTSCRIPT = "PingFangSC-Light"
PINGFANG_PATHS = (Path("/System/Library/Fonts/PingFang.ttc"),
                  Path("/System/Library/Fonts/Supplemental/PingFang.ttc"),
                  Path("/Library/Fonts/PingFang.ttc"))
NAME_STYLES = ("pingfang_light", "warm_calligraphic")


def font_names(font):
    names = font["name"]
    return {"family": names.getDebugName(1), "style": names.getDebugName(2),
            "postscript_name": names.getDebugName(6)}


@lru_cache(maxsize=8)
def font_info(path, stamp, length, required_postscript=None):
    """Inspect TTF/OTF/TTC faces without extracting or copying font files."""
    path = Path(path)
    try:
        with path.open("rb") as source:
            collection = source.read(4) == b"ttcf"
        if collection:
            with path.open("rb") as stream, TTCollection(stream, lazy=True) as fonts:
                face_count = len(fonts.fonts)
        else:
            face_count = 1
        selected = None
        for index in range(face_count):
            with path.open("rb") as stream, TTFont(stream, fontNumber=index if collection else -1, lazy=True) as font:
                names = font_names(font)
                if required_postscript is None or names["postscript_name"] == required_postscript:
                    glyphs = frozenset(code for code, glyph in (font.getBestCmap() or {}).items()
                                       if glyph != ".notdef")
                    selected = index, names, glyphs
                    break
    except (OSError, TTLibError, KeyError) as error:
        raise ValueError("Name font must be a readable TrueType/OpenType font or collection") from error
    if selected is None:
        raise ValueError(f"Name font does not contain required face {required_postscript}; no substitute used")
    index, names, glyphs = selected
    info = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "face_index": index, **names,
            "license": "environment font; verify permission separately; font file is not redistributed"}
    if path == DEFAULT_NAME_FONT.resolve():
        source = json.loads((FONT_ROOT/"source.json").read_text())
        if source["sha256"] != info["sha256"]:
            raise ValueError("Bundled name font differs from its licensed source record")
        info.update(family=source["family"], license=source["license"],
                    source=source["font_url"], license_path=str(FONT_ROOT/"OFL.txt"))
    return glyphs, info


def resolve_name_font(font_path, style):
    required = PINGFANG_POSTSCRIPT if style == "pingfang_light" else None
    if font_path or required is None:
        path = Path(font_path or DEFAULT_NAME_FONT).expanduser().resolve()
        try:
            stat = path.stat()
        except OSError as error:
            raise ValueError(f"Name font unavailable: {path}; required face: {required or style}") from error
        return path, font_info(str(path), stat.st_mtime_ns, stat.st_size, required)
    candidates = list(PINGFANG_PATHS)
    # Fontconfig may return a fallback. Always inspect the file's actual PostScript face.
    try:
        result = subprocess.run(["fc-match", "-f", "%{file}", "PingFang SC:style=Light"],
                                capture_output=True, text=True, timeout=5, check=False)
        if result.returncode == 0 and result.stdout.strip():
            candidates.append(Path(result.stdout.strip()))
    except (OSError, subprocess.TimeoutExpired):
        pass
    for candidate in dict.fromkeys(candidates):
        if not candidate.is_file():
            continue
        path = candidate.resolve()
        stat = path.stat()
        try:
            return path, font_info(str(path), stat.st_mtime_ns, stat.st_size, required)
        except ValueError:
            continue
    raise ValueError("Required font PingFang SC Light (PingFangSC-Light) is unavailable. "
                     "Use an authorized environment with this font or --name-font pointing to its existing "
                     "TTF/OTF/TTC; no substitute used. Do not copy Apple system fonts into the repository. "
                     "Use --no-name only for a separately requested text-free cover.")


def quoted_name(text):
    if text.startswith("「") and text.endswith("」"):
        text = text[1:-1].strip()
    if not text or "「" in text or "」" in text:
        raise ValueError("Character name must have one balanced pair of corner quotes")
    return f"「{text}」"


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


def render_name(cover, text, subject_bottom, *, font_path=None, size_fraction=None,
                style="pingfang_light"):
    """Place a verified font below the subject; never substitute a requested face."""
    if (not isinstance(text, str) or not text.strip() or len(text) > 80
            or any(ord(char) < 32 for char in text)):
        raise ValueError("Character name must be a visible single line of at most 80 characters")
    if style not in NAME_STYLES:
        raise ValueError("Unknown name style")
    thin = style == "pingfang_light"
    if size_fraction is None:
        size_fraction = 96/1080 if thin else 0.078
    if not math.isfinite(size_fraction) or not 0.025 <= size_fraction <= 0.12:
        raise ValueError("Name size must be 0.025-0.12 of canvas width")
    text = text.strip()
    if thin:
        text = quoted_name(text)
    path, (glyphs, provenance) = resolve_name_font(font_path, style)
    missing = [char for char in text if ord(char) not in glyphs]
    if missing:
        raise ValueError(f"Name font {provenance['postscript_name']} lacks glyphs: "
                         + "".join(dict.fromkeys(missing)) + "; provide a licensed font covering the name and quotes; no substitute used")
    width, height = cover.size
    font_size = max(12, round(width*size_fraction))
    minimum = max(10, round(width*0.025))
    while True:
        font = ImageFont.truetype(str(path), font_size, index=provenance["face_index"])
        tracking = max(1, round(font_size*(0.125 if thin else 0.10)))
        mask = lettering_mask(text, font, tracking)
        if mask.width <= width*0.78:
            break
        font_size -= 1
        if font_size < minimum:
            raise ValueError("Character name is too long; use a shorter reviewed name")
    if thin:
        x, y = round((width-mask.width)/2), round(height*(1138/1440)-mask.height/2)
        if y <= subject_bottom+round(height*0.025) or x < 0 or y+mask.height > height:
            raise ValueError("Name would be clipped or overlap the subject; move the subject up, reduce its size or use --no-name")
        ink = Image.new("RGBA", mask.size, (255, 255, 255, 0))
        ink.putalpha(mask)
        result = cover.convert("RGBA")
        result.alpha_composite(ink, (x, y))
        bbox = [x, y, x+mask.width, y+mask.height]
        return result, {"text": text, "style": style, "font": dict(provenance),
                        "font_pixels": font_size, "tracking_pixels": tracking,
                        "ink_bbox": bbox, "effect_bbox": bbox,
                        "fill": [255, 255, 255], "stroke_pixels": 0,
                        "shadow": False, "gradient": False, "corner_quotes": True}
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
