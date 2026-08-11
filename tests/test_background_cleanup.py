from __future__ import annotations

import sys
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from cleanup_pixel import cleanup_pixel  # noqa: E402
from remove_background import remove_background  # noqa: E402


class BackgroundRemovalTests(unittest.TestCase):
    def test_removes_diagonally_exterior_white_and_preserves_enclosed_white(self) -> None:
        rgba = np.full((7, 7, 4), 255, dtype=np.uint8)
        rgba[1:6, 1:6, :3] = (40, 60, 80)
        rgba[1, 1, :3] = 255
        rgba[3, 3, :3] = 255

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            output = Path(tmp) / "output.png"
            Image.fromarray(rgba, "RGBA").save(source)
            metadata = remove_background(source, output, method="white")
            result = np.asarray(Image.open(output).convert("RGBA"))

        self.assertEqual(result[1, 1, 3], 0)
        self.assertEqual(result[3, 3, 3], 255)
        self.assertGreater(metadata["removed_exterior_near_white_pixels"], 0)
        self.assertEqual(metadata["background_connectivity"], 8)

    def test_existing_alpha_cleans_only_exterior_near_white(self) -> None:
        rgba = np.zeros((7, 7, 4), dtype=np.uint8)
        rgba[1:6, 1:6] = (40, 60, 80, 255)
        rgba[1, 1] = (255, 255, 255, 255)
        rgba[3, 3] = (255, 255, 255, 255)

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            output = Path(tmp) / "output.png"
            Image.fromarray(rgba, "RGBA").save(source)
            metadata = remove_background(source, output)
            result = np.asarray(Image.open(output).convert("RGBA"))

        self.assertEqual(metadata["method"], "existing-alpha")
        self.assertEqual(result[1, 1, 3], 0)
        self.assertEqual(result[3, 3, 3], 255)

    def test_preserves_narrow_bridge_connected_to_white_subject_region(self) -> None:
        rgba = np.full((9, 9, 4), 255, dtype=np.uint8)
        rgba[2:7, 2:7, :3] = (40, 60, 80)
        rgba[3:6, 3:6, :3] = 255
        rgba[2, 4, :3] = 255

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            output = Path(tmp) / "output.png"
            Image.fromarray(rgba, "RGBA").save(source)
            metadata = remove_background(source, output, method="white")
            result = np.asarray(Image.open(output).convert("RGBA"))

        self.assertTrue(np.all(result[3:6, 3:6, 3] == 255))
        self.assertEqual(result[2, 4, 3], 255)
        self.assertEqual(metadata["narrow_bridge_guard_radius"], 1)
        self.assertGreater(metadata["preserved_interior_near_white_components"], 0)


class PixelCleanupTests(unittest.TestCase):
    def test_removes_tiny_edge_white_but_preserves_interior_white(self) -> None:
        rgba = np.zeros((9, 9, 4), dtype=np.uint8)
        rgba[2:7, 2:7] = (40, 60, 80, 255)
        rgba[2, 3] = (255, 255, 255, 255)
        rgba[4, 5] = (255, 255, 255, 255)

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            output = Path(tmp) / "output.png"
            preview = Path(tmp) / "preview.png"
            Image.fromarray(rgba, "RGBA").save(source)
            metadata = cleanup_pixel(source, output, preview_path=preview)
            result = np.asarray(Image.open(output).convert("RGBA"))
            with Image.open(preview) as preview_image:
                preview_size = preview_image.size

        self.assertEqual(result[2, 3, 3], 0)
        self.assertEqual(result[4, 5, 3], 255)
        self.assertEqual(metadata["removed_edge_white_pixels"], 1)
        self.assertFalse(metadata["deferred_review_recommended"])
        self.assertEqual(preview_size, (72, 72))

    def test_preserves_edge_white_connected_to_interior_white(self) -> None:
        rgba = np.zeros((7, 7, 4), dtype=np.uint8)
        rgba[2:5, 2:5] = (40, 60, 80, 255)
        rgba[2, 3] = (255, 255, 255, 255)
        rgba[3, 3] = (255, 255, 255, 255)

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            output = Path(tmp) / "output.png"
            Image.fromarray(rgba, "RGBA").save(source)
            metadata = cleanup_pixel(source, output)
            result = np.asarray(Image.open(output).convert("RGBA"))

        self.assertTrue(np.all(result[2:4, 3, 3] == 255))
        self.assertEqual(metadata["preserved_ambiguous_edge_white_components"], 1)
        self.assertTrue(metadata["deferred_review_recommended"])

    def test_preserves_larger_edge_white_component_and_records_recommendation(self) -> None:
        rgba = np.zeros((8, 8, 4), dtype=np.uint8)
        rgba[2:6, 2:6] = (40, 60, 80, 255)
        rgba[2, 2:5] = (255, 255, 255, 255)

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            output = Path(tmp) / "output.png"
            Image.fromarray(rgba, "RGBA").save(source)
            metadata = cleanup_pixel(source, output)
            result = np.asarray(Image.open(output).convert("RGBA"))

        self.assertTrue(np.all(result[2, 2:5, 3] == 255))
        self.assertEqual(metadata["preserved_ambiguous_edge_white_components"], 1)
        self.assertTrue(metadata["deferred_review_recommended"])

    def test_removes_isolated_colored_foreground_pixel(self) -> None:
        rgba = np.zeros((5, 5, 4), dtype=np.uint8)
        rgba[2, 2] = (255, 0, 0, 255)

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            output = Path(tmp) / "output.png"
            Image.fromarray(rgba, "RGBA").save(source)
            metadata = cleanup_pixel(source, output)
            result = np.asarray(Image.open(output).convert("RGBA"))

        self.assertEqual(result[2, 2, 3], 0)
        self.assertEqual(metadata["removed_isolated_foreground_pixels"], 1)


if __name__ == "__main__":
    unittest.main()
