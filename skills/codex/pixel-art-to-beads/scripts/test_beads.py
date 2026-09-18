"""Small behavioral checks; run with python -m unittest discover -s scripts -p test_beads.py."""
import copy
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import numpy as np
from PIL import Image

from bead_palette import load_palette, map_colors
from bead_pattern import DEFAULT_PALETTE, create_project, mirror, statistics, validate_project
from prepare_source import prepare


class BeadTests(unittest.TestCase):
    def setUp(self):
        self.palette = {"id": "test", "colors": [
            {"code": "W", "rgb": [255, 255, 255]},
            {"code": "K", "rgb": [0, 0, 0]},
            {"code": "R", "rgb": [255, 0, 0]},
        ]}
        self.rgba = np.array([[[255, 255, 255, 255], [0, 0, 0, 0], [255, 0, 0, 255]],
                              [[0, 0, 0, 255], [255, 255, 255, 255], [0, 0, 0, 0]]], dtype=np.uint8)

    def test_white_blank_mirror_counts(self):
        rows, _ = map_colors(self.rgba, self.palette)
        self.assertEqual(rows, [["W", None, "R"], ["K", "W", None]])
        self.assertEqual(mirror(rows), [["R", None, "W"], [None, "W", "K"]])
        self.assertEqual(mirror(mirror(rows)), rows)
        self.assertEqual(statistics(rows), {"W": 2, "K": 1, "R": 1})
        self.assertEqual(statistics(rows), statistics(mirror(rows)))

    def test_cap_inventory_and_palette_validation(self):
        rows, _ = map_colors(self.rgba, self.palette, max_colors=2, allowed=["W", "K"], locked=["K"])
        self.assertLessEqual(len(statistics(rows)), 2)
        self.assertLessEqual(set(statistics(rows)), {"W", "K"})
        with self.assertRaises(ValueError):
            map_colors(self.rgba, self.palette, allowed=["UNKNOWN"])
        palette = copy.deepcopy(self.palette)
        palette["colors"].append(palette["colors"][0])
        with self.assertRaises(ValueError):
            map_colors(self.rgba, palette)
        self.assertEqual(len(load_palette(DEFAULT_PALETTE)["colors"]), 221)

    def test_source_canvas_alpha_and_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/"source.png"
            Image.fromarray(self.rgba).save(source)
            project = create_project(source, self.palette, "test", canvas=(5, 4))
            validate_project(project)
            self.assertEqual(statistics(project["cells"]), {"W": 2, "K": 1, "R": 1})
            with self.assertRaises(ValueError):
                create_project(source, self.palette, "test", canvas=(2, 2))
            metadata = prepare(source, Path(directory)/"prepared", logical=True)
            self.assertTrue(metadata["logical_input"])
            with Image.open(Path(directory)/"prepared/04_pixel_perfect.png") as prepared:
                self.assertEqual(prepared.size, (3, 2))
            with self.assertRaises(ValueError):
                prepare(source, Path(directory)/"prepared", logical=True)
            rgba = self.rgba.copy()
            rgba[0, 0, 3] = 128
            Image.fromarray(rgba).save(source)
            with self.assertRaises(ValueError):
                create_project(source, self.palette, "test")

    def test_background_removal_uses_semantic_worker_and_preserves_white(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/"opaque.png"
            rgba = np.full((7, 7, 4), 255, dtype=np.uint8)
            rgba[2:5, 2:5, :3] = 0
            rgba[3, 3, :3] = 255
            Image.fromarray(rgba).save(source)

            def segmentation(source_path, mask_path, **kwargs):
                mask = np.zeros((7, 7), dtype=np.uint8)
                mask[2:5, 2:5] = 255
                Image.fromarray(mask).save(mask_path)
                return {"test_worker": True}

            with patch("remove_background.run_segmentation_model", side_effect=segmentation) as worker:
                prepare(source, Path(directory)/"prepared", logical=True, remove_bg=True)
                self.assertEqual(worker.call_count, 1)
            with Image.open(Path(directory)/"prepared/04_pixel_perfect.png") as result:
                cells = np.asarray(result)
                self.assertEqual(cells.shape[:2], (3, 3))
                self.assertTrue(np.array_equal(cells[1, 1], [255, 255, 255, 255]))
            rgba[:, :, 3] = 0
            Image.fromarray(rgba).save(source)
            with self.assertRaises(ValueError):
                create_project(source, self.palette, "test")


if __name__ == "__main__":
    unittest.main()
