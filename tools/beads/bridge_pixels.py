#!/usr/bin/env python3
"""Restore source-supported one-cell diagonal bridges; explicit opt-in, never join gaps."""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import label

from bead_palette import lab
from bead_pattern import validate_project
from ranma_reviewed_bridge import ALLOWED_XY, load_selection, verify_result


def repair_bridges(cells, palette, source, x_edges, y_edges, *, max_additions=4,
                   _reviewed_selection=None):
    """Use exact source-cell footprints; preserve every existing bead and palette code."""
    rows = np.array(cells, dtype=object)
    original = rows.copy()
    colors = {c["code"]: c["rgb"] for c in palette["colors"]}
    if max_additions < 1 or max_additions > 16:
        raise ValueError("Bridge budget must be 1-16 cells")
    if source.ndim != 3 or source.shape[2] != 4:
        raise ValueError("Source must be RGBA with reviewed foreground alpha")
    for edges, count, bound in [
        (x_edges, rows.shape[1], source.shape[1]),
        (y_edges, rows.shape[0], source.shape[0]),
    ]:
        if len(edges) != count + 1 or any(type(v) is not int for v in edges):
            raise ValueError(
                "Exact integer source boundaries must match the logical grid"
            )
        if (
            edges[0] < 0
            or edges[-1] > bound
            or any(a >= b for a, b in zip(edges, edges[1:]))
        ):
            raise ValueError("Invalid source boundaries")
    source_mask = source[:, :, 3] >= 128
    changes = []
    before = label(rows != None)[1]  # noqa: E711
    # Only original diagonal contacts qualify; inserted beads never seed a chain.
    candidates = []
    for y in range(rows.shape[0] - 1):
        for x in range(rows.shape[1] - 1):
            occupied = original[y : y + 2, x : x + 2] != None  # noqa: E711
            if occupied.sum() != 2 or occupied[0, 0] != occupied[1, 1]:
                continue
            endpoints = [(x + int(dx), y + int(dy)) for dy, dx in np.argwhere(occupied)]
            choices = []
            for dy, dx in np.argwhere(~occupied):
                cx, cy = x + int(dx), y + int(dy)
                if _reviewed_selection is not None and [cx, cy] != ALLOWED_XY:
                    continue
                x0, x1 = x_edges[cx : cx + 2]
                y0, y1 = y_edges[cy : cy + 2]
                mask = source_mask[y0:y1, x0:x1]
                components, count = label(mask)
                supported = None
                for component in range(1, count + 1):
                    patch = components == component
                    crossing = []
                    for ex, ey in endpoints:
                        if ex < cx:
                            crossing.append(
                                x0 > 0
                                and np.any(patch[:, 0] & source_mask[y0:y1, x0 - 1])
                            )
                        elif ex > cx:
                            crossing.append(
                                x1 < source.shape[1]
                                and np.any(patch[:, -1] & source_mask[y0:y1, x1])
                            )
                        elif ey < cy:
                            crossing.append(
                                y0 > 0 and np.any(patch[0] & source_mask[y0 - 1, x0:x1])
                            )
                        else:
                            crossing.append(
                                y1 < source.shape[0]
                                and np.any(patch[-1] & source_mask[y1, x0:x1])
                            )
                    if all(crossing) and (
                        supported is None or patch.sum() > supported.sum()
                    ):
                        supported = patch
                if supported is None or supported.mean() < 0.15:
                    continue
                # Both endpoints must connect locally through this same source component.
                rx0, rx1 = x_edges[x], x_edges[x + 2]
                ry0, ry1 = y_edges[y], y_edges[y + 2]
                local, _ = label(source_mask[ry0:ry1, rx0:rx1])
                sy, sx = np.argwhere(supported)[0]
                component = local[y0 - ry0 + sy, x0 - rx0 + sx]
                anchors = [
                    local[
                        (y_edges[ey] + y_edges[ey + 1]) // 2 - ry0,
                        (x_edges[ex] + x_edges[ex + 1]) // 2 - rx0,
                    ]
                    for ex, ey in endpoints
                ]
                if not component or any(v != component for v in anchors):
                    continue
                rgb = np.median(source[y0:y1, x0:x1, :3][supported], axis=0)
                neighbor_codes = sorted({original[ey, ex] for ex, ey in endpoints})
                distances = np.sum(
                    (lab([colors[c] for c in neighbor_codes]) - lab(rgb)) ** 2, axis=1
                )
                code = neighbor_codes[int(np.argmin(distances))]
                if _reviewed_selection is not None:
                    # Hash-bound approval picks an existing endpoint color;
                    # it never waives the coverage/crossing checks above.
                    code = _reviewed_selection["code"]
                    if code not in neighbor_codes:
                        continue
                choices.append(
                    {
                        "x": cx,
                        "y": cy,
                        "code": code,
                        "source_coverage": float(supported.mean()),
                        "source_bounds": [x0, y0, x1, y1],
                    }
                )
            choices.sort(key=lambda c: (-c["source_coverage"], c["y"], c["x"]))
            # Do not arbitrarily choose between equally plausible corners.
            if choices and (
                len(choices) == 1
                or choices[0]["source_coverage"] - choices[1]["source_coverage"] >= 0.02
            ):
                candidates.append((choices[0], endpoints))
    candidates.sort(key=lambda v: (-v[0]["source_coverage"], v[0]["y"], v[0]["x"]))
    for candidate, endpoints in candidates:
        components, _ = label(rows != None)  # noqa: E711
        if len({components[y, x] for x, y in endpoints}) != 2:
            continue
        if len(changes) >= max_additions:
            raise ValueError(
                "Evidence-supported bridges exceed the budget; review without modifying input"
            )
        rows[candidate["y"], candidate["x"]] = candidate["code"]
        changes.append(candidate)
    assert np.array_equal(rows[original != None], original[original != None])  # noqa: E711
    assert set(rows[rows != None]) <= set(original[original != None])  # noqa: E711
    return rows.tolist(), {
        "components_before": int(before),
        "components_after": int(label(rows != None)[1]),  # noqa: E711
        "added_cells": changes,
        "existing_cells_unchanged": True,
        "palette_union_unchanged": True,
        "status": "needs_visual_review",
    }


