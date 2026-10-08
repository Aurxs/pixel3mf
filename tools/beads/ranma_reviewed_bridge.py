"""One reviewed Ranma hair-tip bridge; deliberately not a general pixel override."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image


SCHEMA = "ranma-reviewed-source-bridge/v1"
ALLOWED_XY = [49, 30]
EXCLUDED_XY = [[13, 6], [14, 6], [48, 28], [48, 29]]
RGBA = [0, 0, 0, 255]
# Main-conversation approval is for these exact artifacts, not caller-chosen hashes.
APPROVED = {
    "source_original_sha256": "db583bb034b765f302574e069e78735c65e0943447ef00e39dea3b4de4c73b00",
    "source_canvas_sha256": "2e3a8ea97c0dfb0835708e9cdf4c8d53cdc70bfa49ed244cc3b3dc99c4bd4936",
    "reference_grid_sha256": "ac5fd23776b97bffad8b1b599bb063d304563cbee7bb3816e529a3092e9bb0ad",
    "approved_candidate_sha256": "f1f116a83e5f0c4f49f75348bc728d5a2e6856d1a73e75873e61f2add59b5b40",
    "path_sha256": "0ee1abcc516c83ca5f6ba3e0660d5571afa0aa7e0dd7cce27b5c0505dbfe508d",
    "edges_sha256": "91fa3961bc529e77366f7103e3121fa4aee8fdb969aefc010bbf95d35b06b566",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest_json(value):
    return hashlib.sha256(json.dumps(value, separators=(",", ":")).encode()).hexdigest()


def image_artifacts(evidence):
    """Extra images that must travel with the replayable bridge evidence."""
    selection = evidence.get("reviewed_selection")
    if selection is None:
        return []
    require(isinstance(selection, dict) and selection.get("schema") == SCHEMA,
            "unsupported reviewed bridge selection")
    return [selection["source_original"], selection["approved_candidate"]]


def load_selection(project, evidence_path, source, xs, ys, *, max_additions):
    evidence_path = Path(evidence_path)
    evidence = json.loads(evidence_path.read_text())
    selection = evidence.get("reviewed_selection")
    if selection is None:
        return None
    image_artifacts(evidence)
    require(max_additions == 1 and not project.get("uncompressed_crop"),
            "reviewed Ranma bridge requires budget one and no extra crop")
    require(selection.get("reviewer_role") == "main-conversation"
            and selection.get("allowed_candidate_xy") == ALLOWED_XY
            and selection.get("excluded_candidate_xy") == EXCLUDED_XY
            and selection.get("bridge_rgba") == RGBA,
            "only the reviewed Ranma position/color and background exclusions are allowed")
    for key in ("source_canvas_sha256", "reference_grid_sha256"):
        require(evidence.get(key) == APPROVED[key], "reviewed Ranma artifact hash mismatch")
    arrays = {}
    for key in ("source_original", "approved_candidate", "reference_grid", "source_canvas"):
        name = selection[key] if key in selection else evidence[key]
        require(isinstance(name, str) and Path(name).name == name and name not in (".", ".."),
                "reviewed bridge images require safe local basenames")
        path = evidence_path.parent / name
        expected = APPROVED[key + "_sha256"]
        claimed = selection.get(key + "_sha256") if key in selection else evidence[key + "_sha256"]
        require(claimed == expected and hashlib.sha256(path.read_bytes()).hexdigest() == expected,
                "reviewed Ranma artifact hash mismatch")
        arrays[key] = np.array(Image.open(path).convert("RGBA"))
    original, reference, approved = (arrays[key] for key in
                                     ("source_original", "reference_grid", "approved_candidate"))
    require(np.array_equal(arrays["source_canvas"], source)
            and original.shape == source.shape and np.all(original[:, :, 3] == 255)
            and np.array_equal(original[:, :, :3], source[:, :, :3]),
            "reviewed original/source RGB or Alpha changed")
    require(reference.shape == approved.shape == (64, 58, 4), "reviewed Ranma grid changed")
    require(digest_json({"x_edges": xs, "y_edges": ys}) == APPROVED["edges_sha256"],
            "reviewed Ranma sampling boundaries changed")
    removed = [[v["x"], v["y"]] for v in evidence["reference_differences"]]
    require(removed == EXCLUDED_XY and all(reference[y, x, 3] == 0 for x, y in EXCLUDED_XY),
            "reviewed background exclusions differ from the correction")
    expected = reference.copy()
    x, y = ALLOWED_XY
    require(expected[y, x, 3] == 0, "reviewed bridge position already occupied")
    expected[y, x] = RGBA
    require(np.array_equal(approved, expected), "approved candidate contains side edits")
    colors = {c["code"]: c["rgb"] for c in project["palette"]["colors"]}
    cells = np.array(project["cells"], dtype=object)
    require(cells.shape == reference.shape[:2], "reviewed project grid changed")
    for yy, xx in np.argwhere(reference[:, :, 3] == 255):
        require(colors.get(cells[yy, xx]) == reference[yy, xx, :3].tolist(),
                "reviewed project recolors existing pixels")
    endpoints = [(49, 29), (48, 30)]
    codes = [cells[yy, xx] for xx, yy in endpoints if colors.get(cells[yy, xx]) == RGBA[:3]]
    require(bool(codes), "reviewed bridge color must already exist at an endpoint")
    path = selection.get("path_source_xy")
    require(selection.get("path_sha256") == APPROVED["path_sha256"]
            and digest_json(path) == APPROVED["path_sha256"], "reviewed black-line path hash mismatch")
    require(isinstance(path, list) and len(path) > 1
            and all(isinstance(v, list) and len(v) == 2 and all(type(n) is int for n in v) for v in path),
            "invalid reviewed black-line path")
    centers = [[(xs[xx] + xs[xx + 1]) // 2, (ys[yy] + ys[yy + 1]) // 2] for xx, yy in endpoints]
    require(path[0] == centers[0] and path[-1] == centers[1], "black-line endpoints changed")
    for px, py in path:
        require(xs[48] <= px < xs[50] and ys[29] <= py < ys[31]
                and int(original[py, px, :3].max()) <= 16 and source[py, px, 3] >= 128,
                "path leaves the local original black foreground")
    require(all(abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1 for a, b in zip(path, path[1:])),
            "black-line path is not pixel 4-connected")
    require(any(xs[x] <= px < xs[x + 1] and ys[y] <= py < ys[y + 1] for px, py in path),
            "black-line path does not cross the allowed bridge footprint")
    return {"code": sorted(codes)[0], "approved_rgba": approved, "selection": selection}


def verify_result(project, cells, report, selection):
    if selection is None:
        return
    additions = report["added_cells"]
    require(len(additions) == 1 and [additions[0]["x"], additions[0]["y"]] == ALLOWED_XY
            and additions[0]["code"] == selection["code"],
            "reviewed bridge must add exactly its supported cell")
    colors = {c["code"]: c["rgb"] for c in project["palette"]["colors"]}
    original = np.array(project["cells"], dtype=object)
    actual = np.array(cells, dtype=object)
    expected = original.copy()
    x, y = ALLOWED_XY
    expected[y, x] = selection["code"]
    require(np.array_equal(actual, expected), "reviewed bridge changed other cells")
    approved = selection["approved_rgba"]
    for yy, xx in np.argwhere(actual != None):  # noqa: E711
        require(colors[actual[yy, xx]] == approved[yy, xx, :3].tolist()
                and approved[yy, xx, 3] == 255, "reviewed bridge differs from approved pixels")
    require(np.array_equal(actual != None, approved[:, :, 3] == 255),  # noqa: E711
            "reviewed bridge differs from approved Alpha")
