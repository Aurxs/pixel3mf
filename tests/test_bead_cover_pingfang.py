"""Use synthetic fonts to exercise face selection; never bundle Apple fonts."""
import argparse
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import TTCollection
from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"tools/beads"))
from cover_lettering import DEFAULT_NAME_FONT, font_info, render_name  # noqa: E402
from render_cover import add_options, options, render_cover  # noqa: E402


def build_fixture_font(postscript, *, cff=False, missing=""):
    """Build small OFL-independent geometric fixtures with distinct test names."""
    builder = FontBuilder(1000, isTTF=not cff)
    chars = set("「」菲欧妮角色名•时装")-set(missing)
    cmap = {ord(char): f"uni{ord(char):04X}" for char in chars}
    order = [".notdef", *cmap.values()]
    builder.setupGlyphOrder(order)
    builder.setupCharacterMap(cmap)
    shapes = {}
    for glyph in order:
        pen = T2CharStringPen(1000, None) if cff else TTGlyphPen(None)
        pen.moveTo((100, 0))
        pen.lineTo((100, 700))
        pen.lineTo((800, 700))
        pen.lineTo((800, 0))
        pen.closePath()
        shapes[glyph] = pen.getCharString() if cff else pen.glyph()
    if cff:
        builder.setupCFF(postscript, {"FullName": postscript, "FamilyName": "Cover Fixture"}, shapes, {})
    else:
        builder.setupGlyf(shapes)
    builder.setupHorizontalMetrics({glyph: (1000, 100) for glyph in order})
    builder.setupHorizontalHeader(ascent=800, descent=-200)
    builder.setupNameTable({"familyName": "Cover Fixture", "styleName": postscript.split("-")[-1],
                            "psName": postscript, "fullName": postscript})
    builder.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    builder.setupPost()
    return builder.font


