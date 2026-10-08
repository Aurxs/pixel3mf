"""Synthetic hash-bound fixtures; production approval pins are never weakened."""
from collections import deque
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/beads"))
import bridge_pixels as bridge
import ranma_reviewed_bridge as reviewed


class RanmaReviewedBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.xs, self.ys = list(range(0, 581, 10)), list(range(0, 641, 10))
        original = np.full((640, 580, 4), 255, dtype=np.uint8)
        source = original.copy()
        source[:, :, 3] = 0
        for box, rgb in [((490, 290, 500, 300), [0, 0, 0]),
                         ((480, 300, 490, 310), [1, 0, 1]),
                         ((490, 300, 493, 310), [0, 0, 0])]:
            x0, y0, x1, y1 = box
            original[y0:y1, x0:x1, :3] = rgb
            source[y0:y1, x0:x1] = [*rgb, 255]
        for x, y in reviewed.EXCLUDED_XY:
            source[y*10:(y+1)*10, x*10:(x+1)*10, 3] = 255
        reference = source[5::10, 5::10].copy()
        for x, y in reviewed.EXCLUDED_XY:
            reference[y, x, 3] = 0
        approved = reference.copy()
        approved[30, 49] = reviewed.RGBA
        for name, array in [("original.png", original), ("source.png", source),
                            ("reference.png", reference), ("approved.png", approved)]:
            Image.fromarray(array).save(self.root / name)
        dark = original[:, :, :3].max(axis=2) <= 16
        start, target = (495, 295), (485, 305)
        queue, previous = deque([start]), {start: None}
        while queue:
            x, y = queue.popleft()
            if (x, y) == target:
                break
            for point in [(x-1, y), (x+1, y), (x, y-1), (x, y+1)]:
                xx, yy = point
                if 480 <= xx < 500 and 290 <= yy < 310 and dark[yy, xx] and point not in previous:
                    previous[point] = (x, y)
                    queue.append(point)
        path, point = [], target
        while point is not None:
            path.append(list(point))
            point = previous[point]
        path.reverse()
        pins = {key + "_sha256": self.sha(self.root / name) for key, name in
                [("source_original", "original.png"), ("source_canvas", "source.png"),
                 ("reference_grid", "reference.png"), ("approved_candidate", "approved.png")]}
        pins.update(path_sha256=reviewed.digest_json(path),
                    edges_sha256=reviewed.digest_json({"x_edges": self.xs, "y_edges": self.ys}))
        # Patch only the immutable artifact pins for this synthetic fixture.
        # Coordinates, exclusions, budget, path/coverage and replay guards all run.
        self.pin_patch = patch.object(reviewed, "APPROVED", pins)
        self.pin_patch.start()
        self.addCleanup(self.pin_patch.stop)
        self.project = {"schema": "pixel-art-to-beads/v1",
                        "palette": {"colors": [{"code": "BLACK", "rgb": [0, 0, 0]},
                                                {"code": "TIP", "rgb": [1, 0, 1]}]},
                        "cells": [[None] * 58 for _ in range(64)]}
        self.project["cells"][29][49] = "BLACK"
        self.project["cells"][30][48] = "TIP"
        sampled = source[5::10, 5::10]
        differences = [{"x": int(x), "y": int(y), "sampled": sampled[y, x].tolist(),
                        "reference": reference[y, x].tolist()}
                       for y, x in np.argwhere(np.any(sampled != reference, axis=2))]
        self.evidence = {"schema": "pixel-sampling-evidence/v1", "alpha_threshold": 128,
                         "source_canvas": "source.png", "reference_grid": "reference.png",
                         "source_canvas_sha256": pins["source_canvas_sha256"],
                         "reference_grid_sha256": pins["reference_grid_sha256"],
                         "x_edges": self.xs, "y_edges": self.ys,
                         "reference_differences": differences,
                         "manifest_cleanup": {"removed_edge_white_pixels": len(differences)},
                         "reviewed_selection": {"schema": reviewed.SCHEMA,
                             "reviewer_role": "main-conversation", "source_original": "original.png",
                             "source_original_sha256": pins["source_original_sha256"],
                             "approved_candidate": "approved.png",
                             "approved_candidate_sha256": pins["approved_candidate_sha256"],
                             "allowed_candidate_xy": reviewed.ALLOWED_XY.copy(),
                             "excluded_candidate_xy": deepcopy(reviewed.EXCLUDED_XY),
                             "bridge_rgba": reviewed.RGBA.copy(), "path_source_xy": path,
                             "path_sha256": pins["path_sha256"]}}

    @staticmethod
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def execute(self, *, evidence=None, project=None, budget=1):
        (self.root / "input.json").write_text(json.dumps(project or self.project))
        (self.root / "evidence.json").write_text(json.dumps(evidence or self.evidence))
        return bridge.run(self.root / "input.json", self.root / "evidence.json",
                          self.root / "result.json", max_additions=budget)

    def test_selects_real_bridge_excludes_white_and_has_no_other_edits(self):
        inputs = {p.name: p.read_bytes() for p in self.root.glob("*.png")}
        report = self.execute()
        addition = report["added_cells"]
        self.assertEqual([(c["x"], c["y"], c["code"]) for c in addition], [(49, 30, "BLACK")])
        self.assertGreaterEqual(addition[0]["source_coverage"], 0.15)
        self.assertEqual((report["components_before"], report["components_after"]), (2, 1))
        output = json.loads((self.root / "result.json").read_text())
        expected = deepcopy(self.project["cells"])
        expected[30][49] = "BLACK"
        self.assertEqual(output["cells"], expected)
        self.assertEqual(output["palette"], self.project["palette"])
        for x, y in reviewed.EXCLUDED_XY:
            self.assertIsNone(output["cells"][y][x])
        for name, content in inputs.items():
            self.assertEqual((self.root / name).read_bytes(), content)

    def test_wrong_or_background_position_and_missing_exclusions_are_rejected(self):
        for key, value in [("allowed_candidate_xy", [48, 29]),
                           ("allowed_candidate_xy", [47, 30]),
                           ("excluded_candidate_xy", []), ("bridge_rgba", [1, 0, 1, 255])]:
            with self.subTest(key=key, value=value):
                evidence = deepcopy(self.evidence)
                evidence["reviewed_selection"][key] = value
                with self.assertRaisesRegex(ValueError, "only the reviewed Ranma"):
                    self.execute(evidence=evidence)
                self.assertFalse((self.root / "result.json").exists())

    def test_hashes_cannot_be_rebound_to_changed_source_reference_or_approved_image(self):
        for name, location, key in [("original.png", "reviewed_selection", "source_original_sha256"),
                                    ("source.png", None, "source_canvas_sha256"),
                                    ("reference.png", None, "reference_grid_sha256"),
                                    ("approved.png", "reviewed_selection", "approved_candidate_sha256")]:
            with self.subTest(name=name):
                file = self.root / name
                original = file.read_bytes()
                file.write_bytes(original + b"tampered")
                evidence = deepcopy(self.evidence)
                target = evidence[location] if location else evidence
                target[key] = self.sha(file)
                try:
                    with self.assertRaisesRegex(ValueError, "hash mismatch"):
                        self.execute(evidence=evidence)
                    self.assertFalse((self.root / "result.json").exists())
                finally:
                    file.write_bytes(original)

    def test_altered_path_and_boundaries_are_rejected(self):
        evidence = deepcopy(self.evidence)
        evidence["reviewed_selection"]["path_source_xy"][1][0] += 1
        evidence["reviewed_selection"]["path_sha256"] = reviewed.digest_json(
            evidence["reviewed_selection"]["path_source_xy"])
        with self.assertRaisesRegex(ValueError, "path hash mismatch"):
            self.execute(evidence=evidence)
        evidence = deepcopy(self.evidence)
        evidence["x_edges"][0] += 1
        with self.assertRaisesRegex(ValueError, "sampling boundaries changed"):
            self.execute(evidence=evidence)

    def test_budget_and_project_recolor_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "budget one"):
            self.execute(budget=2)
        project = deepcopy(self.project)
        project["palette"]["colors"][0]["rgb"] = [0, 1, 0]
        with self.assertRaisesRegex(ValueError, "recolors existing"):
            self.execute(project=project)

    def test_existing_coverage_and_local_connectivity_gate_cannot_be_waived(self):
        original = bridge.repair_bridges
        def insufficient(*args, **kwargs):
            source = args[2].copy()
            source[300:310, 490:500, 3] = 0
            modified = (*args[:2], source, *args[3:])
            return original(*modified, **kwargs)
        with patch.object(bridge, "repair_bridges", side_effect=insufficient):
            with self.assertRaisesRegex(ValueError, "exactly its supported cell"):
                self.execute()
        self.assertFalse((self.root / "result.json").exists())

    def test_repair_side_edit_is_rejected_before_any_result_is_written(self):
        original = bridge.repair_bridges
        def side_edit(*args, **kwargs):
            cells, report = original(*args, **kwargs)
            cells[20][20] = "BLACK"
            return cells, report
        with patch.object(bridge, "repair_bridges", side_effect=side_edit):
            with self.assertRaisesRegex(ValueError, "changed other cells"):
                self.execute()
        self.assertFalse((self.root / "result.json").exists())


if __name__ == "__main__":
    unittest.main()
