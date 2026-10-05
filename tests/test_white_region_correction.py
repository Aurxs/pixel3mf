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


if __name__ == "__main__":
    unittest.main()
