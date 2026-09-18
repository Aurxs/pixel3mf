import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/beads"))
from unittest.mock import patch

import numpy as np
from PIL import Image

from compress_pixels import exterior_shell, finish, prepare, resize_cells


class CompressionTests(unittest.TestCase):
    def test_fit_preserves_aspect_and_existing_small_grid(self):
        rows = np.full((80, 80), None, dtype=object)
        rows[4:77, 6:74] = "H7"
        resized, metadata = resize_cells(rows, 52)
        self.assertEqual(resized.shape, (52, 52))
        self.assertEqual(metadata["subject_size"], [48, 52])
        small, metadata = resize_cells([["H7", None], ["H2", "H7"]], 52)
        self.assertEqual(metadata["subject_size"], [2, 2])
        self.assertEqual(np.count_nonzero(small != None), 3)  # noqa: E711

    def test_exterior_shell_excludes_enclosed_holes_and_interior(self):
        occupied = np.ones((7, 7), dtype=bool)
        occupied[3, 3] = False
        shell = exterior_shell(occupied)
        self.assertEqual(int(shell.sum()), 24)
        self.assertFalse(shell[3, 2])
        self.assertFalse(shell[3, 3])
        self.assertFalse(shell[2, 2])

    def test_ai_finish_locks_outline_without_changing_interior(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            rgba = np.zeros((16, 16, 4), dtype=np.uint8)
            rgba[2:14, 2:14] = [0, 0, 0, 255]
            rgba[3:13, 3:13] = [254, 255, 255, 255]
            rgba[7:9, 7:9] = [0, 0, 0, 0]
            Image.fromarray(rgba).save(temp / "source.png")
            prepare(temp / "source.png", temp / "run", target=16)
            with Image.open(temp / "run/01_seed.png") as image:
                sampled = np.array(image)
            mask = sampled[:, :, 3] == 255
            shell = exterior_shell(mask)
            y, x = np.argwhere(shell)[0]
            sampled[y, x] = [254, 255, 255, 255]
            Image.fromarray(sampled).save(temp / "candidate.png")
            with patch("perfect_pixel.get_perfect_pixel", return_value=(16, 16, sampled)):
                report = finish(temp / "run", temp / "candidate.png")
            before = json.loads((temp / "run/run.json").read_text())
            after = json.loads((temp / "run/attempt-1/project.json").read_text())
            a, b = np.array(before["cells"], dtype=object), np.array(after["cells"], dtype=object)
            self.assertEqual(report["outline_restored_cells"], 1)
            self.assertTrue(np.array_equal(a, b))
            self.assertTrue((b[shell] == "H7").all())
            with patch("perfect_pixel.get_perfect_pixel", return_value=(17, 16, sampled)):
                with self.assertRaises(ValueError):
                    finish(temp / "run", temp / "candidate.png", "attempt-2")

    def test_outline_does_not_reselect_palette_or_change_interior(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            colors = [[0, 0, 0], [65, 25, 25], [220, 170, 90], [255, 230, 180],
                      [160, 70, 30], [240, 240, 240], [190, 100, 80]]
            rgba = np.zeros((24, 24, 4), dtype=np.uint8)
            for y in range(2, 22):
                for x in range(2, 22):
                    rgba[y, x] = colors[(x+y*3) % len(colors)] + [255]
            Image.fromarray(rgba).save(temp / "source.png")
            prepare(temp / "source.png", temp / "plain", target=16, max_colors=5, outline="none")
            prepare(temp / "source.png", temp / "outlined", target=16, max_colors=5, outline="black")
            plain = json.loads((temp / "plain/run.json").read_text())
            outlined = json.loads((temp / "outlined/run.json").read_text())
            self.assertEqual(plain["mapping"], outlined["mapping"])
            a, b = np.array(plain["cells"], dtype=object), np.array(outlined["cells"], dtype=object)
            shell = exterior_shell(a != None)  # noqa: E711
            self.assertTrue(np.array_equal(a[~shell], b[~shell]))
            self.assertTrue((b[shell] == "H7").all())


if __name__ == "__main__":
    unittest.main()
