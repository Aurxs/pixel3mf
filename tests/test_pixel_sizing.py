from __future__ import annotations

from decimal import Decimal
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_ROOT / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from lumina_batch import (  # noqa: E402
    _preview_form_data,
    _read_lumina_nozzle_width,
    build_pixel_size_plan,
)
from prepare_square_canvas import prepare_canvas, prepare_square  # noqa: E402
from cleanup_pixel import finalize_pixel_grid  # noqa: E402
from refine_pixel import (  # noqa: E402
    detect_source_grid,
    refine_mask_to_grid,
    refine_pixel,
    validate_detected_grid,
)


class PixelSizePlanTests(unittest.TestCase):
    def test_square_50_grid_maps_to_two_by_two_cells(self) -> None:
        plan = build_pixel_size_plan(50, 50, cells_per_logical_pixel=2)

        self.assertEqual(plan["expected_lumina_grid"], {"width": 100, "height": 100})
        self.assertEqual(plan["nominal_target_width_mm"], "42.00")
        self.assertEqual(plan["nominal_target_height_mm"], "42.00")
        self.assertEqual(plan["logical_pixel_pitch_mm"], "0.84")
        self.assertTrue(plan["exact_integer_mapping"])

    def test_square_50_grid_maps_to_three_by_three_cells(self) -> None:
        plan = build_pixel_size_plan(50, 50)

        self.assertEqual(plan["expected_lumina_grid"], {"width": 150, "height": 150})
        self.assertEqual(plan["nominal_target_width_mm"], "63.00")
        self.assertEqual(plan["nominal_target_height_mm"], "63.00")
        self.assertTrue(plan["exact_integer_mapping"])

    def test_rectangular_odd_grid_preserves_every_row(self) -> None:
        plan = build_pixel_size_plan(80, 79)

        self.assertEqual(plan["expected_lumina_grid"], {"width": 240, "height": 237})
        self.assertEqual(plan["simulated_lumina_grid"], {"width": 240, "height": 237})
        self.assertEqual(plan["nominal_target_width_mm"], "100.80")
        self.assertEqual(plan["nominal_target_height_mm"], "99.54")

    def test_decimal_boundary_width_does_not_lose_a_cell(self) -> None:
        plan = build_pixel_size_plan(62, 73)

        self.assertEqual(plan["nominal_target_width_mm"], "78.12")
        self.assertEqual(plan["expected_lumina_grid"], {"width": 186, "height": 219})
        self.assertEqual(plan["simulated_lumina_grid"], {"width": 186, "height": 219})

    def test_all_accepted_grid_pairs_map_exactly(self) -> None:
        for cells in (2, 3):
            for width in range(60, 86):
                for height in range(60, 86):
                    with self.subTest(cells=cells, width=width, height=height):
                        plan = build_pixel_size_plan(
                            width,
                            height,
                            cells_per_logical_pixel=cells,
                        )
                        self.assertEqual(
                            plan["simulated_lumina_grid"],
                            {"width": width * cells, "height": height * cells},
                        )

    def test_preview_form_uses_dynamic_width(self) -> None:
        params = {
            "target_width_mm": 100.8,
            "auto_bg": False,
            "bg_tol": 40,
            "modeling_mode": "pixel",
            "quantize_colors": 256,
            "enable_cleanup": True,
            "hue_weight": 0.6,
        }
        lut = {"name": "test-lut", "color_mode": "RYBW"}

        form = _preview_form_data(lut, params)

        self.assertEqual(form["target_width_mm"], "100.8")

    def test_reads_expected_lumina_nozzle_width_without_importing_lumina(self) -> None:
        value = _read_lumina_nozzle_width(PROJECT_ROOT / "Lumina-Layers")
        self.assertEqual(value, Decimal("0.42"))


