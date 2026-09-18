"""Validated palette input and deterministic perceptual matching (CIELAB Delta E 76)."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import numpy as np


def validate_palette(palette):
    colors = palette.get("colors", [])
    if not colors or len(colors) > 4096:
        raise ValueError("Palette must contain 1-4096 colors")
    seen = set()
    for color in colors:
        code = color.get("code", "")
        rgb = color.get("rgb", [])
        if not isinstance(code, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,12}", code) or code in seen:
            raise ValueError(f"Invalid or duplicate color code: {code}")
        if len(rgb) != 3 or any(type(v) is not int or not 0 <= v <= 255 for v in rgb):
            raise ValueError(f"Invalid RGB for {code}")
        seen.add(code)
    return palette


def load_palette(path):
    path = Path(path)
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        colors = []
        for row in rows:
            value = row["hex"].lstrip("#")
            if not re.fullmatch(r"[0-9a-fA-F]{6}", value):
                raise ValueError("CSV hex must contain six hex digits")
            colors.append({"code": row["code"], "rgb": [int(value[i:i+2], 16) for i in (0, 2, 4)]})
        palette = {"id": path.stem, "name": path.stem, "source": "user_supplied", "colors": colors}
    else:
        palette = json.loads(path.read_text(encoding="utf-8"))
    return validate_palette(palette)


def lab(rgb):
    rgb = np.asarray(rgb, dtype=float) / 255
    linear = np.where(rgb > 0.04045, ((rgb + 0.055) / 1.055) ** 2.4, rgb / 12.92)
    xyz = linear @ np.array([[0.4124564, 0.3575761, 0.1804375],
                             [0.2126729, 0.7151522, 0.0721750],
                             [0.0193339, 0.1191920, 0.9503041]]).T
    xyz /= np.array([0.95047, 1, 1.08883])
    f = np.where(xyz > (6 / 29) ** 3, np.cbrt(xyz), xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]),
                     200 * (f[..., 1] - f[..., 2])], axis=-1)


def map_colors(rgba, palette, max_colors=None, allowed=None, locked=None):
    """Return color-code rows; transparent cells are None, never white beads."""
    validate_palette(palette)
    colors = palette["colors"]
    known = {c["code"] for c in colors}
    allowed, locked = set(allowed or known), set(locked or [])
    if not allowed <= known or not locked <= allowed:
        raise ValueError("Allowed and locked colors must exist in the selected palette")
    colors = [c for c in colors if c["code"] in allowed]
    if max_colors is not None and (max_colors < 1 or max_colors < len(locked)):
        raise ValueError("max-colors must be positive and include all locked colors")
    occupied = rgba[:, :, 3] == 255
    unique, inverse, counts = np.unique(rgba[:, :, :3][occupied], axis=0, return_inverse=True, return_counts=True)
    if len(unique) == 0:
        raise ValueError("No occupied cells")
    if len(unique) > 4096:
        raise ValueError("Too many colors for a logical pixel source; refine the source first")
    distance = ((lab(unique)[:, None, :] - lab([c["rgb"] for c in colors])[None, :, :]) ** 2).sum(axis=2)
    selected = list(range(len(colors)))
    initial = distance.argmin(axis=1)
    if max_colors and len(set(initial)) > max_colors:
        # Greedy weighted facility selection: preserve locked anchors, then minimize total error.
        selected = [i for i, c in enumerate(colors) if c["code"] in locked]
        best = distance[:, selected].min(axis=1) if selected else np.full(len(unique), np.inf)
        while len(selected) < min(max_colors, len(colors)):
            cost = (np.minimum(best[:, None], distance) * counts[:, None]).sum(axis=0)
            cost[selected] = np.inf
            index = int(cost.argmin())
            selected.append(index)
            best = np.minimum(best, distance[:, index])
    nearest = np.asarray(selected)[distance[:, selected].argmin(axis=1)]
    mapped = np.empty(occupied.shape, dtype=object)
    mapped[:] = None
    mapped[occupied] = np.array([colors[i]["code"] for i in nearest], dtype=object)[inverse]
    delta = np.sqrt(distance[np.arange(len(unique)), nearest])
    return mapped.tolist(), {
        "method": "CIELAB_D65_DeltaE76", "dithering": False,
        "mean_delta_e": float(np.average(delta, weights=counts)), "max_delta_e": float(delta.max()),
        "source_colors": len(unique), "max_colors": max_colors,
        "allowed": sorted(allowed), "locked": sorted(locked),
    }
