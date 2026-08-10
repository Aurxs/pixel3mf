#!/usr/bin/env python3
"""Remove an image background, preferring rembg with a near-white fallback."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def _has_useful_alpha(image: Image.Image) -> bool:
    low, high = image.getchannel("A").getextrema()
    return low < 250 and high > 0


def _near_white_to_alpha(image: Image.Image, threshold: int = 245) -> Image.Image:
    rgba = np.asarray(image.convert("RGBA")).copy()
    near_white = np.all(rgba[:, :, :3] >= threshold, axis=2).astype(np.uint8)
    count, labels = cv2.connectedComponents(near_white, connectivity=4)
    if count <= 1:
        return Image.fromarray(rgba, "RGBA")

    border_labels = np.unique(
        np.concatenate((labels[0], labels[-1], labels[:, 0], labels[:, -1]))
    )
    background = np.isin(labels, border_labels[border_labels != 0])
    rgba[background, 3] = 0
    return Image.fromarray(rgba, "RGBA")


def _rembg_result_is_usable(image: Image.Image) -> bool:
    alpha = np.asarray(image.getchannel("A"))
    coverage = float(np.count_nonzero(alpha > 8)) / alpha.size
    return 0.005 < coverage < 0.98


def remove_background(
    input_path: str | Path,
    output_path: str | Path,
    method: str = "auto",
    white_threshold: int = 245,
) -> str:
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
            result = _near_white_to_alpha(source, white_threshold)
            used = f"near-white-fallback ({type(exc).__name__})"
    else:
        result = _near_white_to_alpha(source, white_threshold)
        used = "near-white"

    result.save(output_path)
    return used


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--method", choices=("auto", "rembg", "white"), default="auto")
    parser.add_argument("--white-threshold", type=int, default=245)
    args = parser.parse_args()
    used = remove_background(args.input, args.output, args.method, args.white_threshold)
    print(f"background_method={used}")


if __name__ == "__main__":
    main()
