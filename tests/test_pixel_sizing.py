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
from refine_pixel import refine_pixel  # noqa: E402


class PixelSizePlanTests(unittest.TestCase):
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
        for width in range(60, 86):
            for height in range(60, 86):
                with self.subTest(width=width, height=height):
                    plan = build_pixel_size_plan(width, height)
                    self.assertEqual(
                        plan["simulated_lumina_grid"],
                        {"width": width * 3, "height": height * 3},
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


if __name__ == "__main__":
    unittest.main()
