from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import white_fallback as fallback
from white_region_correction import correct_regions


class RegionCorrectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.parent = self.root / "parent"
        self.output = self.root / "corrected"
        # Synthetic, non-character geometry with the eight reviewed region sizes.
        # Coordinates are on the padded 57x57 working grid; no private image fixture.
        self.cells = {
            "1": [(26, 7), (27, 7), (28, 7)],
            "2": [(11, 27), (11, 28), (11, 29)],
            "3": [(29, 28), (30, 28), (29, 29), (30, 29)],
            "4": [(19, 32), (20, 32), (19, 33)],
            "5": [(49, 32), (49, 33)],
            "6": [(12, 43), (13, 43), (13, 44), (14, 44),
                  (14, 45), (15, 45), (15, 46), (16, 47)],
            "7": [(35, 45)], "8": [(29, 48)],
        }
        rgba = np.full((53, 53, 4), 255, dtype=np.uint8)
        rgba[1:52, 1:51] = (20, 30, 40, 255)
        for cells in self.cells.values():
            for x, y in cells:
                rgba[y - 2, x - 2] = (254, 253, 255, 255)
        source = self.root / "source.png"
        Image.fromarray(rgba).save(source)
        mask = self.root / "failed.png"
        Image.new("L", (53, 53), 0).save(mask)
        evidence = self.root / "failure.json"
        fallback.write_json(evidence, {
            "schema": "white-fallback-failure/v1", "source_sha256": fallback.sha256(source),
            "failure_kind": "semantic_mask_unusable", "reason": "Synthetic missing subject",
            "source_accepted": True, "white_background_suitable": True,
            "model_masks": [{"model": "isnet-anime", "path": "failed.png", "sha256": fallback.sha256(mask)}]})
        grid = {"width": 53, "height": 53}

        def refine(src, output, preview, **kwargs):
            data = np.array(Image.open(src))
            # Model a known logical exterior; raster near-white bridge guards
            # are covered elsewhere and need not be emulated by 1px fixtures.
            data[:, :, 3] = 0
            data[1:52, 1:51, 3] = 255
            data = np.pad(data, ((2, 2), (2, 2), (0, 0)))
            Image.fromarray(data).save(output)
            Image.fromarray(data).resize((456, 456), Image.Resampling.NEAREST).save(preview)
            return {"detected_grid": grid, "working_grid": {"width": 57, "height": 57}}

        with patch.object(fallback, "detect_source_grid", return_value=grid), patch.object(
            fallback, "refine_pixel", side_effect=refine
        ):
            fallback.prepare(source, evidence, self.parent)
        self.decisions = {
            "schema": "white-fallback-correction/v1", "reviewer_role": "main-conversation",
            "manifest_sha256": fallback.sha256(self.parent / "candidate.json"),
            "candidate_sha256": fallback.sha256(self.parent / "candidate.png"),
            "components": {key: {"decision": "background" if key in {"1", "2", "5", "6"} else "preserve",
                                 "reason": "Confirmed background gap" if key in {"1", "2", "5", "6"}
                                 else "Protect eye whites and unchanged clothing"} for key in self.cells}}
        self.path = self.root / "decisions.json"

    def correct(self):
        fallback.write_json(self.path, self.decisions)
        return correct_regions(self.parent, self.path, self.output)

    def test_exact_16_alpha_changes_rgb_eyes_and_all_other_alpha_preserved(self):
        before_files = {p.name: p.read_bytes() for p in self.parent.iterdir()}
        # Old approval must not be carried into the new candidate.
        fallback.write_json(self.parent / "review.json", {"decision": "approved"})
        fallback.write_json(self.parent / "approval.json", {"prior": True})
        manifest = json.loads(self.correct().read_text())
        original = np.array(Image.open(self.parent / "candidate.png"))
        final = np.array(Image.open(self.output / "candidate.png"))
        self.assertEqual(final.shape, (51, 50, 4))
        self.assertTrue(np.array_equal(original[:, :, :3], final[:, :, :3]))
        changed = np.any(original != final, axis=2)
        self.assertEqual(int(changed.sum()), 16)
        report = json.loads((self.output / "correction.json").read_text())
        x0, y0 = report["candidate_crop_origin_in_working"]
        expected = np.zeros(changed.shape, dtype=bool)
        for key in ("1", "2", "5", "6"):
            for x, y in self.cells[key]:
                expected[y - y0, x - x0] = True
        self.assertTrue(np.array_equal(changed, expected))
        self.assertTrue(np.all(final[expected, 3] == 0))
        self.assertTrue(np.array_equal(original[~expected], final[~expected]))
        for key in ("3", "4", "7", "8"):
            for x, y in self.cells[key]:
                self.assertEqual(final[y - y0, x - x0, 3], 255)
        self.assertTrue(np.array_equal(np.array(Image.open(self.output / "candidate_mask.png")), final[:, :, 3]))
        self.assertEqual(set(manifest["source_grid"]), {"width", "height"})
        for name, content in before_files.items():
            self.assertEqual((self.parent / name).read_bytes(), content)
        for name in ("review.json", "approval.json", "04_pixel_perfect.png", "05_pixel_preview_8x.png"):
            self.assertFalse((self.output / name).exists())
        for name, digest in manifest["artifacts"].items():
            self.assertEqual(fallback.sha256(self.output / name), digest)
        review = json.loads((self.output / "review.template.json").read_text())
        self.assertEqual(review["decision"], "pending")
        self.assertFalse(any(review["checks"].values()))
        self.assertEqual(set(review["components"]), {"3", "4", "7", "8"})
        with self.assertRaises(ValueError):
            fallback.promote(self.output / "review.template.json")

    def test_hash_id_role_and_nonexplicit_decisions_rejected_before_writing(self):
        baseline = json.loads(json.dumps(self.decisions))
        variants = []
        for key in ("manifest_sha256", "candidate_sha256", "reviewer_role"):
            variants.append({**baseline, key: "incorrect"})
        for mapping in ({"all": {"decision": "background", "reason": "all white"}},
                        {k: v for k, v in baseline["components"].items() if k != "3"},
                        {**baseline["components"], "99": {"decision": "background", "reason": "unknown"}}):
            variants.append({**baseline, "components": mapping})
        for bad in ("unresolved", "foreground", "background_hole"):
            variants.append({**baseline, "components": {**baseline["components"], "1": {"decision": bad, "reason": "x"}}})
        variants.append({**baseline, "components": {**baseline["components"], "1": {"decision": "background", "reason": " "}}})
        for v in variants:
            with self.subTest(v=v):
                self.decisions = v
                with self.assertRaises(ValueError):
                    self.correct()
                self.assertFalse(self.output.exists())

    def test_blanket_white_deletion_and_noop_rejected(self):
        for decision in ("background", "preserve"):
            for item in self.decisions["components"].values():
                item["decision"] = decision
            with self.assertRaisesRegex(ValueError, "proper subset"):
                self.correct()
            self.assertFalse(self.output.exists())

    def test_tampered_candidate_or_region_mapping_rejected(self):
        path = self.parent / "candidate.png"
        path.write_bytes(path.read_bytes() + b"changed")
        with self.assertRaisesRegex(ValueError, "artifact changed"):
            self.correct()
        self.assertFalse(self.output.exists())

    def test_rebound_wrong_geometry_still_rejected(self):
        path = self.parent / "white_regions.json"
        components = json.loads(path.read_text())
        components[0]["area_cells"] += 1
        fallback.write_json(path, components)
        manifest_path = self.parent / "candidate.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["artifacts"][path.name] = fallback.sha256(path)
        fallback.write_json(manifest_path, manifest)
        self.decisions["manifest_sha256"] = fallback.sha256(manifest_path)
        with self.assertRaisesRegex(ValueError, "geometry"):
            self.correct()

    def test_old_review_cannot_promote_new_candidate_fresh_review_can(self):
        old_review = json.loads((self.parent / "review.template.json").read_text())
        old_review.update(decision="approved", notes="Old review must not transfer")
        old_review["checks"] = dict.fromkeys(fallback.CHECKS, True)
        self.correct()
        path = self.output / "review.json"
        fallback.write_json(path, old_review)
        with self.assertRaisesRegex(ValueError, "main-conversation"):
            fallback.promote(path)
        new = json.loads((self.output / "review.template.json").read_text())
        new.update(decision="approved", notes="Synthetic new visual review of corrections and retained whites")
        new["checks"] = dict.fromkeys(fallback.CHECKS, True)
        for item in new["components"].values():
            item.update(decision="foreground", reason="Confirmed retained foreground")
        fallback.write_json(path, new)
        promoted = fallback.promote(path)
        self.assertEqual(promoted.read_bytes(), (self.output / "candidate.png").read_bytes())
        with self.assertRaises(FileExistsError):
            self.correct()


class RegionCorrectionCropTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def prepare(self, rgba, selected):
        """Prepare synthetic logical cells through the existing fallback gate."""
        source = self.root / "source.png"
        opaque = rgba.copy()
        opaque[:, :, 3] = 255
        Image.fromarray(opaque).save(source)
        failed = self.root / "failed.png"
        Image.new("L", (rgba.shape[1], rgba.shape[0]), 0).save(failed)
        evidence = self.root / "failure.json"
        fallback.write_json(evidence, {
            "schema": "white-fallback-failure/v1", "source_sha256": fallback.sha256(source),
            "failure_kind": "semantic_mask_unusable", "reason": "Synthetic missing subject",
            "source_accepted": True, "white_background_suitable": True,
            "model_masks": [{"model": "isnet-anime", "path": failed.name,
                             "sha256": fallback.sha256(failed)}]})
        grid = {"width": rgba.shape[1], "height": rgba.shape[0]}

        def refine(src, output, preview, **kwargs):
            data = np.pad(rgba, ((2, 2), (2, 2), (0, 0)))
            Image.fromarray(data).save(output)
            Image.fromarray(data).save(preview)
            return {"detected_grid": grid, "working_grid": {
                "width": data.shape[1], "height": data.shape[0]}}

        parent = self.root / "parent"
        with patch.object(fallback, "detect_source_grid", return_value=grid), patch.object(
            fallback, "refine_pixel", side_effect=refine
        ):
            fallback.prepare(source, evidence, parent)
        regions = json.loads((parent / "white_regions.json").read_text())
        decisions = self.root / "decisions.json"
        fallback.write_json(decisions, {
            "schema": "white-fallback-correction/v1", "reviewer_role": "main-conversation",
            "manifest_sha256": fallback.sha256(parent / "candidate.json"),
            "candidate_sha256": fallback.sha256(parent / "candidate.png"),
            "components": {r["id"]: {
                "decision": "background" if r["id"] in selected else "preserve",
                "reason": "Synthetic reviewed edge" if r["id"] in selected else "Retained white detail",
            } for r in regions}})
        return parent, decisions, self.root / "corrected"

    def test_reviewed_five_cells_allow_top_crop_without_changing_source_grid(self):
        rgba = np.full((68, 70, 4), (255, 255, 255, 0), dtype=np.uint8)
        rgba[2:67, 3:66] = (20, 30, 40, 255)
        # Three reviewed regions: two top tips and a two-cell interior region.
        for x, y in [(27, 1), (28, 1), (57, 1), (24, 7), (25, 7), (35, 30), (36, 30)]:
            rgba[y, x] = (254, 253, 255, 255)
        parent, decisions, output = self.prepare(rgba, {"1", "2", "3"})
        before_files = {p.name: p.read_bytes() for p in parent.iterdir()}
        original = np.array(Image.open(parent / "candidate.png"))
        manifest = json.loads(correct_regions(parent, decisions, output).read_text())
        report = json.loads((output / "correction.json").read_text())
        final = np.array(Image.open(output / "candidate.png"))
        self.assertEqual(original.shape, (66, 63, 4))
        self.assertEqual(final.shape, (65, 63, 4))
        self.assertEqual(report["removed_cells"], 5)
        self.assertEqual(report["removed_candidate_xy"], [[24, 0], [25, 0], [54, 0], [21, 6], [22, 6]])
        expected = original.copy()
        for x, y in report["removed_candidate_xy"]:
            expected[y, x, 3] = 0
        self.assertTrue(np.array_equal(final, expected[1:]))
        self.assertEqual(report["removed_coordinates_frame"], "parent_candidate")
        self.assertEqual(report["crop_box_in_parent_candidate"], [0, 1, 63, 66])
        self.assertEqual(report["parent_candidate_crop_origin_in_working"], [5, 3])
        self.assertEqual(report["candidate_crop_origin_in_working"], [5, 4])
        self.assertEqual(manifest["source_grid"], {"width": 70, "height": 68})
        self.assertEqual(manifest["working_grid"], {"width": 74, "height": 72})
        self.assertEqual(manifest["candidate_grid"], {"width": 63, "height": 65})
        before_working = np.array(Image.open(parent / "03_working_grid.png"))
        after_working = np.array(Image.open(output / "03_working_grid.png"))
        expected_working = before_working.copy()
        for x, y in report["removed_candidate_xy"]:
            expected_working[y + 3, x + 5, 3] = 0
        self.assertTrue(np.array_equal(after_working, expected_working))
        self.assertTrue(np.array_equal(np.array(Image.open(output / "candidate_mask.png")), final[:, :, 3]))
        with Image.open(output / "candidate_8x.png") as preview:
            self.assertTrue(np.array_equal(np.array(preview), np.repeat(np.repeat(final, 8, axis=0), 8, axis=1)))
        with Image.open(output / "correction_diff_8x.png") as diff:
            self.assertEqual(diff.size, (63 * 8, 66 * 8))
        remaining = json.loads((output / "white_regions.json").read_text())
        self.assertEqual([r["id"] for r in remaining], ["4"])
        self.assertEqual(remaining[0]["working_bbox"], [37, 32, 2, 1])
        for name, data in before_files.items():
            self.assertEqual((parent / name).read_bytes(), data)
        for name, digest in manifest["artifacts"].items():
            self.assertEqual(fallback.sha256(output / name), digest)
        with self.assertRaises(ValueError):
            fallback.promote(output / "review.template.json")
        old_review = json.loads((parent / "review.template.json").read_text())
        old_review.update(decision="approved", checks=dict.fromkeys(fallback.CHECKS, True), notes="Old approval")
        fallback.write_json(output / "review.json", old_review)
        with self.assertRaisesRegex(ValueError, "main-conversation"):
            fallback.promote(output / "review.json")
        fresh = json.loads((output / "review.template.json").read_text())
        fresh.update(decision="approved", checks=dict.fromkeys(fallback.CHECKS, True), notes="Synthetic fresh crop review")
        for item in fresh["components"].values():
            item.update(decision="foreground", reason="Retained synthetic white detail")
        fallback.write_json(output / "review.json", fresh)
        self.assertEqual(fallback.promote(output / "review.json").read_bytes(), (output / "candidate.png").read_bytes())

    def test_each_outer_edge_can_crop_without_removing_retained_pixels(self):
        for edge in ("top", "bottom", "left", "right"):
            with self.subTest(edge=edge), tempfile.TemporaryDirectory() as folder:
                self.root = Path(folder)
                rgba = np.full((53, 53, 4), (255, 255, 255, 0), dtype=np.uint8)
                rgba[10:40, 10:40] = (20, 30, 40, 255)
                selection = {"top": (10, slice(10, 40)), "bottom": (39, slice(10, 40)),
                             "left": (slice(10, 40), 10), "right": (slice(10, 40), 39)}[edge]
                rgba[selection] = (254, 253, 255, 255)
                rgba[24, 24:26] = (254, 253, 255, 255)
                selected = {"2"} if edge == "bottom" else {"1"}
                parent, decisions, output = self.prepare(rgba, selected)
                correct_regions(parent, decisions, output)
                report = json.loads((output / "correction.json").read_text())
                boxes = {"top": [0, 1, 30, 30], "bottom": [0, 0, 30, 29],
                         "left": [1, 0, 30, 30], "right": [0, 0, 29, 30]}
                self.assertEqual(report["crop_box_in_parent_candidate"], boxes[edge])
                l, t, r, b = boxes[edge]
                original = np.array(Image.open(parent / "candidate.png"))
                self.assertTrue(np.array_equal(np.array(Image.open(output / "candidate.png")), original[t:b, l:r]))

    def test_all_transparent_result_rejected_before_output(self):
        rgba = np.full((53, 53, 4), (255, 255, 255, 0), dtype=np.uint8)
        rgba[10:12, 10:12] = (254, 253, 255, 255)
        # A second white component is retained in working evidence but already
        # removed by preparation's isolated-cell cleanup. It is not authorized
        # for deletion and must not make an empty corrected candidate valid.
        rgba[20, 20] = (254, 253, 255, 255)
        parent, decisions, output = self.prepare(rgba, {"1"})
        with self.assertRaisesRegex(ValueError, "retain foreground"):
            correct_regions(parent, decisions, output)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
