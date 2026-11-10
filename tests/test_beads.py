"""Focused checks for the project bead tools."""
import copy
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/beads"))

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

    def test_sharma_reference_values_and_broadcast(self):
        from bead_palette import delta_e_2000

        # Sharma, Wu and Dalal (2005), published CIEDE2000 reference pairs:
        # https://hajim.rochester.edu/ece/sites/gsharma/ciede2000/dataNprograms/ciede2000testdata.txt
        cases = [([50, 2.6772, -79.7751], [50, 0, -82.7485], 2.0425),
         ([50, 3.1571, -77.2803], [50, 0, -82.7485], 2.8615),
         ([50, 2.8361, -74.02], [50, 0, -82.7485], 3.4412),
         ([50, -1.3802, -84.2814], [50, 0, -82.7485], 1.0),
         ([50, -1.1848, -84.8006], [50, 0, -82.7485], 1.0),
         ([50, -0.9009, -85.5211], [50, 0, -82.7485], 1.0),
         ([50, 0, 0], [50, -1, 2], 2.3669),
         ([50, -1, 2], [50, 0, 0], 2.3669),
         ([50, 2.49, -0.001], [50, -2.49, 0.001], 7.1792),
         ([50, 2.49, -0.001], [50, -2.49, 0.0011], 7.2195),
         ([50, 2.49, -0.001], [50, -2.49, 0.0009], 7.1792),
         ([50, 2.49, -0.001], [50, -2.49, 0.0012], 7.2195),
         ([50, -0.001, 2.49], [50, 0.0009, -2.49], 4.8045),
         ([50, -0.001, 2.49], [50, 0.001, -2.49], 4.8045),
         ([50, -0.001, 2.49], [50, 0.0011, -2.49], 4.7461),
         ([50, 2.5, 0], [50, 0, -2.5], 4.3065),
         ([50, 2.5, 0], [73, 25, -18], 27.1492),
         ([50, 2.5, 0], [61, -5, 29], 22.8977),
         ([50, 2.5, 0], [56, -27, -3], 31.903),
         ([50, 2.5, 0], [58, 24, 15], 19.4535),
         ([50, 2.5, 0], [50, 3.1736, 0.5854], 1.0),
         ([50, 2.5, 0], [50, 3.2972, 0], 1.0),
         ([50, 2.5, 0], [50, 1.8634, 0.5757], 1.0),
         ([50, 2.5, 0], [50, 3.2592, 0.335], 1.0),
         ([60.2574, -34.0099, 36.2677], [60.4626, -34.1751, 39.4387], 1.2644),
         ([63.0109, -31.0961, -5.8663], [62.8187, -29.7946, -4.0864], 1.263),
         ([61.2901, 3.7196, -5.3901], [61.4292, 2.248, -4.962], 1.8731),
         ([35.0831, -44.1164, 3.7933], [35.0232, -40.0716, 1.5901], 1.8645),
         ([22.7233, 20.0904, -46.694], [23.0331, 14.973, -42.5619], 2.0373),
         ([36.4612, 47.858, 18.3852], [36.2715, 50.5065, 21.2231], 1.4146),
         ([90.8027, -2.0831, 1.441], [91.1528, -1.6435, 0.0447], 1.4441),
         ([90.9257, -0.5406, -0.9208], [88.6381, -0.8985, -0.7239], 1.5381),
         ([6.7747, -0.2908, -2.4247], [5.8714, -0.0985, -2.2286], 0.6377),
         ([2.0776, 0.0795, -1.135], [0.9033, -0.0636, -0.5514], 0.9082)]
        for first, second, expected in cases:
            with self.subTest(first=first, second=second):
                self.assertAlmostEqual(float(delta_e_2000(first, second)), expected, delta=.0001)
                self.assertAlmostEqual(float(delta_e_2000(second, first)), expected, delta=.0001)
        first = np.array([cases[0][0], cases[1][0]])
        second = np.array([cases[0][1], cases[2][0], cases[3][0]])
        matrix = delta_e_2000(first[:, None, :], second[None, :, :])
        self.assertEqual(matrix.shape, (2, 3))
        for i in range(2):
            for j in range(3):
                self.assertAlmostEqual(matrix[i, j], delta_e_2000(first[i], second[j]))

    def test_ciede2000_capped_selection_and_transparency(self):
        palette = {"colors": [{"code": "W", "rgb": [255, 255, 255]},
                              {"code": "K", "rgb": [0, 0, 0]},
                              {"code": "R", "rgb": [255, 0, 0]}]}
        # Three distinct nearest codes exceed the cap. The large transparent
        # black background must not outweigh the four opaque red cells.
        rgba = np.zeros((20, 20, 4), dtype=np.uint8)
        rgba[0, 0] = [255, 255, 255, 255]
        rgba[0, 1] = [0, 0, 0, 255]
        rgba[0, 2:6] = [255, 0, 0, 255]
        rows, metadata = map_colors(rgba, palette, max_colors=2, locked=["W"])
        counts = statistics(rows)
        self.assertEqual(metadata["source_colors"], 3)
        self.assertEqual(set(counts), {"W", "R"})
        self.assertEqual(sum(counts.values()), 6)
        self.assertEqual(rows[0][0], "W")
        self.assertIsNone(rows[1][1])

    def test_ciede2000_white_skin_hair_and_transparency(self):
        palette = {"colors": [
            {"code": "W", "rgb": [255, 255, 255]},
            {"code": "S", "rgb": [255, 236, 222]},
            {"code": "H", "rgb": [150, 140, 145]},
            {"code": "K", "rgb": [0, 0, 0]},
        ]}
        rgba = np.array([[[255, 255, 255, 255], [255, 236, 222, 255], [150, 140, 145, 255]],
                         [[0, 0, 0, 255], [255, 236, 222, 0], [255, 255, 255, 255]]], dtype=np.uint8)
        rows, metadata = map_colors(rgba, palette, max_colors=4, locked=["W"])
        self.assertEqual(rows, [["W", "S", "H"], ["K", None, "W"]])
        self.assertEqual(metadata["method"], "CIELAB_D65_CIEDE2000")
        self.assertFalse(metadata["dithering"])
        self.assertEqual(metadata["mean_delta_e"], 0)
        self.assertEqual(sum(statistics(rows).values()), 5)

    def test_new_palette_skin_candidates_are_not_forced(self):
        palette = load_palette(DEFAULT_PALETTE)
        codes = ["E16", "G1", "H12", "H18", "H19"]
        colors = {c["code"]: c["rgb"] for c in palette["colors"]}
        self.assertEqual(colors["E16"], [255, 236, 222])
        self.assertEqual(colors["G1"], [255, 226, 206])
        self.assertEqual(colors["H12"], [255, 245, 237])
        self.assertEqual(colors["H18"], [255, 253, 240])
        self.assertEqual(colors["H19"], [246, 239, 226])
        pixels = np.array([[colors[c]+[255] for c in codes]], dtype=np.uint8)
        rows, _ = map_colors(pixels, palette, allowed=codes)
        self.assertEqual(rows, [codes])

    def test_ciede2000_chunked_nearest_matches_direct_calculation(self):
        from bead_palette import delta_e_2000, lab
        palette = {"colors": [{"code": "K", "rgb": [0, 0, 0]},
                              {"code": "W", "rgb": [255, 255, 255]},
                              {"code": "P", "rgb": [180, 90, 130]}]}
        pixels = np.array([[[i, 2*i, 255-i, 255] for i in range(80)]], dtype=np.uint8)
        rows, _ = map_colors(pixels, palette)
        source = lab(pixels[0, :, :3])
        target = lab([c["rgb"] for c in palette["colors"]])
        expected = np.argmin(delta_e_2000(source[:, None, :], target[None, :, :]), axis=1)
        self.assertEqual(rows[0], [palette["colors"][i]["code"] for i in expected])

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
