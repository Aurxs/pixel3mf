#!/usr/bin/env python3
"""Make normal and horizontal-mirror bead charts, vector PDF, CSV and editable JSON."""
from __future__ import annotations

import argparse
from collections import Counter, deque
import csv
import hashlib
import json
import math
from pathlib import Path
import shutil

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

from bead_palette import load_palette, map_colors, validate_palette

ROOT = Path(__file__).resolve().parents[2] / "skills/codex/pixel-art-to-beads"
DEFAULT_PALETTE = ROOT / "assets/palettes/mard-221.json"


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def mirror(rows):
    return [list(reversed(row)) for row in rows]


def statistics(rows):
    count = Counter(code for row in rows for code in row if code is not None)
    return dict(sorted(count.items(), key=lambda item: (-item[1], item[0])))


def validate_project(project):
    if project.get("schema") != "pixel-art-to-beads/v1":
        raise ValueError("Unsupported project schema")
    validate_palette(project["palette"])
    rows = project["cells"]
    if not rows or not rows[0] or len(rows) > 256 or len(rows[0]) > 256:
        raise ValueError("Grid dimensions must be 1-256")
    width = len(rows[0])
    known = {c["code"] for c in project["palette"]["colors"]}
    if any(len(row) != width or any(c is not None and c not in known for c in row) for row in rows):
        raise ValueError("Ragged grid or unknown color code")
    if not statistics(rows):
        raise ValueError("Project contains no beads")
    return project


def components(rows):
    active = {(x, y) for y, row in enumerate(rows) for x, code in enumerate(row) if code is not None}
    found = []
    while active:
        start = min(active, key=lambda p: (p[1], p[0]))
        active.remove(start)
        queue, size = deque([start]), 0
        while queue:
            x, y = queue.popleft()
            size += 1
            for adjacent in ((x-1, y), (x+1, y), (x, y-1), (x, y+1)):
                if adjacent in active:
                    active.remove(adjacent)
                    queue.append(adjacent)
        found.append({"first_cell": [start[0]+1, start[1]+1], "beads": size})
    return sorted(found, key=lambda c: -c["beads"])


