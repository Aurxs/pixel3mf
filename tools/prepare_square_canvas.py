#!/usr/bin/env python3
"""Crop visible content and center it on a transparent square canvas."""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image


def prepare_square(
    input_path: str | Path,
    output_path: str | Path,
    padding_ratio: float = 0.12,
) -> tuple[int, int]:
    image = Image.open(input_path).convert("RGBA")
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError("input image is fully transparent")

    subject = image.crop(bbox)
    side = max(1, math.ceil(max(subject.size) * (1 + 2 * padding_ratio)))
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    position = ((side - subject.width) // 2, (side - subject.height) // 2)
    canvas.alpha_composite(subject, position)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path)
    return canvas.size


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--padding-ratio", type=float, default=0.12)
    args = parser.parse_args()
    width, height = prepare_square(args.input, args.output, args.padding_ratio)
    print(f"canvas={width}x{height}")


if __name__ == "__main__":
    main()
