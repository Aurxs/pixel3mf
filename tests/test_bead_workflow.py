import tempfile
import unittest
from pathlib import Path
import sys

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/beads"))
from run_workflow import publish_four, trim_empty_border  # noqa: E402


class FourChartTests(unittest.TestCase):
    def test_trim_removes_only_outer_empty_rows_and_columns(self):
        cells = [[None] * 6 for _ in range(5)]
        cells[1][2:5] = ["H2", "H7", None]
        cells[2][2:5] = [None, None, "G11"]
        cells[3][2:5] = ["H7", None, "H2"]
        project = trim_empty_border({"cells": cells})
        self.assertEqual(project["cells"], [
            ["H2", "H7", None], [None, None, "G11"], ["H7", None, "H2"]])
        self.assertEqual(project["uncompressed_crop"]["bbox"], [2, 1, 5, 4])
        with self.assertRaisesRegex(ValueError, "no occupied"):
            trim_empty_border({"cells": [[None]]})

    def test_delivers_exactly_four_independent_files_and_preserves_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, size in [("uncompressed", (8, 9)), ("compressed", (5, 5))]:
                folder = root/name
                folder.mkdir()
                Image.new("RGB", size, "red").save(folder/"正常版.png")
                Image.new("RGB", size, "blue").save(folder/"镜像版.png")
                (folder/"extra.txt").write_text("internal artifact")
            products = publish_four(root/"uncompressed", root/"compressed", root/"delivery")
            self.assertEqual(len(products), 4)
            self.assertEqual(len(list((root/"delivery").iterdir())), 4)
            for item, size in zip(products, [(8, 9), (8, 9), (5, 5), (5, 5)]):
                with Image.open(item["path"]) as image:
                    self.assertEqual(image.size, size)
            with self.assertRaises(ValueError):
                publish_four(root/"uncompressed", root/"compressed", root/"delivery")


if __name__ == "__main__":
    unittest.main()
