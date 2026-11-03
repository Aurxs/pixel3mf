#!/usr/bin/env python3
"""Review, promote and export RGB-only refinement of a promoted white correction."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import tempfile

import cv2
import numpy as np
from PIL import Image

import white_fallback as white
from white_region_correction import correct_regions
from refine_pixel import validate_detected_grid
from reviewed_bridge_export import read, rgba, require, local, snapshot_candidate, compare_candidate
from lumina_batch import LUT_FILENAME, DEFAULT_PARAMS, build_pixel_size_plan, convert_with_lumina_batch

CHECKS = (*white.CHECKS, "upstream_correction_and_promotion_reviewed", "every_rgb_change_reviewed",
          "same_grid_and_alpha", "at_most_18_visible_colors", "four_connected_foreground",
          "protected_white_regions_reviewed")
PROMOTED = ("04_pixel_perfect.png", "05_pixel_preview_8x.png", "approval.json")


def verify_upstream(root):
    original, corrected = root / "original", root / "corrected"
    parent = read(original / "candidate.json")
    require(parent.get("correction") is None, "expected original white candidate")
    validate_detected_grid(parent["source_grid"]["width"], parent["source_grid"]["height"])
    # Retained model masks only; no model inference and no caller-selected mask.
    for mask in read(original / "failure_evidence.json")["model_masks"]:
        require(Path(mask["path"]).name == mask["path"], "unsafe failure mask path")
        local(original, mask["path"])
    with tempfile.TemporaryDirectory() as temp:
        temp = Path(temp)
        white.prepare(original / "01_source.png", original / "failure_evidence.json", temp / "original")
        compare_candidate(original, temp / "original")
        correct_regions(original, corrected / "correction_decisions.json", temp / "corrected")
        compare_candidate(corrected, temp / "corrected")
    validated = white.validate_review(corrected / "review.json")
    # A portable snapshot retains the old promotion's historical path verbatim.
    # It is evidence only: never open that path, and verify every other field.
    historical = read(root / "upstream.json")["candidate_path"]
    require(isinstance(historical, str) and Path(historical).is_absolute()
            and Path(historical).name == "candidate.png", "invalid historical promotion path")
    require(read(corrected / "approval.json") == {**validated, "candidate_path": historical},
            "upstream promotion does not match approved correction")
    require(white.sha256(corrected / PROMOTED[0]) == white.sha256(corrected / "candidate.png")
            and white.sha256(corrected / PROMOTED[1]) == white.sha256(corrected / "candidate_8x.png"),
            "upstream promoted pixels or preview changed")
    return {"source_grid": parent["source_grid"], "source_sha256": parent["source_sha256"],
            "upstream_manifest_sha256": validated["manifest_sha256"],
            "upstream_review_sha256": validated["review_sha256"],
            "upstream_approval_sha256": white.sha256(corrected / "approval.json")}


def refinement_report(root):
    corrected = root / "corrected"
    before, after = rgba(corrected / "04_pixel_perfect.png"), rgba(root / "candidate.png")
    require(before.shape == after.shape, "refinement grid dimensions changed; no resampling or cropping")
    require(set(np.unique(before[:, :, 3])).issubset({0, 255})
            and set(np.unique(after[:, :, 3])).issubset({0, 255}), "Alpha must be binary")
    require(np.array_equal(before[:, :, 3], after[:, :, 3]), "refinement Alpha changed")
    solid = before[:, :, 3] == 255
    require(np.array_equal(before[~solid], after[~solid]), "transparent RGB must remain unchanged")
    palette = np.unique(after[solid, :3], axis=0).tolist()
    require(0 < len(palette) <= 18, "refinement requires at most 18 visible RGB colors")
    count, _ = cv2.connectedComponents(solid.astype(np.uint8), connectivity=4)
    require(count == 2, "foreground must have exactly one 4-connected component")
    changed = np.any(before[:, :, :3] != after[:, :, :3], axis=2)
    changes = [{"x": int(x), "y": int(y), "before_rgb": before[y, x, :3].tolist(),
                "after_rgb": after[y, x, :3].tolist()} for y, x in np.argwhere(changed)]
    # Protect every surviving formal near-white region, including the eyes.
    # Reuse its exact original membership and existing tolerance (12), never a
    # new user mask or a globally applied color replacement/removal operation.
    bg = read(corrected / "semantic_components.json")
    require(bg["background_color_tolerance"] == 12, "white protection tolerance changed")
    working = rgba(corrected / "parent_03_working_grid.png")
    whites = ((working[:, :, 3] == 255) &
              (np.max(np.abs(working[:, :, :3].astype(int) - bg["background_rgb"]), axis=2) <= 12))
    _, labels = cv2.connectedComponents(whites.astype(np.uint8), connectivity=8)
    ox, oy = read(corrected / "correction.json")["candidate_crop_origin_in_working"]
    h, w = solid.shape
    labels = labels[oy:oy + h, ox:ox + w]
    require(labels.shape == solid.shape, "white protection grid mismatch")
    protected = []
    for region in read(corrected / "white_regions.json"):
        cells = (labels == int(region["id"])) & solid
        require(int(cells.sum()) == region["area_cells"], "protected white region membership changed")
        require(np.all(np.abs(after[cells, :3].astype(int) - bg["background_rgb"]) <= 12),
                "protected white region RGB is no longer white")
        protected.append({"id": region["id"], "cells_xy": [[int(x), int(y)] for y, x in np.argwhere(cells)]})
    return {"schema": "reviewed-rgb-diff/v1", "coordinates": "unchanged_corrected_candidate_xy_zero_based",
            "before_sha256": white.sha256(corrected / "04_pixel_perfect.png"),
            "after_sha256": white.sha256(root / "candidate.png"),
            "export_grid": {"width": w, "height": h}, "alpha_unchanged": True, "alpha_values": [0, 255]
            if np.any(~solid) else [255], "visible_colors": len(palette), "palette_rgb": palette,
            "foreground_cells": int(solid.sum()), "four_connected_components": count - 1,
            "changed_cells": len(changes), "rgb_changes": changes, "protected_white_regions": protected,
            "white_reference_rgb": bg["background_rgb"], "white_tolerance": 12}


def inventory(root):
    expected = {"candidate.png", "candidate_8x.png", "rgb_diff.json", "rgb_diff_8x.png", "upstream.json",
                "original/candidate.json", "corrected/candidate.json", "corrected/review.json"}
    expected.update("corrected/" + name for name in PROMOTED)
    for folder in ("original", "corrected"):
        expected.update(f"{folder}/{name}" for name in read(root / folder / "candidate.json")["artifacts"])
    return expected


def previews(root):
    after = rgba(root / "candidate.png")
    before = rgba(root / "corrected/04_pixel_perfect.png")
    im = Image.fromarray(after)
    size = (im.width * 8, im.height * 8)
    preview = im.resize(size, Image.Resampling.NEAREST)
    changed = np.any(before[:, :, :3] != after[:, :, :3], axis=2)
    marked = after.copy()
    marked[changed] = [255, 0, 255, 255]
    return preview, Image.fromarray(marked).resize(size, Image.Resampling.NEAREST)


def prepare(corrected, review, candidate, output):
    require(review.resolve().parent == corrected.resolve(), "upstream review must belong to corrected bundle")
    require(not output.exists(), "use a new review bundle")
    white.validate_review(review)
    require(read(corrected / "candidate.json").get("correction") == "correction.json",
            "formal white correction required")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temp:
        root = Path(temp) / "bundle"
        root.mkdir()
        snapshot_candidate(corrected, root / "corrected")
        shutil.copyfile(review, root / "corrected/review.json")
        for name in PROMOTED:
            shutil.copyfile(corrected / name, root / "corrected" / name)
        white.write_json(root / "upstream.json", {"candidate_path": read(corrected / "approval.json")["candidate_path"]})
        # Reconstruct the complete original bundle from unchanged retained
        # source/failure evidence, then bind it to the formal correction replay.
        evidence = read(root / "corrected/failure_evidence.json")
        for mask in evidence["model_masks"]:
            require(Path(mask["path"]).name == mask["path"], "unsafe failure mask path")
            local(root / "corrected", mask["path"])
        white.prepare(root / "corrected/01_source.png", root / "corrected/failure_evidence.json", root / "original")
        details = verify_upstream(root)
        shutil.copyfile(candidate, root / "candidate.png")
        report = refinement_report(root)
        white.write_json(root / "rgb_diff.json", report)
        for image, name in zip(previews(root), ("candidate_8x.png", "rgb_diff_8x.png")):
            image.save(root / name)
        manifest = {"schema": "reviewed-rgb-candidate/v1", **details, "export_grid": report["export_grid"],
                    "refinement_kind": "logical_grid_rgb_only", "status": "needs_main_visual_review",
                    "artifacts": {name: white.sha256(local(root, name)) for name in sorted(inventory(root))}}
        white.write_json(root / "candidate.json", manifest)
        white.write_json(root / "review.template.json", {
            "schema": "reviewed-rgb-review/v1", "reviewer_role": "main-conversation", "decision": "pending",
            "manifest_sha256": white.sha256(root / "candidate.json"),
            "candidate_sha256": white.sha256(root / "candidate.png"),
            "rgb_diff_sha256": white.sha256(root / "rgb_diff.json"),
            "checks": dict.fromkeys(CHECKS, False), "components": {
                c["id"]: {"decision": "unresolved", "reason": ""}
                for c in read(root / "corrected/white_regions.json")}, "notes": ""})
        shutil.move(str(root), str(output))
    return output / "candidate.json"


def validate_review(review):
    root = review.resolve().parent
    manifest, decision = read(root / "candidate.json"), read(review)
    require(manifest.get("schema") == "reviewed-rgb-candidate/v1"
            and decision.get("schema") == "reviewed-rgb-review/v1", "fresh RGB refinement review schema required")
    require(decision.get("candidate_sha256") == white.sha256(root / "candidate.png"), "reviewed final hash mismatch")
    require(decision.get("rgb_diff_sha256") == white.sha256(root / "rgb_diff.json"), "reviewed RGB diff hash mismatch")
    white.validate_main_review(decision, root / "candidate.json", read(root / "corrected/white_regions.json"), checks=CHECKS)
    require(set(manifest["artifacts"]) == inventory(root), "incomplete chain hash inventory")
    for name, digest in manifest["artifacts"].items():
        require(white.sha256(local(root, name)) == digest, "reviewed chain artifact hash mismatch")
    details = verify_upstream(root)
    report = refinement_report(root)
    require(read(root / "rgb_diff.json") == report, "RGB diff replay mismatch")
    require(all(manifest[key] == value for key, value in details.items())
            and manifest["export_grid"] == report["export_grid"]
            and manifest["refinement_kind"] == "logical_grid_rgb_only", "chain metadata mismatch")
    for image, name in zip(previews(root), ("candidate_8x.png", "rgb_diff_8x.png")):
        require(np.array_equal(rgba(root / name), np.array(image)), "preview differs from candidate or RGB diff")
    return {**details, "export_grid": report["export_grid"],
            "manifest_sha256": white.sha256(root / "candidate.json"), "review_sha256": white.sha256(review),
            "candidate_sha256": white.sha256(root / "candidate.png"), "rgb_diff_sha256": white.sha256(root / "rgb_diff.json")}


def promote(review):
    validated = validate_review(review)
    root = review.resolve().parent
    require(not any((root / name).exists() for name in PROMOTED), "preserve existing promotion")
    shutil.copyfile(root / "candidate.png", root / PROMOTED[0])
    shutil.copyfile(root / "candidate_8x.png", root / PROMOTED[1])
    white.write_json(root / "approval.json", validated)
    return root / PROMOTED[0]


def convert(review, output, lumina_dir, api_url="http://127.0.0.1:8000", *, character_name, research, official_sources):
    validated = validate_review(review)
    root = review.resolve().parent
    require(read(root / "approval.json") == validated, "promotion does not match current approval")
    require(white.sha256(root / PROMOTED[0]) == validated["candidate_sha256"]
            and white.sha256(root / PROMOTED[1]) == white.sha256(root / "candidate_8x.png"), "promoted pixels or preview changed")
    require(not output.exists() and not output.resolve().is_relative_to(root), "use a new Stage 4 output directory outside the review bundle")
    require(bool(character_name.strip()) and research.is_file() and bool(official_sources), "subject and retained official research sources are required")
    lut = lumina_dir / "lut-npy预设/bambulab" / LUT_FILENAME
    lut_hash = white.sha256(lut)
    output.mkdir(parents=True)
    shutil.copytree(root, output / "reviewed_chain")
    shutil.copyfile(research, output / "00_official_character_research.md")
    for name in PROMOTED[:2]:
        shutil.copyfile(root / name, output / name)
    image = output / PROMOTED[0]
    manifest = {"schema": "reviewed-rgb-export/v1", **validated, "status": "running",
                "timestamp": datetime.now(timezone.utc).isoformat(), "character_name": character_name,
                "official_character_research_status": "completed",
                "official_character_research_path": "00_official_character_research.md",
                "official_character_research_sha256": white.sha256(research), "official_character_sources": official_sources,
                "source_path": "reviewed_chain/original/01_source.png",
                "working_grid_path": "reviewed_chain/corrected/03_working_grid.png",
                "refined_path": PROMOTED[0], "preview_path": PROMOTED[1],
                "refinement_kind": "logical_grid_rgb_only", "rgb_diff_path": "reviewed_chain/rgb_diff.json",
                "lut_path": str(lut.resolve()), "lut_sha256": lut_hash, "parameters": dict(DEFAULT_PARAMS), "variants": {}}
    path = output / "manifest.json"
    white.write_json(path, manifest)
    try:
        w, h = validated["export_grid"]["width"], validated["export_grid"]["height"]
        for cells in (2, 3):
            variant = f"{cells}x{cells}"
            require(white.sha256(image) == validated["candidate_sha256"] and white.sha256(lut) == lut_hash, "conversion input changed")
            result = convert_with_lumina_batch(image, output / f"07_lumina_batch_result_{variant}.zip",
                output / f"08_final_{variant}.3mf", lumina_dir, api_url,
                preview_path=output / f"06_lumina_2d_preview_{variant}.png",
                size_plan=build_pixel_size_plan(w, h, cells_per_logical_pixel=cells), cells_per_logical_pixel=cells)
            require(white.sha256(lut) == lut_hash and white.sha256(Path(result["lut_path"])) == lut_hash
                    and white.sha256(image) == validated["candidate_sha256"],
                    "conversion used a different LUT or changed the approved image")
            result["outputs"] = {name: {"path": name, "sha256": white.sha256(output / name)} for name in (
                f"06_lumina_2d_preview_{variant}.png", f"07_lumina_batch_result_{variant}.zip", f"08_final_{variant}.3mf")}
            manifest["variants"][variant] = result
            white.write_json(path, manifest)
        manifest["status"] = "needs_main_color_review"
    except Exception as exc:
        manifest.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        white.write_json(path, manifest)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    for name in ("corrected", "review", "candidate", "output"):
        prep.add_argument("--" + name, type=Path, required=True)
    pro = sub.add_parser("promote")
    pro.add_argument("--review", type=Path, required=True)
    conv = sub.add_parser("convert")
    conv.add_argument("--review", type=Path, required=True)
    conv.add_argument("--output", type=Path, required=True)
    conv.add_argument("--lumina-dir", type=Path, default=Path("Lumina-Layers"))
    conv.add_argument("--api-url", default="http://127.0.0.1:8000")
    conv.add_argument("--character-name", required=True)
    conv.add_argument("--research", type=Path, required=True)
    conv.add_argument("--official-source", dest="official_sources", action="append", required=True)
    args = vars(parser.parse_args())
    command = args.pop("command")
    print({"prepare": prepare, "promote": promote, "convert": convert}[command](**args))


if __name__ == "__main__":
    main()
