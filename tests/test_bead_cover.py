import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"tools/beads"))
from render_cover import foreground, render_cover  # noqa: E402
from run_workflow import cover  # noqa: E402


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file() and "covers" not in p.relative_to(root).parts}


class BeadCoverTests(unittest.TestCase):
    def fixture(self, root):
        project = {
            "schema": "pixel-art-to-beads/v1", "title": "拼豆作品",
            "palette": {"colors": [{"code": "BLACK", "rgb": [0, 0, 0]},
                                     {"code": "WHITE", "rgb": [255, 255, 255]},
                                     {"code": "RED", "rgb": [210, 50, 60]}]},
            "cells": [[None]*7, [None, "BLACK", "WHITE", "RED", None, None, None],
                      [None, "BLACK", None, "RED", None, "WHITE", None],
                      [None, None, "RED", "RED", None, None, None], [None]*7],
        }
        path = root/"图纸数据.json"
        path.write_text(json.dumps(project), encoding="utf-8")
        # Different colors on either side make background provenance/crop observable.
        reference = Image.new("RGB", (900, 700), (30, 80, 180))
        reference.paste((190, 80, 30), (450, 0, 900, 700))
        reference.save(root/"official.png")
        return project, path, root/"official.png"

    def test_foreground_preserves_cells_holes_white_detached_pieces_and_orientation(self):
        with tempfile.TemporaryDirectory() as directory:
            project, _, _ = self.fixture(Path(directory))
            original = copy.deepcopy(project)
            for texture in (False, True):
                with self.subTest(texture=texture):
                    image, box = foreground(project, 10, texture=texture)
                    self.assertEqual(box, (1, 1, 6, 4))
                    self.assertEqual(image.size, (50, 30))
                    colors = {c["code"]: tuple(c["rgb"])+ (255,) for c in project["palette"]["colors"]}
                    for y, row in enumerate(project["cells"][1:4]):
                        for x, code in enumerate(row[1:6]):
                            self.assertEqual(image.getpixel((x*10+5, y*10+5)),
                                             colors[code] if code else (0, 0, 0, 0))
                    self.assertEqual(image.getchannel("A").tobytes().count(255), 8*100)
            self.assertEqual(project, original)

    def test_render_provenance_and_new_directory_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, path, reference = self.fixture(root)
            before = hashes(root)
            report = render_cover(path, reference, root/"covers/one", reference_note="same character/costume",
                                  reference_source="retained research", size=(600, 800),
                                  reference_crop=(450, 0, 900, 700))
            self.assertEqual(hashes(root), before)
            self.assertEqual(report["statistics"]["total_beads"], 8)
            self.assertEqual(report["reference"]["sha256"], before["official.png"])
            self.assertEqual(report["project"]["sha256"], before["图纸数据.json"])
            self.assertFalse(report["layout"]["text"])
            self.assertFalse(report["layout"]["mirrored"])
            with Image.open(report["products"]["cover"]) as image:
                self.assertEqual(image.size, (600, 800))
                self.assertEqual(image.mode, "RGB")
            with Image.open(report["products"]["background"]) as image:
                r, _, b = image.getpixel((300, 50))
                self.assertGreater(r, b*2)  # Only the chosen official-art crop is used.
            products = {p.name: p.read_bytes() for p in (root/"covers/one").iterdir()}
            with self.assertRaisesRegex(ValueError, "already exists"):
                render_cover(path, reference, root/"covers/one", reference_note="same")
            self.assertEqual(products, {p.name: p.read_bytes() for p in (root/"covers/one").iterdir()})

    def test_rejects_invalid_settings_without_partial_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, path, reference = self.fixture(root)
            for settings in ({"reference_note": " "}, {"size": (0, 800)}, {"size": (4096, 4096)},
                             {"blur": float("nan")}, {"zoom": 0.9}, {"focal": (1.1, 0.5)},
                             {"center": (0, 0)}, {"reference_crop": (-1, 0, 50, 50)},
                             {"reference_crop": (0, 0, 1000, 700)}):
                with self.subTest(settings=settings), self.assertRaises(ValueError):
                    render_cover(path, reference, root/"new", **{"reference_note": "same", **settings})
                self.assertFalse((root/"new").exists())
            Image.new("RGB", (52, 52)).save(root/"logical.png")
            with self.assertRaisesRegex(ValueError, "original large"):
                render_cover(path, root/"logical.png", root/"new", reference_note="same")
            invalid = json.loads(path.read_text())
            invalid["cells"][1][1] = "UNKNOWN"
            path.write_text(json.dumps(invalid))
            with self.assertRaisesRegex(ValueError, "unknown color"):
                render_cover(path, reference, root/"new", reference_note="same")
            self.assertFalse((root/"new").exists())

    def test_workflow_cover_keeps_two_and_four_chart_runs_byte_identical(self):
        for oversized in (False, True):
            with self.subTest(oversized=oversized), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                _, project, reference = self.fixture(root)
                run = root/"run"
                run.mkdir()
                variants = ("uncompressed", "compressed") if oversized else ("uncompressed",)
                state = {"schema": "bead-chart-workflow/v2", "primary_products": [], "paths": {}}
                for variant in variants:
                    chart_dir = run/"work"/variant
                    chart_dir.mkdir(parents=True)
                    (chart_dir/"图纸数据.json").write_bytes(project.read_bytes())
                    state["paths"][variant] = str(chart_dir)
                (run/"manifest.json").write_text(json.dumps(state))
                with self.assertRaisesRegex(ValueError, "Finish"):
                    cover(run, reference, reference_note="same")
                (run/"delivery").mkdir()
                for i in range(4 if oversized else 2):
                    product = run/"delivery"/f"{i+1:02d}.png"
                    Image.new("RGB", (12, 14), (i*60, 100, 200)).save(product)
                    state["primary_products"].append({"path": str(product)})
                state["expected_primary_products"] = 4 if oversized else 2
                state["status"] = "accepted"
                (run/"manifest.json").write_text(json.dumps(state))
                before = hashes(root)
                for variant in variants:
                    report = cover(run, reference, reference_note="same character/costume",
                                   variant=variant, name=variant, size=(600, 800))
                    self.assertEqual(report["project"]["path"],
                                     str(Path(json.loads((run/"manifest.json").read_text())["paths"][variant])/"图纸数据.json"))
                    self.assertEqual(hashes(root), before)
                if not oversized:
                    with self.assertRaisesRegex(ValueError, "unavailable"):
                        cover(run, reference, variant="compressed", reference_note="same")
                for name in ("", "..", "../escape"):
                    with self.assertRaisesRegex(ValueError, "simple directory"):
                        cover(run, reference, name=name, reference_note="same")
                result = subprocess.run([sys.executable, str(ROOT/"tools/beads/run_workflow.py"),
                                         "cover", str(run), "--reference", str(reference),
                                         "--reference-note", "same character/costume", "--name", "cli",
                                         "--size", "600", "800"], capture_output=True, text=True,
                                        cwd=root)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)["status"], "cover_ready_for_review")
                self.assertEqual(hashes(root), before)
                self.assertEqual(len(list((run/"delivery").iterdir())), 4 if oversized else 2)

    def test_cli_and_exif_orientation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, path, reference = self.fixture(root)
            exif = Image.Exif()
            exif[274] = 6
            with Image.open(reference) as image:
                image.save(root/"rotated.jpg", exif=exif)
            result = subprocess.run([sys.executable, str(ROOT/"tools/beads/render_cover.py"),
                                     str(path), str(root/"covers/cli"), "--reference", str(root/"rotated.jpg"),
                                     "--reference-note", "same character/costume", "--size", "600", "800",
                                     "--reference-crop", "0", "0", "700", "900", "--flat"],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "cover_ready_for_review")
            report = json.loads((root/"covers/cli/cover.json").read_text())
            self.assertEqual(report["reference"]["original_size"], [700, 900])
            self.assertEqual(report["layout"]["texture"], "flat")


if __name__ == "__main__":
    unittest.main()
