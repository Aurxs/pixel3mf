"""Apply explicit, source-bound main-review decisions to a new logical candidate.

No inference, color-key deletion, promotion, or conversion is performed here.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

import cv2
import numpy as np
from PIL import Image, ImageDraw


def _original_candidate(candidate_dir: Path):
    # Imported lazily so white_fallback can expose the CLI without a cycle.
    from white_fallback import sha256

    candidate_dir = Path(candidate_dir)
    manifest_path = candidate_dir / "candidate.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("schema") != "white-fallback-candidate/v1"
            or manifest.get("correction") is not None
            or manifest.get("method") != "white"
            or manifest.get("white_threshold") != 245
            or manifest.get("working_padding_cells") != 2):
        raise ValueError("correction requires an unchanged original white-fallback candidate")
    artifacts = manifest.get("artifacts", {})
    required = {"01_source.png", "candidate.png", "candidate_8x.png", "03_working_grid.png",
                "white_regions.json", "semantic_components.json", "failure_evidence.json",
                "white_regions_review.png", "outline_review.png"}
    if not required.issubset(artifacts):
        raise ValueError("candidate correction evidence is incomplete")
    for name, digest in artifacts.items():
        if Path(name).name != name or sha256(candidate_dir / name) != digest:
            raise ValueError("candidate artifact changed after preparation")
    if sha256(candidate_dir / "01_source.png") != manifest.get("source_sha256"):
        raise ValueError("candidate source hash mismatch")
    components = json.loads((candidate_dir / "white_regions.json").read_text(encoding="utf-8"))
    ids = {c["id"] for c in components}
    if len(ids) != len(components):
        raise ValueError("component IDs must be unique")
    working = np.asarray(Image.open(candidate_dir / "03_working_grid.png").convert("RGBA")).copy()
    candidate = np.asarray(Image.open(candidate_dir / "candidate.png").convert("RGBA")).copy()
    for name, rgba, key in (("working", working, "working_grid"),
                            ("candidate", candidate, "candidate_grid")):
        if not set(np.unique(rgba[:, :, 3])).issubset({0, 255}):
            raise ValueError(f"{name} alpha must be binary")
        if manifest[key] != {"width": rgba.shape[1], "height": rgba.shape[0]}:
            raise ValueError(f"{name} grid mismatch")
    bg = json.loads((candidate_dir / "semantic_components.json").read_text(encoding="utf-8"))
    if bg.get("background_color_tolerance") != 12:
        raise ValueError("background color tolerance must remain 12")
    # Reconstruct the prepared component membership with the unchanged rules.
    # Color identifies the reviewed label; only explicit decisions authorize deletion.
    difference = np.abs(working[:, :, :3].astype(np.int16) - np.array(bg["background_rgb"]))
    whites = (working[:, :, 3] > 0) & (np.max(difference, axis=2) <= 12)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(whites.astype(np.uint8), connectivity=8)
    if ids != {str(i) for i in range(1, count)}:
        raise ValueError("component IDs do not match the original logical membership")
    for c in components:
        x, y, w, h, area = map(int, stats[int(c["id"])])
        if c["working_bbox"] != [x, y, w, h] or c["area_cells"] != area:
            raise ValueError("component geometry does not match the bound candidate")

    # Locate the unscaled tight crop by exact RGB, including hidden RGB. Cleanup
    # may already have removed isolated alpha cells, which must stay untouched.
    height, width = candidate.shape[:2]
    origins = []
    for y in range(working.shape[0] - height + 1):
        for x in range(working.shape[1] - width + 1):
            tile = working[y:y + height, x:x + width]
            if (np.array_equal(tile[:, :, :3], candidate[:, :, :3])
                    and np.all(candidate[:, :, 3] <= tile[:, :, 3])):
                origins.append((x, y))
    if len(origins) != 1:
        raise ValueError("cannot uniquely map the candidate to its unchanged working grid")
    x0, y0 = origins[0]
    return manifest, components, working, candidate, labels, (x0, y0)


def _region_binding(labels: np.ndarray, component_id: str) -> dict:
    cells = [[int(x), int(y)] for y, x in np.argwhere(labels == int(component_id))]
    digest = hashlib.sha256(json.dumps(cells, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {"working_cells": cells, "region_sha256": digest}


def _unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate correction decision field")
        result[key] = value
    return result


def correction_template(candidate_dir: Path, output: Path) -> Path:
    """Bind an unresolved review to existing regions; never infer any decision."""
    from white_fallback import sha256

    candidate_dir, output = Path(candidate_dir), Path(output)
    if output.resolve().is_relative_to(candidate_dir.resolve()):
        raise ValueError("write the correction template outside the unchanged candidate directory")
    _, components, _, _, labels, _ = _original_candidate(candidate_dir)
    template = {
        "schema": "white-fallback-correction/v2", "reviewer_role": "main-conversation",
        "manifest_sha256": sha256(candidate_dir / "candidate.json"),
        "candidate_sha256": sha256(candidate_dir / "candidate.png"),
        "references": {},
        "components": {c["id"]: {
            "decision": "unresolved", "reason": "", **_region_binding(labels, c["id"]),
            "reference_id": "", "reference_bbox": None,
            "reference_observation": "", "candidate_observation": "",
        } for c in components},
    }
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(template, ensure_ascii=False, indent=2) + "\n")
    return output


def _validate_individual_reviews(decisions: dict, root: Path, labels: np.ndarray,
                                 selected: set[str], artifacts: dict) -> dict[str, Path]:
    from white_fallback import sha256

    references = decisions.get("references")
    if not isinstance(references, dict) or not references:
        raise ValueError("individual review requires hash-bound reference images")
    verified, sizes = {}, {}
    for key, item in references.items():
        if not isinstance(item, dict):
            raise ValueError("each reference requires a local image, hash and source")
        name = item.get("path")
        if (not isinstance(name, str) or not name.startswith("correction_reference_")
                or Path(name).name != name or "/" in name or "\\" in name
                or name in artifacts or name in {p.name for p in verified.values()}):
            raise ValueError("reference image must use a unique correction_reference_ basename")
        path = root / name
        if (not path.is_file() or path.is_symlink()
                or not isinstance(item.get("source"), str) or not item["source"].strip()
                or sha256(path) != item.get("sha256")):
            raise ValueError("reference image hash or source provenance mismatch")
        with Image.open(path) as image:
            sizes[key] = image.size
            image.verify()
        verified[key] = path
    used = set()
    for key in selected:
        item = decisions["components"][key]
        expected = _region_binding(labels, key)
        cells = item.get("working_cells")
        if (not isinstance(cells, list)
                or any(not isinstance(p, list) or len(p) != 2
                       or any(type(v) is not int for v in p) for p in cells)
                or cells != expected["working_cells"]
                or item.get("region_sha256") != expected["region_sha256"]):
            raise ValueError("individual region coordinates and hash must match exact working-grid membership")
        ref = item.get("reference_id")
        if not isinstance(ref, str) or ref not in verified:
            raise ValueError("each deleted region requires its own explicit reference correspondence")
        bbox = item.get("reference_bbox")
        if (not isinstance(bbox, list) or len(bbox) != 4
                or any(type(v) is not int for v in bbox)):
            raise ValueError("reference_bbox must identify integer image coordinates [x, y, width, height]")
        x, y, w, h = bbox
        rw, rh = sizes[ref]
        if min(x, y) < 0 or min(w, h) <= 0 or x + w > rw or y + h > rh:
            raise ValueError("reference_bbox is outside its hash-bound image")
        for field in ("reference_observation", "candidate_observation"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise ValueError("each deleted region requires reference and candidate observations")
        used.add(ref)
    if used != set(verified):
        raise ValueError("reference images must correspond exactly to individually reviewed regions")
    return verified


def correct_regions(candidate_dir: Path, decisions_path: Path, output: Path) -> Path:
    from white_fallback import CHECKS, sha256, write_json

    candidate_dir, decisions_path, output = map(Path, (candidate_dir, decisions_path, output))
    manifest, components, working, candidate, labels, (x0, y0) = _original_candidate(candidate_dir)
    manifest_path = candidate_dir / "candidate.json"
    artifacts = manifest["artifacts"]
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"), object_pairs_hook=_unique_fields)
    if (decisions.get("schema") not in {"white-fallback-correction/v1", "white-fallback-correction/v2"}
            or decisions.get("reviewer_role") != "main-conversation"
            or decisions.get("manifest_sha256") != sha256(manifest_path)
            or decisions.get("candidate_sha256") != sha256(candidate_dir / "candidate.png")):
        raise ValueError("main-conversation correction with exact manifest and candidate hashes required")

    choices = decisions.get("components", {})
    ids = {c["id"] for c in components}
    if not isinstance(choices, dict) or len(ids) != len(components) or set(choices) != ids:
        raise ValueError("component IDs must match every original numbered white region exactly")
    for item in choices.values():
        if (not isinstance(item, dict) or item.get("decision") not in {"background", "preserve"}
                or not isinstance(item.get("reason"), str) or not item["reason"].strip()):
            raise ValueError("each component requires an explicit background/preserve decision and reason")
    selected = {key for key, item in choices.items() if item["decision"] == "background"}
    if not selected or (selected == ids and decisions["schema"] == "white-fallback-correction/v1"):
        raise ValueError("select a nonempty proper subset; blanket white-region deletion is prohibited")

    references = {}
    if decisions["schema"] == "white-fallback-correction/v2":
        references = _validate_individual_reviews(decisions, decisions_path.parent,
                                                  labels, selected, artifacts)
    height, width = candidate.shape[:2]
    removed_working = np.isin(labels, [int(key) for key in selected])
    removed = removed_working[y0:y0 + height, x0:x0 + width]
    if removed.sum() != removed_working.sum() or not np.all(candidate[removed, 3] == 255):
        raise ValueError("selected component is not fully opaque inside the candidate")
    if selected == ids:
        # This exception is only for individually evidenced interior holes.
        # Topology cannot classify white clothing/eyes: main review still must.
        interior = cv2.erode((candidate[:, :, 3] == 255).astype(np.uint8),
                             np.ones((3, 3), dtype=np.uint8),
                             borderType=cv2.BORDER_CONSTANT, borderValue=0).astype(bool)
        if not np.all(interior[removed]):
            raise ValueError("all-region correction requires enclosed regions away from transparency and canvas edges")
    corrected, corrected_working = candidate.copy(), working.copy()
    corrected[removed, 3] = 0
    corrected_working[removed_working, 3] = 0
    occupied = np.argwhere(corrected[:, :, 3] == 255)
    if not len(occupied):
        raise ValueError("region correction must retain foreground")
    # Verify permission-scoped changes in the parent coordinate frame before
    # cropping. Only fully transparent outer rows/columns may then be removed.
    assert np.array_equal(corrected[:, :, :3], candidate[:, :, :3])
    assert np.array_equal(corrected[~removed, 3], candidate[~removed, 3])
    top, left = map(int, occupied.min(axis=0))
    bottom, right = map(int, occupied.max(axis=0) + 1)
    tight = corrected[top:bottom, left:right]
    candidate_grid = {"width": right - left, "height": bottom - top}

    output.mkdir(parents=True, exist_ok=False)
    # Keep all source/failure evidence; never copy an existing approval or review.
    for name in artifacts:
        shutil.copyfile(candidate_dir / name, output / name)
    for path in references.values():
        shutil.copyfile(path, output / path.name)
    for name in ("candidate.json", "candidate.png", "03_working_grid.png", "white_regions.json"):
        shutil.copyfile(candidate_dir / name, output / ("parent_" + name))
    write_json(output / "correction_decisions.json", decisions)
    Image.fromarray(tight).save(output / "candidate.png")
    Image.fromarray(tight).resize(((right - left) * 8, (bottom - top) * 8), Image.Resampling.NEAREST).save(output / "candidate_8x.png")
    Image.fromarray(tight[:, :, 3]).save(output / "candidate_mask.png")
    Image.fromarray(corrected_working).save(output / "03_working_grid.png")
    h, w = working.shape[:2]
    Image.fromarray(corrected_working).resize((w * 8, h * 8), Image.Resampling.NEAREST).save(output / "03_working_preview.png")
    remaining = [{**c, "status": "needs_visual_review"} for c in components if c["id"] not in selected]
    write_json(output / "white_regions.json", remaining)

    board = Image.new("RGBA", (w * 12, h * 12), (140, 140, 140, 255))
    board.alpha_composite(Image.fromarray(corrected_working).resize(board.size, Image.Resampling.NEAREST))
    overlay = board.convert("RGB")
    draw = ImageDraw.Draw(overlay)
    for c in remaining:
        x, y, cw, ch = c["working_bbox"]
        draw.rectangle((x * 12, y * 12, (x + cw) * 12 - 1, (y + ch) * 12 - 1), outline="lime", width=2)
        draw.text((x * 12, y * 12), c["id"], fill="red", stroke_width=1)
    overlay.save(output / "white_regions_review.png")
    solid = corrected_working[:, :, 3] == 255
    boundary = solid & ~cv2.erode(solid.astype(np.uint8), np.ones((3, 3), dtype=np.uint8)).astype(bool)
    contour = corrected_working.copy()
    contour[boundary] = (255, 215, 0, 255)
    Image.fromarray(contour).resize(board.size, Image.Resampling.NEAREST).save(output / "outline_review.png")
    # Only the diagnostic image has painted RGB; candidate RGB is unchanged.
    diff = candidate.copy()
    diff[removed] = (255, 0, 255, 255)
    canvas = Image.new("RGBA", (width, height), (140, 140, 140, 255))
    canvas.alpha_composite(Image.fromarray(diff))
    canvas.resize((width * 8, height * 8), Image.Resampling.NEAREST).save(output / "correction_diff_8x.png")
    report = {"schema": "white-fallback-correction-result/v1",
              "status": "needs_new_main_visual_review", "parent_manifest_sha256": sha256(manifest_path),
              "parent_candidate_sha256": sha256(candidate_dir / "candidate.png"),
              "source_sha256": manifest["source_sha256"], "candidate_grid": candidate_grid,
              "parent_candidate_grid": manifest["candidate_grid"],
              "removed_component_ids": sorted(selected, key=int), "removed_cells": int(removed.sum()),
              "preserved_component_ids": sorted(ids - selected, key=int),
              "removed_candidate_xy": [[int(x), int(y)] for y, x in np.argwhere(removed)],
              "removed_coordinates_frame": "parent_candidate",
              "parent_candidate_crop_origin_in_working": [x0, y0],
              "crop_box_in_parent_candidate": [left, top, right, bottom],
              "candidate_crop_origin_in_working": [x0 + left, y0 + top],
              "correction_diff_grid": manifest["candidate_grid"],
              "pixel_invariants_frame": "parent_candidate_before_tight_crop",
              "rgb_unchanged": True,
              "other_alpha_unchanged": True, "alpha_values": np.unique(corrected[:, :, 3]).tolist(),
              "prior_review_reused": False, "conversion_invoked": False}
    if decisions["schema"] == "white-fallback-correction/v2":
        report.update(decision_schema=decisions["schema"],
                      all_numbered_regions_selected=selected == ids,
                      enclosed_region_guard_applied=selected == ids)
    write_json(output / "correction.json", report)
    manifest = {**manifest, "status": "needs_main_visual_review", "correction": "correction.json",
                "candidate_grid": candidate_grid,
                "warning": "Explicit Alpha-only region correction followed by transparent-edge tight cropping; previous review does not approve this candidate.",
                "artifacts": {p.name: sha256(p) for p in sorted(output.iterdir()) if p.is_file()}}
    write_json(output / "candidate.json", manifest)
    write_json(output / "review.template.json", {
        "schema": "white-fallback-review/v1", "reviewer_role": "main-conversation",
        "manifest_sha256": sha256(output / "candidate.json"), "decision": "pending",
        "checks": dict.fromkeys(CHECKS, False),
        "components": {c["id"]: {"decision": "unresolved", "reason": ""} for c in remaining},
        "notes": "Inspect corrected candidate, difference, binary mask, remaining whites and outline anew."})
    return output / "candidate.json"
