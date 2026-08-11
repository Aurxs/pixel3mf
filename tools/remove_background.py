#!/usr/bin/env python3
"""Remove a background while conservatively preserving white subject regions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def _has_useful_alpha(image: Image.Image) -> bool:
    low, high = image.getchannel("A").getextrema()
    return low < 250 and high > 0


def _refine_exterior_near_white(
    image: Image.Image,
    threshold: int = 245,
) -> tuple[Image.Image, dict[str, int]]:
    """Remove only near-white pixels connected to the exterior background.

    Transparent pixels and near-white pixels form the traversable background. A
    one-pixel erosion separates narrow bridges before exterior flood-fill; enclosed
    near-white cores are then restored first so a pinhole in the outline cannot expose
    and delete an entire white face or clothing region.
    """
    rgba = np.asarray(image.convert("RGBA")).copy()
    alpha = rgba[:, :, 3]
    near_white = np.all(rgba[:, :, :3] >= threshold, axis=2)
    traversable = ((alpha <= 8) | near_white).astype(np.uint8)
    kernel = np.ones((3, 3), dtype=np.uint8)
    padded = np.pad(traversable, 1, constant_values=1)
    stable = cv2.erode(padded, kernel, iterations=1)[1:-1, 1:-1]
    count, labels = cv2.connectedComponents(stable, connectivity=8)
    if count <= 1:
        return Image.fromarray(rgba, "RGBA"), {
            "removed_exterior_near_white_pixels": 0,
            "preserved_interior_near_white_components": 0,
        }

    border_labels = np.unique(
        np.concatenate((labels[0], labels[-1], labels[:, 0], labels[:, -1]))
    )
    exterior_core = np.isin(labels, border_labels[border_labels != 0])
    interior_near_white_core = (stable > 0) & near_white & ~exterior_core
    protected_interior = cv2.dilate(
        interior_near_white_core.astype(np.uint8), kernel, iterations=1
    ).astype(bool) & near_white
    exterior = cv2.dilate(
        exterior_core.astype(np.uint8), kernel, iterations=1
    ).astype(bool) & (traversable > 0) & ~protected_interior
    removable = near_white & (alpha > 8) & exterior
    rgba[removable] = 0

    preserved = near_white & (rgba[:, :, 3] > 8)
    preserved_count, _ = cv2.connectedComponents(
        preserved.astype(np.uint8), connectivity=8
    )
    return Image.fromarray(rgba, "RGBA"), {
        "removed_exterior_near_white_pixels": int(removable.sum()),
        "preserved_interior_near_white_components": max(0, preserved_count - 1),
    }


def _rembg_result_is_usable(image: Image.Image) -> bool:
    alpha = np.asarray(image.getchannel("A"))
    coverage = float(np.count_nonzero(alpha > 8)) / alpha.size
    return 0.005 < coverage < 0.98


def remove_background(
    input_path: str | Path,
    output_path: str | Path,
    method: str = "auto",
    white_threshold: int = 245,
) -> dict[str, object]:
    source = Image.open(input_path).convert("RGBA")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if _has_useful_alpha(source):
        result, used = source, "existing-alpha"
    elif method != "white":
        try:
            from rembg import remove

            result = remove(source).convert("RGBA")
            if not _rembg_result_is_usable(result):
                raise ValueError("rembg produced an implausible foreground mask")
            used = "rembg"
        except Exception as exc:
            if method == "rembg":
                raise RuntimeError(f"rembg failed: {exc}") from exc
            result = source
            used = f"near-white-fallback ({type(exc).__name__})"
    else:
        result = source
        used = "near-white"

    result, cleanup = _refine_exterior_near_white(result, white_threshold)
    result.save(output_path)
    return {
        "method": used,
        "white_threshold": int(white_threshold),
        "background_connectivity": 8,
        "narrow_bridge_guard_radius": 1,
        **cleanup,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--method", choices=("auto", "rembg", "white"), default="auto")
    parser.add_argument("--white-threshold", type=int, default=245)
    args = parser.parse_args()
    metadata = remove_background(args.input, args.output, args.method, args.white_threshold)
    print(json.dumps(metadata, ensure_ascii=False))


if __name__ == "__main__":
    main()
