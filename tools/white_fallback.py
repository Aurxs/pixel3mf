#!/usr/bin/env python3
"""White-first or fallback candidate preparation with Agent visual review."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

import cv2
import numpy as np
from PIL import Image, ImageDraw

from cleanup_pixel import finalize_pixel_grid
from refine_pixel import detect_source_grid, refine_pixel
from remove_background import remove_background

CHECKS = ("source_accepted", "white_background_suitable", "outline_preserved",
          "eyes_and_white_subject_preserved", "internal_holes_resolved", "natural_face_and_gaze")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def prepare(source: Path, failure_evidence: Path, output: Path) -> Path:
    """Create a review-only candidate from source review or retained model failure."""
    evidence = json.loads(failure_evidence.read_text(encoding="utf-8"))
    automatic = evidence.get("schema") == "white-first-processing/v1"
    white_first = automatic or evidence.get("schema") == "white-first-source-review/v1"
    valid_route = (
        white_first and evidence.get("reviewer_role") == ("not-reviewed" if automatic else "main-conversation")
        and evidence.get("model_masks", []) == []
    ) or (
        evidence.get("schema") == "white-fallback-failure/v1"
        and evidence.get("failure_kind") == "semantic_mask_unusable"
    )
    if (not valid_route
            or evidence.get("source_sha256") != sha256(source)
            or not isinstance(evidence.get("reason"), str) or not evidence["reason"].strip()
            or (evidence.get("source_ready_for_processing") is not True
                if white_first else evidence.get("source_accepted") is not True)
            or evidence.get("white_background_suitable") is not True):
        raise ValueError("source-bound acceptance and white suitability review or model failure evidence required")
    rgba = np.asarray(Image.open(source).convert("RGBA"))
    border = np.concatenate((rgba[0], rgba[-1], rgba[:, 0], rgba[:, -1]))
    if not np.all(rgba[:, :, 3] == 255) or not np.all(border[:, :3] >= 245):
        raise ValueError("white fallback requires an opaque source with a near-white border (245)")
    masks = evidence.get("model_masks", []) if white_first else evidence.get("model_masks")
    if not isinstance(masks, list) or (not white_first and not masks):
        raise ValueError("retain at least one failed IS-Net mask as evidence")
    verified_masks = []
    for item in masks:
        if item.get("model") not in {"isnet-anime", "isnet-general-use"}:
            raise ValueError("failure evidence must identify an allowed IS-Net model")
        path = failure_evidence.parent / item["path"]
        with Image.open(path) as mask:
            mask_size = mask.size
        if sha256(path) != item.get("sha256") or mask_size != (rgba.shape[1], rgba.shape[0]):
            raise ValueError("failed model mask hash or size mismatch")
        verified_masks.append(path)
    grid = detect_source_grid(source, validate_density=not white_first)
    output.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(source, output / "01_source.png")
    copied_evidence = dict(evidence)
    copied_evidence["model_masks"] = []
    for i, (item, path) in enumerate(zip(masks, verified_masks)):
        name = f"failed_model_{i}.png"
        shutil.copyfile(path, output / name)
        copied_evidence["model_masks"].append({**item, "path": name})
    # Retain this legacy filename for correction/export replay compatibility;
    # the schema distinguishes a source review from actual model failure.
    write_json(output / "failure_evidence.json", copied_evidence)
    bg = remove_background(output / "01_source.png", output / "02_white_cutout.png",
                           method="white", semantic_mask_path=output / "02_white_mask.png")
    refined = refine_pixel(output / "02_white_cutout.png", output / "03_working_grid.png",
                           output / "03_working_preview.png", expected_source_grid=grid,
                           working_padding_cells=2, binarize_alpha=False,
                           validate_source_density=not white_first)
    cleanup = finalize_pixel_grid(
        output / "03_working_grid.png", output / "candidate.png", output / "candidate_8x.png",
        background_rgb=bg["background_rgb"], components_path=output / "semantic_components.json",
        overlay_path=output / "semantic_overlay.png")
    working = np.asarray(Image.open(output / "03_working_grid.png").convert("RGBA"))
    solid = working[:, :, 3] > 0
    difference = np.abs(working[:, :, :3].astype(np.int16) - np.array(bg["background_rgb"]))
    whites = solid & (np.max(difference, axis=2) <= bg["background_color_tolerance"])
    count, labels, stats, _ = cv2.connectedComponentsWithStats(whites.astype(np.uint8), connectivity=8)
    components = []
    base = Image.fromarray(working).resize((working.shape[1] * 12, working.shape[0] * 12), Image.Resampling.NEAREST)
    board = Image.new("RGBA", base.size, (140, 140, 140, 255))
    board.alpha_composite(base)
    overlay = board.convert("RGB")
    draw = ImageDraw.Draw(overlay)
    for label in range(1, count):
        x, y, width, height, area = map(int, stats[label])
        components.append({"id": str(label), "working_bbox": [x, y, width, height],
                           "area_cells": area, "status": "needs_visual_review"})
        draw.rectangle((x * 12, y * 12, (x + width) * 12 - 1, (y + height) * 12 - 1), outline="lime", width=2)
        draw.text((x * 12, y * 12), str(label), fill="red", stroke_width=1)
    overlay.save(output / "white_regions_review.png")
    boundary = solid & ~cv2.erode(solid.astype(np.uint8), np.ones((3, 3), dtype=np.uint8)).astype(bool)
    contour = working.copy()
    contour[boundary] = (255, 215, 0, 255)
    Image.fromarray(contour).resize(base.size, Image.Resampling.NEAREST).save(output / "outline_review.png")
    write_json(output / "white_regions.json", components)
    artifacts = {p.name: sha256(p) for p in sorted(output.iterdir()) if p.is_file()}
    manifest = {"schema": "white-fallback-candidate/v1", "status": "needs_main_visual_review",
                "source_sha256": sha256(source), "source_grid": grid,
                "detected_grid": refined["detected_grid"], "working_grid": refined["working_grid"],
                "candidate_grid": cleanup["export_grid"], "method": "white", "white_threshold": 245,
                "preparation_route": "white-first" if white_first else "semantic-fallback",
                "working_padding_cells": 2, "artifacts": artifacts,
                "warning": "Color alpha is not semantic confidence; every internal white region needs review."}
    write_json(output / "candidate.json", manifest)
    write_json(output / "review.template.json", {
        "schema": "white-fallback-review/v1", "reviewer_role": "main-conversation",
        "manifest_sha256": sha256(output / "candidate.json"), "decision": "pending",
        "checks": dict.fromkeys(CHECKS, False),
        "components": {c["id"]: {"decision": "unresolved", "reason": ""} for c in components},
        "notes": ""})
    return output / "candidate.json"


def prepare_automatic(source: Path, output: Path) -> Path:
    """Run white-first processing without asking the Agent for a preliminary review."""
    evidence = {
        "schema": "white-first-processing/v1", "reviewer_role": "not-reviewed",
        "source_sha256": sha256(source), "source_ready_for_processing": True,
        "white_background_suitable": True,
        "reason": "Automatic processing request only; decode/alpha/border checks run in prepare. No visual acceptance asserted.",
        "model_masks": [],
    }
    with tempfile.TemporaryDirectory(prefix="pixel-white-first-") as temp:
        path = Path(temp) / "processing.json"
        write_json(path, evidence)
        return prepare(source, path, output)


def validate_main_review(review: dict, manifest_path: Path, components: list, *, checks=CHECKS) -> None:
    """Shared exact-manifest main review and per-region acceptance gate."""
    if (review.get("manifest_sha256") != sha256(manifest_path)
            or review.get("reviewer_role") != "main-conversation"
            or review.get("decision") != "approved"
            or not isinstance(review.get("notes"), str) or not review["notes"].strip()
            or any(review.get("checks", {}).get(key) is not True for key in checks)):
        raise ValueError("main-conversation visual approval of this exact candidate is required")
    decisions = review.get("components", {})
    if set(decisions) != {c["id"] for c in components}:
        raise ValueError("every white region requires an individual review")
    for decision in decisions.values():
        if (decision.get("decision") != "foreground" or not isinstance(decision.get("reason"), str)
                or not decision["reason"].strip()):
            raise ValueError("suspected white holes or unresolved regions block export; do not auto-delete them")


def validate_review(review_path: Path, source: Path | None = None) -> dict:
    """Verify the recorded main review against exact, unchanged candidate artifacts."""
    root = review_path.resolve().parent
    review = json.loads(review_path.read_text(encoding="utf-8"))
    manifest_path = root / "candidate.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("schema") != "white-fallback-candidate/v1"
            or review.get("schema") != "white-fallback-review/v1"):
        raise ValueError("main-conversation visual approval of this exact candidate is required")
    artifacts = manifest.get("artifacts", {})
    required = {"01_source.png", "candidate.png", "candidate_8x.png", "03_working_grid.png",
                "white_regions.json", "white_regions_review.png", "outline_review.png", "failure_evidence.json"}
    if manifest.get("correction") is not None:
        if manifest["correction"] != "correction.json":
            raise ValueError("unknown candidate correction record")
        required.update({"correction.json", "correction_decisions.json", "candidate_mask.png",
                         "correction_diff_8x.png", "parent_candidate.json", "parent_candidate.png",
                         "parent_03_working_grid.png", "parent_white_regions.json"})
    if not required.issubset(artifacts):
        raise ValueError("candidate review artifacts are incomplete")
    for name, digest in artifacts.items():
        if Path(name).name != name or sha256(root / name) != digest:
            raise ValueError("candidate artifact changed after preparation")
    if sha256(root / "01_source.png") != manifest["source_sha256"]:
        raise ValueError("candidate source provenance mismatch")
    if source is not None and sha256(source) != manifest["source_sha256"]:
        raise ValueError("reviewed source hash mismatch")
    components = json.loads((root / "white_regions.json").read_text(encoding="utf-8"))
    validate_main_review(review, manifest_path, components)
    return {"candidate_path": str(root / "candidate.png"), "manifest_sha256": sha256(manifest_path),
            "review_sha256": sha256(review_path), "source_grid": manifest["source_grid"]}


def promote(review_path: Path) -> Path:
    """Publish Stage 3 filenames only after the main-conversation review is complete."""
    validated = validate_review(review_path)
    root = review_path.resolve().parent
    for name in ("04_pixel_perfect.png", "05_pixel_preview_8x.png", "approval.json"):
        if (root / name).exists():
            raise FileExistsError("approved artifacts already exist; preserve the prior review")
    shutil.copyfile(validated["candidate_path"], root / "04_pixel_perfect.png")
    shutil.copyfile(root / "candidate_8x.png", root / "05_pixel_preview_8x.png")
    write_json(root / "approval.json", validated)
    return root / "04_pixel_perfect.png"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("prepare")
    create.add_argument("--source", required=True, type=Path)
    evidence_args = create.add_mutually_exclusive_group(required=False)
    evidence_args.add_argument("--failure-evidence", dest="failure_evidence", type=Path)
    evidence_args.add_argument("--source-review", dest="failure_evidence", type=Path,
                               help="Source-bound Agent review for white-first preparation; no model required")
    create.add_argument("--output", required=True, type=Path)
    approve = sub.add_parser("promote")
    approve.add_argument("--review", required=True, type=Path)
    correct = sub.add_parser("correct")
    correct.add_argument("--candidate", required=True, type=Path)
    correct.add_argument("--decisions", required=True, type=Path)
    correct.add_argument("--output", required=True, type=Path)
    template = sub.add_parser("correction-template")
    template.add_argument("--candidate", required=True, type=Path)
    template.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.command in {"correct", "correction-template"}:
        from white_region_correction import correct_regions, correction_template

        print(correction_template(args.candidate, args.output) if args.command == "correction-template"
              else correct_regions(args.candidate, args.decisions, args.output))
    else:
        print((prepare(args.source, args.failure_evidence, args.output) if args.failure_evidence
               else prepare_automatic(args.source, args.output)) if args.command == "prepare"
              else promote(args.review))


if __name__ == "__main__":
    main()
