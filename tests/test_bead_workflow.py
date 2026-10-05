import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
import sys

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/beads"))
from run_workflow import complete, prepare, publish_charts, trim_empty_border  # noqa: E402


class SizeAwareChartTests(unittest.TestCase):
    def test_shared_constraints_keep_rare_detail_in_both_sizes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            palette = {"colors": [
                {"code": "BLUE", "rgb": [0, 80, 200]},
                {"code": "SHADE", "rgb": [0, 85, 205]},
                {"code": "LIP", "rgb": [220, 90, 100]},
            ]}
            (root/"palette.json").write_text(json.dumps(palette))
            image = Image.new("RGBA", (9, 8), (0, 80, 200, 255))
            image.putpixel((2, 2), (0, 85, 205, 255))
            image.paste((220, 90, 100, 255), (4, 4, 6, 6))
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
            self.assertIn("LIP", {c for row in seed["cells"] for c in row})
            self.assertEqual(seed["mapping"], state["color_mapping"])
            self.assertEqual(state["color_mapping"]["locked"], ["LIP"])
            self.assertEqual(state["uncompressed_statistics"]["colors"], 2)

    def test_logical_boundaries_and_transparent_padding(self):
        from PIL import ImageOps
        for width, height, padded in [(35, 43, False), (52, 52, False),
                                      (52, 53, False), (53, 40, False),
                                      (35, 43, True)]:
            with self.subTest(size=(width, height), padded=padded), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                image = Image.new("RGBA", (width, height), (0, 80, 200, 255))
                image.putpixel((1, 2), (220, 90, 100, 255))
                image.putpixel((3, 4), (0, 0, 0, 0))
                if padded:
                    canvas = Image.new("RGBA", (100, 100))
                    canvas.paste(image, (9, 11))
                    image = canvas
                image.save(root/"source.png")
                original_bytes = (root/"source.png").read_bytes()
                oversized = width > 52 or height > 52
                state = prepare(root/"source.png", root/"run", "test", outline="none")
                self.assertEqual(state["logical_size"], [width, height])
                self.assertEqual(state["compression_required"], oversized)
                self.assertEqual(state["expected_primary_products"], 4 if oversized else 2)
                self.assertEqual(state["uncompressed_statistics"]["total_beads"], width*height-1)
                self.assertEqual((root/"run/work/02_compression").exists(), oversized)
                if not oversized:
                    self.assertNotIn("ai_input", state["paths"])
                    with self.assertRaisesRegex(ValueError, "No compression"):
                        complete(root/"run", candidate=root/"nonexistent.png")
                else:
                    with self.assertRaisesRegex(ValueError, "Choose exactly one"):
                        complete(root/"run")
                state = complete(root/"run", algorithm_only=oversized)
                self.assertEqual(len(state["primary_products"]), 4 if oversized else 2)
                self.assertEqual(len(list((root/"run/delivery").iterdir())), 4 if oversized else 2)
                self.assertEqual(state["status"], "four_charts_ready_for_review" if oversized else "two_charts_ready_for_review")
                self.assertEqual((root/"source.png").read_bytes(), original_bytes)
                for variant in ["uncompressed"] + (["compressed"] if oversized else []):
                    charts = Path(state["paths"][variant])
                    project = json.loads((charts/"图纸数据.json").read_text())
                    stats = project["statistics"]
                    self.assertEqual(sum(stats["counts"].values()), stats["total_beads"])
                    if variant == "compressed":
                        self.assertEqual([stats["width"], stats["height"]], [52, 52])
                    with Image.open(charts/"正常版_预览.png") as normal, Image.open(charts/"镜像版_预览.png") as mirrored:
                        self.assertEqual(ImageOps.mirror(normal).tobytes(), mirrored.tobytes())
                with self.assertRaisesRegex(ValueError, "already published"):
                    complete(root/"run", algorithm_only=oversized)

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
            products = publish_charts(root/"uncompressed", root/"compressed", root/"delivery")
            self.assertEqual(len(products), 4)
            self.assertEqual(len(list((root/"delivery").iterdir())), 4)
            for item, size in zip(products, [(8, 9), (8, 9), (5, 5), (5, 5)]):
                with Image.open(item["path"]) as image:
                    self.assertEqual(image.size, size)
            with self.assertRaises(ValueError):
                publish_charts(root/"uncompressed", root/"compressed", root/"delivery")


if __name__ == "__main__":
    unittest.main()
