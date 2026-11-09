import copy
from functools import partial
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image, ImageStat

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"tools/beads"))
from render_cover import background_frame, foreground, render_cover as compose_cover  # noqa: E402
from run_workflow import cover  # noqa: E402

# Background/workflow fixtures use the explicit portable legacy style.
# PingFang defaults and collection selection have independent font fixtures.
render_cover = partial(compose_cover, name_style="warm_calligraphic")


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file() and "covers" not in p.relative_to(root).parts}


class BeadCoverTests(unittest.TestCase):
    def test_contain_retains_full_reference_and_fills_canvas_without_stretching(self):
        source = Image.new("RGB", (1200, 600), (200, 40, 30))
        source.paste((30, 50, 200), (600, 0, 1200, 600))
        image, plan = background_frame(source, (600, 800), fit="contain", zoom=1,
                                       focal=(0.5, 0.5), blur=0.016)
        self.assertEqual(image.size, (600, 800))
        self.assertEqual(image.mode, "RGB")
        self.assertEqual(plan["visible_source_box"], (0, 0, 1200, 600))
        self.assertEqual(plan["scaled_size"], (600, 300))
        self.assertEqual(plan["visible_fraction"], 1)
        self.assertEqual(plan["backing"], "same_reference_blurred_fill")
        self.assertEqual(image.getpixel((80, 400)), (200, 40, 30))
        self.assertEqual(image.getpixel((520, 400)), (30, 50, 200))
        self.assertTrue(all(min(image.getpixel(p)) > 0 for p in ((0, 0), (599, 0), (0, 799), (599, 799))))
        _, close = background_frame(source, (600, 800), fit="cover", zoom=1.12,
                                     focal=(0.5, 0.5), blur=0.026)
        self.assertLess(close["visible_fraction"], 0.4)

    def test_background_geometry_handles_portraits_panoramas_and_zoom_out(self):
        for source_size in ((500, 900), (2000, 300), (1, 700)):
            for fit, zoom, focal in (("contain", 0.75, (0, 1)), ("contain", 1, (0.5, 0.5)),
                                     ("cover", 3, (1, 0))):
                with self.subTest(source=source_size, fit=fit, zoom=zoom):
                    source = Image.new("RGB", source_size, (40, 80, 150))
                    image, plan = background_frame(source, (300, 400), fit=fit, zoom=zoom,
                                                   focal=focal, blur=0.016)
                    self.assertEqual(image.size, (300, 400))
                    self.assertAlmostEqual(plan["scaled_size"][0], source.width*plan["uniform_scale"], delta=1)
                    self.assertAlmostEqual(plan["scaled_size"][1], source.height*plan["uniform_scale"], delta=1)
                    left, top, right, bottom = plan["visible_source_box"]
                    self.assertTrue(0 <= left < right <= source.width)
                    self.assertTrue(0 <= top < bottom <= source.height)
                    self.assertLessEqual(plan["visible_fraction"], 1)
                    if fit == "contain":
                        self.assertEqual(plan["visible_fraction"], 1)

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
            self.assertTrue(report["layout"]["text"])
            self.assertEqual(report["layout"]["name"]["text"], "拼豆作品")
            self.assertFalse(report["layout"]["mirrored"])
            self.assertEqual(report["layout"]["background_framing"]["fit"], "contain")
            self.assertEqual(report["layout"]["background_framing"]["visible_fraction"], 1)
            self.assertEqual(report["layout"]["zoom"], 1)
            self.assertEqual(report["layout"]["blur_fraction"], 0.016)
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

    def test_original_foreground_preserves_every_rgba_pixel_without_palette_repainting(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project, path, reference = self.fixture(root)
            pixels = Image.new("RGBA", (7, 5), (17, 19, 23, 0))
            colors = {"BLACK": (7, 9, 11, 255), "WHITE": (255, 255, 255, 255),
                      "RED": (237, 39, 71, 255)}
            for y, row in enumerate(project["cells"]):
                for x, code in enumerate(row):
                    if code is not None:
                        pixels.putpixel((x, y), colors[code])
            original = root/"original.png"
            pixels.save(original)
            before = hashes(root)
            report = render_cover(path, reference, root/"covers/raw", reference_note="same",
                                  foreground_path=original, size=(600, 800))
            self.assertEqual(hashes(root), before)
            self.assertEqual(report["foreground_input"]["kind"], "original_pixels")
            self.assertEqual(report["foreground_input"]["sha256"], before["original.png"])
            self.assertEqual(report["layout"]["texture"], "source_pixels")
            scale = report["layout"]["cell_pixels"]
            expected = pixels.crop((1, 1, 6, 4)).resize((5*scale, 3*scale), Image.Resampling.NEAREST)
            with Image.open(report["products"]["foreground"]) as actual:
                self.assertEqual(actual.tobytes(), expected.tobytes())
            with self.assertRaisesRegex(ValueError, "cannot have bead texture"):
                render_cover(path, reference, root/"covers/textured", reference_note="same",
                             foreground_path=original, texture=True)
            self.assertFalse((root/"covers/textured").exists())
            pixels.putpixel((3, 3), (0, 0, 0, 0))
            pixels.save(original)
            with self.assertRaisesRegex(ValueError, "dimensions/occupancy"):
                render_cover(path, reference, root/"covers/wrong", reference_note="same", foreground_path=original)
            self.assertFalse((root/"covers/wrong").exists())

    def test_rejects_invalid_settings_without_partial_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, path, reference = self.fixture(root)
            for settings in ({"reference_note": " "}, {"size": (0, 800)}, {"size": (4096, 4096)},
                             {"blur": float("nan")}, {"zoom": 0.49}, {"background_fit": "stretch"},
                             {"focal": (1.1, 0.5)},
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

    def test_background_revision_preserves_foreground_and_chart_inputs_exactly(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, project, reference = self.fixture(root)
            before = hashes(root)
            close = render_cover(project, reference, root/"covers/close", reference_note="same",
                                 size=(600, 800), background_fit="cover", zoom=1.12, blur=0.026)
            wide = render_cover(project, reference, root/"covers/wide", reference_note="same", size=(600, 800))
            self.assertEqual(hashes(root), before)
            self.assertEqual(close["statistics"], wide["statistics"])
            self.assertEqual(close["products_sha256"]["foreground"], wide["products_sha256"]["foreground"])
            self.assertNotEqual(close["products_sha256"]["background"], wide["products_sha256"]["background"])
            self.assertGreater(wide["layout"]["background_framing"]["visible_fraction"],
                               close["layout"]["background_framing"]["visible_fraction"])

    def test_smaller_default_subject_exposes_more_gently_lit_background(self):
        for portrait in (False, True):
            with self.subTest(portrait=portrait), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                project, path, reference = self.fixture(root)
                if portrait:
                    project["cells"] = [list(row) for row in zip(*project["cells"])]
                    path.write_text(json.dumps(project))
                before = hashes(root)
                old = render_cover(path, reference, root/"covers/old", reference_note="same", size=(600, 800),
                                   subject_width=0.70, subject_height=0.62, brightness=0.78)
                new = render_cover(path, reference, root/"covers/new", reference_note="same", size=(600, 800))
                self.assertEqual(hashes(root), before)
                self.assertEqual(old["statistics"], new["statistics"])
                self.assertEqual(new["layout"]["saturation"], old["layout"]["saturation"])
                with Image.open(old["products"]["foreground"]) as previous, Image.open(new["products"]["foreground"]) as subject:
                    self.assertLess(subject.width, previous.width)
                    self.assertLess(subject.height, previous.height)
                    self.assertLessEqual(subject.width, 600*0.60)
                    self.assertLessEqual(subject.height, 800*0.52)
                    scale = new["layout"]["cell_pixels"]
                    left, top, right, bottom = new["layout"]["subject_bbox_cells"]
                    self.assertEqual(subject.size, ((right-left)*scale, (bottom-top)*scale))
                    colors = {c["code"]: tuple(c["rgb"])+(255,) for c in project["palette"]["colors"]}
                    for y in range(top, bottom):
                        for x in range(left, right):
                            code = project["cells"][y][x]
                            self.assertEqual(subject.getpixel(((x-left)*scale+scale//2, (y-top)*scale+scale//2)),
                                             colors[code] if code else (0, 0, 0, 0))
                with Image.open(old["products"]["background"]) as dark, Image.open(new["products"]["background"]) as light:
                    lift = ImageStat.Stat(light.convert("L")).mean[0]/ImageStat.Stat(dark.convert("L")).mean[0]
                    self.assertTrue(1.08 < lift < 1.13)
                    self.assertLess(max(channel[1] for channel in light.getextrema()), 255)
                    p, q = dark.getpixel((80, 400)), light.getpixel((80, 400))
                    for old_value, new_value in zip(p, q):
                        self.assertAlmostEqual(new_value, old_value*0.86/0.78, delta=2)
                    self.assertGreaterEqual(max(q)-min(q), max(p)-min(p))

    def test_workflow_cover_keeps_two_and_four_chart_runs_byte_identical(self):
        for oversized in (False, True):
            with self.subTest(oversized=oversized), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                data, project, reference = self.fixture(root)
                run = root/"run"
                run.mkdir()
                variants = ("uncompressed", "compressed") if oversized else ("uncompressed",)
                state = {"schema": "bead-chart-workflow/v2", "primary_products": [], "paths": {}}
                for variant in variants:
                    chart_dir = run/"work"/variant
                    chart_dir.mkdir(parents=True)
                    (chart_dir/"图纸数据.json").write_bytes(project.read_bytes())
                    state["paths"][variant] = str(chart_dir)
                pixels = Image.new("RGBA", (7, 5))
                colors = {c["code"]: tuple(c["rgb"])+(255,) for c in data["palette"]["colors"]}
                for y, row in enumerate(data["cells"]):
                    for x, code in enumerate(row):
                        if code is not None:
                            pixels.putpixel((x, y), colors[code])
                pixels.save(run/"work/00_source.png")
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
                                   variant=variant, name=variant, size=(600, 800), name_style="warm_calligraphic")
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
                                         "--size", "600", "800", "--name-style", "warm_calligraphic"], capture_output=True, text=True,
                                        cwd=root)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)["status"], "cover_ready_for_review")
                report = json.loads((run/"covers/cli/cover.json").read_text())
                self.assertEqual(report["foreground_input"]["path"], str(run/"work/00_source.png"))
                self.assertEqual(report["layout"]["texture"], "source_pixels")
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
                                     "--reference-crop", "0", "0", "700", "900", "--flat",
                                     "--background-fit", "contain", "--zoom", "0.85",
                                     "--name-style", "warm_calligraphic"],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "cover_ready_for_review")
            report = json.loads((root/"covers/cli/cover.json").read_text())
            self.assertEqual(report["reference"]["original_size"], [700, 900])
            self.assertEqual(report["layout"]["texture"], "flat")
            self.assertEqual(report["layout"]["zoom"], 0.85)
            self.assertEqual(report["layout"]["subject_width"], 0.60)
            self.assertEqual(report["layout"]["subject_height"], 0.52)
            self.assertEqual(report["layout"]["brightness"], 0.86)


if __name__ == "__main__":
    unittest.main()
