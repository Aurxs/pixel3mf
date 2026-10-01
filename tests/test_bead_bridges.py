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


if __name__ == "__main__":
    unittest.main()
