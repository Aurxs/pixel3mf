#!/usr/bin/env python3
"""Remove the four user-identified white background holes from a refined grid."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def remove_selected_white_holes(
    input_path: str | Path,
    output_path: str | Path,
    preview_path: str | Path | None = None,
    white_threshold: int = 245,
) -> dict[str, object]:
    rgba = np.asarray(Image.open(input_path).convert("RGBA")).copy()
    # Three additional near-white isolated cells identified by the user in the
    # current 74x78 refined grid. They are RGB 236-244, so a >=245 white mask
    # does not catch them; keep this cleanup explicitly coordinate-scoped.
    target_logical_cells = ((14, 59), (12, 65), (53, 55))
    removed_logical_cells = []
    for x, y in target_logical_cells:
        if not (0 <= y < rgba.shape[0] and 0 <= x < rgba.shape[1]):
            raise ValueError(f"target logical cell out of bounds: {(x, y)}")
        if rgba[y, x, 3] > 8:
            rgba[y, x] = (0, 0, 0, 0)
            removed_logical_cells.append([x, y])

    solid = rgba[:, :, 3] > 8
    near_white = solid & np.all(rgba[:, :, :3] >= white_threshold, axis=2)
    count, labels, stats, centroids = cv2.connectedComponentsWithStats(
        near_white.astype(np.uint8), connectivity=8
    )

    # These are the four white holes identified by the user in the 74x78
    # refined grid. The last region intentionally starts at x=59 because the
    # right-side component's centroid is x=61.5.
    target_regions = (
        (23, 44, 37, 60),  # large hole below the face, left
        (44, 50, 57, 60),  # hole below the face, right
        (12, 59, 22, 70),  # hole inside the left red decoration
        (59, 64, 68, 73),  # hole inside the right red decoration
    )
    removed = []
    for label in range(1, count):
        cx, cy = centroids[label]
        if not any(x0 <= cx < x1 and y0 <= cy < y1 for x0, y0, x1, y1 in target_regions):
            continue
        component = labels == label
        x, y, w, h, area = stats[label]
        rgba[component] = (0, 0, 0, 0)
        removed.append({"bbox": [int(x), int(y), int(w), int(h)], "pixels": int(area)})

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = Image.fromarray(rgba, "RGBA")
    result.save(output_path)
    if preview_path is not None:
        preview_path = Path(preview_path)
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        result.resize((result.width * 8, result.height * 8), Image.Resampling.NEAREST).save(
            preview_path
        )
    return {
        "white_threshold": int(white_threshold),
        "target_regions": [list(region) for region in target_regions],
        "removed_components": removed,
        "removed_pixels": int(sum(item["pixels"] for item in removed)),
        "target_logical_cells": [list(cell) for cell in target_logical_cells],
        "removed_logical_cells": removed_logical_cells,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--preview")
    args = parser.parse_args()
    print(
        json.dumps(
            remove_selected_white_holes(args.input, args.output, args.preview),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
