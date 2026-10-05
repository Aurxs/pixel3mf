#!/usr/bin/env python3
"""Publish an original mirror pair, adding a fitted pair only for oversized logical grids."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil

from PIL import Image

from bead_palette import load_palette
from bead_pattern import DEFAULT_PALETTE, create_project, export_project
from compress_pixels import finish as finish_compression
from compress_pixels import prepare as prepare_compression


def save_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def trim_empty_border(project):
    """Crop only empty outer rows/columns; keep bead cells and internal holes intact."""
    cells = project["cells"]
    occupied = [(x, y) for y, row in enumerate(cells)
                for x, code in enumerate(row) if code is not None]
    if not occupied:
        raise ValueError("The source has no occupied bead cells")
    left = min(x for x, _ in occupied)
    top = min(y for _, y in occupied)
    right = max(x for x, _ in occupied) + 1
    bottom = max(y for _, y in occupied) + 1
    project["uncompressed_crop"] = {
        "source_grid": [len(cells[0]), len(cells)],
        "bbox": [left, top, right, bottom], "resampled": False,
    }
    project["cells"] = [row[left:right] for row in cells[top:bottom]]
    return project


def publish_charts(uncompressed, compressed, destination):
    """Publish the original pair and, when supplied, the compressed pair."""
    destination = Path(destination)
    if destination.exists():
        raise ValueError("Delivery already exists; retain previous results and use a new run")
    sources = [
        (Path(uncompressed)/"正常版.png", "01_未压缩.png", "uncompressed", False),
        (Path(uncompressed)/"镜像版.png", "02_未压缩_镜像.png", "uncompressed", True),
    ]
    if compressed is not None:
        sources += [
            (Path(compressed)/"正常版.png", "03_压缩.png", "compressed", False),
            (Path(compressed)/"镜像版.png", "04_压缩_镜像.png", "compressed", True),
        ]
    for source, _, _, _ in sources:
        with Image.open(source) as image:
            image.verify()
    staging = destination.with_name(destination.name + ".staging")
    if staging.exists():
        raise ValueError("Incomplete delivery staging exists; inspect it before retrying")
    staging.mkdir(parents=True)
    products = []
    for source, name, size, mirrored in sources:
        shutil.copy2(source, staging/name)
        products.append({"path": str((destination/name).resolve()), "variant": size,
                         "mirrored": mirrored, "sha256": hashlib.sha256(source.read_bytes()).hexdigest()})
    staging.rename(destination)
    return products


def prepare(source, run, title, *, target=52, palette=DEFAULT_PALETTE, max_colors=None,
            outline="auto", font=None, allowed=None, locked=None):
    source, run = Path(source).resolve(), Path(run).resolve()
    if run.exists() and any(run.iterdir()):
        raise ValueError("Use a new empty run directory")
    if target < 1:
        raise ValueError("Target must be positive")
    # Validate the source and palette before creating partial workflow outputs.
    original = trim_empty_border(
        create_project(source, load_palette(palette), title, max_colors=max_colors,
                       allowed=allowed, locked=locked))
    run.mkdir(parents=True, exist_ok=True)
    work = run/"work"
    work.mkdir()
    shutil.copy2(source, work/("00_original" + source.suffix.lower()))
    source_png = work/"00_source.png"
    with Image.open(source) as image:
        image.convert("RGBA").save(source_png)
    original_charts = work/"01_uncompressed"
    export_project(original, original_charts, font=font)
    logical_size = [len(original["cells"][0]), len(original["cells"])]
    compression_required = any(size > target for size in logical_size)
    state = {"schema": "bead-chart-workflow/v2", "status": "ready_to_publish",
             "title": title, "source": {"path": str(source),
                 "sha256": hashlib.sha256(source.read_bytes()).hexdigest()},
             "color_mapping": original["mapping"],
             "target": target, "font": str(Path(font).resolve()) if font else None,
             "logical_size": logical_size, "compression_required": compression_required,
             "expected_primary_products": 4 if compression_required else 2,
             "paths": {"uncompressed": str(original_charts)},
             "uncompressed_statistics": original["statistics"],
             "uncompressed_crop": original["uncompressed_crop"], "primary_products": []}
    if compression_required:
        compression = work/"02_compression"
        prepare_compression(source_png, compression, target, palette, max_colors, outline,
                            allowed=allowed, locked=locked)
        seed = json.loads((compression/"run.json").read_text(encoding="utf-8"))
        seed["title"] = title
        save_json(compression/"run.json", seed)
        state["status"] = "awaiting_ai"
        state["paths"].update(compression=str(compression),
                              ai_input=str(compression/"02_ai_input.png"),
                              ai_prompt=str(compression/"03_prompt.txt"))
    save_json(run/"manifest.json", state)
    return state


def complete(run, candidate=None, *, algorithm_only=False, attempt="attempt-1"):
    run = Path(run).resolve()
    state_path = run/"manifest.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("schema") not in {"bead-four-chart-workflow/v1", "bead-chart-workflow/v2"}:
        raise ValueError("Unsupported workflow schema")
    if (run/"delivery").exists():
        raise ValueError("This workflow has already published its products")
    if not state.get("compression_required", True):
        if candidate or algorithm_only:
            raise ValueError("No compression is needed; finish without compression options")
        state["compression_mode"] = "not_needed"
        state["primary_products"] = publish_charts(state["paths"]["uncompressed"], None, run/"delivery")
        state["status"] = "two_charts_ready_for_review"
        save_json(state_path, state)
        return state
    if algorithm_only == bool(candidate):
        raise ValueError("Choose exactly one of AI candidate or algorithm-only")
    if Path(attempt).name != attempt or attempt in {".", ".."}:
        raise ValueError("Attempt must be a simple directory name")
    compression = Path(state["paths"]["compression"])
    if algorithm_only:
        project = json.loads((compression/"run.json").read_text(encoding="utf-8"))
        state["compression_mode"] = "algorithm_only"
    else:
        try:
            state["compression_report"] = finish_compression(compression, candidate, attempt)
        except (ValueError, OSError) as error:
            state["status"] = "ai_candidate_rejected"
            state["last_error"] = str(error)
            save_json(state_path, state)
            raise
        project = json.loads((compression/attempt/"project.json").read_text(encoding="utf-8"))
        state["compression_mode"] = "algorithm_then_ai"
    project["title"] = state["title"]
    compressed_charts = run/"work"/f"03_compressed_{attempt}"
    export_project(project, compressed_charts, font=state["font"])
    state["paths"]["compressed"] = str(compressed_charts)
    state["compressed_statistics"] = project["statistics"]
    state["primary_products"] = publish_charts(state["paths"]["uncompressed"], compressed_charts, run/"delivery")
    state["status"] = "four_charts_ready_for_review"
    state.pop("last_error", None)
    save_json(state_path, state)
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("source")
    prep.add_argument("run")
    prep.add_argument("--title", default="拼豆作品")
    prep.add_argument("--target", type=int, default=52)
    prep.add_argument("--palette", default=str(DEFAULT_PALETTE))
    prep.add_argument("--max-colors", type=int)
    prep.add_argument("--allowed", help="Comma-separated reviewed shared color codes")
    prep.add_argument("--locked", help="Comma-separated anchors retained during reduction")
    prep.add_argument("--outline", choices=["auto", "black", "none"], default="auto")
    prep.add_argument("--font")
    done = sub.add_parser("finish")
    done.add_argument("run")
    choice = done.add_mutually_exclusive_group()
    choice.add_argument("--candidate")
    choice.add_argument("--algorithm-only", action="store_true")
    done.add_argument("--attempt", default="attempt-1")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            state = prepare(args.source, args.run, args.title, target=args.target,
                            palette=args.palette, max_colors=args.max_colors,
                            outline=args.outline, font=args.font,
                            allowed=args.allowed.split(",") if args.allowed else None,
                            locked=args.locked.split(",") if args.locked else None)
        else:
            state = complete(args.run, args.candidate, algorithm_only=args.algorithm_only, attempt=args.attempt)
        print(json.dumps({"status": state["status"], "paths": state["paths"],
                          "primary_products": state["primary_products"],
                          "logical_size": state.get("logical_size"),
                          "compression_required": state.get("compression_required", True),
                          "expected_primary_products": state.get("expected_primary_products", 4),
                          "uncompressed": state["uncompressed_statistics"],
                          "compressed": state.get("compressed_statistics")}, ensure_ascii=False))
    except (ValueError, OSError, KeyError, ImportError) as error:
        parser.exit(2, f"{error}\n")


if __name__ == "__main__":
    main()
