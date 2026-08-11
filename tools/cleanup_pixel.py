#!/usr/bin/env python3
"""Conservatively clean isolated foreground and tiny exterior white artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


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
