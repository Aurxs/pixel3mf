#!/usr/bin/env python3
"""Recover a logical pixel grid; no dependencies on another skill or checkout."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image, ImageOps


def prepare(source, output, *, logical=False, remove_bg=False, mask=None):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use a new empty output directory; existing artifacts are retained")
    output.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, output / ("00_original" + source.suffix.lower()))
    image = ImageOps.exif_transpose(Image.open(source)).convert("RGBA")
    image.save(output / "01_source.png")
    meta = {"source": str(source), "logical_input": logical, "background_removed": remove_bg}
    if mask:
        alpha = Image.open(mask).convert("L")
        if alpha.size != image.size or not set(alpha.getdata()).issubset({0, 255}):
            raise ValueError("Reviewed mask must match the oriented source size and be binary")
        shutil.copy2(mask, output / "02_reviewed_mask.png")
        image.putalpha(alpha)
    elif remove_bg and np.all(np.asarray(image)[:, :, 3] == 255):
        from remove_background import remove_background

        meta["background"] = remove_background(
            output / "01_source.png", output / "02_background.png",
            method="rembg", background_model="isnet-general-use", alpha_policy="auto",
        )
        image = Image.open(output / "02_background.png").convert("RGBA")
    rgba = np.asarray(image).copy()
    if not logical:
        from perfect_pixel import get_perfect_pixel

        width, height, refined = get_perfect_pixel(rgba, sample_method="center", fix_square=False)
        if width is None or height is None:
            raise ValueError("Grid detection failed; inspect the source instead of forcing a grid")
        rgba = np.asarray(refined, dtype=np.uint8)
        if rgba.ndim != 3 or rgba.shape[2] != 4:
            raise ValueError("Perfect Pixel did not preserve RGBA; review before proceeding")
        meta["detected_grid"] = [int(width), int(height)]
    partial = (rgba[:, :, 3] > 0) & (rgba[:, :, 3] < 255)
    meta["partial_alpha_cells"] = int(partial.sum())
    working = output / "03_working_grid.png"
    if "background" in meta:
        # Keep semantic confidence until component decisions have been made.
        from cleanup_pixel import finalize_pixel_grid

        Image.fromarray(rgba).save(working)
        meta["cleanup"] = finalize_pixel_grid(
            working, output / "04_pixel_perfect.png", output / "05_pixel_preview_8x.png",
            background_rgb=meta["background"]["background_rgb"],
            components_path=output / "03_components.json",
            overlay_path=output / "03_overlay.png", alpha_policy="semantic",
        )
    else:
        if logical and partial.any():
            raise ValueError("Logical input must have binary alpha; use refinement for raw sources")
        rgba[:, :, 3] = np.where(rgba[:, :, 3] >= 128, 255, 0)
        result = Image.fromarray(rgba)
        result.save(working)
        box = result.getbbox()
        if box is None:
            raise ValueError("Source has no occupied cells")
        # Known logical grids retain their canvas; generated grids lose only empty outer rows.
        if not logical:
            result = result.crop(box)
        result.save(output / "04_pixel_perfect.png")
        result.resize((result.width * 8, result.height * 8), Image.Resampling.NEAREST).save(
            output / "05_pixel_preview_8x.png"
        )
    meta["status"] = "needs_visual_review"
    (output / "preparation.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    return meta


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("output")
    parser.add_argument("--logical", action="store_true")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--remove-background", action="store_true")
    group.add_argument("--mask", help="Reviewed binary mask at oriented source resolution")
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.source, args.output, logical=args.logical,
                                 remove_bg=args.remove_background, mask=args.mask), ensure_ascii=False))
    except (ValueError, OSError, ImportError) as error:
        parser.exit(2, f"{error}\n")
