from __future__ import annotations

import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from cleanup_pixel import (  # noqa: E402
    AmbiguousMaskError,
    cleanup_pixel,
    finalize_pixel_grid,
)
from remove_background import remove_background  # noqa: E402


class BackgroundRemovalTests(unittest.TestCase):
    def test_mask_override_must_be_binary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = Image.new("RGB", (4, 4), "white")
            source.save(root / "source.png")
            Image.new("L", (4, 4), 128).save(root / "mask.png")

            with self.assertRaisesRegex(ValueError, "must be binary"):
                remove_background(
                    root / "source.png",
                    root / "output.png",
                    mask_override=root / "mask.png",
                )

    def test_nonwhite_solid_background_uses_border_color_and_keeps_white_subject(self) -> None:
        rgba = np.full((9, 9, 4), (20, 120, 200, 255), dtype=np.uint8)
        rgba[2:7, 2:7] = (40, 50, 60, 255)
        rgba[4, 4] = (255, 255, 255, 255)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            Image.fromarray(rgba, "RGBA").save(source)

            def fake_segment(source_path, mask_path, **kwargs):
                mask = np.zeros((9, 9), dtype=np.uint8)
                mask[2:7, 2:7] = 255
                Image.fromarray(mask, "L").save(mask_path)
                return {
                    "model": kwargs["model_name"],
                    "requested_device": kwargs["device"],
                    "active_providers": ["CPUExecutionProvider"],
                }

            with patch(
                "remove_background.run_segmentation_model",
                side_effect=fake_segment,
            ):
                metadata = remove_background(source, root / "output.png")
            result = np.asarray(Image.open(root / "output.png").convert("RGBA"))

        self.assertEqual(metadata["background_rgb"], [20, 120, 200])
        self.assertEqual(result[0, 0, 3], 0)
        self.assertEqual(result[4, 4, 3], 255)

    def test_general_model_adjudicates_enclosed_white_hole(self) -> None:
        rgba = np.full((11, 11, 4), (255, 255, 255, 255), dtype=np.uint8)
        rgba[2:9, 2:9] = (40, 50, 60, 255)
        rgba[4, 4] = (255, 255, 255, 255)  # background gap
        rgba[6, 6] = (255, 255, 255, 255)  # semantic eye/highlight

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            Image.fromarray(rgba, "RGBA").save(source)

            def fake_segment(source_path, mask_path, **kwargs):
                mask = np.zeros((11, 11), dtype=np.uint8)
                mask[2:9, 2:9] = 255
                if kwargs["model_name"] == "isnet-general-use":
                    mask[4, 4] = 40
                Image.fromarray(mask, "L").save(mask_path)
                return {
                    "model": kwargs["model_name"],
                    "requested_device": kwargs["device"],
                    "active_providers": ["CPUExecutionProvider"],
                }

            with patch(
                "remove_background.run_segmentation_model",
                side_effect=fake_segment,
            ) as segment:
                metadata = remove_background(source, root / "output.png")
            result = np.asarray(Image.open(root / "output.png").convert("RGBA"))

        self.assertEqual(segment.call_count, 2)
        self.assertTrue(metadata["fallback_model_used"])
        self.assertLessEqual(result[4, 4, 3], 51)
        self.assertEqual(result[6, 6, 3], 255)

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

    def test_existing_alpha_repair_does_not_color_key_opaque_white(self) -> None:
        rgba = np.zeros((7, 7, 4), dtype=np.uint8)
        rgba[1:6, 1:6] = (40, 60, 80, 255)
        rgba[1, 1] = (255, 255, 255, 255)
        rgba[3, 3] = (255, 255, 255, 255)

        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            output = Path(tmp) / "output.png"
            Image.fromarray(rgba, "RGBA").save(source)
            def fake_segment(source_path, mask_path, **kwargs):
                alpha = Image.open(source_path).convert("RGBA").getchannel("A")
                alpha.save(mask_path)
                return {
                    "model": kwargs["model_name"],
                    "requested_device": kwargs["device"],
                    "active_providers": ["CPUExecutionProvider"],
                }

            with patch("remove_background.run_segmentation_model", side_effect=fake_segment):
                metadata = remove_background(source, output)
            result = np.asarray(Image.open(output).convert("RGBA"))

        self.assertEqual(metadata["method"], "existing-alpha-repair")
        self.assertEqual(metadata["background_rgb"], None)
        self.assertEqual(result[1, 1, 3], 255)
        self.assertEqual(result[3, 3, 3], 255)

    def test_preserve_keeps_binary_alpha_and_hidden_black_rgb_exactly(self) -> None:
        rgba = np.zeros((7, 7, 4), dtype=np.uint8)
        rgba[1:6, 1:6] = (0, 0, 0, 255)
        rgba[2:5, 2:5] = (80, 40, 20, 255)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            output = root / "output.png"
            Image.fromarray(rgba, "RGBA").save(source)
            with patch("remove_background.run_segmentation_model") as segment:
                metadata = remove_background(
                    source, output, alpha_policy="preserve"
                )
            result = np.asarray(Image.open(output).convert("RGBA"))

        segment.assert_not_called()
        np.testing.assert_array_equal(result[:, :, 3], rgba[:, :, 3])
        self.assertEqual(metadata["alpha_policy_effective"], "preserve")
        self.assertIsNone(metadata["background_rgb"])

    def test_mask_override_is_authoritative_and_skips_models(self) -> None:
        rgba = np.zeros((6, 6, 4), dtype=np.uint8)
        rgba[:, :, 3] = 255
        rgba[0, 0, 3] = 128
        override = np.zeros((6, 6), dtype=np.uint8)
        override[1:5, 1:5] = 255

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            mask = root / "mask.png"
            output = root / "output.png"
            Image.fromarray(rgba, "RGBA").save(source)
            Image.fromarray(override, "L").save(mask)
            with patch("remove_background.run_segmentation_model") as segment:
                metadata = remove_background(
                    source, output, mask_override=mask
                )
            result = np.asarray(Image.open(output).convert("RGBA"))

        segment.assert_not_called()
        np.testing.assert_array_equal(result[:, :, 3], override)
        self.assertEqual(metadata["alpha_policy_effective"], "mask-override")

    def test_partial_cutout_requires_two_model_agreement_for_repairs(self) -> None:
        rgba = np.zeros((7, 7, 4), dtype=np.uint8)
        rgba[1:6, 1:6] = (0, 0, 0, 255)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            output = root / "output.png"
            Image.fromarray(rgba, "RGBA").save(source)

            model_inputs = []

            def fake_segment(source_path, mask_path, **kwargs):
                model_input = np.asarray(
                    Image.open(source_path).convert("RGBA")
                )
                model_inputs.append(model_input)
                mask = rgba[:, :, 3].copy()
                mask[3, 3] = 0
                mask[3, 4] = 0 if kwargs["model_name"] == "isnet-anime" else 255
                Image.fromarray(mask, "L").save(mask_path)
                return {"model": kwargs["model_name"]}

            with patch(
                "remove_background.run_segmentation_model",
                side_effect=fake_segment,
            ) as segment:
                metadata = remove_background(source, output)
            result = np.asarray(Image.open(output).convert("RGBA"))

        self.assertEqual(segment.call_count, 2)
        self.assertTrue(all(np.all(item[:, :, 3] == 255) for item in model_inputs))
        self.assertTrue(all(np.all(item[0, 0, :3] == 255) for item in model_inputs))
        self.assertEqual(result[3, 3, 3], 0)
        self.assertIn(result[3, 4, 3], (127, 128))
        self.assertEqual(result[0, 0, 3], 0)
        self.assertEqual(metadata["repair_approved_pixels"], 1)
        self.assertEqual(metadata["repair_ambiguous_pixels"], 1)

    def test_nonbinary_existing_alpha_is_rejected(self) -> None:
        rgba = np.full((5, 5, 4), (20, 40, 60, 255), dtype=np.uint8)
        rgba[0, 0, 3] = 128
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            Image.fromarray(rgba, "RGBA").save(source)
            with self.assertRaisesRegex(ValueError, "must be binary"):
                remove_background(source, root / "output.png")

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

    def test_semantic_cleanup_removes_hair_gap_and_preserves_eye_white(self) -> None:
        rgba = np.zeros((9, 9, 4), dtype=np.uint8)
        rgba[2:7, 2:7] = (40, 50, 60, 255)
        rgba[3, 3] = (255, 255, 255, 20)  # background hole
        rgba[4, 5] = (255, 255, 255, 250)  # eye/highlight

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            output = root / "output.png"
            preview = root / "preview.png"
            components = root / "components.json"
            overlay = root / "overlay.png"
            Image.fromarray(rgba, "RGBA").save(source)
            metadata = finalize_pixel_grid(
                source,
                output,
                preview,
                background_rgb=[255, 255, 255],
                components_path=components,
                overlay_path=overlay,
            )
            result = np.asarray(Image.open(output).convert("RGBA"))

        self.assertEqual(result[1, 1, 3], 0)
        self.assertEqual(result[2, 3, 3], 255)
        self.assertEqual(metadata["export_grid"], {"width": 5, "height": 5})
        self.assertEqual(metadata["alpha_values"], [0, 255])

    def test_general_model_component_consensus_removes_soft_hair_gap(self) -> None:
        rgba = np.zeros((9, 9, 4), dtype=np.uint8)
        rgba[1:8, 1:8] = (40, 50, 60, 255)
        rgba[2:5, 3] = (255, 255, 255, 80)
        rgba[5, 5] = (255, 255, 255, 250)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            Image.fromarray(rgba, "RGBA").save(source)
            metadata = finalize_pixel_grid(
                source,
                root / "output.png",
                root / "preview.png",
                background_rgb=[255, 255, 255],
                components_path=root / "components.json",
                overlay_path=root / "overlay.png",
            )
            result = np.asarray(Image.open(root / "output.png").convert("RGBA"))

        self.assertTrue(np.all(result[1:4, 2, 3] == 0))
        self.assertEqual(result[4, 4, 3], 255)
        self.assertEqual(metadata["ambiguous_component_count"], 0)

    def test_ambiguous_semantic_component_blocks_export(self) -> None:
        rgba = np.zeros((7, 7, 4), dtype=np.uint8)
        rgba[1:6, 1:6] = (40, 50, 60, 255)
        rgba[3, 3] = (255, 255, 255, 128)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            Image.fromarray(rgba, "RGBA").save(source)
            with self.assertRaises(AmbiguousMaskError):
                finalize_pixel_grid(
                    source,
                    root / "output.png",
                    root / "preview.png",
                    background_rgb=[255, 255, 255],
                    components_path=root / "components.json",
                    overlay_path=root / "overlay.png",
                )
            self.assertTrue((root / "components.json").is_file())
            self.assertTrue((root / "overlay.png").is_file())

    def test_preserve_policy_keeps_isolated_black_pixel(self) -> None:
        rgba = np.zeros((5, 5, 4), dtype=np.uint8)
        rgba[2, 2] = (0, 0, 0, 255)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.png"
            Image.fromarray(rgba, "RGBA").save(source)
            metadata = finalize_pixel_grid(
                source,
                root / "output.png",
                root / "preview.png",
                background_rgb=None,
                components_path=root / "components.json",
                overlay_path=root / "overlay.png",
                alpha_policy="preserve",
            )
            result = np.asarray(Image.open(root / "output.png").convert("RGBA"))

        self.assertEqual(result.shape[:2], (1, 1))
        self.assertEqual(result[0, 0, 3], 255)
        self.assertEqual(metadata["removed_isolated_foreground_pixels"], 0)

    def test_repair_removes_internal_hole_but_protects_one_cell_outline(self) -> None:
        source_alpha = np.zeros((9, 9), dtype=np.uint8)
        source_alpha[1:8, 1:8] = 255
        rgba = np.zeros((9, 9, 4), dtype=np.uint8)
        rgba[1:8, 1:8] = (0, 0, 0, 255)
        rgba[1, 4, 3] = 0
        rgba[4, 4, 3] = 0

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            Image.fromarray(rgba, "RGBA").save(root / "working.png")
            Image.fromarray(source_alpha, "L").save(root / "source-alpha.png")
            metadata = finalize_pixel_grid(
                root / "working.png",
                root / "output.png",
                root / "preview.png",
                background_rgb=None,
                components_path=root / "components.json",
                overlay_path=root / "overlay.png",
                alpha_policy="repair",
                source_alpha_grid_path=root / "source-alpha.png",
            )
            result = np.asarray(Image.open(root / "output.png").convert("RGBA"))

        self.assertEqual(result[0, 3, 3], 255)
        self.assertEqual(result[3, 3, 3], 0)
        self.assertEqual(metadata["approved_repair_cells"], 1)
        self.assertEqual(metadata["protected_boundary_cells"], 1)

    def test_repair_ambiguity_blocks_before_export(self) -> None:
        source_alpha = np.zeros((9, 9), dtype=np.uint8)
        source_alpha[1:8, 1:8] = 255
        rgba = np.zeros((9, 9, 4), dtype=np.uint8)
        rgba[1:8, 1:8] = (20, 30, 40, 255)
        rgba[4, 4, 3] = 128

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            Image.fromarray(rgba, "RGBA").save(root / "working.png")
            Image.fromarray(source_alpha, "L").save(root / "source-alpha.png")
            with self.assertRaises(AmbiguousMaskError):
                finalize_pixel_grid(
                    root / "working.png",
                    root / "output.png",
                    root / "preview.png",
                    background_rgb=None,
                    components_path=root / "components.json",
                    overlay_path=root / "overlay.png",
                    alpha_policy="repair",
                    source_alpha_grid_path=root / "source-alpha.png",
                )
            payload = __import__("json").loads(
                (root / "components.json").read_text(encoding="utf-8")
            )

        self.assertEqual(payload["ambiguous_component_count"], 1)


if __name__ == "__main__":
    unittest.main()
