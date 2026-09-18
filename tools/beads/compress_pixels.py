#!/usr/bin/env python3
"""Reusable size-constrained pixel compression: prepare -> optional AI -> finish."""
from __future__ import annotations

import argparse
from collections import Counter, deque
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image

from bead_palette import lab, load_palette, map_colors
from bead_pattern import DEFAULT_PALETTE, components, statistics


def save_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def exterior_shell(occupied):
    """One cell inside the outside contour; enclosed transparent holes are excluded."""
    occupied = np.asarray(occupied, dtype=bool)
    padded = np.pad(occupied, 1, constant_values=False)
    exterior = np.zeros(padded.shape, dtype=bool)
    exterior[0, 0] = True
    queue = deque([(0, 0)])
    while queue:
        y, x = queue.popleft()
        for yy, xx in ((y-1, x), (y+1, x), (y, x-1), (y, x+1)):
            if 0 <= yy < padded.shape[0] and 0 <= xx < padded.shape[1]:
                if not padded[yy, xx] and not exterior[yy, xx]:
                    exterior[yy, xx] = True
                    queue.append((yy, xx))
    adjacent = (exterior[:-2, 1:-1] | exterior[2:, 1:-1]
                | exterior[1:-1, :-2] | exterior[1:-1, 2:])
    return occupied & adjacent


def resize_cells(rows, target):
    """Preserve aspect ratio; separate occupancy coverage from categorical color voting."""
    rows = np.asarray(rows, dtype=object)
    occupied = rows != None  # noqa: E711
    if not occupied.any():
        raise ValueError("Empty source")
    ys, xs = np.where(occupied)
    tight = rows[ys.min():ys.max()+1, xs.min():xs.max()+1]
    h, w = tight.shape
    scale = min(1, target/w, target/h)
    width, height = max(1, round(w*scale)), max(1, round(h*scale))
    resized = np.full((height, width), None, dtype=object)
    for y in range(height):
        y0, y1 = y*h/height, (y+1)*h/height
        for x in range(width):
            x0, x1 = x*w/width, (x+1)*w/width
            votes = Counter()
            for iy in range(int(y0), min(h, int(np.ceil(y1)))):
                for ix in range(int(x0), min(w, int(np.ceil(x1)))):
                    code = tight[iy, ix]
                    if code is not None:
                        votes[code] += (min(y1, iy+1)-max(y0, iy))*(min(x1, ix+1)-max(x0, ix))
            if sum(votes.values()) >= 0.5*(x1-x0)*(y1-y0):
                center = tight[min(h-1, int((y0+y1)/2)), min(w-1, int((x0+x1)/2))]
                resized[y, x] = max(votes, key=lambda code: (votes[code], code == center))
    result = np.full((target, target), None, dtype=object)
    left, top = (target-width)//2, (target-height)//2
    result[top:top+height, left:left+width] = resized
    return result, {"original_canvas": [rows.shape[1], rows.shape[0]], "tight_size": [w, h],
                    "subject_size": [width, height], "target": target, "scale": scale}


def rgba_image(rows, palette):
    colors = {c["code"]: c["rgb"] for c in palette["colors"]}
    return Image.fromarray(np.array([[colors[c]+[255] if c else [0, 0, 0, 0] for c in row]
                                    for row in rows], dtype=np.uint8))


def compression_prompt(target, key, outline):
    rule = ("The complete exterior contour is locked: preserve every black outer-edge cell as black. "
            "Keep a continuous one-cell stepped outline inside the existing silhouette. Never replace "
            "it with hair, skin or clothing colors, erase it or expand it outward. Do not add black "
            "lines to interior facial features or thicken existing strokes."
            if outline else "Preserve the existing edge treatment; do not invent an outline.")
    return f"""Edit the attached {target}×{target} pixel sprite on its existing logical grid. It is a size-constrained draft derived from the original artwork. Preserve the exact grid, occupied silhouette, pose, proportions, expression and every transparent cutout hole. Make only small whole-cell corrections to improve readability of important features. Keep the main color regions and existing palette. Show this same grid enlarged with nearest-neighbor.

For an existing face, prioritize the eyes and mouth within their current small pixel footprints. Keep the gaze and perspective. Preserve distinct dark eyelid/pupil, iris-color and eye-white cells; do not merge them into a solid black patch or enlarge the eyes. Preserve the original open or closed mouth expression, and make its corners and opening readable with a few shaped pixel clusters. Keep the mouth distinct from skin using the existing warm colors. Avoid a filled rectangular mouth stamp, a single dot, new teeth, a new smile or new highlights. Simplify nearby hair shading before sacrificing these facial features. Do not add a face where none exists.

{rule}

One flat color per cell; no gradients, antialiasing, texture, finer pixels or new accessories. Preserve the white eye and clothing cells. Keep all empty cells exactly uniform RGB({key[0]},{key[1]},{key[2]}), the reserved background color already present in the input. Never use that color on the subject. Return an opaque image on this flat solid background, with no transparency preview, patterned backdrop, grid lines, labels, text or shadows.
"""


