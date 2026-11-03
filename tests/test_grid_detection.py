from __future__ import annotations

from contextlib import redirect_stdout
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from refine_pixel import _auto_detect_grid, detect_source_grid, refine_pixel, refine_mask_to_grid


def regular_source(width: int, height: int, pitch: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(20261103)
    palette = np.array([[15, 30, 45, 255], [220, 100, 20, 255],
                        [60, 180, 140, 255], [255, 255, 255, 255]], dtype=np.uint8)
    logical = palette[rng.integers(0, len(palette), (height, width))]
    return logical.repeat(pitch, axis=0).repeat(pitch, axis=1), logical


class GridDetectionTests(unittest.TestCase):
    def detect(self, source: np.ndarray) -> tuple[int | None, int | None, np.ndarray]:
        with redirect_stdout(io.StringIO()):
            return _auto_detect_grid(source)

    def test_regular_40_grid_is_detected_but_rejected_by_source_density_gate(self) -> None:
        source, logical = regular_source(40, 40, 32)
        original = source.copy()
        width, height, sampled = self.detect(source)
        self.assertEqual((width, height), (40, 40))
        np.testing.assert_array_equal(sampled, logical)
        np.testing.assert_array_equal(source, original)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.png"
            Image.fromarray(source).save(path)
            original_bytes = path.read_bytes()
            with redirect_stdout(io.StringIO()), self.assertRaisesRegex(
                ValueError, r"overly coarse source grid \(40x40\).*45-80"
            ):
                detect_source_grid(path)
            self.assertEqual(path.read_bytes(), original_bytes)

    def test_regular_64_grid_with_16_pixel_cells_still_passes(self) -> None:
        source, logical = regular_source(64, 64, 16)
        width, height, sampled = self.detect(source)
        self.assertEqual((width, height), (64, 64))
        np.testing.assert_array_equal(sampled, logical)

    def test_accepted_densities_with_coarse_cells_and_rectangular_canvas(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for width, height in ((45, 45), (48, 48), (45, 80), (80, 45), (80, 80)):
                with self.subTest(width=width, height=height):
                    source, logical = regular_source(width, height, 24)
                    path = root / "source.png"
                    Image.fromarray(source).save(path)
                    original = path.read_bytes()
                    with redirect_stdout(io.StringIO()):
                        detected = detect_source_grid(path)
                        refined = refine_pixel(path, root / "grid.png", root / "preview.png",
                                               expected_source_grid=detected)
                        refine_mask_to_grid(path, root / "alpha.png", expected_source_grid=detected)
                    self.assertEqual((detected["width"], detected["height"]), (width, height))
                    self.assertIsNone(refined["forced_grid"])
                    np.testing.assert_array_equal(np.asarray(Image.open(root / "grid.png")), logical)
                    self.assertEqual(path.read_bytes(), original)

    def test_irregular_cell_widths_are_not_promoted_to_a_regular_grid(self) -> None:
        source, _ = regular_source(40, 40, 32)
        # Shift alternating bands by non-cell offsets: no common coarse lattice exists.
        for band in range(40):
            source[band * 32:(band + 1) * 32] = np.roll(
                source[band * 32:(band + 1) * 32], band % 7, axis=1)
        width, height, _ = self.detect(source)
        self.assertEqual((width, height), (None, None))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "irregular.png"
            Image.fromarray(source).save(path)
            with redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, "could not detect"):
                detect_source_grid(path)

    def test_offset_grid_with_partial_border_cells_is_not_subdivided(self) -> None:
        source, _ = regular_source(40, 40, 32)
        source = np.roll(source, (16, 16), axis=(0, 1))
        width, height, _ = self.detect(source)
        self.assertEqual((width, height), (None, None))

    def test_recovered_grids_outside_acceptance_range_are_still_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.png"
            for width, height in ((44, 45), (45, 44), (81, 80), (80, 81)):
                with self.subTest(width=width, height=height):
                    source, _ = regular_source(width, height, 24)
                    Image.fromarray(source).save(path)
                    with redirect_stdout(io.StringIO()), self.assertRaisesRegex(
                        ValueError, rf"{width}x{height}.*45-80 cells per axis"
                    ):
                        detect_source_grid(path)

    def test_auxiliary_mask_is_sampled_on_the_same_rgb_lattice(self) -> None:
        source, _ = regular_source(50, 47, 24)
        rng = np.random.default_rng(7)
        alpha = rng.integers(0, 256, source.shape[:2], dtype=np.uint8)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path, mask = root / "source.png", root / "mask.png"
            Image.fromarray(source).save(path)
            Image.fromarray(alpha).save(mask)
            original_source, original_mask = path.read_bytes(), mask.read_bytes()
            with redirect_stdout(io.StringIO()):
                grid = detect_source_grid(path)
                refine_mask_to_grid(path, root / "sampled_alpha.png",
                                    expected_source_grid=grid, mask_path=mask)
            np.testing.assert_array_equal(np.asarray(Image.open(root / "sampled_alpha.png")),
                                          alpha[12::24, 12::24])
            self.assertEqual(path.read_bytes(), original_source)
            self.assertEqual(mask.read_bytes(), original_mask)

    def test_successful_upstream_detection_is_preserved_without_grid_override(self) -> None:
        source, logical = regular_source(64, 64, 16)
        result = (64, 64, logical)
        with patch("refine_pixel.get_perfect_pixel", return_value=result) as detector:
            self.assertIs(self.detect(source), result)
        detector.assert_called_once_with(source, sample_method="center", fix_square=False)

    def test_uniform_image_has_no_grid_and_unstructured_noise_is_rejected(self) -> None:
        width, height, _ = self.detect(np.full((512, 512, 4), 255, dtype=np.uint8))
        self.assertEqual((width, height), (None, None))
        rng = np.random.default_rng(10)
        source = rng.integers(0, 256, (512, 512, 4), dtype=np.uint8)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "noise.png"
            Image.fromarray(source).save(path)
            with redirect_stdout(io.StringIO()), self.assertRaises(ValueError):
                detect_source_grid(path)


if __name__ == "__main__":
    unittest.main()
