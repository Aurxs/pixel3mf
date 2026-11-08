#!/usr/bin/env python3
"""Compose a text-free bead cover from saved chart cells and original character art."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from bead_pattern import statistics, validate_project


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def foreground(project, cell, *, texture=True):
    """Render fused square beads without resampling, recoloring or filling holes."""
    rows = project["cells"]
    occupied = [(x, y) for y, row in enumerate(rows)
                for x, code in enumerate(row) if code is not None]
    bbox = (min(x for x, _ in occupied), min(y for _, y in occupied),
            max(x for x, _ in occupied)+1, max(y for _, y in occupied)+1)
    left, top, right, bottom = bbox
    image = Image.new("RGBA", ((right-left)*cell, (bottom-top)*cell))
    draw = ImageDraw.Draw(image)
    colors = {c["code"]: tuple(c["rgb"]) for c in project["palette"]["colors"]}
    for x, y in occupied:
        rgb = colors[rows[y][x]]
        xx, yy = (x-left)*cell, (y-top)*cell
        draw.rectangle((xx, yy, xx+cell-1, yy+cell-1), fill=rgb+(255,))
        if texture and cell >= 5:
            # A one-pixel lip suggests fused beads; cell centers retain exact palette RGB.
            light = tuple(round(v+(255-v)*0.12) for v in rgb)+(255,)
            dark = tuple(round(v*0.83) for v in rgb)+(255,)
            draw.line((xx, yy, xx+cell-2, yy), fill=light)
            draw.line((xx, yy+1, xx, yy+cell-2), fill=light)
            draw.line((xx+1, yy+cell-1, xx+cell-1, yy+cell-1), fill=dark)
            draw.line((xx+cell-1, yy+1, xx+cell-1, yy+cell-1), fill=dark)
    return image, bbox


def render_cover(project_path, reference_path, output, *, reference_note,
                 reference_source=None, size=(1080, 1440), reference_crop=None,
                 focal=(0.5, 0.5), zoom=1.12, blur=0.026, brightness=0.78,
                 saturation=0.88, subject_width=0.70, subject_height=0.62,
                 center=(0.5, 0.49), texture=True):
    project_path, reference_path, output = (Path(p).resolve() for p in
                                           (project_path, reference_path, output))
    if output.exists():
        raise ValueError("Cover output already exists; use a new directory")
    if not reference_note or not reference_note.strip():
        raise ValueError("Record the visually checked character and costume in reference_note")
    if (len(size) != 2 or any(isinstance(v, bool) or not isinstance(v, int) for v in size)
            or not all(256 <= v <= 4096 for v in size) or size[0]*size[1] > 12_000_000):
        raise ValueError("Cover dimensions must be 256-4096, at most 12 megapixels")
    values = (*focal, *center, zoom, blur, brightness, saturation, subject_width, subject_height)
    if (len(focal) != 2 or len(center) != 2 or not all(math.isfinite(v) for v in values)
            or not all(0 <= v <= 1 for v in (*focal, *center))
            or not 1 <= zoom <= 3 or not 0 < blur <= 0.15
            or not 0 < brightness <= 1.5 or not 0 <= saturation <= 2
            or not 0.1 <= subject_width <= 0.9 or not 0.1 <= subject_height <= 0.9):
        raise ValueError("Invalid cover layout or background settings")
    project_hash, reference_hash = digest(project_path), digest(reference_path)
    if project_hash == reference_hash:
        raise ValueError("Background must be separate original character reference art")
    project = validate_project(json.loads(project_path.read_text(encoding="utf-8")))
    with Image.open(reference_path) as source:
        source = ImageOps.exif_transpose(source).convert("RGBA")
    reference_size = source.size
    if max(reference_size) < 512:
        raise ValueError("Use the original large character reference, not a logical pixel grid")
    if reference_crop is not None:
        if (len(reference_crop) != 4 or any(not isinstance(v, int) for v in reference_crop)
                or not 0 <= reference_crop[0] < reference_crop[2] <= source.width
                or not 0 <= reference_crop[1] < reference_crop[3] <= source.height):
            raise ValueError("Reference crop must be an in-bounds left,top,right,bottom box")
        source = source.crop(reference_crop)
    # Flatten reference transparency before resizing to avoid hidden-RGB fringes.
    matte = Image.new("RGBA", source.size, (37, 39, 43, 255))
    matte.alpha_composite(source)
    background = ImageOps.fit(matte.convert("RGB"), size, Image.Resampling.LANCZOS,
                              bleed=(1-1/zoom)/2, centering=focal)
    background = background.filter(ImageFilter.GaussianBlur(size[0]*blur))
    background = ImageEnhance.Color(background).enhance(saturation)
    background = ImageEnhance.Brightness(background).enhance(brightness)
    # Soft edge falloff keeps the crisp subject prominent without a panel or caption.
    falloff = Image.radial_gradient("L").resize(size, Image.Resampling.BILINEAR)
    falloff = falloff.point(lambda v: round(v*0.16))
    background = Image.composite(Image.new("RGB", size, "black"), background, falloff)
    rows = project["cells"]
    points = [(x, y) for y, row in enumerate(rows) for x, code in enumerate(row) if code is not None]
    logical_size = (max(x for x, _ in points)-min(x for x, _ in points)+1,
                    max(y for _, y in points)-min(y for _, y in points)+1)
    cell = math.floor(min(size[0]*subject_width/logical_size[0],
                          size[1]*subject_height/logical_size[1]))
    if cell < 1:
        raise ValueError("Canvas is too small to show every bead; increase dimensions")
    subject, bbox = foreground(project, cell, texture=texture)
    position = (round(size[0]*center[0]-subject.width/2),
                round(size[1]*center[1]-subject.height/2))
    if (position[0] < 0 or position[1] < 0 or position[0]+subject.width > size[0]
            or position[1]+subject.height > size[1]):
        raise ValueError("Subject would be clipped; adjust center or subject size")
    shadow = Image.new("RGBA", size)
    alpha = Image.new("L", size)
    alpha.paste(subject.getchannel("A"), (position[0]+round(size[0]*0.006),
                                         position[1]+round(size[0]*0.012)))
    alpha = alpha.filter(ImageFilter.GaussianBlur(size[0]*0.012)).point(lambda v: round(v*0.38))
    shadow.putalpha(alpha)
    cover = background.convert("RGBA")
    cover.alpha_composite(shadow)
    cover.alpha_composite(subject, position)
    counts = statistics(rows)
    report = {
        "schema": "bead-cover/v1", "status": "cover_ready_for_review", "title": project.get("title"),
        "project": {"path": str(project_path), "sha256": project_hash},
        "reference": {"path": str(reference_path), "sha256": reference_hash,
                      "source": reference_source, "identity_and_costume_check": reference_note,
                      "original_size": reference_size, "crop": reference_crop},
        "layout": {"size": size, "focal": focal, "zoom": zoom, "blur_fraction": blur,
                   "blur_pixels": size[0]*blur, "brightness": brightness, "saturation": saturation,
                   "subject_width": subject_width, "subject_height": subject_height,
                   "center": center, "cell_pixels": cell, "subject_position": position,
                   "subject_bbox_cells": bbox, "texture": "fused_square" if texture else "flat",
                   "text": False, "mirrored": False},
        "statistics": {"width": len(rows[0]), "height": len(rows), "counts": counts,
                       "total_beads": sum(counts.values()), "colors": len(counts)},
        "products": {"cover": str(output/"封面.png"), "foreground": str(output/"前景.png"),
                     "background": str(output/"背景.png")},
    }
    # Check inputs again before publishing separate artifacts. Never export or rewrite charts.
    if digest(project_path) != project_hash or digest(reference_path) != reference_hash:
        raise ValueError("An input changed during rendering; retry from stable inputs")
    output.mkdir(parents=True, exist_ok=False)
    subject.save(output/"前景.png")
    background.save(output/"背景.png")
    cover.convert("RGB").save(output/"封面.png")
    report["products_sha256"] = {name: digest(path) for name, path in report["products"].items()}
    (output/"cover.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def add_options(parser):
    parser.add_argument("--reference", required=True, help="Original art used in character generation")
    parser.add_argument("--reference-note", required=True, help="Checked character and matching costume")
    parser.add_argument("--reference-source", help="Retained source URL or research record")
    parser.add_argument("--reference-crop", nargs=4, type=int, metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"))
    parser.add_argument("--size", nargs=2, type=int, default=(1080, 1440), metavar=("WIDTH", "HEIGHT"))
    parser.add_argument("--focal", nargs=2, type=float, default=(0.5, 0.5), metavar=("X", "Y"))
    parser.add_argument("--zoom", type=float, default=1.12)
    parser.add_argument("--blur", type=float, default=0.026, help="Gaussian radius as a fraction of width")
    parser.add_argument("--brightness", type=float, default=0.78)
    parser.add_argument("--saturation", type=float, default=0.88)
    parser.add_argument("--subject-width", type=float, default=0.70)
    parser.add_argument("--subject-height", type=float, default=0.62)
    parser.add_argument("--center", nargs=2, type=float, default=(0.5, 0.49), metavar=("X", "Y"))
    parser.add_argument("--flat", action="store_true", help="Omit bead surface relief")


def options(args):
    names = ("reference_note", "reference_source", "reference_crop", "size", "focal", "zoom", "blur",
             "brightness", "saturation", "subject_width", "subject_height", "center")
    return {**{name: getattr(args, name) for name in names}, "texture": not args.flat}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", help="Existing 图纸数据.json; never reconstruct a chart screenshot")
    parser.add_argument("output", help="New directory for cover and internal layers")
    add_options(parser)
    args = parser.parse_args()
    try:
        report = render_cover(args.project, args.reference, args.output, **options(args))
        print(json.dumps({"status": report["status"], "products": report["products"]}, ensure_ascii=False))
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, f"{error}\n")


if __name__ == "__main__":
    main()