def prepare(source, output, target=52, palette_path=DEFAULT_PALETTE, max_colors=None,
            outline="auto", outline_code="H7"):
    if not 8 <= target <= 256:
        raise ValueError("Target must be 8-256 cells")
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use a new empty run directory")
    with Image.open(source) as image:
        rgba = np.array(image.convert("RGBA"))
    if max(rgba.shape[:2]) > 256 or not set(np.unique(rgba[:, :, 3])).issubset({0, 255}):
        raise ValueError("Input must be an accepted logical grid with binary alpha; refine raw art first")
    palette = load_palette(palette_path)
    source_shell = exterior_shell(rgba[:, :, 3] == 255)
    dark = rgba[:, :, :3] @ np.array([0.2126, 0.7152, 0.0722]) < 50
    source_dark_ratio = float(dark[source_shell].mean()) if source_shell.any() else 0
    protected = outline == "black" or (outline == "auto" and source_dark_ratio >= 0.90)
    if protected:
        matches = [c for c in palette["colors"] if c["code"] == outline_code]
        if not matches or max(matches[0]["rgb"]) > 60:
            raise ValueError("Outline protection requires an existing near-black palette code")
    # Outline policy must not change global palette selection or internal facial colors.
    cells, mapping = map_colors(rgba, palette, max_colors=max_colors)
    rows, dimensions = resize_cells(cells, target)
    shell = exterior_shell(rows != None)  # noqa: E711
    locked_cells = int((shell & (rows != outline_code)).sum()) if protected else 0
    if protected:
        rows[shell] = outline_code
    if max_colors and len(statistics(rows)) > max_colors:
        raise ValueError("Outline consumes a color slot; increase max-colors or adjust the palette")
    occupied_colors = [c["rgb"] for c in palette["colors"] if c["code"] in statistics(rows)]
    choices = np.array([[255, 0, 255], [0, 255, 0], [0, 255, 255]])
    distance = ((lab(choices)[:, None] - lab(occupied_colors)[None, :])**2).sum(axis=2).min(axis=1)
    key = choices[int(distance.argmax())].tolist()
    if float(distance.max()) < 25**2:
        raise ValueError("No distinct background key; use a reviewed true-alpha AI output")
    output.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, output / "00_original.png")
    image = rgba_image(rows, palette)
    image.save(output / "01_seed.png")
    background = Image.new("RGB", image.size, tuple(key))
    background.paste(image, mask=image.getchannel("A"))
    zoom = max(4, min(20, 1200//target))
    background.resize((target*zoom, target*zoom), Image.Resampling.NEAREST).save(output / "02_ai_input.png")
    (output / "03_prompt.txt").write_text(compression_prompt(target, key, protected), encoding="utf-8")
    project = {"schema": "pixel-art-to-beads/v1", "title": "拼豆作品", "palette": palette,
               "source": {"path": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest()},
               "mapping": mapping, "cells": rows.tolist(),
               "compression": {**dimensions, "method": "area-weighted categorical votes",
                               "background_key": key, "outline_protected": protected,
                               "outline_code": outline_code, "source_dark_boundary_ratio": source_dark_ratio,
                               "palette_selection_independent_of_outline": True,
                               "seed_outline_cells_restored": locked_cells,
                               "state": "seed_ready", "attempt_limit": 2}}
    save_json(output / "run.json", project)
    return project["compression"]


def finish(run, candidate, attempt="attempt-1"):
    run, candidate = Path(run).resolve(), Path(candidate).resolve()
    if Path(attempt).name != attempt or attempt in {".", ".."}:
        raise ValueError("Attempt must be a simple directory name")
    project = json.loads((run / "run.json").read_text())
    settings = project["compression"]
    output = run / attempt
    if output.exists():
        raise ValueError("Attempt output exists; preserve earlier candidates")
    output.mkdir()
    shutil.copy2(candidate, output / "00_ai_original.png")
    from perfect_pixel import get_perfect_pixel

    with Image.open(candidate) as image:
        rgba = np.array(image.convert("RGBA"))
    width, height, refined = get_perfect_pixel(rgba, sample_method="center", fix_square=False)
    detected = [int(width or 0), int(height or 0)]
    report = {"detected_grid": detected, "target": settings["target"], "forced_grid": False}
    if detected != [settings["target"]]*2:
        save_json(output / "report.json", {**report, "status": "rejected_grid"})
        raise ValueError(f"Detected {detected}; expected exact target. No forced resampling applied")
    sampled = np.asarray(refined, dtype=np.uint8)
    if sampled.ndim != 3 or sampled.shape[2] != 4:
        raise ValueError("Refinement did not preserve RGBA")
    Image.fromarray(sampled).save(output / "01_sampled.png")
    seeded = np.array(project["cells"], dtype=object)
    occupied = seeded != None  # noqa: E711
    if np.any(rgba[:, :, 3] < 128):
        candidate_mask = sampled[:, :, 3] >= 128
        extraction = "generated_alpha"
    else:
        key_distance = np.max(np.abs(sampled[:, :, :3].astype(int)-settings["background_key"]), axis=2)
        candidate_mask = key_distance > 45
        extraction = "reserved_color_key"
        background_match = float((~candidate_mask)[~occupied].mean()) if (~occupied).any() else 1
        if background_match < 0.95:
            save_json(output / "report.json", {**report, "status": "rejected_background",
                                               "background_match": background_match})
            raise ValueError("AI changed the reserved background; no blanket white removal permitted")
    drift = int((candidate_mask != occupied).sum())
    if drift > max(4, int(occupied.sum()*0.01)):
        save_json(output / "report.json", {**report, "status": "rejected_silhouette", "changed_cells": drift})
        raise ValueError("AI changed the occupied silhouette beyond the small sampling tolerance")
    # The seed geometry is an invariant; restore only minor sampled occupancy drift.
    seed_rgba = np.array(rgba_image(seeded, project["palette"]))
    missing = occupied & ~candidate_mask
    sampled[missing] = seed_rgba[missing]
    sampled[:, :, 3] = np.where(occupied, 255, 0)
    rows, mapping = map_colors(sampled, project["palette"], allowed=list(statistics(seeded)))
    rows = np.array(rows, dtype=object)
    shell = exterior_shell(occupied)
    restored = 0
    if settings["outline_protected"]:
        restored = int((rows[shell] != settings["outline_code"]).sum())
        rows[shell] = settings["outline_code"]
    project["cells"] = rows.tolist()
    project["compression"] = {**settings, "state": "needs_visual_review", "ai_candidate": str(candidate),
                              "detected_grid": detected, "background_extraction": extraction,
                              "sampling_mask_cells_restored": drift, "outline_cells_restored_after_ai": restored,
                              "ai_mapping": mapping}
    image = rgba_image(rows, project["palette"])
    image.save(output / "02_final.png")
    image.resize((image.width*12, image.height*12), Image.Resampling.NEAREST).save(output / "03_preview.png")
    save_json(output / "project.json", project)
    report.update(status="needs_visual_review", mask_unchanged=True, outline_restored_cells=restored,
                  occupied_cells=int(occupied.sum()), components=len(components(rows.tolist())))
    save_json(output / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("source")
    prep.add_argument("output")
    prep.add_argument("--target", type=int, default=52)
    prep.add_argument("--palette", default=str(DEFAULT_PALETTE))
    prep.add_argument("--max-colors", type=int)
    prep.add_argument("--outline", choices=["auto", "black", "none"], default="auto")
    prep.add_argument("--outline-code", default="H7")
    done = sub.add_parser("finish")
    done.add_argument("run")
    done.add_argument("candidate")
    done.add_argument("--attempt", default="attempt-1")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare(args.source, args.output, args.target, args.palette, args.max_colors,
                             args.outline, args.outline_code)
        else:
            result = finish(args.run, args.candidate, args.attempt)
        print(json.dumps(result, ensure_ascii=False))
    except (ValueError, OSError, KeyError, ImportError) as error:
        parser.exit(2, f"{error}\n")


if __name__ == "__main__":
    main()
