#!/usr/bin/env python3
"""Remove fully isolated foreground specks from a transparent pixel image."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image


def cleanup_pixel(input_path: str | Path, output_path: str | Path) -> int:
    rgba = np.asarray(Image.open(input_path).convert("RGBA")).copy()
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
    Image.fromarray(rgba, "RGBA").save(output_path)
    return int(isolated.sum())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("output")
    args = parser.parse_args()
    print(f"removed_pixels={cleanup_pixel(args.input, args.output)}")


if __name__ == "__main__":
    main()
