from __future__ import annotations

import hashlib
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


def _remove_background(source: str | Path, output: str | Path, *args, **kwargs):
    shutil.copyfile(source, output)
    with Image.open(source) as image:
        source_size = image.size
    Image.new("L", source_size, 255).save(kwargs["semantic_mask_path"])
    return {
        "background_rgb": [255, 255, 255],
        "background_color_tolerance": 12,
        "foreground_threshold": 0.8,
        "background_threshold": 0.2,
    }


def _refine_image(
    source: str | Path,
    output: str | Path,
    preview: str | Path,
    *args,
    **kwargs,
) -> dict[str, object]:
    shutil.copyfile(source, output)
    shutil.copyfile(source, preview)
    return {
        "source_grid": {"width": 4, "height": 3},
        "working_grid": {"width": 4, "height": 3},
        "output_grid": {"width": 4, "height": 3},
    }


def _finalize_image(
    source: str | Path,
    output: str | Path,
    preview: str | Path,
    *args,
    **kwargs,
) -> dict[str, object]:
    shutil.copyfile(source, output)
    shutil.copyfile(source, preview)
    Path(kwargs["components_path"]).write_text("{}\n", encoding="utf-8")
    Image.new("RGB", (4, 3), "white").save(kwargs["overlay_path"])
    return {"export_grid": {"width": 4, "height": 3}}


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
    def test_pipeline_rejects_non_cpu_segmentation_device(self) -> None:
        with self.assertRaisesRegex(ValueError, "CPU-only"):
            pipeline_module.run_pipeline(
                "/tmp/not-read.png",
                segmentation_device="coreml",
                official_character_research_status="not_applicable",
            )

    def test_source_density_failure_is_recorded_structurally(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "source.png"
            Image.new("RGBA", (4, 3), (20, 40, 60, 255)).save(source)
            with patch.object(
                pipeline_module,
                "detect_source_grid",
                side_effect=ValueError("detected source grid 59x86 is outside 60-85"),
            ):
                with self.assertRaisesRegex(ValueError, "59x86"):
                    pipeline_module.run_pipeline(
                        source,
                        character_name="density failure",
                        output_root=tmp_path / "output",
                        official_character_research_status="not_applicable",
                    )

            run_dirs = list((tmp_path / "output").iterdir())
            self.assertEqual(len(run_dirs), 1)
            manifest = json.loads(
                (run_dirs[0] / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                manifest["source_acceptance"]["density_gate"], "failed"
            )
            self.assertIn("59x86", manifest["source_acceptance"]["reason"])

    def test_pipeline_exports_two_by_two_and_three_by_three_3mfs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "source.png"
            Image.new("RGBA", (4, 3), (20, 40, 60, 255)).save(source)

            with (
                patch.object(
                    pipeline_module,
                    "detect_source_grid",
                    return_value={"width": 4, "height": 3},
                ),
                patch.object(
                    pipeline_module,
                    "remove_background",
                    side_effect=_remove_background,
                ),
                patch.object(pipeline_module, "refine_pixel", side_effect=_refine_image),
                patch.object(
                    pipeline_module,
                    "finalize_pixel_grid",
                    side_effect=_finalize_image,
                ),
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
            self.assertEqual(manifest["source_grid"], {"width": 4, "height": 3})
            self.assertEqual(manifest["working_grid"], {"width": 4, "height": 3})
            self.assertEqual(manifest["export_grid"], {"width": 4, "height": 3})
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

    def test_pipeline_reuses_requested_run_dir_and_records_generation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            run_dir = tmp_path / "output" / "workbuddy-run"
            run_dir.mkdir(parents=True)
            (run_dir / "workbuddy_state.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "run_id": run_dir.name,
                        "max_attempts": 3,
                        "route": "generate",
                        "attempts": [],
                        "pipeline_attempts": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            source = tmp_path / "source.png"
            Image.new("RGBA", (4, 3), (20, 40, 60, 255)).save(source)
            generation = {
                "version": 1,
                "provider": "tokenhub",
                "model": "hy-image-v3.0",
                "attempts": [{"number": 1, "task_id": "job-1"}],
                "selected_attempt": 1,
            }
            provenance = {
                "original_path": str(source),
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            }

            with (
                patch.object(
                    pipeline_module,
                    "detect_source_grid",
                    return_value={"width": 4, "height": 3},
                ),
                patch.object(
                    pipeline_module,
                    "remove_background",
                    side_effect=_remove_background,
                ),
                patch.object(pipeline_module, "refine_pixel", side_effect=_refine_image),
                patch.object(
                    pipeline_module,
                    "finalize_pixel_grid",
                    side_effect=_finalize_image,
                ),
                patch.object(
                    pipeline_module,
                    "convert_with_lumina_batch",
                    side_effect=_convert_variant,
                ),
            ):
                actual_run_dir = pipeline_module.run_pipeline(
                    source,
                    character_name="test character",
                    output_root=tmp_path / "ignored",
                    official_character_research_status="not_applicable",
                    run_dir=run_dir,
                    generation_metadata=generation,
                    source_provenance=provenance,
                )

            self.assertEqual(actual_run_dir, run_dir.resolve())
            manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["generation"], generation)
            self.assertEqual(manifest["source_provenance"], provenance)

    def test_requested_run_dir_rejects_existing_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "existing"
            run_dir.mkdir()
            (run_dir / "manifest.json").write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(FileExistsError, "already contains"):
                pipeline_module.run_pipeline(
                    "/tmp/not-read.png",
                    official_character_research_status="not_applicable",
                    run_dir=run_dir,
                )

    def test_requested_run_dir_rejects_unowned_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "existing"
            run_dir.mkdir()
            (run_dir / "important-user-file.txt").write_text("keep me\n", encoding="utf-8")
            with self.assertRaisesRegex(FileExistsError, "not owned"):
                pipeline_module.run_pipeline(
                    "/tmp/not-read.png",
                    official_character_research_status="not_applicable",
                    run_dir=run_dir,
                )
            self.assertEqual(
                (run_dir / "important-user-file.txt").read_text(encoding="utf-8"),
                "keep me\n",
            )

    def test_nonempty_requested_run_dir_requires_matching_workbuddy_owner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "existing"
            run_dir.mkdir()
            (run_dir / "01_source.png").write_bytes(b"source")
            with self.assertRaisesRegex(FileExistsError, "not owned"):
                pipeline_module.run_pipeline(
                    "/tmp/not-read.png",
                    official_character_research_status="not_applicable",
                    run_dir=run_dir,
                )

    def test_source_provenance_rejects_invalid_digest(self) -> None:
        with self.assertRaisesRegex(ValueError, "lowercase SHA-256"):
            pipeline_module.run_pipeline(
                "/tmp/not-read.png",
                official_character_research_status="not_applicable",
                source_provenance={
                    "original_path": "/tmp/original.png",
                    "sha256": "not-a-digest",
                },
            )

    def test_generation_metadata_rejects_sensitive_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "sensitive field"):
            pipeline_module.validate_generation_metadata(
                {
                    "version": 1,
                    "attempts": [],
                    "selected_attempt": None,
                    "api_key": "must-not-be-written",
                }
            )

    def test_generation_metadata_requires_supported_shape(self) -> None:
        with self.assertRaisesRegex(ValueError, "attempts must be a list"):
            pipeline_module.validate_generation_metadata(
                {
                    "version": 1,
                    "attempts": {},
                    "selected_attempt": None,
                }
            )

    def test_generation_metadata_rejects_unknown_camel_case_secret_field(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported fields"):
            pipeline_module.validate_generation_metadata(
                {
                    "version": 1,
                    "attempts": [{"number": 1, "apiKey": "secret"}],
                    "selected_attempt": None,
                }
            )

    def test_generation_metadata_redacts_signed_url_queries_and_bearer_values(self) -> None:
        value = pipeline_module.validate_generation_metadata(
            {
                "version": 1,
                "attempts": [
                    {
                        "number": 1,
                        "error": {
                            "type": "HTTPError",
                            "message": (
                                "Bearer secret-value at "
                                "https://bucket.cos.example/object?sign=secret"
                            ),
                        },
                    }
                ],
                "selected_attempt": None,
            }
        )
        message = value["attempts"][0]["error"]["message"]
        self.assertNotIn("secret-value", message)
        self.assertNotIn("sign=secret", message)
        self.assertIn("[REDACTED]", message)


if __name__ == "__main__":
    unittest.main()