def find_font(explicit=None):
    candidates = [explicit] if explicit else [
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/usr/share/fonts/truetype/arphic/uming.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/msyh.ttc",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            try:
                pdfmetrics.registerFont(TTFont("BeadFont", candidate))
                ImageFont.truetype(candidate, 16)
                needed = set("镜像版拼豆图纸色颗用量清单行列页校准线钉距实际大小打印")
                if any(ord(c) not in pdfmetrics.getFont("BeadFont").face.charToGlyph for c in needed):
                    continue
                return candidate
            except (OSError, ValueError):
                continue
    raise ValueError("A Chinese-capable TrueType font is required; provide --font /path/to/font.ttf")


class Surface:
    """Top-left drawing coordinates shared by PNG and vector PDF."""
    def __init__(self, width, height, font, pdf=None):
        self.width, self.height, self.font_path, self.pdf = width, height, font, pdf
        self.fonts = {}
        if pdf is None:
            self.image = Image.new("RGB", (math.ceil(width), math.ceil(height)), "white")
            self.draw = ImageDraw.Draw(self.image)

    def font(self, size):
        size = max(1, round(size))
        if size not in self.fonts:
            self.fonts[size] = ImageFont.truetype(self.font_path, size)
        return self.fonts[size]

    def text(self, x, y, value, size=14, color="#24282D", center=False, max_width=None):
        value = str(value)
        if max_width:
            while pdfmetrics.stringWidth(value, "BeadFont", size) > max_width and size > 5:
                size -= 0.5
        if self.pdf:
            self.pdf.setFillColor(color)
            self.pdf.setFont("BeadFont", size)
            baseline = self.height-y-size*0.35
            if center:
                self.pdf.drawCentredString(x, baseline, value)
            else:
                self.pdf.drawString(x, baseline, value)
        else:
            self.draw.text((x, y), value, fill=color, font=self.font(size), anchor="mm" if center else "lm")

    def rect(self, x, y, w, h, color):
        if self.pdf:
            self.pdf.setFillColor(color)
            self.pdf.rect(x, self.height-y-h, w, h, fill=1, stroke=0)
        else:
            self.draw.rectangle((x, y, x+w, y+h), fill=color)

    def line(self, x1, y1, x2, y2, color="#CFD3D7", width=1):
        if self.pdf:
            self.pdf.setStrokeColor(color)
            self.pdf.setLineWidth(width)
            self.pdf.line(x1, self.height-y1, x2, self.height-y2)
        else:
            self.draw.line((x1, y1, x2, y2), fill=color, width=max(1, round(width)))


def rgb_hex(rgb):
    return "#" + "".join(f"{v:02X}" for v in rgb)


def ink(rgb):
    values = np.asarray(rgb) / 255
    linear = np.where(values > 0.04045, ((values+0.055)/1.055)**2.4, values/12.92)
    return "#FFFFFF" if float(linear @ [0.2126, 0.7152, 0.0722]) < 0.179 else "#111111"


def grid(surface, rows, palette, x, y, cell, major=5, offset=(0, 0)):
    colors = {c["code"]: c["rgb"] for c in palette["colors"]}
    width, height = len(rows[0]), len(rows)
    surface.rect(x-cell, y-cell, (width+2)*cell, (height+2)*cell, "#EEF0F2")
    for yy, row in enumerate(rows):
        for xx, code in enumerate(row):
            rgb = colors[code] if code is not None else [249, 249, 249]
            surface.rect(x+xx*cell, y+yy*cell, cell, cell, rgb_hex(rgb))
            if code is not None:
                surface.text(x+(xx+0.5)*cell, y+(yy+0.5)*cell, code, cell*0.34,
                             ink(rgb), center=True, max_width=cell*0.9)
            else:
                surface.text(x+(xx+0.5)*cell, y+(yy+0.5)*cell, "·", cell*0.4, "#BABEC3", center=True)
    for xx in range(width+1):
        strong = (xx+offset[0]) % major == 0
        surface.line(x+xx*cell, y, x+xx*cell, y+height*cell,
                     "#DC7777" if strong else "#B8BEC5", 1.4 if strong else 0.5)
    for yy in range(height+1):
        strong = (yy+offset[1]) % major == 0
        surface.line(x, y+yy*cell, x+width*cell, y+yy*cell,
                     "#DC7777" if strong else "#B8BEC5", 1.4 if strong else 0.5)
    for xx in range(width):
        for yy in (y-cell*0.5, y+(height+0.5)*cell):
            surface.text(x+(xx+0.5)*cell, yy, xx+offset[0]+1, cell*0.34, center=True)
    for yy in range(height):
        for xx in (x-cell*0.5, x+(width+0.5)*cell):
            surface.text(xx, y+(yy+0.5)*cell, yy+offset[1]+1, cell*0.34, center=True)


def chart_size(rows, counts):
    cell = 28
    width = max(960, (len(rows[0])+2)*cell+48)
    columns = max(1, (width-48)//164)
    height = 108+(len(rows)+2)*cell + math.ceil(len(counts)/columns)*38 + 68
    return width, height, cell, columns


def overview(surface, project, mirrored, major):
    rows = mirror(project["cells"]) if mirrored else project["cells"]
    counts = statistics(rows)
    width, height, cell, columns = chart_size(rows, counts)
    title = f"{project['title']} · 镜像版" if mirrored else project['title']
    surface.text(24, 36, title, 30, max_width=width-48)
    surface.text(24, 76, f"{len(rows[0])} × {len(rows)} / {len(counts)} 色 / 共 {sum(counts.values())} 颗", 23)
    x, y = (width-len(rows[0])*cell)/2, 108+cell
    grid(surface, rows, project["palette"], x, y, cell, major)
    colors = {c["code"]: c["rgb"] for c in project["palette"]["colors"]}
    legend_y = y+(len(rows)+1)*cell+24
    for i, (code, quantity) in enumerate(counts.items()):
        xx, yy = 24+(i % columns)*164, legend_y+(i//columns)*38
        surface.rect(xx, yy-12, 52, 26, rgb_hex(colors[code]))
        surface.text(xx+26, yy+1, code, 14, ink(colors[code]), center=True, max_width=48)
        surface.text(xx+63, yy+1, f"{quantity} 颗", 16)
    surface.text(24, height-27, project['palette'].get('name', '自定义色卡'), 14,
                 "#616770", max_width=width-48)


def preview(rows, palette, path):
    colors = {c["code"]: c["rgb"] for c in palette["colors"]}
    rgba = np.array([[colors[c]+[255] if c is not None else [0, 0, 0, 0] for c in row] for row in rows], dtype=np.uint8)
    image = Image.fromarray(rgba)
    image.resize((image.width*12, image.height*12), Image.Resampling.NEAREST).save(path)


def render_pdf(project, path, font, major, pitch=None):
    pdf = Canvas(str(path), pagesize=A4)
    pdf.setTitle(project['title'])
    page_w, page_h = A4
    width, height, cell, _ = chart_size(project["cells"], statistics(project["cells"]))
    scale = min((page_w-40)/width, (page_h-68)/height)
    for mirrored in (False, True):
        pdf.saveState()
        pdf.translate((page_w-width*scale)/2, page_h-28-height*scale)
        pdf.scale(scale, scale)
        overview(Surface(width, height, font, pdf), project, mirrored, major)
        pdf.restoreState()
        pdf.showPage()
        if cell*scale >= 12 and pitch is None:
            continue
        size = pitch*72/25.4 if pitch is not None else 18
        cols = max(1, int((page_w-48)/size)-2)
        lines = max(1, int((page_h-146)/size)-2)
        rows = mirror(project["cells"]) if mirrored else project["cells"]
        pages = math.ceil(len(rows[0])/cols)*math.ceil(len(rows)/lines)
        page = 0
        for y in range(0, len(rows), lines):
            for x in range(0, len(rows[0]), cols):
                page += 1
                tile = [row[x:x+cols] for row in rows[y:y+lines]]
                surface = Surface(page_w, page_h, font, pdf)
                title = f"{project['title']} · 镜像版" if mirrored else project['title']
                surface.text(24, 27, title, 16, max_width=page_w-48)
                surface.text(24, 54, f"第 {page}/{pages} 页 · 列 {x+1}-{x+len(tile[0])} / 行 {y+1}-{y+len(tile)}", 11)
                grid(surface, tile, project["palette"], 24+size, 85+size, size, major, (x, y))
                if pitch is not None:
                    surface.line(24, page_h-48, 24+50*72/25.4, page_h-48, "#111111", 1)
                    surface.text(24, page_h-27, f"50 mm 校准线 · 钉距 {pitch:g} mm · 按 100% 实际大小打印", 10)
                pdf.showPage()
    colors = {c["code"]: c["rgb"] for c in project["palette"]["colors"]}
    counts = list(statistics(project["cells"]).items())
    for offset in range(0, len(counts), 60):
        surface = Surface(page_w, page_h, font, pdf)
        surface.text(24, 30, f"用量清单 · {project['title']}", 18, max_width=page_w-48)
        for i, (code, quantity) in enumerate(counts[offset:offset+60]):
            x, y = 24+(i//30)*280, 95+(i % 30)*22
            surface.rect(x, y-8, 55, 18, rgb_hex(colors[code]))
            surface.text(x+27, y, code, 10, ink(colors[code]), center=True, max_width=51)
            surface.text(x+70, y, f"{quantity} 颗", 11)
        pdf.showPage()
    pdf.save()


def export_project(project, output, *, font=None, major=5, pitch=None, spare=0):
    validate_project(project)
    if major < 1 or not 0 <= spare <= 100 or (pitch is not None and not 1 <= pitch <= 20):
        raise ValueError("Invalid grid interval, spare percentage, or peg pitch (1-20 mm)")
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use a new empty output directory")
    font = find_font(font)
    needed = set(str(project["title"]) + str(project["palette"].get("name", "")))
    if any(ord(c) not in pdfmetrics.getFont("BeadFont").face.charToGlyph for c in needed):
        raise ValueError("Selected font cannot render the title or palette name; provide --font")
    output.mkdir(parents=True, exist_ok=True)
    counts = statistics(project["cells"])
    project["statistics"] = {"width": len(project["cells"][0]), "height": len(project["cells"]),
                             "total_beads": sum(counts.values()), "colors": len(counts), "counts": counts}
    project["components"] = components(project["cells"])
    project["render"] = {"major_every": major, "peg_pitch_mm": pitch, "spare_percent": spare,
                         "mirror": "horizontal_cells_only", "coordinates": "1-based top-left per variant"}
    project["status"] = "rendered_needs_visual_review"
    width, height, _, _ = chart_size(project["cells"], counts)
    for mirrored, name in ((False, "正常版"), (True, "镜像版")):
        surface = Surface(width, height, font)
        overview(surface, project, mirrored, major)
        surface.image.save(output / f"{name}.png", dpi=(300, 300))
        rows = mirror(project["cells"]) if mirrored else project["cells"]
        preview(rows, project["palette"], output / f"{name}_预览.png")
    render_pdf(project, output / "打印图纸.pdf", font, major, pitch)
    with (output / "用量清单.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["色号", "HEX", "准确用量", "建议备料"])
        colors = {c["code"]: c["rgb"] for c in project["palette"]["colors"]}
        for code, quantity in counts.items():
            writer.writerow([code, rgb_hex(colors[code]), quantity, math.ceil(quantity*(1+spare/100))])
    write_json(output / "图纸数据.json", project)
    return project


def create_project(source, palette, title, *, max_colors=None, allowed=None, locked=None, canvas=None,
                   fill=None):
    source = Path(source).resolve()
    image = ImageOps.exif_transpose(Image.open(source)).convert("RGBA")
    if max(image.size) > 256:
        raise ValueError("Input must be a logical grid up to 256 cells per axis; refine enlarged art first")
    rgba = np.array(image)
    if not set(np.unique(rgba[:, :, 3])).issubset({0, 255}):
        raise ValueError("Logical input requires binary alpha; run prepare_source.py for raw sources")
    if canvas:
        width, height = canvas
        if width < image.width or height < image.height or max(canvas) > 256:
            raise ValueError("Canvas must contain the original grid; resizing needs a separate reviewed edit")
        expanded = Image.new("RGBA", canvas)
        expanded.paste(image, ((width-image.width)//2, (height-image.height)//2))
        rgba = np.array(expanded)
    cells, mapping = map_colors(rgba, palette, max_colors, allowed, locked)
    if fill:
        known = {c["code"] for c in palette["colors"]}
        if fill not in known or (allowed and fill not in allowed):
            raise ValueError("Background fill must exist in the allowed palette")
        cells = [[code if code is not None else fill for code in row] for row in cells]
        if max_colors and len(statistics(cells)) > max_colors:
            raise ValueError("Background fill exceeds max-colors; reserve a color or increase the limit")
    return {"schema": "pixel-art-to-beads/v1", "title": title, "palette": palette,
            "source": {"path": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest()},
            "mapping": mapping, "background_fill": fill, "cells": cells}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Logical PNG, or saved project JSON for re-rendering")
    parser.add_argument("output", help="New empty output folder")
    parser.add_argument("--title")
    parser.add_argument("--palette", help="Palette JSON or CSV; default bundled MARD 221")
    parser.add_argument("--max-colors", type=int)
    parser.add_argument("--allowed", help="Comma-separated available color codes")
    parser.add_argument("--locked", help="Comma-separated anchors retained during palette reduction")
    parser.add_argument("--canvas", help="Larger canvas WxH; does not resample")
    parser.add_argument("--fill", help="Fill every transparent cell with this bead color")
    parser.add_argument("--font")
    parser.add_argument("--major-every", type=int)
    parser.add_argument("--peg-pitch-mm", type=float)
    parser.add_argument("--spare-percent", type=float)
    args = parser.parse_args()
    try:
        if Path(args.source).suffix.lower() == ".json":
            if any(v is not None for v in (args.palette, args.max_colors, args.allowed, args.locked, args.canvas, args.fill)):
                raise ValueError("Project re-render preserves colors; use the retained source PNG to remap")
            project = json.loads(Path(args.source).read_text(encoding="utf-8"))
            if args.title:
                project["title"] = args.title
        else:
            canvas = tuple(int(v) for v in args.canvas.lower().split("x")) if args.canvas else None
            if canvas and len(canvas) != 2:
                raise ValueError("Canvas format is WxH")
            project = create_project(args.source, load_palette(args.palette or DEFAULT_PALETTE),
                                     args.title or "拼豆作品", max_colors=args.max_colors,
                                     allowed=args.allowed.split(",") if args.allowed else None,
                                     locked=args.locked.split(",") if args.locked else None,
                                     canvas=canvas, fill=args.fill)
        settings = project.get("render", {})
        result = export_project(
            project, args.output, font=args.font,
            major=args.major_every if args.major_every is not None else settings.get("major_every", 5),
            pitch=args.peg_pitch_mm if args.peg_pitch_mm is not None else settings.get("peg_pitch_mm"),
            spare=args.spare_percent if args.spare_percent is not None else settings.get("spare_percent", 0),
        )
        if Path(args.source).suffix.lower() != ".json":
            ImageOps.exif_transpose(Image.open(args.source)).convert("RGBA").save(Path(args.output) / "源像素网格.png")
            shutil.copy2(args.source, Path(args.output) / ("原始输入"+Path(args.source).suffix.lower()))
        print(json.dumps({"output": str(Path(args.output).resolve()), "statistics": result["statistics"],
                          "components": len(result["components"]), "status": result["status"]}, ensure_ascii=False))
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, f"{error}\n")


if __name__ == "__main__":
    main()
