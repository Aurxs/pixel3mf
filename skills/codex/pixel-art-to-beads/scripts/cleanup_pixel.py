#!/usr/bin/env python3
"""Conservatively clean isolated foreground and tiny exterior white artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


class AmbiguousMaskError(ValueError):
    """Raised when semantic background components require explicit approval."""


def cleanup_pixel(
    input_path: str | Path,
    output_path: str | Path,
    preview_path: str | Path | None = None,
    white_threshold: int = 245,
    max_edge_white_area: int = 2,
) -> dict[str, int | bool]:
    rgba = np.asarray(Image.open(input_path).convert("RGBA")).copy()
    solid = rgba[:, :, 3] > 8
    transparent = ~solid
    near_white = np.all(rgba[:, :, :3] >= white_threshold, axis=2) & solid
    exterior_neighbor = cv2.dilate(
        transparent.astype(np.uint8), np.ones((3, 3), dtype=np.uint8), iterations=1
    ).astype(bool)

    removed_edge_white_pixels = 0
    removed_edge_white_components = 0
    preserved_edge_white_components = 0
    component_count, labels = cv2.connectedComponents(
        near_white.astype(np.uint8), connectivity=8
    )
    for label in range(1, component_count):
        component = labels == label
        if not np.any(component & exterior_neighbor):
            continue
        area = int(component.sum())
        exterior_area = int(np.count_nonzero(component & exterior_neighbor))
        if area <= max_edge_white_area and exterior_area == area:
            rgba[component] = 0
            removed_edge_white_pixels += area
            removed_edge_white_components += 1
        else:
            preserved_edge_white_components += 1

    solid = rgba[:, :, 3] > 8
    padded = np.pad(solid, 1, constant_values=False)
    neighbors = np.zeros_like(solid, dtype=np.uint8)
    for dy in range(3):
        for dx in range(3):
            if dx == 1 and dy == 1:
                continue
            neighbors += padded[dy : dy + solid.shape[0], dx : dx + solid.shape[1]]
    isolated = solid & (neighbors == 0)
    rgba[isolated] = 0

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = Image.fromarray(rgba, "RGBA")
    result.save(output_path)
    if preview_path is not None:
        preview_path = Path(preview_path)
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        result.resize(
            (result.width * 8, result.height * 8), Image.Resampling.NEAREST
        ).save(preview_path)
    return {
        "removed_isolated_foreground_pixels": int(isolated.sum()),
        "removed_edge_white_pixels": removed_edge_white_pixels,
        "removed_edge_white_components": removed_edge_white_components,
        "preserved_ambiguous_edge_white_components": preserved_edge_white_components,
        "deferred_review_recommended": preserved_edge_white_components > 0,
    }


def _pad_square(array: np.ndarray) -> np.ndarray:
    height, width = array.shape[:2]
    if width == height:
        return array
    side = max(width, height)
    result = np.zeros((side, side, 4), dtype=array.dtype)
    x = (side - width) // 2
    y = (side - height) // 2
    result[y : y + height, x : x + width] = array
    return result


def finalize_pixel_grid(
    input_path: str | Path,
    output_path: str | Path,
    preview_path: str | Path,
    *,
    background_rgb: list[int] | tuple[int, int, int] | None,
    components_path: str | Path,
    overlay_path: str | Path,
    alpha_policy: str = "semantic",
    source_alpha_grid_path: str | Path | None = None,
    foreground_threshold: float = 0.80,
    background_threshold: float = 0.20,
    background_color_tolerance: int = 12,
    allow_ambiguous: bool = False,
    square_output: bool = False,
) -> dict[str, object]:
    """Resolve semantic alpha on the logical grid and tight-crop for export."""
    if not 0 <= background_threshold < foreground_threshold <= 1:
        raise ValueError("semantic thresholds must satisfy 0 <= bg < fg <= 1")
    if alpha_policy not in {"semantic", "preserve", "repair", "mask-override"}:
        raise ValueError(f"unsupported effective alpha policy: {alpha_policy}")
    rgba = np.asarray(Image.open(input_path).convert("RGBA")).copy()
    probability = rgba[:, :, 3].astype(np.float32) / 255.0
    decisions: list[dict[str, object]] = []
    ambiguous = np.zeros(probability.shape, dtype=bool)
    protected = np.zeros(probability.shape, dtype=bool)
    resolved_alpha = probability >= 0.5
    background_payload: list[int] | None = None
    original_foreground_cells = int(resolved_alpha.sum())
    approved_repair = np.zeros(probability.shape, dtype=bool)
    forbidden_deletion_attempts = 0

    if alpha_policy == "semantic":
        if background_rgb is None:
            raise ValueError("semantic cleanup requires background_rgb")
        background = np.asarray(background_rgb, dtype=np.int16)
        background_payload = [int(value) for value in background]
        difference = np.abs(rgba[:, :, :3].astype(np.int16) - background)
        background_like = np.max(difference, axis=2) <= background_color_tolerance
        component_count, labels, stats, _ = cv2.connectedComponentsWithStats(
            background_like.astype(np.uint8), connectivity=8
        )
        for label in range(1, component_count):
            component = labels == label
            score = float(np.median(probability[component]))
            minimum_score = float(np.min(probability[component]))
            maximum_score = float(np.max(probability[component]))
            background_fraction = float(
                np.mean(probability[component] <= background_threshold)
            )
            foreground_fraction = float(
                np.mean(probability[component] >= foreground_threshold)
            )
            x, y, width, height, area = [int(value) for value in stats[label]]
            if score <= background_threshold or maximum_score < 0.5:
                decision = "background"
                resolved_alpha[component] = False
            elif score >= foreground_threshold:
                decision = "foreground"
                resolved_alpha[component] = True
            else:
                decision = "ambiguous"
                ambiguous[component] = True
                resolved_alpha[component] = score >= 0.5
            decisions.append(
                {
                    "id": label,
                    "area_cells": area,
                    "bbox": {
                        "x": x,
                        "y": y,
                        "width": width,
                        "height": height,
                    },
                    "minimum_foreground_probability": round(minimum_score, 6),
                    "median_foreground_probability": round(score, 6),
                    "maximum_foreground_probability": round(maximum_score, 6),
                    "background_fraction": round(background_fraction, 6),
                    "foreground_fraction": round(foreground_fraction, 6),
                    "decision": decision,
                }
            )

        padded = np.pad(resolved_alpha, 1, constant_values=False)
        neighbors = np.zeros_like(resolved_alpha, dtype=np.uint8)
        for dy in range(3):
            for dx in range(3):
                if dx == 1 and dy == 1:
                    continue
                neighbors += padded[
                    dy : dy + resolved_alpha.shape[0],
                    dx : dx + resolved_alpha.shape[1],
                ]
        isolated = resolved_alpha & (neighbors == 0)
        # A detached bead may be intentional. Preserve it for the chart's component review.
    elif alpha_policy == "repair":
        if source_alpha_grid_path is None:
            raise ValueError("repair cleanup requires source_alpha_grid_path")
        source_alpha = np.asarray(
            Image.open(source_alpha_grid_path).convert("L"), dtype=np.uint8
        )
        if source_alpha.shape != probability.shape:
            raise ValueError("source alpha grid does not match working grid")
        values = set(np.unique(source_alpha).tolist())
        if not values.issubset({0, 255}):
            raise ValueError("source alpha grid must be binary")
        source_foreground = source_alpha == 255
        original_foreground_cells = int(source_foreground.sum())
        boundary = cv2.dilate(
            (~source_foreground).astype(np.uint8),
            np.ones((3, 3), dtype=np.uint8),
            iterations=1,
        ).astype(bool) & source_foreground
        proposed_background = source_foreground & (
            probability <= background_threshold
        )
        protected = proposed_background & boundary
        approved_repair = proposed_background & ~boundary
        ambiguous = (
            source_foreground
            & (probability > background_threshold)
            & (probability < foreground_threshold)
            & ~boundary
        )
        resolved_alpha = source_foreground.copy()
        resolved_alpha[approved_repair] = False
        forbidden_deletion_attempts = int(
            np.count_nonzero(resolved_alpha & ~source_foreground)
        )
        resolved_alpha &= source_foreground

        for decision_name, mask in (
            ("approved-background-repair", approved_repair),
            ("ambiguous", ambiguous),
            ("protected-boundary", protected),
        ):
            count, labels, stats, _ = cv2.connectedComponentsWithStats(
                mask.astype(np.uint8), connectivity=8
            )
            for label in range(1, count):
                x, y, width, height, area = [int(value) for value in stats[label]]
                decisions.append(
                    {
                        "id": len(decisions) + 1,
                        "area_cells": area,
                        "bbox": {
                            "x": x,
                            "y": y,
                            "width": width,
                            "height": height,
                        },
                        "decision": decision_name,
                    }
                )
        isolated = np.zeros(probability.shape, dtype=bool)
    else:
        # Preserve and explicit mask override are authoritative. In particular,
        # RGB values hidden under transparent pixels are never color-keyed.
        isolated = np.zeros(probability.shape, dtype=bool)

    components_path = Path(components_path)
    overlay_path = Path(overlay_path)
    components_path.parent.mkdir(parents=True, exist_ok=True)
    component_payload = {
        "alpha_policy_effective": alpha_policy,
        "background_rgb": background_payload,
        "background_color_tolerance": background_color_tolerance,
        "foreground_threshold": foreground_threshold,
        "background_threshold": background_threshold,
        "ambiguous_component_count": int(
            sum(item["decision"] == "ambiguous" for item in decisions)
        ),
        "original_foreground_cells": original_foreground_cells,
        "final_foreground_cells_before_crop": int(resolved_alpha.sum()),
        "approved_repair_cells": int(approved_repair.sum()),
        "protected_boundary_cells": int(protected.sum()),
        "forbidden_deletion_attempts": forbidden_deletion_attempts,
        "components": decisions,
    }
    components_path.write_text(
        json.dumps(component_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    overlay = rgba[:, :, :3].copy()
    overlay[ambiguous] = (255, 0, 255)
    overlay[protected] = (255, 215, 0)
    Image.fromarray(overlay, "RGB").resize(
        (overlay.shape[1] * 8, overlay.shape[0] * 8),
        Image.Resampling.NEAREST,
    ).save(overlay_path)

    ambiguous_count = component_payload["ambiguous_component_count"]
    if ambiguous_count and not allow_ambiguous:
        raise AmbiguousMaskError(
            f"semantic mask contains {ambiguous_count} ambiguous background "
            f"component(s); inspect {overlay_path} or provide --mask-override"
        )

    rgba[:, :, 3] = resolved_alpha.astype(np.uint8) * 255
    occupied = np.argwhere(resolved_alpha)
    if occupied.size == 0:
        raise ValueError("semantic cleanup produced a fully transparent grid")
    y0, x0 = occupied.min(axis=0)
    y1, x1 = occupied.max(axis=0) + 1
    cropped = rgba[y0:y1, x0:x1]
    tight_width = int(cropped.shape[1])
    tight_height = int(cropped.shape[0])
    if square_output:
        cropped = _pad_square(cropped)

    output_path = Path(output_path)
    preview_path = Path(preview_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    final = Image.fromarray(cropped, "RGBA")
    final.save(output_path)
    final.resize(
        (final.width * 8, final.height * 8), Image.Resampling.NEAREST
    ).save(preview_path)
    return {
        "alpha_policy_effective": alpha_policy,
        "removed_isolated_foreground_pixels": 0,
        "preserved_isolated_foreground_pixels": int(isolated.sum()),
        "ambiguous_component_count": int(ambiguous_count),
        "ambiguous_allowed": bool(allow_ambiguous),
        "original_foreground_cells": original_foreground_cells,
        "final_foreground_cells_before_crop": int(resolved_alpha.sum()),
        "approved_repair_cells": int(approved_repair.sum()),
        "protected_boundary_cells": int(protected.sum()),
        "forbidden_deletion_attempts": forbidden_deletion_attempts,
        "working_grid": {"width": int(rgba.shape[1]), "height": int(rgba.shape[0])},
        "tight_subject_grid": {"width": tight_width, "height": tight_height},
        "export_grid": {"width": final.width, "height": final.height},
        "crop_box": {
            "left": int(x0),
            "top": int(y0),
            "right": int(x1),
            "bottom": int(y1),
        },
        "outer_transparent_cells_removed": {
            "columns": int(rgba.shape[1] - tight_width),
            "rows": int(rgba.shape[0] - tight_height),
        },
        "square_output": bool(square_output),
        "components_path": str(components_path),
        "overlay_path": str(overlay_path),
        "alpha_values": [0, 255],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--preview")
    parser.add_argument("--white-threshold", type=int, default=245)
    parser.add_argument("--max-edge-white-area", type=int, default=2)
    args = parser.parse_args()
    metadata = cleanup_pixel(
        args.input,
        args.output,
        preview_path=args.preview,
        white_threshold=args.white_threshold,
        max_edge_white_area=args.max_edge_white_area,
    )
    print(json.dumps(metadata, ensure_ascii=False))


if __name__ == "__main__":
    main()