class PingFangCoverTests(unittest.TestCase):
    def fixture(self, root, *, cff=False, missing=""):
        path = root/"synthetic.ttc"
        collection = TTCollection()
        collection.fonts = [build_fixture_font("CoverFixture-Regular", cff=cff),
                            build_fixture_font("CoverFixture-Light", cff=cff, missing=missing)]
        collection.save(path)
        collection.close()
        return path

    def fixture_environment(self, path):
        context = ExitStack()
        context.enter_context(patch("cover_lettering.PINGFANG_POSTSCRIPT", "CoverFixture-Light"))
        context.enter_context(patch("cover_lettering.PINGFANG_PATHS", (path,)))
        context.enter_context(patch("cover_lettering.subprocess.run", side_effect=FileNotFoundError))
        return context

    def test_selects_light_face_from_ttf_and_cff_collections_without_copying_font(self):
        for cff in (False, True):
            with self.subTest(cff=cff), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                path = self.fixture(root, cff=cff)
                before = path.read_bytes()
                canvas = Image.new("RGBA", (1080, 1440), (31, 41, 59, 255))
                with self.fixture_environment(path):
                    rendered, info = render_name(canvas, "菲欧妮", 1020)
                    quoted, repeated = render_name(canvas, "「菲欧妮」", 1020, font_path=path)
                self.assertEqual(info["text"], "「菲欧妮」")
                self.assertEqual(info["font"]["postscript_name"], "CoverFixture-Light")
                self.assertEqual(info["font"]["face_index"], 1)
                self.assertEqual(info["font_pixels"], 96)
                self.assertEqual(info["tracking_pixels"], 12)
                self.assertEqual(info["fill"], [255, 255, 255])
                self.assertEqual(info["stroke_pixels"], 0)
                self.assertFalse(info["shadow"] or info["gradient"])
                self.assertEqual(info["ink_bbox"], info["effect_bbox"])
                self.assertAlmostEqual((info["ink_bbox"][1]+info["ink_bbox"][3])/2, 1138, delta=1)
                self.assertEqual(quoted.tobytes(), rendered.tobytes())
                self.assertEqual(repeated["text"], info["text"])
                self.assertEqual(rendered.crop((0, 0, 1080, 1020)).tobytes(), canvas.crop((0, 0, 1080, 1020)).tobytes())
                self.assertIsNotNone(ImageChops.difference(rendered.convert("RGB"), canvas.convert("RGB")).getbbox())
                self.assertEqual(path.read_bytes(), before)
                self.assertEqual(list(root.iterdir()), [path])

    def test_larger_default_keeps_clear_gap_and_canvas_bounds(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.fixture(Path(directory))
            with self.fixture_environment(path):
                for width, height, subject_bottom in ((600, 800, 568), (1080, 1440, 1020)):
                    with self.subTest(size=(width, height)):
                        canvas = Image.new("RGBA", (width, height))
                        _, old = render_name(canvas, "菲欧妮", subject_bottom, size_fraction=48/1080)
                        _, enlarged = render_name(canvas, "菲欧妮", subject_bottom)
                        left, top, right, bottom = enlarged["ink_bbox"]
                        self.assertEqual(enlarged["font_pixels"], round(width*96/1080))
                        self.assertAlmostEqual(enlarged["font_pixels"], 2*old["font_pixels"], delta=1)
                        self.assertGreater(right-left, old["ink_bbox"][2]-old["ink_bbox"][0])
                        self.assertTrue(0 <= left < right <= width)
                        self.assertTrue(subject_bottom+height*0.025 < top < bottom <= height)
                        self.assertEqual(enlarged["text"], "「菲欧妮」")

    def test_named_outfit_preserves_bullet_and_single_quote_pair(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.fixture(Path(directory))
            with self.fixture_environment(path):
                canvas = Image.new("RGBA", (1080, 1440))
                plain, info = render_name(canvas, "角色名•时装名", 1020)
                quoted, repeated = render_name(canvas, "「角色名•时装名」", 1020)
            self.assertEqual(info["text"], "「角色名•时装名」")
            self.assertEqual(repeated["text"], info["text"])
            self.assertEqual(plain.tobytes(), quoted.tobytes())
            self.assertLessEqual(info["ink_bbox"][2]-info["ink_bbox"][0], 1080*0.78)

    def test_no_fallback_for_missing_font_wrong_face_or_missing_quotes(self):
        canvas = Image.new("RGBA", (1080, 1440))
        with patch("cover_lettering.PINGFANG_PATHS", ()), patch("cover_lettering.subprocess.run", side_effect=FileNotFoundError):
            with self.assertRaisesRegex(ValueError, "PingFang SC Light.*unavailable"):
                render_name(canvas, "菲欧妮", 1020)
        fallback = SimpleNamespace(returncode=0, stdout=str(DEFAULT_NAME_FONT))
        with patch("cover_lettering.PINGFANG_PATHS", ()), patch("cover_lettering.subprocess.run", return_value=fallback):
            with self.assertRaisesRegex(ValueError, "PingFang SC Light.*unavailable"):
                render_name(canvas, "菲欧妮", 1020)
        with self.assertRaisesRegex(ValueError, "required face PingFangSC-Light"):
            render_name(canvas, "菲欧妮", 1020, font_path=DEFAULT_NAME_FONT)
        with tempfile.TemporaryDirectory() as directory:
            path = self.fixture(Path(directory), missing="「")
            with self.fixture_environment(path), self.assertRaisesRegex(ValueError, "CoverFixture-Light lacks glyphs: 「"):
                render_name(canvas, "菲欧妮", 1020)

    def test_quotes_size_and_overlap_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.fixture(Path(directory))
            with self.fixture_environment(path):
                for text in ("「菲欧妮", "菲欧妮」", "「」", "「「菲欧妮」」"):
                    with self.subTest(text=text), self.assertRaisesRegex(ValueError, "balanced"):
                        render_name(Image.new("RGBA", (1080, 1440)), text, 1020)
                with self.assertRaisesRegex(ValueError, "overlap"):
                    render_name(Image.new("RGBA", (1080, 1440)), "菲欧妮", 1130)
                _, fitted = render_name(Image.new("RGBA", (1080, 1440)), "菲欧妮"*6, 1020)
                self.assertLess(fitted["font_pixels"], 48)

    def test_standalone_opentype_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"synthetic.otf"
            build_fixture_font("CoverFixture-Light", cff=True).save(path)
            stat = path.stat()
            glyphs, info = font_info(str(path), stat.st_mtime_ns, stat.st_size, "CoverFixture-Light")
            self.assertIn(ord("「"), glyphs)
            self.assertEqual(info["face_index"], 0)
            self.assertEqual(info["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_cover_options_and_input_preservation_with_new_default(self):
        parser = argparse.ArgumentParser()
        add_options(parser)
        settings = options(parser.parse_args(["--reference", "unused", "--reference-note", "same"]))
        self.assertEqual(settings["name_style"], "pingfang_light")
        self.assertIsNone(settings["name_size"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self.fixture(root)
            project = root/"project.json"
            project.write_text(json.dumps({"schema": "pixel-art-to-beads/v1", "title": "菲欧妮",
                               "palette": {"colors": [{"code": "A", "rgb": [70, 80, 90]}]},
                               "cells": [["A", None], [None, "A"]]}))
            reference = root/"reference.png"
            Image.new("RGB", (800, 900), (70, 100, 120)).save(reference)
            before = project.read_bytes(), reference.read_bytes(), path.read_bytes()
            with self.fixture_environment(path):
                named = render_cover(project, reference, root/"named", **settings)
                plain = render_cover(project, reference, root/"plain", reference_note="same", show_name=False)
            for layer in ("foreground", "background"):
                self.assertEqual(named["products_sha256"][layer], plain["products_sha256"][layer])
            self.assertEqual(named["layout"]["name"]["text"], "「菲欧妮」")
            self.assertEqual(named["status"], "cover_ready_for_review")
            self.assertEqual((project.read_bytes(), reference.read_bytes(), path.read_bytes()), before)
            with patch("cover_lettering.PINGFANG_PATHS", ()), patch("cover_lettering.subprocess.run", side_effect=FileNotFoundError):
                with self.assertRaisesRegex(ValueError, "unavailable"):
                    render_cover(project, reference, root/"missing", reference_note="same")
            self.assertFalse((root/"missing").exists())


if __name__ == "__main__":
    unittest.main()
