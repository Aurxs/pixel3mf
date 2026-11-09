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

from refine_pixel import _auto_detect_grid, _exact_fractional_grid, detect_source_grid, refine_pixel, refine_mask_to_grid


def regular_source(width: int, height: int, pitch: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(20261103)
    palette = np.array([[15, 30, 45, 255], [220, 100, 20, 255],
                        [60, 180, 140, 255], [255, 255, 255, 255]], dtype=np.uint8)
    logical = palette[rng.integers(0, len(palette), (height, width))]
    return logical.repeat(pitch, axis=0).repeat(pitch, axis=1), logical


def fractional_source(width: int, height: int, canvas: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    logical = regular_source(width, height, 1)[1]
    return np.asarray(Image.fromarray(logical).resize(canvas, Image.Resampling.NEAREST)).copy(), logical


class GridDetectionTests(unittest.TestCase):
    def detect(self, source: np.ndarray) -> tuple[int | None, int | None, np.ndarray]:
        with redirect_stdout(io.StringIO()):
            return _auto_detect_grid(source)

    def test_fractional_grid_round_trip_on_original_canvas(self) -> None:
        for width, height, canvas in ((49, 49, (1254, 1254)), (45, 80, (1151, 2047)),
                                      (80, 45, (2047, 1151))):
            with self.subTest(width=width, height=height):
                source, logical = fractional_source(width, height, canvas)
                original = source.copy()
                result = self.detect(source)
                self.assertEqual(result[:2], (width, height))
                np.testing.assert_array_equal(result[2], logical)
                np.testing.assert_array_equal(source, original)

    def test_regular_and_fractional_sources_outside_density_range_are_rejected(self) -> None:
        cases = [(style, width, height, 24)
                 for style in ("regular", "fractional")
                 for width, height in ((44, 45), (45, 44), (91, 90), (90, 91))]
        cases.append(("regular", 40, 40, 32))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.png"
            for style, width, height, pitch in cases:
                with self.subTest(style=style, grid=(width, height)):
                    if style == "fractional":
                        source, _ = fractional_source(width, height, (width * 25 + 7, height * 25 + 7))
                    else:
                        source, logical = regular_source(width, height, pitch)
                        detected = self.detect(source)
                        self.assertEqual(detected[:2], (width, height))
                        np.testing.assert_array_equal(detected[2], logical)
                    Image.fromarray(source).save(path)
                    original = path.read_bytes()
                    with redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, "45-90"):
                        detect_source_grid(path)
                    self.assertEqual(path.read_bytes(), original)

    def test_fractional_tie_breaking_and_exact_rgb_reconstruction(self) -> None:
        logical = regular_source(50, 50, 1)[1]
        extent, count = 1255, 50
        numerator = (2 * np.arange(extent, dtype=np.int64) + 1) * count
        self.assertFalse(np.array_equal(numerator // (2 * extent),
                                        (numerator - 1) // (2 * extent)))
        for offset in (0, -1):
            index = (numerator + offset) // (2 * extent)
            source = logical[index[:, None], index[None, :]]
            with self.subTest(offset=offset):
                result = _exact_fractional_grid(source)
                self.assertIsNotNone(result)
                width, height, sampled = result
                self.assertEqual((width, height), (50, 50))
                np.testing.assert_array_equal(sampled, logical)
                np.testing.assert_array_equal(sampled[index[:, None], index[None, :], :3], source[:, :, :3])

    def test_fractional_tie_does_not_create_false_blur_warning(self) -> None:
        logical = regular_source(80, 80, 1)[1]
        extent, count = 1960, 80
        index = (((2 * np.arange(extent, dtype=np.int64) + 1) * count) - 1) // (2 * extent)
        source = logical[index[:, None], index[None, :]]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'source.png'
            Image.fromarray(source).save(path)
            with redirect_stdout(io.StringIO()):
                result = detect_source_grid(path)
        self.assertEqual((result['width'], result['height']), (80, 80))
        self.assertNotIn('minor_blur_antialiasing_or_whole_cell_tone_variation', result['warnings'])
        self.assertEqual(result['render_metrics']['rgb_pixels_over_delta_8_fraction'], 0)

    def test_fractional_evidence_rejects_missing_extra_and_shifted_boundaries(self) -> None:
        source, logical = fractional_source(49, 49, (1254, 1254))
        # A silent logical boundary makes a finer grid unobservable.
        ambiguous = logical.copy()
        ambiguous[:, 10] = ambiguous[:, 9]
        ambiguous = np.asarray(Image.fromarray(ambiguous).resize((1254, 1254), Image.Resampling.NEAREST))
        noisy = source.copy()
        noisy[5, 5, 0] ^= 1
        shifted = np.roll(source, 5, axis=1)
        for candidate in (ambiguous, noisy, shifted):
            with self.subTest(kind=('ambiguous' if candidate is ambiguous else 'noisy' if candidate is noisy else 'shifted')):
                self.assertIsNone(_exact_fractional_grid(candidate))
                self.assertEqual(self.detect(candidate)[:2], (None, None))

    def test_fractional_evidence_rejects_mixed_widths_and_non_pixel_image(self) -> None:
        source, _ = fractional_source(49, 49, (1254, 1254))
        # Move one boundary only, introducing mixed logical widths.
        mixed = source.copy()
        mixed[:, 512:516] = mixed[:, 511:512]
        y, x = np.indices((512, 512))
        photo = np.stack((x % 256, y % 256, (x + y) % 256, np.full_like(x, 255)), axis=2).astype(np.uint8)
        for candidate in (mixed, photo):
            self.assertIsNone(_exact_fractional_grid(candidate))
            self.assertEqual(self.detect(candidate)[:2], (None, None))

    def test_fractional_mask_uses_same_original_cell_centers(self) -> None:
        source, logical = fractional_source(49, 49, (1254, 1254))
        rng = np.random.default_rng(9)
        mask = rng.integers(0, 256, source.shape[:2], dtype=np.uint8)
        # Recover centers independently from the known rasterizer mapping.
        index = ((2 * np.arange(1254) + 1) * 49) // (2 * 1254)
        edges = np.concatenate(([0], np.flatnonzero(np.diff(index)) + 1, [1254]))
        centers = (edges[:-1] + edges[1:]) // 2
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path, mask_path = root / 'source.png', root / 'mask.png'
            Image.fromarray(source).save(path)
            Image.fromarray(mask).save(mask_path)
            original = path.read_bytes(), mask_path.read_bytes()
            with redirect_stdout(io.StringIO()):
                grid = detect_source_grid(path)
                refine_pixel(path, root / 'grid.png', root / 'preview.png', expected_source_grid=grid)
                refine_mask_to_grid(path, root / 'alpha.png', expected_source_grid=grid, mask_path=mask_path)
            np.testing.assert_array_equal(np.asarray(Image.open(root / 'grid.png')), logical)
            np.testing.assert_array_equal(np.asarray(Image.open(root / 'alpha.png')), mask[centers[:, None], centers[None, :]])
            self.assertEqual((path.read_bytes(), mask_path.read_bytes()), original)

    def test_accepted_densities_with_coarse_cells_and_rectangular_canvas(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for width, height, pitch in ((45, 45, 24), (90, 90, 24), (45, 80, 24),
                                         (80, 45, 24), (64, 64, 16)):
                with self.subTest(width=width, height=height):
                    source, logical = regular_source(width, height, pitch)
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
