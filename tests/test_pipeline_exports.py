from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_ROOT / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import run_pipeline as pipeline_module  # noqa: E402


def _copy_image(source: str | Path, output: str | Path, *args, **kwargs) -> None:
    shutil.copyfile(source, output)


def _refine_image(
    source: str | Path,
    output: str | Path,
    preview: str | Path,
    *args,
    **kwargs,
) -> dict[str, object]:
    shutil.copyfile(source, output)
    shutil.copyfile(source, preview)
    return {"output_grid": {"width": 4, "height": 3}}


def _convert_variant(
    input_path: str | Path,
    zip_path: str | Path,
    final_path: str | Path,
    lumina_dir: str | Path,
    *args,
    preview_path: str | Path,
    size_plan: dict[str, object],
    cells_per_logical_pixel: int,
    **kwargs,
) -> dict[str, object]:
    Path(zip_path).write_bytes(b"zip")
    Path(final_path).write_bytes(b"3mf")
    Path(preview_path).write_bytes(b"png")
    return {
        "pixel_size_plan": size_plan,
        "cells_per_logical_pixel": cells_per_logical_pixel,
    }


class PipelineExportTests(unittest.TestCase):
    def test_pipeline_exports_two_by_two_and_three_by_three_3mfs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "source.png"
            Image.new("RGBA", (4, 3), (20, 40, 60, 255)).save(source)

            with (
                patch.object(pipeline_module, "remove_background", side_effect=_copy_image),
                patch.object(pipeline_module, "prepare_canvas", side_effect=_copy_image),
                patch.object(pipeline_module, "refine_pixel", side_effect=_refine_image),
                patch.object(pipeline_module, "cleanup_pixel", return_value={}),
                patch.object(
                    pipeline_module,
                    "convert_with_lumina_batch",
                    side_effect=_convert_variant,
                ) as convert,
            ):
                run_dir = pipeline_module.run_pipeline(
                    source,
                    character_name="test character",
                    output_root=tmp_path / "output",
                    official_character_research_status="not_applicable",
                )

            self.assertEqual(convert.call_count, 2)
            self.assertTrue((run_dir / "08_test-character_2x2.3mf").is_file())
            self.assertTrue((run_dir / "08_test-character_3x3.3mf").is_file())

            manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(set(manifest["final_3mfs"]), {"2x2", "3x3"})
            self.assertEqual(set(manifest["lumina"]["variants"]), {"2x2", "3x3"})
            self.assertEqual(
                manifest["perfect_pixel"]["pixel_size_plans"]["2x2"][
                    "expected_lumina_grid"
                ],
                {"width": 8, "height": 6},
            )
            self.assertEqual(
                manifest["perfect_pixel"]["pixel_size_plans"]["3x3"][
                    "expected_lumina_grid"
                ],
                {"width": 12, "height": 9},
            )


if __name__ == "__main__":
    unittest.main()
