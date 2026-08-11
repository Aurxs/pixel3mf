#!/usr/bin/env python3
"""Crop visible content and add transparent breathing room without rescaling."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image


def prepare_canvas(
    input_path: str | Path,
    output_path: str | Path,
    padding_ratio: float = 0.12,
    square: bool = False,
) -> tuple[int, int]:
    """Prepare a transparent canvas while preserving the subject aspect ratio.

    ``square=True`` retains the legacy square-output behavior for explicit use.
    The pixel-art pipeline keeps this disabled so Perfect Pixel can preserve its
    detected rectangular logical grid.
    """
    image = Image.open(input_path).convert("RGBA")
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError("input image is fully transparent")
    if padding_ratio < 0:
        raise ValueError("padding_ratio must be non-negative")

    subject = image.crop(bbox)
    pad_x = math.ceil(subject.width * padding_ratio)
    pad_y = math.ceil(subject.height * padding_ratio)
    width = max(1, subject.width + 2 * pad_x)
    height = max(1, subject.height + 2 * pad_y)
    if square:
        width = height = max(width, height)
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    position = ((width - subject.width) // 2, (height - subject.height) // 2)
    canvas.alpha_composite(subject, position)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)
    return canvas.size


def prepare_square(
    input_path: str | Path,
    output_path: str | Path,
    padding_ratio: float = 0.12,
) -> tuple[int, int]:
    """Compatibility wrapper for callers that explicitly require a square."""
    return prepare_canvas(input_path, output_path, padding_ratio, square=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--padding-ratio", type=float, default=0.12)
    parser.add_argument(
        "--square",
        action="store_true",
        help="Use the legacy square canvas instead of preserving aspect ratio",
    )
    args = parser.parse_args()
    width, height = prepare_canvas(
        args.input, args.output, args.padding_ratio, square=args.square
    )
    print(f"canvas={width}x{height}")


if __name__ == "__main__":
    main()
