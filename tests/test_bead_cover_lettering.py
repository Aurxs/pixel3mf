import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"tools/beads"))
from cover_lettering import DEFAULT_NAME_FONT, FONT_ROOT, render_name  # noqa: E402
from render_cover import foreground, render_cover, rim_highlight  # noqa: E402


class CoverLetteringTests(unittest.TestCase):
    def fixture(self, root):
        project = {"schema": "pixel-art-to-beads/v1", "title": "菲欧妮",
                   "palette": {"colors": [{"code": "DARK", "rgb": [30, 20, 35]},
                                           {"code": "WHITE", "rgb": [255, 255, 255]}]},
                   "cells": [["DARK", "DARK", "DARK"],
                             ["WHITE", None, "DARK"], ["DARK", "DARK", "DARK"]]}
        path = root/"project.json"
        path.write_text(json.dumps(project), encoding="utf-8")
        reference = root/"reference.png"
        Image.new("RGB", (800, 900), (90, 110, 160)).save(reference)
        return project, path, reference

    def test_name_is_readable_below_subject_and_uses_recorded_licensed_font(self):
        original = Image.new("RGBA", (600, 800), (80, 100, 150, 255))
        before = original.tobytes()
        rendered, info = render_name(original, "菲欧妮", 500)
        self.assertEqual(original.tobytes(), before)
        self.assertIsNotNone(ImageChops.difference(rendered.convert("RGB"), original.convert("RGB")).getbbox())
        left, top, right, bottom = info["effect_bbox"]
        self.assertTrue(0 <= left < right <= 600)
        self.assertTrue(500 < top < bottom <= 800)
        self.assertEqual(rendered.crop((0, 0, 600, 500)).tobytes(), original.crop((0, 0, 600, 500)).tobytes())
        self.assertEqual(info["font"]["sha256"], hashlib.sha256(DEFAULT_NAME_FONT.read_bytes()).hexdigest())
        self.assertEqual(info["font"]["license"], "SIL Open Font License 1.1")
        self.assertIn("SIL OPEN FONT LICENSE", (FONT_ROOT/"OFL.txt").read_text())
        source = json.loads((FONT_ROOT/"source.json").read_text())
        self.assertFalse(source["modified"])
        self.assertEqual(info["font"]["sha256"], source["sha256"])
        _, fitted = render_name(original, "菲欧妮蕾法爱菈的超长角色名字", 500)
        self.assertLess(fitted["font_pixels"], info["font_pixels"])
        self.assertLessEqual(fitted["ink_bbox"][2]-fitted["ink_bbox"][0], 600*0.78)

    def test_invalid_names_missing_glyphs_and_clipping_are_explicit_errors(self):
        canvas = Image.new("RGBA", (600, 800))
        for text in (" ", "甲\n乙", "名"*81):
            with self.subTest(text=text), self.assertRaises(ValueError):
                render_name(canvas, text, 500)
        with self.assertRaisesRegex(ValueError, "lacks glyphs"):
            render_name(canvas, "名字\U0010ffff", 500)
        with self.assertRaisesRegex(ValueError, "clipped"):
            render_name(canvas, "菲欧妮", 780)
        with self.assertRaisesRegex(ValueError, "Name size"):
            render_name(canvas, "菲欧妮", 500, size_fraction=float("nan"))
        with tempfile.TemporaryDirectory() as directory:
            invalid = Path(directory)/"font.ttf"
            invalid.write_bytes(b"not a TrueType font")
            with self.assertRaisesRegex(ValueError, "TrueType"):
                render_name(canvas, "菲欧妮", 500, font_path=invalid)

    def test_rim_light_stays_outside_beads_and_enclosed_holes(self):
        with tempfile.TemporaryDirectory() as directory:
            project, _, _ = self.fixture(Path(directory))
            subject, _ = foreground(project, 12)
            before = subject.tobytes()
            glow, info = rim_highlight(subject, (120, 140), (40, 40), 12, 0.4)
            self.assertEqual(subject.tobytes(), before)
            alpha = glow.getchannel("A")
            self.assertGreater(alpha.getextrema()[1], 0)
            self.assertLessEqual(alpha.getextrema()[1], 102)
            for y in range(40, 76):
                for x in range(40, 76):
                    self.assertEqual(alpha.getpixel((x, y)), 0)
            self.assertEqual(info["placement"], "outside_silhouette_internal_holes_excluded")
            disabled, _ = rim_highlight(subject, (120, 140), (40, 40), 12, 0)
            self.assertEqual(disabled.getchannel("A").getextrema(), (0, 0))

    def test_cover_adds_name_and_glow_without_changing_chart_or_foreground(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project, path, reference = self.fixture(root)
            before = path.read_bytes(), reference.read_bytes()
            plain = render_cover(path, reference, root/"plain", reference_note="same", size=(600, 800),
                                 show_name=False, glow=0)
            named = render_cover(path, reference, root/"named", reference_note="same", size=(600, 800))
            self.assertEqual((path.read_bytes(), reference.read_bytes()), before)
            self.assertEqual(plain["statistics"], named["statistics"])
            for key in ("foreground", "background"):
                self.assertEqual(plain["products_sha256"][key], named["products_sha256"][key])
            self.assertFalse(plain["layout"]["text"])
            self.assertIsNone(plain["layout"]["name"])
            self.assertEqual(named["layout"]["name"]["text"], project["title"])
            override = render_cover(path, reference, root/"override", reference_note="same", size=(600, 800),
                                    name_text="角色名")
            self.assertEqual(override["layout"]["name"]["text"], "角色名")
            self.assertEqual(override["products_sha256"]["foreground"], named["products_sha256"]["foreground"])
            self.assertNotEqual(plain["products_sha256"]["cover"], named["products_sha256"]["cover"])
            with Image.open(plain["products"]["cover"]) as a, Image.open(named["products"]["cover"]) as b:
                cell = named["layout"]["cell_pixels"]
                x, y = named["layout"]["subject_position"]
                for yy, row in enumerate(project["cells"]):
                    for xx, code in enumerate(row):
                        if code:
                            point = (x+xx*cell+cell//2, y+yy*cell+cell//2)
                            self.assertEqual(a.getpixel(point), b.getpixel(point))
            with self.assertRaisesRegex(ValueError, "lacks glyphs"):
                render_cover(path, reference, root/"invalid", reference_note="same", name_text="\U0010ffff")
            self.assertFalse((root/"invalid").exists())
            result = subprocess.run([sys.executable, str(ROOT/"tools/beads/render_cover.py"), str(path),
                                     str(root/"cli"), "--reference", str(reference), "--reference-note", "same",
                                     "--no-name", "--glow", "0", "--size", "600", "800"],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            metadata = json.loads((root/"cli/cover.json").read_text())
            self.assertFalse(metadata["layout"]["text"])
            self.assertEqual(metadata["layout"]["glow"]["strength"], 0)


if __name__ == "__main__":
    unittest.main()
