#!/usr/bin/env python3
"""Refine a pixel-style image with Perfect Pixel and save an 8x preview."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
from perfect_pixel import get_perfect_pixel


MIN_ACCEPTED_GRID = 60
MAX_ACCEPTED_GRID = 85


def validate_detected_grid(grid_w: int, grid_h: int) -> None:
    """Reject source densities that should be regenerated before conversion."""
    if grid_w > MAX_ACCEPTED_GRID or grid_h > MAX_ACCEPTED_GRID:
        raise ValueError(
            "Perfect Pixel detected an overly dense source grid "
            f"({grid_w}x{grid_h}); the accepted range is "
            f"{MIN_ACCEPTED_GRID}-{MAX_ACCEPTED_GRID} cells per axis. Regenerate "
            "the source instead of resizing or forcing a downstream grid"
        )
    if grid_w < MIN_ACCEPTED_GRID or grid_h < MIN_ACCEPTED_GRID:
        raise ValueError(
            "Perfect Pixel detected an overly coarse source grid "
            f"({grid_w}x{grid_h}); the accepted range is "
            f"{MIN_ACCEPTED_GRID}-{MAX_ACCEPTED_GRID} cells per axis. Regenerate "
            "the source instead of resizing or forcing a downstream grid"
        )


def _pad_square(array: np.ndarray) -> np.ndarray:
    height, width = array.shape[:2]
    if width == height:
        return array
    side = max(width, height)
    channels = array.shape[2] if array.ndim == 3 else 1
    shape = (side, side, channels) if array.ndim == 3 else (side, side)
    result = np.zeros(shape, dtype=array.dtype)
    x = (side - width) // 2
    y = (side - height) // 2
    result[y : y + height, x : x + width] = array
    return result


def refine_pixel(
    input_path: str | Path,
    output_path: str | Path,
    preview_path: str | Path,
) -> dict[str, object]:
    rgba = np.asarray(Image.open(input_path).convert("RGBA"))
    grid_w, grid_h, refined = get_perfect_pixel(
        rgba, sample_method="center", fix_square=False
    )
    auto_detected = grid_w is not None and grid_h is not None
    if not auto_detected:
        raise ValueError(
            "Perfect Pixel could not detect a logical grid; regenerate a clearer "
            "low-resolution pixel-art source instead of forcing a downstream grid"
        )
    validate_detected_grid(int(grid_w), int(grid_h))
    detected_grid = (
        {"width": int(grid_w), "height": int(grid_h)} if auto_detected else None
    )

    refined = np.asarray(refined)
    if refined.ndim != 3 or refined.shape[2] != 4:
        rgb = refined[:, :, :3]
        alpha = np.asarray(
            Image.fromarray(rgba[:, :, 3]).resize(
                (rgb.shape[1], rgb.shape[0]), Image.Resampling.NEAREST
            )
        )
        refined = np.dstack((rgb, alpha))

    refined_grid = {"width": int(refined.shape[1]), "height": int(refined.shape[0])}
    squared = _pad_square(refined.astype(np.uint8))
    final = Image.fromarray(squared, "RGBA")

    output_path = Path(output_path)
    preview_path = Path(preview_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    final.save(output_path)
    final.resize(
        (final.width * 8, final.height * 8), Image.Resampling.NEAREST
    ).save(preview_path)

    return {
        "detected_grid": detected_grid,
        "refined_grid": refined_grid,
        "output_grid": {"width": final.width, "height": final.height},
        "accepted_grid_range": {
            "minimum_per_axis": MIN_ACCEPTED_GRID,
            "maximum_per_axis": MAX_ACCEPTED_GRID,
            "inclusive": True,
        },
        "auto_detected": auto_detected,
        "auto_accepted": True,
        "forced_grid": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("preview")
    args = parser.parse_args()
    metadata = refine_pixel(args.input, args.output, args.preview)
    print(json.dumps(metadata, ensure_ascii=False))


if __name__ == "__main__":
    main()
