"""Synthetic approvals are test-only; production prepare always emits pending."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import white_fallback as white
from white_region_correction import correct_regions
import reviewed_rgb_refinement_export as export


class ReviewedRGBRefinementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        grid = {"width": 45, "height": 45}
        detector = patch.object(white, "detect_source_grid", return_value=grid)
        detector.start()
        self.addCleanup(detector.stop)

        def refine(source, output, preview, **kwargs):
            data = np.pad(export.rgba(source)[5::10, 5::10], ((2, 2), (2, 2), (0, 0)))
            Image.fromarray(data).save(output)
            Image.fromarray(data).resize((392, 392), Image.Resampling.NEAREST).save(preview)
            return {"detected_grid": grid, "working_grid": {"width": 49, "height": 49}}

        refiner = patch.object(white, "refine_pixel", side_effect=refine)
        refiner.start()
        self.addCleanup(refiner.stop)
        data = np.full((450, 450, 4), 255, dtype=np.uint8)
        data[30:420, 30:420] = [90, 130, 170, 255]
        data[100:110, 100:110] = 255
        data[200:210, 200:210] = 255
        Image.fromarray(data).save(self.root / "source.png")
        Image.new("L", (450, 450), 0).save(self.root / "failed.png")
        white.write_json(self.root / "failure.json", {
            "schema": "white-fallback-failure/v1", "source_sha256": white.sha256(self.root / "source.png"),
            "failure_kind": "semantic_mask_unusable", "reason": "Synthetic test mask missing subject",
            "source_accepted": True, "white_background_suitable": True,
            "model_masks": [{"model": "isnet-anime", "path": "failed.png", "sha256": white.sha256(self.root / "failed.png")}]})
        self.original, self.corrected = self.root / "original", self.root / "corrected"
        white.prepare(self.root / "source.png", self.root / "failure.json", self.original)
        regions = export.read(self.original / "white_regions.json")
        self.assertEqual(len(regions), 2)
        white.write_json(self.root / "decisions.json", {
            "schema": "white-fallback-correction/v1", "reviewer_role": "main-conversation",
            "manifest_sha256": white.sha256(self.original / "candidate.json"),
            "candidate_sha256": white.sha256(self.original / "candidate.png"),
            "components": {c["id"]: {"decision": "background" if i == 0 else "preserve",
                                      "reason": "Synthetic reviewed white patch or hole"} for i, c in enumerate(regions)}})
        correct_regions(self.original, self.root / "decisions.json", self.corrected)
        self.upstream_review = self.corrected / "review.json"
        upstream = export.read(self.corrected / "review.template.json")
        self.approve_synthetic(upstream, self.upstream_review)
        white.promote(self.upstream_review)
        self.master = self.root / "master.png"
        data = export.rgba(self.corrected / "candidate.png")
        data[0, 0, :3] = [80, 120, 160]
        # Palette reduction may change white RGB within the established tolerance.
        data[17, 17, :3] = [251, 250, 252]
        Image.fromarray(data).save(self.master)
        self.bundle = self.root / "bundle"
        self.prepare()
        self.review = self.bundle / "review.json"
        self.approve_synthetic(export.read(self.bundle / "review.template.json"), self.review)
        self.context = {"character_name": "Synthetic", "research": self.root / "research.md",
                        "official_sources": ["https://example.org/synthetic-test"]}
        self.context["research"].write_text("Synthetic research fixture")

    @staticmethod
    def approve_synthetic(data, path):
        data.update(decision="approved", notes="Synthetic unit-test approval only")
        data["checks"] = dict.fromkeys(data["checks"], True)
        data["components"] = {key: {"decision": "foreground", "reason": "Synthetic preserved white"}
                              for key in data["components"]}
        white.write_json(path, data)

    def prepare(self, output=None):
        return export.prepare(self.corrected, self.upstream_review, self.master, output or self.bundle)

    def rebind(self, *names):
        manifest = export.read(self.bundle / "candidate.json")
        for name in names:
            manifest["artifacts"][name] = white.sha256(self.bundle / name)
        white.write_json(self.bundle / "candidate.json", manifest)
        review = export.read(self.review)
        review.update(manifest_sha256=white.sha256(self.bundle / "candidate.json"),
                      candidate_sha256=white.sha256(self.bundle / "candidate.png"),
                      rgb_diff_sha256=white.sha256(self.bundle / "rgb_diff.json"))
        white.write_json(self.review, review)

    def test_pending_package_exact_diff_and_lossless_promotion(self):
        template = export.read(self.bundle / "review.template.json")
        self.assertEqual(template["decision"], "pending")
        self.assertFalse(any(template["checks"].values()))
        with self.assertRaisesRegex(ValueError, "visual approval"):
            export.promote(self.bundle / "review.template.json")
        report = export.read(self.bundle / "rgb_diff.json")
        self.assertEqual(report["changed_cells"], 2)
        self.assertEqual(report["rgb_changes"], [
            {"x": 0, "y": 0, "before_rgb": [90, 130, 170], "after_rgb": [80, 120, 160]},
            {"x": 17, "y": 17, "before_rgb": [255, 255, 255], "after_rgb": [251, 250, 252]}])
        export.promote(self.review)
        self.assertEqual((self.bundle / "04_pixel_perfect.png").read_bytes(), self.master.read_bytes())
        self.assertEqual(export.rgba(self.master).shape, export.rgba(self.bundle / "04_pixel_perfect.png").shape)
        self.assertTrue(np.array_equal(export.rgba(self.master)[:, :, 3], export.rgba(self.corrected / "candidate.png")[:, :, 3]))
        with self.assertRaisesRegex(ValueError, "preserve existing"):
            export.promote(self.review)

    def test_exact_review_hash_role_checks_and_components_required(self):
        baseline = export.read(self.review)
        for change in ({"decision": "pending"}, {"schema": "white-fallback-review/v1"},
                       {"reviewer_role": "worker"}, {"candidate_sha256": "0" * 64},
                       {"manifest_sha256": "0" * 64}, {"rgb_diff_sha256": "0" * 64},
                       {"checks": {}}, {"components": {}}, {"notes": ""}):
            with self.subTest(change=change):
                white.write_json(self.review, {**baseline, **change})
                with self.assertRaises(ValueError):
                    export.promote(self.review)
                self.assertFalse((self.bundle / "approval.json").exists())

    def test_grid_alpha_hidden_rgb_palette_and_protected_white_guards_even_when_rebound(self):
        baseline = export.rgba(self.bundle / "candidate.png")
        cases = []
        cases.append((baseline[:-1], "grid dimensions"))
        cases.append((np.repeat(np.repeat(baseline, 2, axis=0), 2, axis=1), "grid dimensions"))
        for value, message in ((0, "Alpha changed"), (128, "binary")):
            data = baseline.copy(); data[0, 0, 3] = value
            cases.append((data, message))
        data = baseline.copy(); data[7, 7, 3] = 255
        cases.append((data, "Alpha changed"))
        data = baseline.copy(); data[7, 7, 0] ^= 1
        cases.append((data, "transparent RGB"))
        data = baseline.copy()
        for x in range(19): data[0, x, :3] = [x, 50, 100]
        cases.append((data, "18 visible"))
        data = baseline.copy(); data[17, 17, :3] = [10, 20, 30]
        cases.append((data, "no longer white"))
        for data, message in cases:
            with self.subTest(message=message):
                Image.fromarray(data).save(self.bundle / "candidate.png")
                self.rebind("candidate.png")
                with self.assertRaisesRegex(ValueError, message): export.promote(self.review)

    def test_four_connectivity_rejects_diagonal_only_island(self):
        before_path = self.bundle / "corrected/04_pixel_perfect.png"
        before = export.rgba(before_path)
        before[:2, :2, 3] = 0
        before[0, 0, 3] = 255
        before[2, 0, 3] = 0
        before[0, 2, 3] = 0
        Image.fromarray(before).save(before_path)
        Image.fromarray(before).save(self.bundle / "candidate.png")
        with self.assertRaisesRegex(ValueError, "4-connected"): export.refinement_report(self.bundle)

    def test_artifact_tampering_and_incomplete_inventory_rejected(self):
        for name in ("original/01_source.png", "corrected/review.json", "corrected/approval.json",
                     "corrected/04_pixel_perfect.png", "corrected/correction.json", "candidate_8x.png", "rgb_diff.json"):
            path = self.bundle / name
            old = path.read_bytes(); path.write_bytes(old + b" ")
            try:
                with self.assertRaises(ValueError): export.promote(self.review)
            finally: path.write_bytes(old)
        manifest = export.read(self.bundle / "candidate.json")
        manifest["artifacts"].pop("original/01_source.png")
        white.write_json(self.bundle / "candidate.json", manifest)
        self.rebind()
        with self.assertRaisesRegex(ValueError, "inventory"): export.promote(self.review)
        with self.assertRaisesRegex(ValueError, "unsafe"): export.local(self.bundle, "../outside")

    def test_rebound_fabricated_diff_rejected_by_replay(self):
        path = self.bundle / "rgb_diff.json"
        data = export.read(path); data["rgb_changes"] = data["rgb_changes"][:1]
        white.write_json(path, data); self.rebind("rgb_diff.json")
        with self.assertRaisesRegex(ValueError, "diff replay"): export.promote(self.review)

    def test_rebound_preview_rejected(self):
        path = self.bundle / "rgb_diff_8x.png"
        data = export.rgba(path); data[0, 0, 0] ^= 1
        Image.fromarray(data).save(path); self.rebind("rgb_diff_8x.png")
        with self.assertRaisesRegex(ValueError, "preview differs"): export.promote(self.review)

    def test_rebound_broken_correction_chain_rejected(self):
        path = self.bundle / "corrected/correction.json"
        data = export.read(path); data["removed_cells"] += 1
        white.write_json(path, data)
        path = self.bundle / "corrected/candidate.json"
        data = export.read(path); data["artifacts"]["correction.json"] = white.sha256(path.parent / "correction.json")
        white.write_json(path, data)
        self.rebind("corrected/correction.json", "corrected/candidate.json")
        with self.assertRaisesRegex(ValueError, "replay mismatch"): export.promote(self.review)

    def test_rebound_source_density_and_upstream_promotion_rejected(self):
        path = self.bundle / "original/candidate.json"
        baseline = path.read_bytes()
        for width in (44, 81):
            data = json.loads(baseline); data["source_grid"]["width"] = width
            white.write_json(path, data); self.rebind("original/candidate.json")
            with self.assertRaisesRegex(ValueError, "overly"): export.promote(self.review)
        path.write_bytes(baseline); self.rebind("original/candidate.json")
        path = self.bundle / "corrected/approval.json"
        data = export.read(path); data["review_sha256"] = "0" * 64
        white.write_json(path, data); self.rebind("corrected/approval.json")
        with self.assertRaisesRegex(ValueError, "upstream promotion"): export.promote(self.review)

    def test_prepare_requires_formal_approved_promoted_upstream_and_is_atomic(self):
        upstream = export.read(self.upstream_review)
        white.write_json(self.upstream_review, {**upstream, "decision": "pending"})
        with self.assertRaisesRegex(ValueError, "visual approval"): self.prepare(self.root / "pending-bundle")
        self.assertFalse((self.root / "pending-bundle").exists())
        white.write_json(self.upstream_review, upstream)
        path = self.corrected / "approval.json"
        path.unlink()
        out = self.root / "bad-bundle"
        with self.assertRaises(FileNotFoundError): self.prepare(out)
        self.assertFalse(out.exists())

    def test_corrected_candidate_cannot_be_disguised_as_an_uncorrected_source(self):
        manifest = export.read(self.original / "candidate.json")
        manifest["artifacts"] = {name: white.sha256(self.corrected / name)
                                 for name in manifest["artifacts"]}
        white.write_json(self.corrected / "candidate.json", manifest)
        for name in export.PROMOTED:
            (self.corrected / name).unlink()
        review = export.read(self.corrected / "review.template.json")
        review["manifest_sha256"] = white.sha256(self.corrected / "candidate.json")
        self.approve_synthetic(review, self.upstream_review)
        white.promote(self.upstream_review)
        output = self.root / "disguised-original"
        with self.assertRaisesRegex(ValueError, "replay mismatch"):
            self.prepare(output)
        self.assertFalse(output.exists())

    def test_historical_promotion_path_is_retained_as_evidence_and_never_opened(self):
        approval = export.read(self.corrected / "approval.json")
        historical = str(self.root / "missing-historical-machine" / "candidate.png")
        self.assertFalse(Path(historical).exists())
        approval["candidate_path"] = historical
        white.write_json(self.corrected / "approval.json", approval)
        output = self.root / "portable-bundle"
        self.prepare(output)
        self.assertEqual(export.read(output / "upstream.json")["candidate_path"], historical)
        self.assertEqual(export.read(output / "review.template.json")["decision"], "pending")
        self.assertEqual((output / "candidate.png").read_bytes(), self.master.read_bytes())
        self.assertFalse(Path(historical).exists())

    def test_protected_white_tolerance_is_inclusive_12_and_never_13(self):
        for delta in (12, 13):
            with self.subTest(delta=delta):
                data = export.rgba(self.master)
                data[17, 17, :3] = [255 - delta, 255, 255]
                Image.fromarray(data).save(self.master)
                output = self.root / f"white-boundary-{delta}"
                if delta == 12:
                    self.prepare(output)
                    report = export.read(output / "rgb_diff.json")
                    self.assertEqual(report["white_tolerance"], 12)
                    self.assertEqual(report["protected_white_regions"][0]["cells_xy"], [[17, 17]])
                else:
                    with self.assertRaisesRegex(ValueError, "no longer white"):
                        self.prepare(output)
                    self.assertFalse(output.exists())

    def test_exactly_18_visible_colors_pass_and_19_fail_without_changing_alpha(self):
        baseline = export.rgba(self.corrected / "candidate.png")
        for count in (18, 19):
            with self.subTest(count=count):
                data = baseline.copy()
                for x in range(count - 2):
                    data[0, x, :3] = [x + 1, 50, 100]
                Image.fromarray(data).save(self.master)
                output = self.root / f"palette-{count}"
                if count == 18:
                    self.prepare(output)
                    self.assertEqual(export.read(output / "rgb_diff.json")["visible_colors"], 18)
                    self.assertTrue(np.array_equal(export.rgba(output / "candidate.png")[:, :, 3],
                                                   baseline[:, :, 3]))
                else:
                    with self.assertRaisesRegex(ValueError, "18 visible"):
                        self.prepare(output)
                    self.assertFalse(output.exists())

    def test_convert_requires_fresh_approval_and_promotion_before_calling_lumina(self):
        with patch.object(export, "convert_with_lumina_batch") as call:
            with self.assertRaises(ValueError):
                export.convert(self.bundle / "review.template.json", self.root / "out", self.root / "lumina", **self.context)
            with self.assertRaises(FileNotFoundError):
                export.convert(self.review, self.root / "out", self.root / "lumina", **self.context)
            call.assert_not_called()
        self.assertFalse((self.root / "out").exists())

    def run_conversion(self, callback):
        export.promote(self.review)
        lut = self.root / "lumina/lut-npy预设/bambulab" / export.LUT_FILENAME
        lut.parent.mkdir(parents=True); lut.write_bytes(b"Synthetic LUT")
        with patch.object(export, "convert_with_lumina_batch", side_effect=lambda *a, **k: callback(lut, *a, **k)):
            return export.convert(self.review, self.root / "out", self.root / "lumina", **self.context)

    def test_both_variants_use_exact_master_settings_and_retain_evidence(self):
        seen = []
        def convert(lut, image, archive, final, lumina, api, **kwargs):
            seen.append((white.sha256(image), kwargs))
            archive.write_bytes(b"Raw archive"); final.write_bytes(b"Synthetic 3MF")
            Image.new("RGB", (2, 2)).save(kwargs["preview_path"])
            return {"lut_path": str(lut), "parameters": dict(export.DEFAULT_PARAMS)}
        manifest = export.read(self.run_conversion(convert))
        self.assertEqual([x[1]["cells_per_logical_pixel"] for x in seen], [2, 3])
        self.assertTrue(all(x[0] == white.sha256(self.master) for x in seen))
        self.assertEqual(manifest["parameters"], export.DEFAULT_PARAMS)
        self.assertEqual(manifest["status"], "needs_main_color_review")
        for name in ("original/01_source.png", "corrected/approval.json", "rgb_diff.json", "review.json", "approval.json"):
            self.assertTrue((self.root / "out/reviewed_chain" / name).is_file())

    def test_changed_lut_or_master_during_conversion_fails_and_records_failure(self):
        def convert(lut, image, archive, final, lumina, api, **kwargs):
            lut.write_bytes(b"changed LUT")
            return {"lut_path": str(lut)}
        with self.assertRaisesRegex(ValueError, "different LUT"): self.run_conversion(convert)
        self.assertEqual(export.read(self.root / "out/manifest.json")["status"], "failed")

    def test_master_changed_during_conversion_fails_and_records_failure(self):
        def convert(lut, image, archive, final, lumina, api, **kwargs):
            with image.open("ab") as stream: stream.write(b"changed")
            return {"lut_path": str(lut)}
        with self.assertRaisesRegex(ValueError, "changed the approved image"): self.run_conversion(convert)
        self.assertEqual(export.read(self.root / "out/manifest.json")["status"], "failed")

    def test_changed_promoted_master_fails_before_lumina(self):
        export.promote(self.review)
        with (self.bundle / "04_pixel_perfect.png").open("ab") as stream: stream.write(b"changed")
        with patch.object(export, "convert_with_lumina_batch") as call:
            with self.assertRaisesRegex(ValueError, "promoted pixels"):
                export.convert(self.review, self.root / "out", self.root / "lumina", **self.context)
            call.assert_not_called()


class PromotedWhiteCandidateRGBTests(unittest.TestCase):
    """Four synthetic foreground whites; no region correction is performed."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        grid = {"width": 45, "height": 45}
        detector = patch.object(white, "detect_source_grid", return_value=grid)
        detector.start()
        self.addCleanup(detector.stop)

        def refine(source, output, preview, **kwargs):
            data = np.pad(export.rgba(source)[5::10, 5::10], ((2, 2), (2, 2), (0, 0)))
            Image.fromarray(data).save(output)
            Image.fromarray(data).resize((392, 392), Image.Resampling.NEAREST).save(preview)
            return {"detected_grid": grid, "working_grid": {"width": 49, "height": 49}}

        refiner = patch.object(white, "refine_pixel", side_effect=refine)
        refiner.start()
        self.addCleanup(refiner.stop)
        source = np.full((450, 450, 4), 255, dtype=np.uint8)
        source[30:420, 30:420] = [90, 130, 170, 255]
        source[30:60, 30:60] = 255  # Exterior notch retains transparent hidden RGB.
        self.white_cells = {(7, 7), (17, 17), (27, 22), (9, 27)}
        for x, y in self.white_cells:
            source[(y + 3)*10:(y + 4)*10, (x + 3)*10:(x + 4)*10] = 255
        Image.fromarray(source).save(self.root / "source.png")
        Image.new("L", (450, 450), 0).save(self.root / "failed.png")
        white.write_json(self.root / "failure.json", {
            "schema": "white-fallback-failure/v1", "source_sha256": white.sha256(self.root / "source.png"),
            "failure_kind": "semantic_mask_unusable", "reason": "Synthetic test failure only",
            "source_accepted": True, "white_background_suitable": True,
            "model_masks": [{"model": "isnet-anime", "path": "failed.png",
                             "sha256": white.sha256(self.root / "failed.png")}]})
        self.upstream = self.root / "uncorrected"
        white.prepare(self.root / "source.png", self.root / "failure.json", self.upstream)
        self.assertEqual(len(export.read(self.upstream / "white_regions.json")), 4)
        self.review = self.upstream / "review.json"
        ReviewedRGBRefinementTests.approve_synthetic(export.read(self.upstream / "review.template.json"), self.review)
        white.promote(self.review)
        self.master = self.root / "master.png"
        pixels = export.rgba(self.upstream / "candidate.png")
        pixels[4, 4, :3] = [80, 120, 160]
        Image.fromarray(pixels).save(self.master)
        self.output = self.root / "rgb-review"

    def prepare(self):
        return export.prepare(self.upstream, self.review, self.master, self.output)

    def test_uncorrected_promoted_source_binds_all_four_whites_and_requires_fresh_review(self):
        before = {p.name: p.read_bytes() for p in self.upstream.iterdir()}
        manifest = export.read(self.prepare())
        self.assertEqual(manifest["upstream_kind"], "promoted_white_candidate")
        self.assertEqual({p.name: p.read_bytes() for p in self.upstream.iterdir()}, before)
        self.assertEqual((self.output / "candidate.png").read_bytes(), self.master.read_bytes())
        self.assertNotIn("correction", export.read(self.output / "corrected/candidate.json"))
        self.assertFalse((self.output / "corrected/correction.json").exists())
        report = export.read(self.output / "rgb_diff.json")
        cells = {tuple(p) for region in report["protected_white_regions"] for p in region["cells_xy"]}
        self.assertEqual(cells, self.white_cells)
        pending = export.read(self.output / "review.template.json")
        self.assertEqual(len(pending["components"]), 4)
        self.assertEqual(pending["decision"], "pending")
        self.assertFalse(any(pending["checks"].values()))
        self.assertIn("upstream_white_candidate_and_promotion_reviewed", pending["checks"])
        self.assertNotIn("upstream_correction_and_promotion_reviewed", pending["checks"])
        with self.assertRaisesRegex(ValueError, "visual approval"):
            export.promote(self.output / "review.template.json")
        fresh = self.output / "review.json"
        ReviewedRGBRefinementTests.approve_synthetic(pending, fresh)
        valid = export.read(fresh)
        wrong = json.loads(json.dumps(valid))
        wrong["checks"].pop("upstream_white_candidate_and_promotion_reviewed")
        wrong["checks"]["upstream_correction_and_promotion_reviewed"] = True
        white.write_json(fresh, wrong)
        with self.assertRaisesRegex(ValueError, "visual approval"):
            export.promote(fresh)
        self.assertFalse((self.output / "approval.json").exists())
        white.write_json(fresh, valid)
        promoted = export.promote(fresh)
        self.assertEqual(promoted.read_bytes(), self.master.read_bytes())

    def test_each_original_white_region_still_needs_hash_bound_main_foreground_review(self):
        baseline = export.read(self.review)
        for key in baseline["components"]:
            for decision in ("unresolved", "background", None):
                with self.subTest(region=key, decision=decision):
                    review = json.loads(json.dumps(baseline))
                    if decision is None:
                        review["components"].pop(key)
                    else:
                        review["components"][key]["decision"] = decision
                    white.write_json(self.review, review)
                    with self.assertRaises(ValueError):
                        self.prepare()
                    self.assertFalse(self.output.exists())
        for change in ({"decision": "pending"}, {"reviewer_role": "worker"},
                       {"manifest_sha256": "wrong"}, {"checks": {}}, {"notes": ""}):
            with self.subTest(change=change):
                white.write_json(self.review, {**baseline, **change})
                with self.assertRaises(ValueError):
                    self.prepare()
                self.assertFalse(self.output.exists())

    def test_original_promotion_must_exist_and_match_review_and_pixels(self):
        for name in export.PROMOTED:
            path = self.upstream / name
            original = path.read_bytes()
            path.unlink()
            try:
                with self.assertRaises((ValueError, FileNotFoundError)):
                    self.prepare()
                self.assertFalse(self.output.exists())
            finally:
                path.write_bytes(original)
        approval = export.read(self.upstream / "approval.json")
        white.write_json(self.upstream / "approval.json", {**approval, "review_sha256": "wrong"})
        with self.assertRaisesRegex(ValueError, "upstream promotion"):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_uncorrected_source_preserves_alpha_hidden_rgb_and_every_white_region(self):
        original = export.rgba(self.master)
        variants = []
        for x, y in self.white_cells:
            pixels = original.copy()
            pixels[y, x, :3] = [242, 255, 255]
            variants.append((pixels, "no longer white"))
        for x, y, value in ((4, 4, 0), (4, 4, 128), (0, 0, 255)):
            pixels = original.copy()
            pixels[y, x, 3] = value
            variants.append((pixels, "Alpha"))
        pixels = original.copy()
        pixels[0, 0, 0] ^= 1
        variants.append((pixels, "transparent RGB"))
        for pixels, message in variants:
            with self.subTest(message=message):
                Image.fromarray(pixels).save(self.master)
                with self.assertRaisesRegex(ValueError, message):
                    self.prepare()
                self.assertFalse(self.output.exists())

    def test_uncorrected_conversion_keeps_fresh_review_gate_and_both_existing_size_variants(self):
        self.prepare()
        pending = self.output / "review.template.json"
        fresh = self.output / "review.json"
        research = self.root / "research.md"
        research.write_text("Synthetic test research, not an actual character review")
        context = {"character_name": "Synthetic", "research": research,
                   "official_sources": ["https://example.test/synthetic"]}
        stage4, lumina = self.root / "stage4", self.root / "lumina"
        with patch.object(export, "convert_with_lumina_batch") as converter:
            with self.assertRaises(ValueError):
                export.convert(pending, stage4, lumina, **context)
            ReviewedRGBRefinementTests.approve_synthetic(export.read(pending), fresh)
            with self.assertRaises(FileNotFoundError):
                export.convert(fresh, stage4, lumina, **context)
            converter.assert_not_called()
        self.assertFalse(stage4.exists())
        export.promote(fresh)
        lut = lumina / "lut-npy预设/bambulab" / export.LUT_FILENAME
        lut.parent.mkdir(parents=True)
        lut.write_bytes(b"Synthetic LUT")

        def convert(image, archive, final, lumina, api_url, **kwargs):
            self.assertEqual(white.sha256(image), white.sha256(self.master))
            archive.write_bytes(b"Synthetic archive")
            final.write_bytes(b"Synthetic 3MF")
            Image.new("RGB", (2, 2)).save(kwargs["preview_path"])
            return {"lut_path": str(lut), "parameters": dict(export.DEFAULT_PARAMS)}

        with patch.object(export, "convert_with_lumina_batch", side_effect=convert) as converter:
            report = export.read(export.convert(fresh, stage4, lumina, **context))
        self.assertEqual(converter.call_count, 2)
        self.assertEqual(set(report["variants"]), {"2x2", "3x3"})
        self.assertEqual(report["upstream_kind"], "promoted_white_candidate")
        self.assertEqual(report["parameters"]["quantize_colors"], 256)
        self.assertEqual(report["status"], "needs_main_color_review")


if __name__ == "__main__":
    unittest.main()
