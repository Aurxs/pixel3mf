"""Transparent RGB must not join or vote in semantic foreground components."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


def load_cleanup(relative_path: str):
    spec = importlib.util.spec_from_file_location(relative_path, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


IMPLEMENTATIONS = {
    name: load_cleanup(name)
    for name in ("tools/cleanup_pixel.py", "tools/beads/cleanup_pixel.py")
}


class HiddenRGBRegressionTests(unittest.TestCase):
    def finalize(self, module, rgba, root):
        source = root / "source.png"
        Image.fromarray(rgba).save(source)
        metadata = module.finalize_pixel_grid(
            source,
            root / "output.png",
            root / "preview.png",
            background_rgb=[255, 255, 255],
            components_path=root / "components.json",
            overlay_path=root / "overlay.png",
        )
        result = np.asarray(Image.open(root / "output.png").convert("RGBA"))
        return metadata, result

    def test_hidden_rgb_cannot_erase_eye_white_or_white_clothing(self):
        rgba = np.zeros((11, 11, 4), dtype=np.uint8)
        rgba[2:9, 2:9] = (30, 40, 50, 255)
        rgba[2:4, 2:4] = (255, 255, 255, 255)  # eye white at outline
        rgba[6:9, 2:9] = (255, 255, 255, 255)  # white clothing
        for name, module in IMPLEMENTATIONS.items():
            for hidden_rgb in ((255, 255, 255), (0, 0, 0), (73, 144, 203)):
                with self.subTest(implementation=name, hidden_rgb=hidden_rgb):
                    source = rgba.copy()
                    source[source[:, :, 3] == 0, :3] = hidden_rgb
                    with tempfile.TemporaryDirectory() as tmp:
                        metadata, result = self.finalize(module, source, Path(tmp))
                    np.testing.assert_array_equal(result, rgba[2:9, 2:9])
                    self.assertEqual(metadata["final_foreground_cells_before_crop"], 49)
                    self.assertEqual(metadata["ambiguous_component_count"], 0)

    def test_white_foreground_cannot_fill_transparent_internal_hole(self):
        rgba = np.full((9, 9, 4), (30, 40, 50, 255), dtype=np.uint8)
        rgba[2:7, 2:7] = (255, 255, 255, 255)
        rgba[4, 4, 3] = 0
        for name, module in IMPLEMENTATIONS.items():
            with self.subTest(implementation=name), tempfile.TemporaryDirectory() as tmp:
                _, result = self.finalize(module, rgba, Path(tmp))
                np.testing.assert_array_equal(result, rgba)

    def test_transparent_white_bridge_cannot_hide_semantic_ambiguity(self):
        rgba = np.full((9, 9, 4), (30, 40, 50, 255), dtype=np.uint8)
        rgba[4, 1:8] = (255, 255, 255, 0)
        rgba[4, 2, 3] = 128  # unresolved white, separated by transparent cells
        rgba[4, 6, 3] = 255  # confident white
        for name, module in IMPLEMENTATIONS.items():
            with self.subTest(implementation=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                with self.assertRaises(module.AmbiguousMaskError):
                    self.finalize(module, rgba, root)
                self.assertTrue((root / "components.json").is_file())
                self.assertTrue((root / "overlay.png").is_file())
                self.assertFalse((root / "output.png").exists())

    def test_nonzero_mixed_confidence_still_requires_review(self):
        rgba = np.full((9, 9, 4), (30, 40, 50, 255), dtype=np.uint8)
        rgba[4, 3:6, :3] = 255
        rgba[4, 3:6, 3] = (32, 160, 240)
        for name, module in IMPLEMENTATIONS.items():
            with self.subTest(implementation=name), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(module.AmbiguousMaskError):
                    self.finalize(module, rgba, Path(tmp))


if __name__ == "__main__":
    unittest.main()
