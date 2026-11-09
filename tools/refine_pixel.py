#!/usr/bin/env python3
"""Refine a pixel-style image with Perfect Pixel and save an 8x preview."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
from perfect_pixel import get_perfect_pixel


MIN_ACCEPTED_GRID = 45
MAX_ACCEPTED_GRID = 90


def _exact_fractional_grid(rgba: np.ndarray) -> tuple[int, int, np.ndarray] | None:
    """Recover a fully observed, nearest-neighbor RGB lattice.

    Each logical boundary must cause at least one RGB transition somewhere on
    its axis, and there must be no transitions anywhere else. This strict
    condition avoids inferring unobserved subdivisions or tolerating noise.
    The model spans the entire canvas, with no unknown offset or clipped cells.
    An unobserved finer grid is indistinguishable from this visible lattice;
    the returned count is not proof of an artist's intended logical density.
    """
    rgb = rgba[:, :, :3]
    coordinates = []
    counts = []
    for axis, extent in ((1, rgba.shape[1]), (0, rgba.shape[0])):
        changes = np.any(np.diff(rgb, axis=axis) != 0,
                         axis=(0, 2) if axis == 1 else (1, 2))
        observed = np.flatnonzero(changes) + 1
        count = len(observed) + 1
        if len(observed) < 4 or extent / count < 4:
            return None
        # Model pixel centers mapped to equally spaced cells. Compare every
        # transition, not merely the count or an approximate periodicity.
        indices = ((2 * np.arange(extent, dtype=np.int64) + 1) * count) // (2 * extent)
        expected = np.flatnonzero(np.diff(indices)) + 1
        # A pixel center exactly on a boundary can belong to either cell.
        # Rasterizers differ in tie-breaking; accept only those exact ties.
        lower_indices = (((2 * np.arange(extent, dtype=np.int64) + 1) * count) - 1) // (2 * extent)
        alternate = np.flatnonzero(np.diff(lower_indices)) + 1
        if (len(expected) != len(observed) or len(alternate) != len(observed)
                or not np.all((observed == expected) | (observed == alternate))):
            return None
        edges = np.concatenate(([0], observed, [extent]))
        coordinates.append((edges[:-1] + edges[1:]) // 2)
        counts.append(count)

    width, height = counts
    pitches = (rgba.shape[1] / width, rgba.shape[0] / height)
    if max(pitches) / min(pitches) > 1.5:
        return None
    xs, ys = coordinates
    return width, height, rgba[ys[:, None], xs[None, :]].copy()


def _auto_detect_grid(rgba: np.ndarray) -> tuple[int | None, int | None, np.ndarray]:
    """Use Perfect Pixel, then recover an exact observed RGB lattice.

    Perfect Pixel 0.1.4 discards FFT estimates with cells wider than 20 px;
    its gradient fallback also misses two-pixel Sobel plateaus. On failure,
    infer an origin-aligned lattice from *all* RGB transitions. A final strict
    fallback handles noninteger spacing when every boundary is observable.
    These fallbacks cannot rescue blurred, noisy or irregular sources and do
    not establish that no finer, visually indistinguishable grid exists.
    Alpha is sampled on the RGB grid, as in Perfect Pixel, so auxiliary masks
    cannot change the detected source lattice.
    """
    result = get_perfect_pixel(rgba, sample_method="center", fix_square=False)
    if result[0] is not None and result[1] is not None:
        return result

    def fractional_fallback() -> tuple[int | None, int | None, np.ndarray]:
        fractional = _exact_fractional_grid(rgba)
        if fractional is None:
            return result
        print(f"Detected exact full-canvas RGB lattice after Perfect Pixel failure: {fractional[0]}x{fractional[1]}")
        return fractional

    rgb = rgba[:, :, :3]
    pitch = []
    for axis, extent in ((1, rgba.shape[1]), (0, rgba.shape[0])):
        changes = np.any(np.diff(rgb, axis=axis) != 0,
                         axis=(0, 2) if axis == 1 else (1, 2))
        boundaries = np.flatnonzero(changes) + 1
        if len(boundaries) < 4:
            return fractional_fallback()
        cell = int(np.gcd.reduce(np.append(boundaries, extent)))
        # Keep the upstream minimum cell width. Require an observed one-cell
        # interval too: a common divisor alone could invent finer cells for
        # irregular spacing or a phase-shifted grid with clipped border cells.
        if cell < 4 or np.min(np.diff(boundaries)) != cell:
            return fractional_fallback()
        pitch.append(cell)

    cell_w, cell_h = pitch
    if max(pitch) / min(pitch) > 1.5:
        return fractional_fallback()
    grid_w, grid_h = rgba.shape[1] // cell_w, rgba.shape[0] // cell_h
    print(f"Detected exact RGB lattice after Perfect Pixel failure: {grid_w}x{grid_h}")
    return grid_w, grid_h, rgba[cell_h // 2::cell_h, cell_w // 2::cell_w].copy()


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

    grid_w, grid_h, refined = _auto_detect_grid(rgba)
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


def detect_source_grid(input_path: str | Path, *, validate_density: bool = True) -> dict[str, object]:
    """Detect the source grid; diagnostic callers may defer density judgment."""
    rgba = np.asarray(Image.open(input_path).convert("RGBA"))
    grid_w, grid_h, refined = _auto_detect_grid(rgba)
    if grid_w is None or grid_h is None:
        raise ValueError(
            "Perfect Pixel could not detect the source logical grid; regenerate "
            "a clearer low-resolution pixel-art source"
        )
    if validate_density:
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
    if changed_fraction > 0.01:
        # PIL's tie-breaking can differ from a source's exact lattice at
        # boundary pixel centers. Do not report blur when all observed RGB
        # transitions prove exact cells and their samples match this result.
        exact = _exact_fractional_grid(rgba)
        if (exact is not None and exact[:2] == (int(grid_w), int(grid_h))
                and np.array_equal(exact[2][:, :, :3], refined[:, :, :3])):
            changed_fraction = 0.0
    palette_size = int(
        np.unique(refined[:, :, :3].reshape(-1, 3), axis=0).shape[0]
    )
    warnings: list[str] = []
    if not (MIN_ACCEPTED_GRID <= int(grid_w) <= MAX_ACCEPTED_GRID
            and MIN_ACCEPTED_GRID <= int(grid_h) <= MAX_ACCEPTED_GRID):
        warnings.append("source_density_outside_reference_range")
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
        "density_gate_applied": validate_density,
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
    binarize_alpha: bool = False,
) -> dict[str, object]:
    rgba = np.asarray(Image.open(input_path).convert("RGBA"))
    grid_w, grid_h, refined = _auto_detect_grid(rgba)
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
    partial_alpha_cells = int(
        np.count_nonzero((final_array[:, :, 3] > 0) & (final_array[:, :, 3] < 255))
    )
    if binarize_alpha:
        final_array[:, :, 3] = np.where(final_array[:, :, 3] >= 128, 255, 0)
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
        } if validate_source_density else None,
        "density_gate_applied": validate_source_density,
        "alpha_binarized": binarize_alpha,
        "partial_alpha_cells_before_binarization": partial_alpha_cells,
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
        "--png-only",
        action="store_true",
        help="Refine a PNG without applying the 3MF-specific source density gate",
    )
    parser.add_argument(
        "--binarize-alpha",
        action="store_true",
        help="Threshold sampled logical-cell alpha at 128 after Perfect Pixel",
    )
    parser.add_argument(
        "--square-output",
        action="store_true",
        help="Pad the refined grid to a square with complete transparent cells",
    )
    args = parser.parse_args()
    metadata = refine_pixel(
        args.input,
        args.output,
        args.preview,
        square_output=args.square_output,
        validate_source_density=not args.png_only,
        binarize_alpha=args.binarize_alpha,
    )
    print(json.dumps(metadata, ensure_ascii=False))


if __name__ == "__main__":
    main()
