#!/usr/bin/env python3
"""Compose a named bead cover with subtle rim light from saved cells and original art."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps

from bead_pattern import statistics, validate_project
from cover_lettering import NAME_STYLES, render_name


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


def background_frame(source, size, *, fit, zoom, focal, blur):
    """Fit original art uniformly; softly fill uncovered canvas with the same art."""
    ratios = (size[0]/source.width, size[1]/source.height)
    scale = (min(ratios) if fit == "contain" else max(ratios))*zoom
    scaled = tuple(max(1, round(v*scale)) for v in source.size)
    position = tuple(round((bound-extent)*anchor) for bound, extent, anchor in zip(size, scaled, focal))
    box = (max(0, position[0]), max(0, position[1]),
           min(size[0], position[0]+scaled[0]), min(size[1], position[1]+scaled[1]))
    # Crop first so the resized detail never exceeds the canvas, even for panoramas or zoom=3.
    source_box = ((box[0]-position[0])*source.width/scaled[0],
                  (box[1]-position[1])*source.height/scaled[1],
                  (box[2]-position[0])*source.width/scaled[0],
                  (box[3]-position[1])*source.height/scaled[1])
    visible = (box[2]-box[0], box[3]-box[1])
    detail = source.resize(visible, Image.Resampling.LANCZOS, box=source_box)
    detail = detail.filter(ImageFilter.GaussianBlur(size[0]*blur))
    backing = ImageOps.fit(source, size, Image.Resampling.LANCZOS, centering=focal)
    backing = backing.filter(ImageFilter.GaussianBlur(size[0]*max(0.04, blur*2.5)))
    layer = backing.copy()
    layer.paste(detail, box[:2])
    mask = Image.new("L", size)
    feather = max(0, min(round(min(size)*0.14), (min(visible)-1)//4))
    # Feather only internal edges, leaving a fully covered edge opaque.
    inset = (box[0]+(feather if box[0] else 0), box[1]+(feather if box[1] else 0),
             box[2]-1-(feather if box[2] < size[0] else 0),
             box[3]-1-(feather if box[3] < size[1] else 0))
    ImageDraw.Draw(mask).rectangle(inset, fill=255)
    if feather:
        mask = mask.filter(ImageFilter.GaussianBlur(feather/3))
    geometry = {"fit": fit, "uniform_scale": scale, "scaled_size": scaled,
                "canvas_box": box, "visible_source_box": source_box,
                "visible_fraction": ((source_box[2]-source_box[0])*(source_box[3]-source_box[1])
                                     / (source.width*source.height)),
                "backing": "same_reference_blurred_fill", "feather_pixels": feather}
    return Image.composite(layer, backing, mask), geometry


def rim_highlight(subject, size, position, cell, strength):
    """Soft light outside the silhouette; never brighten beads or internal holes."""
    logical_size = (subject.width//cell, subject.height//cell)
    logical = subject.getchannel("A").resize(logical_size, Image.Resampling.NEAREST)
    padded = Image.new("L", (logical.width+2, logical.height+2))
    padded.paste(logical, (1, 1))
    ImageDraw.floodfill(padded, (0, 0), 128)
    filled = padded.point(lambda value: 0 if value == 128 else 255)
    filled = filled.crop((1, 1, logical.width+1, logical.height+1)).resize(subject.size, Image.Resampling.NEAREST)
    silhouette = Image.new("L", size)
    silhouette.paste(filled, position)
    radius = size[0]*0.012
    outside = ImageChops.subtract(silhouette.filter(ImageFilter.GaussianBlur(radius)), silhouette)
    glow = Image.new("RGBA", size, (255, 246, 229, 0))
    glow.putalpha(outside.point(lambda value: round(value*strength)))
    return glow, {"strength": strength, "radius_pixels": radius, "color": [255, 246, 229],
                  "placement": "outside_silhouette_internal_holes_excluded"}


def render_cover(project_path, reference_path, output, *, reference_note,
                 reference_source=None, size=(1080, 1440), reference_crop=None,
                 focal=(0.5, 0.5), zoom=1.0, blur=0.016, background_fit="contain", brightness=0.86,
                 saturation=0.88, subject_width=0.60, subject_height=0.52,
                 center=(0.5, 0.49), texture=True, glow=0.40, show_name=True,
                 name_text=None, name_font=None, name_size=None, name_style="pingfang_light"):
    project_path, reference_path, output = (Path(p).resolve() for p in
                                           (project_path, reference_path, output))
    if output.exists():
        raise ValueError("Cover output already exists; use a new directory")
    if not reference_note or not reference_note.strip():
        raise ValueError("Record the visually checked character and costume in reference_note")
    if (len(size) != 2 or any(isinstance(v, bool) or not isinstance(v, int) for v in size)
            or not all(256 <= v <= 4096 for v in size) or size[0]*size[1] > 12_000_000):
        raise ValueError("Cover dimensions must be 256-4096, at most 12 megapixels")
    values = (*focal, *center, zoom, blur, brightness, saturation, subject_width, subject_height, glow)
    if (len(focal) != 2 or len(center) != 2 or not all(math.isfinite(v) for v in values)
            or not all(0 <= v <= 1 for v in (*focal, *center))
            or background_fit not in {"contain", "cover"}
            or not 0 <= glow <= 1
            or not 0.5 <= zoom <= 3 or not 0 < blur <= 0.15
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
    background, framing = background_frame(matte.convert("RGB"), size, fit=background_fit,
                                           zoom=zoom, focal=focal, blur=blur)
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
    halo, halo_info = rim_highlight(subject, size, position, cell, glow)
    cover.alpha_composite(halo)
    cover.alpha_composite(subject, position)
    name_info = None
    if show_name:
        cover, name_info = render_name(cover, project.get("title", "") if name_text is None else name_text,
                                      position[1]+subject.height, font_path=name_font, size_fraction=name_size,
                                      style=name_style)
    counts = statistics(rows)
    report = {
        "schema": "bead-cover/v1", "status": "cover_ready_for_review", "title": project.get("title"),
        "project": {"path": str(project_path), "sha256": project_hash},
        "reference": {"path": str(reference_path), "sha256": reference_hash,
                      "source": reference_source, "identity_and_costume_check": reference_note,
                      "original_size": reference_size, "crop": reference_crop},
        "layout": {"size": size, "focal": focal, "zoom": zoom, "blur_fraction": blur,
                   "background_framing": framing,
                   "blur_pixels": size[0]*blur, "brightness": brightness, "saturation": saturation,
                   "subject_width": subject_width, "subject_height": subject_height,
                   "center": center, "cell_pixels": cell, "subject_position": position,
                   "subject_bbox_cells": bbox, "texture": "fused_square" if texture else "flat",
                   "text": bool(show_name), "name": name_info, "glow": halo_info, "mirrored": False},
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
    parser.add_argument("--background-fit", choices=["contain", "cover"], default="contain",
                        help="Preserve the reference framing by default; soft same-art fill covers margins")
    parser.add_argument("--zoom", type=float, default=1.0, help="Uniform background scale, 0.5-3")
    parser.add_argument("--blur", type=float, default=0.016, help="Gaussian radius as a fraction of width")
    parser.add_argument("--brightness", type=float, default=0.86)
    parser.add_argument("--saturation", type=float, default=0.88)
    parser.add_argument("--subject-width", type=float, default=0.60)
    parser.add_argument("--subject-height", type=float, default=0.52)
    parser.add_argument("--center", nargs=2, type=float, default=(0.5, 0.49), metavar=("X", "Y"))
    parser.add_argument("--flat", action="store_true", help="Omit bead surface relief")
    parser.add_argument("--glow", type=float, default=0.40, help="Soft external rim light strength, 0-1")
    parser.add_argument("--no-name", action="store_true", help="Explicitly omit character-name lettering")
    parser.add_argument("--name-text", help="Reviewed Chinese character name; defaults to saved project title")
    parser.add_argument("--name-style", choices=NAME_STYLES, default="pingfang_light",
                        help="Default: white PingFang SC Light with corner quotes; no font substitution")
    parser.add_argument("--name-font", help="Existing licensed TTF/OTF/TTC; PingFang style requires PingFangSC-Light")
    parser.add_argument("--name-size", type=float, help="Name font size / cover width; default 48/1080 for PingFang")


def options(args):
    names = ("reference_note", "reference_source", "reference_crop", "size", "focal", "zoom", "blur", "background_fit",
             "brightness", "saturation", "subject_width", "subject_height", "center", "glow",
             "name_text", "name_font", "name_size", "name_style")
    return {**{name: getattr(args, name) for name in names}, "texture": not args.flat, "show_name": not args.no_name}


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
