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


def _pad_cells(array: np.ndarray, cells: int) -> np.ndarray:
    if cells < 0:
        raise ValueError("working_padding_cells must be non-negative")
    if cells == 0:
        return array
    return np.pad(
        array,
        ((cells, cells), (cells, cells), (0, 0)),
        mode="constant",
        constant_values=0,
    )


def refine_mask_to_grid(
    source_path: str | Path,
    output_path: str | Path,
    *,
    expected_source_grid: dict[str, int],
    working_padding_cells: int = 0,
    square_output: bool = False,
    mask_path: str | Path | None = None,
) -> dict[str, object]:
    """Sample source alpha or an auxiliary mask onto the validated logical grid."""
    rgba = np.asarray(Image.open(source_path).convert("RGBA")).copy()
    if mask_path is not None:
        mask = Image.open(mask_path).convert("L")
        if mask.size != (rgba.shape[1], rgba.shape[0]):
            raise ValueError("auxiliary mask size does not match source image")
        rgba[:, :, 3] = np.asarray(mask, dtype=np.uint8)

    grid_w, grid_h, refined = get_perfect_pixel(
        rgba, sample_method="center", fix_square=False
    )
    expected = (
        int(expected_source_grid["width"]),
        int(expected_source_grid["height"]),
    )
    detected = (int(grid_w), int(grid_h)) if grid_w and grid_h else (None, None)
    if detected != expected:
        raise ValueError(
            "auxiliary alpha grid does not match source preflight: "
            f"expected {expected[0]}x{expected[1]}, got {detected[0]}x{detected[1]}"
        )

    alpha = np.asarray(refined, dtype=np.uint8)[:, :, 3]
    if working_padding_cells:
        alpha = np.pad(
            alpha,
            working_padding_cells,
            mode="constant",
            constant_values=0,
        )
    if square_output and alpha.shape[0] != alpha.shape[1]:
        side = max(alpha.shape)
        padded = np.zeros((side, side), dtype=np.uint8)
        x = (side - alpha.shape[1]) // 2
        y = (side - alpha.shape[0]) // 2
        padded[y : y + alpha.shape[0], x : x + alpha.shape[1]] = alpha
        alpha = padded

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(alpha, "L").save(output_path)
    return {
        "grid": {"width": int(alpha.shape[1]), "height": int(alpha.shape[0])},
        "foreground_cells": int(np.count_nonzero(alpha >= 128)),
        "alpha_values": [int(value) for value in np.unique(alpha)],
    }


def detect_source_grid(input_path: str | Path) -> dict[str, object]:
    """Auto-detect and validate density on the untouched source canvas."""
    rgba = np.asarray(Image.open(input_path).convert("RGBA"))
    grid_w, grid_h, refined = get_perfect_pixel(
        rgba, sample_method="center", fix_square=False
    )
    if grid_w is None or grid_h is None:
        raise ValueError(
            "Perfect Pixel could not detect the source logical grid; regenerate "
            "a clearer low-resolution pixel-art source"
        )
    validate_detected_grid(int(grid_w), int(grid_h))
    refined = np.asarray(refined, dtype=np.uint8)
    reconstructed = np.asarray(
        Image.fromarray(refined, "RGBA").resize(
            (rgba.shape[1], rgba.shape[0]), Image.Resampling.NEAREST
        )
    )
    rgb_error = np.max(
        np.abs(
            rgba[:, :, :3].astype(np.int16)
            - reconstructed[:, :, :3].astype(np.int16)
        ),
        axis=2,
    )
    changed_fraction = float(np.mean(rgb_error > 8))
    palette_size = int(
        np.unique(refined[:, :, :3].reshape(-1, 3), axis=0).shape[0]
    )
    warnings: list[str] = []
    if changed_fraction > 0.01:
        warnings.append("minor_blur_antialiasing_or_whole_cell_tone_variation")
    if palette_size > 64:
        warnings.append("palette_exceeds_recommended_count")
    return {
        "width": int(grid_w),
        "height": int(grid_h),
        "warnings": warnings,
        "render_metrics": {
            "rgb_pixels_over_delta_8_fraction": round(changed_fraction, 6),
            "logical_palette_size": palette_size,
        },
        "accepted_range": {
            "minimum_per_axis": MIN_ACCEPTED_GRID,
            "maximum_per_axis": MAX_ACCEPTED_GRID,
            "inclusive": True,
        },
    }


def refine_pixel(
    input_path: str | Path,
    output_path: str | Path,
    preview_path: str | Path,
    square_output: bool = False,
    *,
    expected_source_grid: dict[str, int] | None = None,
    validate_source_density: bool = True,
    working_padding_cells: int = 0,
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
    if validate_source_density:
        validate_detected_grid(int(grid_w), int(grid_h))
    if expected_source_grid is not None:
        expected = (
            int(expected_source_grid["width"]),
            int(expected_source_grid["height"]),
        )
        detected = (int(grid_w), int(grid_h))
        if detected != expected:
            raise ValueError(
                "Perfect Pixel grid changed after semantic masking: "
                f"source preflight was {expected[0]}x{expected[1]}, refinement "
                f"detected {detected[0]}x{detected[1]}"
            )
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
    final_array = _pad_cells(refined.astype(np.uint8), working_padding_cells)
    before_square_width = int(final_array.shape[1])
    before_square_height = int(final_array.shape[0])
    if square_output:
        final_array = _pad_square(final_array)
    final = Image.fromarray(final_array, "RGBA")

    output_path = Path(output_path)
    preview_path = Path(preview_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    final.save(output_path)
    final.resize(
        (final.width * 8, final.height * 8), Image.Resampling.NEAREST
    ).save(preview_path)

    return {
        "source_grid": detected_grid,
        "detected_grid": detected_grid,
        "refined_grid": refined_grid,
        "working_grid": {"width": final.width, "height": final.height},
        "output_grid": {"width": final.width, "height": final.height},
        "working_padding_cells": working_padding_cells,
        "temporary_padding": {
            "columns_added": final.width - refined_grid["width"],
            "rows_added": final.height - refined_grid["height"],
            "included_in_export": False,
        },
        "square_output": square_output,
        "square_padding": {
            "columns_added": final.width - before_square_width,
            "rows_added": final.height - before_square_height,
        },
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
    parser.add_argument(
        "--square-output",
        action="store_true",
        help="Pad the refined grid to a square with complete transparent cells",
    )
    args = parser.parse_args()
    metadata = refine_pixel(
        args.input, args.output, args.preview, square_output=args.square_output
    )
    print(json.dumps(metadata, ensure_ascii=False))


if __name__ == "__main__":
    main()
