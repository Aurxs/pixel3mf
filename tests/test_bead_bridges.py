import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/beads"))
from bridge_pixels import repair_bridges, run, verified_inputs  # noqa: E402


class BridgeTests(unittest.TestCase):
    def source(self, connected=True):
        a = np.zeros((20, 20, 4), dtype=np.uint8)
        a[:10, :10] = [100, 140, 200, 255]
        a[10:, 10:] = [100, 140, 200, 255]
        if connected:
            a[7:10, 10:16] = [100, 140, 200, 255]
        return a

    def test_minimal_source_supported_bridge_preserves_old_cells_and_palette(self):
        rows = [["B", None], [None, "B"]]
        result, report = repair_bridges(
            rows,
            {"colors": [{"code": "B", "rgb": [100, 140, 200]}]},
            self.source(),
            [0, 10, 20],
            [0, 10, 20],
        )
        self.assertEqual(result, [["B", "B"], [None, "B"]])
        self.assertEqual(rows, [["B", None], [None, "B"]])
        self.assertEqual(report["components_before"], 2)
        self.assertEqual(report["components_after"], 1)
        self.assertEqual(len(report["added_cells"]), 1)

    def test_real_gap_and_low_alpha_noise_do_not_connect(self):
        rows = [["B", None], [None, "B"]]
        source = self.source(False)
        source[7:10, 10:16] = [0, 0, 0, 15]
        result, report = repair_bridges(
            rows,
            {"colors": [{"code": "B", "rgb": [100, 140, 200]}]},
            source,
            [0, 10, 20],
            [0, 10, 20],
        )
        self.assertEqual(result, rows)
        self.assertEqual(report["added_cells"], [])

    def test_already_connected_and_separated_decorations_unchanged(self):
        palette = {"colors": [{"code": "B", "rgb": [100, 140, 200]}]}
        for rows in [[["B", "B"], [None, "B"]], [["B", None, None], [None, None, "B"]]]:
            w = len(rows[0])
            source = np.full((20, w * 10, 4), 255, dtype=np.uint8)
            result, report = repair_bridges(
                rows, palette, source, list(range(0, w * 10 + 1, 10)), [0, 10, 20]
            )
            self.assertEqual(result, rows)
            self.assertEqual(report["added_cells"], [])

    def test_ambiguous_two_supported_corners_are_not_arbitrarily_chosen(self):
        source = self.source()
        source[10:16, 7:10] = [100, 140, 200, 255]
        rows = [["B", None], [None, "B"]]
        result, report = repair_bridges(
            rows,
            {"colors": [{"code": "B", "rgb": [100, 140, 200]}]},
            source,
            [0, 10, 20],
            [0, 10, 20],
        )
        self.assertEqual(result, rows)
        self.assertFalse(report["added_cells"])

    def test_replay_rejects_unproven_transform_and_bad_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            source = self.source(False)
            reference = source[np.array([5, 15])[:, None], np.array([5, 15])[None, :]]
            for n, a in [("source", source), ("reference", reference)]:
                Image.fromarray(a).save(p / (n + ".png"))
            evidence = {
                "schema": "pixel-sampling-evidence/v1",
                "alpha_threshold": 128,
                "source_canvas": "source.png",
                "reference_grid": "reference.png",
                "x_edges": [0, 10, 20],
                "y_edges": [0, 10, 20],
                "reference_differences": [],
            }
            for k in ["source_canvas", "reference_grid"]:
                evidence[k + "_sha256"] = hashlib.sha256(
                    (p / evidence[k]).read_bytes()
                ).hexdigest()
            ep = p / "evidence.json"
            ep.write_text(json.dumps(evidence))
            project = {"cells": [["B", None], [None, "B"]]}
            verified_inputs(project, ep)
            project.update(
                schema="pixel-art-to-beads/v1",
                title="test",
                palette={"colors": [{"code": "B", "rgb": [100, 140, 200]}]},
                statistics={"total_beads": 999},
            )
            pp = p / "project.json"
            pp.write_text(json.dumps(project))
            run(pp, ep, p / "result.json")
            saved = json.loads((p / "result.json").read_text())
            self.assertEqual(saved["cells"], project["cells"])
            self.assertNotIn("statistics", saved)
            with self.assertRaisesRegex(ValueError, "new output"):
                run(pp, ep, p / "result.json")

            with self.assertRaisesRegex(ValueError, "occupancy"):
                verified_inputs({"cells": [["B", "B"], [None, "B"]]}, ep)
            evidence["source_canvas_sha256"] = "bad"
            ep.write_text(json.dumps(evidence))
            with self.assertRaisesRegex(ValueError, "hash"):
                verified_inputs(project, ep)


class ReviewedAlphaDeletionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = BridgeTests().source(False)
        # A reviewed white sample in an otherwise empty corner. It does not
        # provide a source-connected bridge, so run() must preserve the grid.
        self.source[5, 15] = [246, 249, 253, 255]
        self.reference = self.source[np.array([5, 15])[:, None], np.array([5, 15])[None, :]].copy()
        self.reference[0, 1, 3] = 0
        self.project = {
            "schema": "pixel-art-to-beads/v1",
            "palette": {"colors": [{"code": "B", "rgb": [100, 140, 200]}]},
            "cells": [["B", None], [None, "B"]],
        }

    def evidence(self):
        """Bind the exact synthetic files and record their actual sample difference."""
        source_path, reference_path = self.root / "source.png", self.root / "reference.png"
        Image.fromarray(self.source).save(source_path)
        Image.fromarray(self.reference).save(reference_path)
        return {
            "schema": "pixel-sampling-evidence/v1", "alpha_threshold": 128,
            "source_canvas": source_path.name, "reference_grid": reference_path.name,
            "source_canvas_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
            "reference_grid_sha256": hashlib.sha256(reference_path.read_bytes()).hexdigest(),
            "x_edges": [0, 10, 20], "y_edges": [0, 10, 20],
            "reference_differences": [{"x": 1, "y": 0,
                                       "sampled": self.source[5, 15].tolist(),
                                       "reference": self.reference[0, 1].tolist()}],
            "manifest_cleanup": {"removed_edge_white_pixels": 1},
        }

    def verify(self, evidence):
        path = self.root / "evidence.json"
        path.write_text(json.dumps(evidence))
        return verified_inputs(self.project, path)

    def test_preserved_hidden_rgb_and_legacy_zero_rgb_are_accepted(self):
        for rgb in ([246, 249, 253], [0, 0, 0]):
            with self.subTest(rgb=rgb):
                self.reference[0, 1, :3] = rgb
                evidence = self.evidence()
                source, xs, ys = self.verify(evidence)
                self.assertTrue(np.array_equal(source, self.source))
                self.assertEqual(xs, [0, 10, 20])
                self.assertEqual(ys, [0, 10, 20])

    def test_formal_run_accepts_alpha_only_record_without_mutating_inputs(self):
        evidence = self.evidence()
        self.verify(evidence)
        project = self.root / "project.json"
        project.write_text(json.dumps(self.project))
        original = {p.name: p.read_bytes() for p in self.root.iterdir()}
        output = self.root / "result.json"
        report = run(project, self.root / "evidence.json", output, max_additions=1)
        self.assertEqual(report["added_cells"], [])
        self.assertEqual(json.loads(output.read_text())["cells"], self.project["cells"])
        for name, content in original.items():
            self.assertEqual((self.root / name).read_bytes(), content)

    def test_rebound_rgb_changes_are_rejected_even_when_recorded(self):
        for rgb in ([245, 249, 253], [246, 249, 252], [0, 249, 253], [255, 255, 255]):
            with self.subTest(rgb=rgb):
                self.reference[0, 1, :3] = rgb
                with self.assertRaisesRegex(ValueError, "Unexplained"):
                    self.verify(self.evidence())

    def test_nonwhite_and_nonforeground_source_deletions_are_rejected(self):
        for sampled in ([239, 249, 253, 255], [246, 249, 253, 127]):
            for preserve in (True, False):
                with self.subTest(sampled=sampled, preserve=preserve):
                    self.source[5, 15] = sampled
                    self.reference[0, 1] = [*(sampled[:3] if preserve else [0, 0, 0]), 0]
                    with self.assertRaisesRegex(ValueError, "Unexplained"):
                        self.verify(self.evidence())

    def test_deleted_reference_alpha_must_be_exactly_zero(self):
        for alpha in (1, 127, 128, 254):
            with self.subTest(alpha=alpha):
                self.reference[0, 1, 3] = alpha
                with self.assertRaisesRegex(ValueError, "Unexplained"):
                    self.verify(self.evidence())

    def test_missing_inaccurate_or_extra_difference_records_are_rejected(self):
        for records in (None, [], [{"x": 0, "y": 0, "sampled": [246, 249, 253, 255],
                                   "reference": [246, 249, 253, 0]}]):
            with self.subTest(records=records):
                evidence = self.evidence()
                if records is None:
                    evidence.pop("reference_differences")
                else:
                    evidence["reference_differences"] = records
                with self.assertRaisesRegex(ValueError, "recorded reference differences"):
                    self.verify(evidence)
        evidence = self.evidence()
        evidence["reference_differences"] *= 2
        with self.assertRaisesRegex(ValueError, "recorded reference differences"):
            self.verify(evidence)

    def test_missing_or_incorrect_deletion_count_is_rejected(self):
        for count in (None, 0, 2):
            with self.subTest(count=count):
                evidence = self.evidence()
                if count is None:
                    evidence.pop("manifest_cleanup")
                else:
                    evidence["manifest_cleanup"]["removed_edge_white_pixels"] = count
                with self.assertRaisesRegex(ValueError, "Unexplained"):
                    self.verify(evidence)

    def test_both_hashes_and_negative_boundary_guard_remain_required(self):
        for field in ("source_canvas_sha256", "reference_grid_sha256"):
            with self.subTest(field=field):
                evidence = self.evidence()
                evidence[field] = "tampered"
                with self.assertRaisesRegex(ValueError, "hash"):
                    self.verify(evidence)
        evidence = self.evidence()
        evidence["y_edges"][0] = -8
        with self.assertRaisesRegex(ValueError, "Invalid evidence boundaries"):
            self.verify(evidence)


if __name__ == "__main__":
    unittest.main()