def verified_inputs(project, evidence_path):
    """Reject missing/mismatched sampling transforms, including unproven 52-cell resizing."""
    evidence_path = Path(evidence_path)
    evidence = json.loads(evidence_path.read_text())
    if (
        evidence.get("schema") != "pixel-sampling-evidence/v1"
        or evidence.get("alpha_threshold") != 128
    ):
        raise ValueError("Unsupported sampling evidence")
    arrays = []
    for key in ["source_canvas", "reference_grid"]:
        path = evidence_path.parent / evidence[key]
        if hashlib.sha256(path.read_bytes()).hexdigest() != evidence[key + "_sha256"]:
            raise ValueError("Sampling evidence file hash mismatch")
        arrays.append(np.array(Image.open(path).convert("RGBA")))
    source, reference = arrays
    xs, ys = evidence["x_edges"], evidence["y_edges"]
    if len(xs) != reference.shape[1] + 1 or len(ys) != reference.shape[0] + 1:
        raise ValueError("Evidence boundaries do not match reference dimensions")
    for edges, bound in [(xs, source.shape[1]), (ys, source.shape[0])]:
        if (
            any(type(v) is not int for v in edges)
            or edges[0] < 0
            or edges[-2] >= bound
            or any(a >= b for a, b in zip(edges, edges[1:]))
        ):
            raise ValueError("Invalid evidence boundaries")
    sampled = source[
        np.clip([(a + b) // 2 for a, b in zip(ys, ys[1:])], 0, source.shape[0] - 1)[
            :, None
        ],
        np.clip([(a + b) // 2 for a, b in zip(xs, xs[1:])], 0, source.shape[1] - 1)[
            None, :
        ],
    ]
    actual = [
        {
            "x": int(x),
            "y": int(y),
            "sampled": sampled[y, x].tolist(),
            "reference": reference[y, x].tolist(),
        }
        for y, x in np.argwhere(np.any(sampled != reference, axis=2))
    ]
    if actual != evidence.get("reference_differences", []):
        raise ValueError(
            "Sampling replay does not match recorded reference differences"
        )
    # Recorded white-edge removals may retain sampled RGB under zero Alpha.
    # Also accept the historical all-zero RGB representation, never recoloring.
    if len(actual) != evidence.get("manifest_cleanup", {}).get(
        "removed_edge_white_pixels", 0
    ) or any(
        min(v["sampled"][:3]) < 240
        or v["sampled"][3] < 128
        or v["reference"][3] != 0
        or v["reference"][:3] not in ([0, 0, 0], v["sampled"][:3])
        for v in actual
    ):
        raise ValueError("Unexplained source-to-reference edits")
    crop = project.get("uncompressed_crop")
    if crop:
        if (
            crop.get("source_grid") != [reference.shape[1], reference.shape[0]]
            or crop.get("resampled") is not False
        ):
            raise ValueError(
                "Only verified non-resampling crop transforms are supported"
            )
        left, top, right, bottom = crop["bbox"]
        if not (
            0 <= left < right <= reference.shape[1]
            and 0 <= top < bottom <= reference.shape[0]
        ):
            raise ValueError("Invalid crop bounds")
        reference = reference[top:bottom, left:right]
        xs, ys = xs[left : right + 1], ys[top : bottom + 1]
    occupied = np.array(project["cells"], dtype=object) != None  # noqa: E711
    if occupied.shape != reference.shape[:2] or not np.array_equal(
        occupied, reference[:, :, 3] >= 128
    ):
        raise ValueError(
            "Project occupancy differs from verified reference; do not guess a transform"
        )
    # Perfect Pixel may extrapolate its last edge beyond the canvas; slices stop at the canvas.
    return (
        source,
        [min(v, source.shape[1]) for v in xs],
        [min(v, source.shape[0]) for v in ys],
    )


def run(project_path, evidence_path, output, max_additions=4):
    output = Path(output)
    if output.exists():
        raise ValueError("Use a new output JSON; preserve earlier results")
    project = json.loads(Path(project_path).read_text())
    validate_project(project)
    source, xs, ys = verified_inputs(project, evidence_path)
    selection = load_selection(project, evidence_path, source, xs, ys,
                               max_additions=max_additions)
    result = deepcopy(project)
    result["cells"], result["bridge_repair"] = repair_bridges(
        project["cells"],
        project["palette"],
        source,
        xs,
        ys,
        max_additions=max_additions,
        _reviewed_selection=selection,
    )
    verify_result(project, result["cells"], result["bridge_repair"], selection)
    result.pop("statistics", None)
    result.pop("components", None)
    result["bridge_repair"]["input_sha256"] = hashlib.sha256(
        Path(project_path).read_bytes()
    ).hexdigest()
    result["bridge_repair"]["evidence_sha256"] = hashlib.sha256(
        Path(evidence_path).read_bytes()
    ).hexdigest()
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return result["bridge_repair"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project")
    parser.add_argument("evidence")
    parser.add_argument("output")
    parser.add_argument("--max-additions", type=int, default=4)
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                run(args.project, args.evidence, args.output, args.max_additions)
            )
        )
    except (ValueError, OSError, KeyError) as error:
        parser.exit(2, f"{error}\n")
