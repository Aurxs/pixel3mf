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
import run_pipeline as pipeline

GRID = {"width": 45, "height": 46}


def fake_refine(source, output, preview, **kwargs):
    rgba = np.array(Image.open(source).convert("RGBA"))
    rgba = np.pad(rgba, ((2, 2), (2, 2), (0, 0)))
    Image.fromarray(rgba).save(output)
    Image.fromarray(rgba).resize((rgba.shape[1] * 8, rgba.shape[0] * 8)).save(preview)
    return {"detected_grid": GRID, "working_grid": {"width": rgba.shape[1], "height": rgba.shape[0]}}


class WhiteFallbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source.png"
        rgba = np.full((13, 13, 4), 255, dtype=np.uint8)
        rgba[2:11, 2:11] = (25, 35, 45, 255)
        rgba[4, 4] = (255, 255, 255, 255)  # eye white or unresolved hole
        rgba[7:10, 4:9] = (255, 255, 255, 255)  # white clothing
        Image.fromarray(rgba).save(self.source)
        Image.new("L", (13, 13), 0).save(self.root / "failed.png")
        self.evidence = self.root / "failure.json"
        self.data = {"schema": "white-fallback-failure/v1", "source_sha256": fallback.sha256(self.source),
                     "failure_kind": "semantic_mask_unusable", "reason": "IS-Net mask deletes the visible subject",
                     "source_accepted": True, "white_background_suitable": True,
                     "model_masks": [{"model": "isnet-anime", "path": "failed.png",
                                      "sha256": fallback.sha256(self.root / "failed.png")}]}
        fallback.write_json(self.evidence, self.data)
        self.output = self.root / "candidate"

    def prepare(self):
        with patch.object(fallback, "detect_source_grid", return_value=GRID), patch.object(
            fallback, "refine_pixel", side_effect=fake_refine
        ) as refine, patch("remove_background.run_segmentation_model") as model:
            result = fallback.prepare(self.source, self.evidence, self.output)
        model.assert_not_called()
        self.assertEqual(refine.call_args.kwargs["expected_source_grid"], GRID)
        return result

    def review(self):
        review = json.loads((self.output / "review.template.json").read_text())
        review.update(decision="approved", notes="Main conversation inspected source, regions, silhouette and gaze.")
        review["checks"] = dict.fromkeys(fallback.CHECKS, True)
        for item in review["components"].values():
            item.update(decision="foreground", reason="Confirmed eye white or white clothing, not a background gap.")
        path = self.output / "review.json"
        fallback.write_json(path, review)
        return path, review

    def test_prepare_retains_source_and_requires_review_without_exporting(self):
        manifest = json.loads(self.prepare().read_text())
        self.assertEqual(self.source.read_bytes(), (self.output / "01_source.png").read_bytes())
        self.assertEqual(manifest["source_grid"], GRID)
        self.assertEqual(manifest["detected_grid"], GRID)
        self.assertEqual(manifest["white_threshold"], 245)
        self.assertEqual(manifest["status"], "needs_main_visual_review")
        self.assertFalse((self.output / "04_pixel_perfect.png").exists())
        self.assertTrue((self.output / "outline_review.png").exists())
        self.assertTrue((self.output / "white_regions_review.png").exists())
        self.assertEqual(len(json.loads((self.output / "white_regions.json").read_text())), 2)
        with self.assertRaises(ValueError):
            fallback.promote(self.output / "review.template.json")

    def test_missing_failure_source_acceptance_or_suitability_blocks_preparation(self):
        for key, bad in [("source_sha256", "bad"), ("failure_kind", "success"),
                         ("source_accepted", False), ("white_background_suitable", False),
                         ("model_masks", []), ("reason", "")]:
            with self.subTest(key=key):
                fallback.write_json(self.evidence, {**self.data, key: bad})
                with self.assertRaises(ValueError):
                    fallback.prepare(self.source, self.evidence, self.output)
                self.assertFalse(self.output.exists())

    def test_nonwhite_or_transparent_source_is_ineligible(self):
        for color in [(244, 255, 255, 255), (255, 255, 255, 0)]:
            with self.subTest(color=color):
                Image.new("RGBA", (13, 13), color).save(self.source)
                fallback.write_json(self.evidence, {**self.data, "source_sha256": fallback.sha256(self.source)})
                with self.assertRaisesRegex(ValueError, "near-white border"):
                    fallback.prepare(self.source, self.evidence, self.output)

    def test_suspected_hole_or_missing_region_blocks_even_with_overall_approval(self):
        self.prepare()
        path, review = self.review()
        key = next(iter(review["components"]))
        for decision in ("background_hole", "unresolved"):
            with self.subTest(decision=decision):
                review["components"][key]["decision"] = decision
                fallback.write_json(path, review)
                with self.assertRaisesRegex(ValueError, "holes or unresolved"):
                    fallback.promote(path)
        review["components"].pop(key)
        fallback.write_json(path, review)
        with self.assertRaisesRegex(ValueError, "every white region"):
            fallback.promote(path)
        self.assertFalse((self.output / "04_pixel_perfect.png").exists())

    def test_changed_candidate_or_source_invalidates_review(self):
        self.prepare()
        path, _ = self.review()
        with self.assertRaisesRegex(ValueError, "source hash"):
            fallback.validate_review(path, self.root / "failed.png")
        Image.new("RGBA", (9, 9), "white").save(self.output / "candidate.png")
        with self.assertRaisesRegex(ValueError, "artifact changed"):
            fallback.promote(path)

    def test_approved_candidate_promotes_exact_bytes_and_cannot_overwrite(self):
        self.prepare()
        path, _ = self.review()
        promoted = fallback.promote(path)
        self.assertEqual(promoted.read_bytes(), (self.output / "candidate.png").read_bytes())
        with self.assertRaises(FileExistsError):
            fallback.promote(path)
        with self.assertRaises(FileExistsError):
            self.prepare()

    def test_pipeline_white_without_review_stops_before_any_model_or_conversion(self):
        with patch.object(pipeline, "convert_with_lumina_batch") as convert, patch.object(pipeline, "remove_background") as bg:
            with self.assertRaisesRegex(ValueError, "white-fallback-review"):
                pipeline.run_pipeline(self.source, background_method="white")
        convert.assert_not_called()
        bg.assert_not_called()

    def test_pipeline_checks_exact_candidate_before_conversion(self):
        self.prepare()
        path, _ = self.review()
        for changed in (False, True):
            with self.subTest(changed=changed), patch.object(pipeline, "detect_source_grid", return_value=GRID), patch.object(
                pipeline, "refine_pixel", side_effect=fake_refine
            ), patch.object(pipeline, "convert_with_lumina_batch", side_effect=RuntimeError("conversion reached")) as convert:
                original_finalize = pipeline.finalize_pixel_grid
                def finalize(*args, **kwargs):
                    result = original_finalize(*args, **kwargs)
                    if changed:
                        im = Image.open(args[1]).convert("RGBA")
                        im.putpixel((0, 0), (255, 0, 0, 255))
                        im.save(args[1])
                    return result
                with patch.object(pipeline, "finalize_pixel_grid", side_effect=finalize):
                    with self.assertRaisesRegex((ValueError, RuntimeError), "differs from|conversion reached"):
                        pipeline.run_pipeline(self.source, output_root=self.root / str(changed),
                                              background_method="white", white_fallback_review=path)
                self.assertEqual(convert.call_count, 0 if changed else 1)

    def test_non_main_or_incomplete_visual_review_cannot_promote(self):
        self.prepare()
        path, review = self.review()
        review["reviewer_role"] = "automatic"
        fallback.write_json(path, review)
        with self.assertRaisesRegex(ValueError, "main-conversation"):
            fallback.promote(path)
        review["reviewer_role"] = "main-conversation"
        review["checks"]["internal_holes_resolved"] = False
        fallback.write_json(path, review)
        with self.assertRaisesRegex(ValueError, "main-conversation"):
            fallback.promote(path)

    def test_export_rejects_changed_settings_and_source_grid(self):
        self.prepare()
        path, _ = self.review()
        for settings in ({"allow_ambiguous_mask": True}, {"square_output": True},
                         {"working_padding_cells": 0}, {"alpha_policy": "preserve"},
                         {"mask_override": "mask.png"}):
            with self.subTest(settings=settings), self.assertRaisesRegex(ValueError, "unchanged candidate"):
                pipeline.run_pipeline(self.source, background_method="white", white_fallback_review=path, **settings)
        with patch.object(pipeline, "detect_source_grid", return_value={"width": 46, "height": 46}), patch.object(
            pipeline, "remove_background"
        ) as background, patch.object(pipeline, "convert_with_lumina_batch") as convert:
            with self.assertRaisesRegex(ValueError, "source grid differs"):
                pipeline.run_pipeline(self.source, output_root=self.root / "changed-grid",
                                      background_method="white", white_fallback_review=path)
        background.assert_not_called()
        convert.assert_not_called()


if __name__ == "__main__":
    unittest.main()
