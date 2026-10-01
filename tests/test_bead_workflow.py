import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
import sys

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/beads"))
from run_workflow import prepare, publish_four, trim_empty_border  # noqa: E402


class FourChartTests(unittest.TestCase):
    def test_shared_constraints_keep_rare_detail_in_both_sizes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            palette = {"colors": [
                {"code": "BLUE", "rgb": [0, 80, 200]},
                {"code": "SHADE", "rgb": [0, 85, 205]},
                {"code": "LIP", "rgb": [220, 90, 100]},
            ]}
            (root/"palette.json").write_text(json.dumps(palette))
            image = Image.new("RGBA", (8, 8), (0, 80, 200, 255))
            image.putpixel((2, 2), (0, 85, 205, 255))
            image.putpixel((4, 4), (220, 90, 100, 255))
            image.save(root/"source.png")
            captured = {}

            def capture_export(project, *args, **kwargs):
                captured.update(project)
                codes = {c for row in project["cells"] for c in row if c}
                project["statistics"] = {"colors": len(codes)}

            with patch("run_workflow.export_project", side_effect=capture_export):
                state = prepare(root/"source.png", root/"run", "test", target=8,
                                palette=root/"palette.json", max_colors=2,
                                allowed=["BLUE", "SHADE", "LIP"], locked=["LIP"],
                                outline="none")
            seed = json.loads((root/"run/work/02_compression/run.json").read_text())
            self.assertEqual(captured["cells"][4][4], "LIP")
            self.assertEqual(seed["cells"], captured["cells"])
            self.assertEqual(seed["mapping"], state["color_mapping"])
            self.assertEqual(state["color_mapping"]["locked"], ["LIP"])
            self.assertEqual(state["uncompressed_statistics"]["colors"], 2)

    def test_outline_cannot_escape_reviewed_allowed_codes(self):
        from compress_pixels import prepare as prepare_compression
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/"palette.json").write_text(json.dumps({"colors": [
                {"code": "H7", "rgb": [0, 0, 0]},
                {"code": "WHITE", "rgb": [255, 255, 255]},
            ]}))
            Image.new("RGBA", (8, 8), (0, 0, 0, 255)).save(root/"source.png")
            with self.assertRaisesRegex(ValueError, "included in allowed"):
                prepare_compression(root/"source.png", root/"run", 8,
                                    root/"palette.json", outline="black",
                                    allowed=["WHITE"])
            self.assertFalse((root/"run").exists())

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
