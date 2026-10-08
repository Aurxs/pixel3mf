#!/usr/bin/env python3
"""Source-bound correction/one-cell bridge review, promotion, and Stage 4 export."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys
import tempfile

import numpy as np
from PIL import Image
from perfect_pixel.perfect_pixel import detect_grid_scale, refine_grids, sample_center

from white_fallback import CHECKS, prepare as prepare_white, sha256, write_json
from white_region_correction import correct_regions
from refine_pixel import validate_detected_grid
from lumina_batch import LUT_FILENAME, DEFAULT_PARAMS, build_pixel_size_plan, convert_with_lumina_batch

sys.path.insert(0, str(Path(__file__).resolve().parent / "beads"))
from bridge_pixels import run as run_bridge  # noqa: E402
from ranma_reviewed_bridge import image_artifacts  # noqa: E402


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def rgba(path):
    with Image.open(path) as image:
        return np.array(image.convert("RGBA"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def local(root, name):
    path = Path(name)
    require(not path.is_absolute() and ".." not in path.parts, "unsafe artifact path")
    result = root / path
    require(result.resolve().is_relative_to(root.resolve()), "artifact escapes bundle")
    return result


def snapshot_candidate(source, target):
    manifest = read(source / "candidate.json")
    target.mkdir()
    for name, digest in manifest["artifacts"].items():
        require(Path(name).name == name, "unsafe candidate artifact")
        path = local(source, name)
        require(sha256(path) == digest, "candidate artifact hash mismatch")
        shutil.copyfile(path, target / name)
    shutil.copyfile(source / "candidate.json", target / "candidate.json")


def compare_candidate(actual, replay):
    # Replaying existing public operations verifies records as well as pixels;
    # a caller cannot bless a fabricated report merely by updating its hash.
    require(read(actual / "candidate.json") == read(replay / "candidate.json"),
            "candidate provenance or density replay mismatch")
    for name, digest in read(actual / "candidate.json")["artifacts"].items():
        require(sha256(local(actual, name)) == digest == sha256(local(replay, name)),
                "candidate artifact replay mismatch")


def sampling_edges(cutout, working):
    gx, gy = detect_grid_scale(cutout, peak_width=6, max_ratio=1.5, min_size=4.0)
    require(gx is not None and gy is not None, "cannot replay source sampling")
    xs, ys = refine_grids(cutout, round(gx), round(gy), 0.25)
    sampled = sample_center(cutout, xs, ys)
    require(np.array_equal(np.pad(sampled, ((2, 2), (2, 2), (0, 0))), working),
            "source sampling differs from original working grid")
    require(all(float(v).is_integer() for v in [*xs, *ys]), "noninteger sampling boundaries")
    return list(map(int, xs)), list(map(int, ys))


def verify_chain(root):
    original, corrected, bridge = (root / name for name in ("original", "corrected", "bridge"))
    parent = read(original / "candidate.json")
    require(parent.get("correction") is None, "expected original candidate")
    validate_detected_grid(parent["source_grid"]["width"], parent["source_grid"]["height"])
    # No model inference: prepare_white validates retained failure masks and
    # replays the unchanged source density/color sampling/cleanup gates.
    with tempfile.TemporaryDirectory() as temp:
        temp = Path(temp)
        prepare_white(original / "01_source.png", original / "failure_evidence.json", temp / "original")
        compare_candidate(original, temp / "original")
        correct_regions(original, corrected / "correction_decisions.json", temp / "corrected")
        compare_candidate(corrected, temp / "corrected")
        evidence = read(bridge / "evidence.json")
        if evidence.get("reviewed_selection") is not None:
            selection = evidence["reviewed_selection"]
            require(sha256(local(bridge, selection["source_original"])) == sha256(original / "01_source.png"),
                    "reviewed bridge original source differs from the chain")
            require(sha256(local(bridge, selection["approved_candidate"])) == sha256(root / "candidate.png"),
                    "reviewed bridge final differs from the approved candidate")
        require(not read(bridge / "input.json").get("uncompressed_crop"), "use exact tight reference; no extra transform")
        for field, expected in (("source_canvas", original / "02_white_cutout.png"),
                                ("reference_grid", corrected / "candidate.png")):
            require(sha256(local(bridge, evidence[field])) == sha256(expected),
                    "bridge source/reference is not the bound correction chain")
        xs, ys = sampling_edges(rgba(original / "02_white_cutout.png"), rgba(original / "03_working_grid.png"))
        report = read(corrected / "correction.json")
        ox, oy = report["candidate_crop_origin_in_working"]
        ox, oy = ox - 2, oy - 2
        before = rgba(corrected / "candidate.png")
        h, w = before.shape[:2]
        require(ox >= 0 and oy >= 0 and evidence["x_edges"] == xs[ox:ox + w + 1]
                and evidence["y_edges"] == ys[oy:oy + h + 1], "bridge boundaries are not the exact source crop")
        project = read(bridge / "input.json")
        colors = {c["code"]: c["rgb"] for c in project["palette"]["colors"]}
        cells = np.array(project["cells"], dtype=object)
        require(cells.shape == (h, w), "bridge input grid mismatch")
        for y, x in np.argwhere(before[:, :, 3] == 255):
            require(cells[y, x] in colors and colors[cells[y, x]] == before[y, x, :3].tolist(),
                    "bridge palette changes existing RGB")
        # The formal bridge entrypoint rechecks hashes, complete differences,
        # count, Alpha, source support, palette, and occupancy with budget one.
        run_bridge(bridge / "input.json", bridge / "evidence.json", temp / "bridge.json", max_additions=1)
        result = read(bridge / "result.json")
        require(result == read(temp / "bridge.json"), "formal bridge report replay mismatch")
        additions = result["bridge_repair"]["added_cells"]
        require(len(additions) == 1, "exactly one source-supported bridge is required")
        after = before.copy()
        cell = additions[0]
        after[cell["y"], cell["x"]] = [*colors[cell["code"]], 255]
        require(np.array_equal(rgba(root / "candidate.png"), after),
                "final RGBA differs from exact correction plus bridge")
        require(set(np.unique(after[:, :, 3])).issubset({0, 255}), "final Alpha is not binary")
    return {"source_grid": parent["source_grid"], "export_grid": {"width": w, "height": h},
            "source_sha256": parent["source_sha256"], "bridge_repair": result["bridge_repair"]}


def prepare(original, corrected, project, evidence, result, candidate, output):
    require(not output.exists(), "use a new review bundle")
    # Build privately and publish only a fully verified, pending bundle.
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temp:
        root = Path(temp) / "bundle"
        root.mkdir()
        snapshot_candidate(original, root / "original")
        snapshot_candidate(corrected, root / "corrected")
        bridge = root / "bridge"
        bridge.mkdir()
        for src, name in ((project, "input.json"), (evidence, "evidence.json"), (result, "result.json")):
            shutil.copyfile(src, bridge / name)
        ev = read(evidence)
        names = [ev[field] for field in ("source_canvas", "reference_grid")] + image_artifacts(ev)
        require(len(names) == len(set(names)), "bridge image basenames must be distinct")
        for name in names:
            require(Path(name).name == name and name not in {"input.json", "evidence.json", "result.json"},
                    "bridge evidence requires local image basenames")
            shutil.copyfile(local(evidence.parent, name), bridge / name)
        shutil.copyfile(candidate, root / "candidate.png")
        details = verify_chain(root)
        im = Image.open(root / "candidate.png").convert("RGBA")
        im.resize((im.width * 8, im.height * 8), Image.Resampling.NEAREST).save(root / "candidate_8x.png")
        artifacts = {p.relative_to(root).as_posix(): sha256(p) for p in sorted(root.rglob('*')) if p.is_file()}
        manifest = {"schema": "reviewed-bridge-candidate/v1", **details, "artifacts": artifacts}
        write_json(root / "candidate.json", manifest)
        regions = read(root / "corrected/white_regions.json")
        write_json(root / "review.template.json", {
            "schema": "reviewed-bridge-review/v1", "reviewer_role": "main-conversation", "decision": "pending",
            "manifest_sha256": sha256(root / "candidate.json"), "candidate_sha256": sha256(root / "candidate.png"),
            "checks": dict.fromkeys((*CHECKS, "correction_and_bridge_reviewed"), False),
            "components": {c["id"]: {"decision": "unresolved", "reason": ""} for c in regions}, "notes": ""})
        shutil.move(str(root), str(output))
    return output / "candidate.json"


def validate_review(review_path):
    from white_fallback import validate_main_review

    root = review_path.resolve().parent
    manifest_path = root / "candidate.json"
    manifest, review = read(manifest_path), read(review_path)
    require(manifest.get("schema") == "reviewed-bridge-candidate/v1"
            and review.get("schema") == "reviewed-bridge-review/v1", "fresh bridge review schema required")
    require(review.get("candidate_sha256") == sha256(root / "candidate.png"), "reviewed final hash mismatch")
    validate_main_review(review, manifest_path, read(root / "corrected/white_regions.json"),
                         checks=(*CHECKS, "correction_and_bridge_reviewed"))
    # Require the complete snapshot, not a caller-selected partial hash list.
    expected = {"candidate.png", "candidate_8x.png", "original/candidate.json", "corrected/candidate.json",
                "bridge/input.json", "bridge/evidence.json", "bridge/result.json"}
    for folder in ("original", "corrected"):
        expected.update(f"{folder}/{name}" for name in read(root / folder / "candidate.json")["artifacts"])
    ev = read(root / "bridge/evidence.json")
    expected.update(f"bridge/{ev[key]}" for key in ("source_canvas", "reference_grid"))
    expected.update(f"bridge/{name}" for name in image_artifacts(ev))
    require(set(manifest["artifacts"]) == expected, "incomplete chain hash inventory")
    for name, digest in manifest["artifacts"].items():
        require(sha256(local(root, name)) == digest, "reviewed chain artifact hash mismatch")
    details = verify_chain(root)
    require(all(manifest[key] == value for key, value in details.items()), "chain metadata mismatch")
    expected_preview = Image.open(root / "candidate.png").convert("RGBA")
    expected_preview = expected_preview.resize((expected_preview.width * 8, expected_preview.height * 8), Image.Resampling.NEAREST)
    require(np.array_equal(rgba(root / "candidate_8x.png"), np.array(expected_preview)), "preview differs from candidate")
    return {**details, "manifest_sha256": sha256(manifest_path), "review_sha256": sha256(review_path),
            "candidate_sha256": sha256(root / "candidate.png")}


def promote(review):
    validated = validate_review(review)
    root = review.resolve().parent
    require(not any((root / name).exists() for name in ("04_pixel_perfect.png", "05_pixel_preview_8x.png", "approval.json")),
            "preserve existing promotion")
    shutil.copyfile(root / "candidate.png", root / "04_pixel_perfect.png")
    shutil.copyfile(root / "candidate_8x.png", root / "05_pixel_preview_8x.png")
    write_json(root / "approval.json", validated)
    return root / "04_pixel_perfect.png"


def convert(review, output, lumina_dir, api_url="http://127.0.0.1:8000", *,
            character_name, research, official_sources):
    validated = validate_review(review)
    root = review.resolve().parent
    require(read(root / "approval.json") == validated, "promotion does not match current approval")
    require(sha256(root / "04_pixel_perfect.png") == validated["candidate_sha256"]
            and sha256(root / "05_pixel_preview_8x.png") == sha256(root / "candidate_8x.png"),
            "promoted pixels or preview changed")
    require(not output.exists() and not output.resolve().is_relative_to(root),
            "use a new Stage 4 output directory outside the review bundle")
    require(bool(character_name.strip()) and research.is_file() and bool(official_sources),
            "subject and retained official research sources are required")
    lut = lumina_dir / "lut-npy预设" / "bambulab" / LUT_FILENAME
    lut_hash = sha256(lut)
    output.mkdir(parents=True)
    # Keep a self-contained approval/lineage snapshot with the conversion.
    shutil.copytree(root, output / "reviewed_chain")
    shutil.copyfile(research, output / "00_official_character_research.md")
    image = output / "04_pixel_perfect.png"
    shutil.copyfile(root / "04_pixel_perfect.png", image)
    shutil.copyfile(root / "05_pixel_preview_8x.png", output / "05_pixel_preview_8x.png")
    manifest = {"schema": "reviewed-bridge-export/v1", **validated, "status": "running",
                "timestamp": datetime.now(timezone.utc).isoformat(), "character_name": character_name,
                "official_character_research_status": "completed",
                "official_character_research_path": "00_official_character_research.md",
                "official_character_sources": official_sources,
                "source_path": "reviewed_chain/original/01_source.png",
                "working_grid_path": "reviewed_chain/corrected/03_working_grid.png",
                "refined_path": "04_pixel_perfect.png", "preview_path": "05_pixel_preview_8x.png",
                "lut_path": str(lut.resolve()), "lut_sha256": lut_hash, "parameters": DEFAULT_PARAMS, "variants": {}}
    path = output / "manifest.json"
    write_json(path, manifest)
    try:
        with Image.open(image) as final_image:
            w, h = final_image.size
        for cells in (2, 3):
            variant = f"{cells}x{cells}"
            require(sha256(image) == validated["candidate_sha256"] and sha256(lut) == lut_hash, "conversion input changed")
            result = convert_with_lumina_batch(image, output / f"07_lumina_batch_result_{variant}.zip",
                output / f"08_final_{variant}.3mf", lumina_dir, api_url,
                preview_path=output / f"06_lumina_2d_preview_{variant}.png",
                size_plan=build_pixel_size_plan(w, h, cells_per_logical_pixel=cells), cells_per_logical_pixel=cells)
            require(sha256(Path(result["lut_path"])) == lut_hash and sha256(image) == validated["candidate_sha256"],
                    "conversion used a different LUT or changed the approved image")
            result["outputs"] = {name: {"path": name, "sha256": sha256(output / name)} for name in (
                f"06_lumina_2d_preview_{variant}.png", f"07_lumina_batch_result_{variant}.zip",
                f"08_final_{variant}.3mf")}
            manifest["variants"][variant] = result
            write_json(path, manifest)
        manifest["status"] = "needs_main_color_review"
    except Exception as exc:
        manifest.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        write_json(path, manifest)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    for name in ("original", "corrected", "project", "evidence", "result", "candidate", "output"):
        prep.add_argument('--' + name, type=Path, required=True)
    pro = sub.add_parser("promote")
    pro.add_argument('--review', type=Path, required=True)
    conv = sub.add_parser("convert")
    conv.add_argument('--review', type=Path, required=True)
    conv.add_argument('--output', type=Path, required=True)
    conv.add_argument('--lumina-dir', type=Path, default=Path('Lumina-Layers'))
    conv.add_argument('--api-url', default='http://127.0.0.1:8000')
    conv.add_argument('--character-name', required=True)
    conv.add_argument('--research', type=Path, required=True)
    conv.add_argument('--official-source', dest='official_sources', action='append', required=True)
    args = vars(parser.parse_args())
    command = args.pop('command')
    print({"prepare": prepare, "promote": promote, "convert": convert}[command](**args))


if __name__ == '__main__':
    main()