class RectangularPreparationTests(unittest.TestCase):
    def test_canvas_preparation_preserves_rectangular_aspect(self) -> None:
        rgba = np.zeros((8, 10, 4), dtype=np.uint8)
        rgba[3:5, 3:7] = (20, 40, 60, 255)

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            rectangular = Path(tmp) / "rectangular.png"
            square = Path(tmp) / "square.png"
            Image.fromarray(rgba, "RGBA").save(source)

            rectangular_size = prepare_canvas(source, rectangular, padding_ratio=0.25)
            square_size = prepare_square(source, square, padding_ratio=0.25)

        self.assertEqual(rectangular_size, (6, 4))
        self.assertEqual(square_size, (6, 6))

    def test_refinement_keeps_detected_rectangular_grid_by_default(self) -> None:
        detected = np.zeros((79, 80, 4), dtype=np.uint8)
        detected[10:70, 10:70] = (20, 40, 60, 255)

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            output = Path(tmp) / "output.png"
            preview = Path(tmp) / "preview.png"
            Image.new("RGBA", (320, 316), (0, 0, 0, 0)).save(source)

            with patch(
                "refine_pixel.get_perfect_pixel",
                return_value=(80, 79, detected),
            ):
                metadata = refine_pixel(source, output, preview)

            with Image.open(output) as final_image:
                final_size = final_image.size
            with Image.open(preview) as preview_image:
                preview_size = preview_image.size

        self.assertEqual(final_size, (80, 79))
        self.assertEqual(preview_size, (640, 632))
        self.assertEqual(metadata["output_grid"], {"width": 80, "height": 79})
        self.assertFalse(metadata["square_output"])
        self.assertEqual(
            metadata["square_padding"], {"columns_added": 0, "rows_added": 0}
        )

    def test_source_density_boundaries_are_inclusive(self) -> None:
        validate_detected_grid(60, 85)
        validate_detected_grid(85, 60)
        with self.assertRaises(ValueError):
            validate_detected_grid(59, 85)
        with self.assertRaises(ValueError):
            validate_detected_grid(60, 86)

    def test_source_detection_failure_remains_a_hard_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            Image.new("RGBA", (120, 120), (20, 40, 60, 255)).save(source)
            with patch(
                "refine_pixel.get_perfect_pixel",
                return_value=(None, None, np.zeros((120, 120, 4), dtype=np.uint8)),
            ):
                with self.assertRaisesRegex(ValueError, "could not detect"):
                    detect_source_grid(source)

    def test_minor_soft_rendering_is_a_warning_not_a_failure(self) -> None:
        source_pixels = np.full((120, 120, 4), (30, 40, 50, 255), dtype=np.uint8)
        source_pixels[30:90, 30:90, :3] = (42, 52, 62)
        refined = np.full((60, 60, 4), (30, 40, 50, 255), dtype=np.uint8)

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            Image.fromarray(source_pixels, "RGBA").save(source)
            with patch(
                "refine_pixel.get_perfect_pixel",
                return_value=(60, 60, refined),
            ):
                metadata = detect_source_grid(source)

        self.assertEqual(metadata["width"], 60)
        self.assertIn(
            "minor_blur_antialiasing_or_whole_cell_tone_variation",
            metadata["warnings"],
        )

    def test_virtual_padding_round_trip_preserves_subject_and_internal_hole(self) -> None:
        refined = np.full((79, 75, 4), (20, 40, 60, 255), dtype=np.uint8)
        refined[30:34, 36:39] = (255, 255, 255, 0)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            working = root / "working.png"
            Image.new("RGBA", (300, 316), (0, 0, 0, 0)).save(source)
            with patch(
                "refine_pixel.get_perfect_pixel",
                return_value=(75, 79, refined),
            ):
                refinement = refine_pixel(
                    source,
                    working,
                    root / "working-preview.png",
                    working_padding_cells=2,
                )
            cleanup = finalize_pixel_grid(
                working,
                root / "export.png",
                root / "export-preview.png",
                background_rgb=[255, 255, 255],
                components_path=root / "components.json",
                overlay_path=root / "overlay.png",
            )
            result = np.asarray(Image.open(root / "export.png").convert("RGBA"))

        self.assertEqual(refinement["working_grid"], {"width": 79, "height": 83})
        self.assertEqual(cleanup["export_grid"], {"width": 75, "height": 79})
        np.testing.assert_array_equal(result, refined)
        plan_2x2 = build_pixel_size_plan(75, 79, cells_per_logical_pixel=2)
        plan_3x3 = build_pixel_size_plan(75, 79, cells_per_logical_pixel=3)
        self.assertEqual(
            (plan_2x2["nominal_target_width_mm"], plan_2x2["nominal_target_height_mm"]),
            ("63.00", "66.36"),
        )
        self.assertEqual(
            (plan_3x3["nominal_target_width_mm"], plan_3x3["nominal_target_height_mm"]),
            ("94.50", "99.54"),
        )

    def test_source_alpha_grid_uses_complete_virtual_cells(self) -> None:
        refined = np.zeros((60, 61, 4), dtype=np.uint8)
        refined[5:55, 6:56] = (20, 40, 60, 255)
        refined[30, 30, 3] = 0

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            output = root / "alpha-grid.png"
            Image.new("RGBA", (244, 240), (0, 0, 0, 0)).save(source)
            with patch(
                "refine_pixel.get_perfect_pixel",
                return_value=(61, 60, refined),
            ):
                metadata = refine_mask_to_grid(
                    source,
                    output,
                    expected_source_grid={"width": 61, "height": 60},
                    working_padding_cells=2,
                )
            result = np.asarray(Image.open(output).convert("L"))

        self.assertEqual(metadata["grid"], {"width": 65, "height": 64})
        self.assertEqual(set(np.unique(result).tolist()), {0, 255})
        self.assertTrue(np.all(result[:2] == 0))
        self.assertEqual(result[32, 32], 0)


if __name__ == "__main__":
    unittest.main()
