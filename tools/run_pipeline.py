#!/usr/bin/env python3
"""Run source image -> transparent pixel art -> Lumina 3MF."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import shutil
import traceback

from PIL import Image

from cleanup_pixel import finalize_pixel_grid
from lumina_batch import (
    DEFAULT_PARAMS,
    LUT_FILENAME,
    build_pixel_size_plan,
    convert_with_lumina_batch,
)
from refine_pixel import detect_source_grid, refine_mask_to_grid, refine_pixel
from remove_background import ALPHA_POLICIES, remove_background


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPORT_CELL_VARIANTS = (2, 3)


def _slug(value: str) -> str:
    slug = re.sub(r"[^\w-]+", "-", value.strip().lower(), flags=re.UNICODE).strip("-_")
    return slug or "run"


def _new_run_dir(output_root: Path, character_name: str, now: datetime) -> Path:
    stem = f"{now.strftime('%Y%m%d_%H%M%S')}_{_slug(character_name)}"
    candidate = output_root / stem
    suffix = 2
    while candidate.exists():
        candidate = output_root / f"{stem}_{suffix}"
        suffix += 1
    candidate.mkdir(parents=True)
    return candidate


def _write_manifest(path: Path, manifest: dict[str, object]) -> None:
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_pipeline(
    source_image: str | Path,
    character_name: str | None = None,
    reference_image: str | Path | None = None,
    output_root: str | Path = "output",
    background_method: str = "auto",
    api_url: str = "http://127.0.0.1:8000",
    official_character_research_path: str | Path | None = None,
    official_character_sources: list[str] | None = None,
    official_character_research_status: str | None = None,
    square_output: bool = False,
    background_model: str = "auto",
    segmentation_device: str = "cpu",
    segmentation_memory_limit_gb: float = 8.0,
    working_padding_cells: int = 2,
    mask_override: str | Path | None = None,
    allow_ambiguous_mask: bool = False,
    alpha_policy: str = "auto",
) -> Path:
    started = datetime.now().astimezone()
    source_image = Path(source_image).expanduser().resolve()
    if character_name is None:
        character_name = source_image.stem
    output_root = Path(output_root)
    if not output_root.is_absolute():
        output_root = (PROJECT_ROOT / output_root).resolve()
    research_path = (
        Path(official_character_research_path).expanduser().resolve()
        if official_character_research_path
        else None
    )
    research_sources = list(official_character_sources or [])
    research_status = official_character_research_status or (
        "completed" if research_path or research_sources else "unknown"
    )
    if research_status not in {"completed", "not_applicable", "unknown"}:
        raise ValueError(
            "official_character_research_status must be completed, "
            "not_applicable, or unknown"
        )
    if research_status == "completed" and (research_path is None or not research_sources):
        raise ValueError(
            "completed official-character research requires a research file "
            "and at least one official source URL"
        )
    if research_path is not None and not research_path.is_file():
        raise FileNotFoundError(f"official research file not found: {research_path}")
    if working_padding_cells < 0:
        raise ValueError("working_padding_cells must be non-negative")
    if segmentation_device != "cpu":
        raise ValueError("segmentation_device is CPU-only and must be 'cpu'")
    if alpha_policy not in ALPHA_POLICIES:
        raise ValueError(f"unsupported alpha policy: {alpha_policy}")
    mask_override_path = (
        Path(mask_override).expanduser().resolve() if mask_override else None
    )
    if mask_override_path is not None and not mask_override_path.is_file():
        raise FileNotFoundError(f"mask override not found: {mask_override_path}")
    run_dir = _new_run_dir(output_root, character_name, started)
    research_output_path = None
    if research_path is not None:
        research_output_path = run_dir / "00_official_character_research.md"
        shutil.copy2(research_path, research_output_path)

    files = {
        "source": run_dir / "01_source.png",
        "semantic_mask": run_dir / "02_semantic_mask.png",
        "mask_review_overlay": run_dir / "02_mask_review_overlay.png",
        "mask_components": run_dir / "02_mask_components.json",
        "background_removed": run_dir / "02_bg_removed.png",
        "working_grid": run_dir / "03_working_grid.png",
        "working_grid_preview_8x": run_dir / "03_working_grid_preview_8x.png",
        "source_alpha_working_grid": run_dir / "03_source_alpha_working_grid.png",
        "pixel_perfect": run_dir / "04_pixel_perfect.png",
        "pixel_preview_8x": run_dir / "05_pixel_preview_8x.png",
        **{
            f"lumina_2d_preview_{cells}x{cells}": (
                run_dir / f"06_lumina_2d_preview_{cells}x{cells}.png"
            )
            for cells in EXPORT_CELL_VARIANTS
        },
        **{
            f"lumina_batch_zip_{cells}x{cells}": (
                run_dir / f"07_lumina_batch_result_{cells}x{cells}.zip"
            )
            for cells in EXPORT_CELL_VARIANTS
        },
        **{
            f"final_3mf_{cells}x{cells}": (
                run_dir / f"08_{_slug(character_name)}_{cells}x{cells}.3mf"
            )
            for cells in EXPORT_CELL_VARIANTS
        },
        "manifest": run_dir / "manifest.json",
    }
    if research_output_path is not None:
        files["official_character_research"] = research_output_path
    manifest: dict[str, object] = {
        "timestamp": started.isoformat(),
        "character_name": character_name,
        "input_image": str(source_image),
        "reference_image": str(Path(reference_image).expanduser().resolve()) if reference_image else None,
        "official_character_research_status": research_status,
        "official_character_research_path": (
            str(research_output_path) if research_output_path else None
        ),
        "official_character_sources": research_sources,
        "files": {key: str(path) for key, path in files.items()},
        "perfect_pixel": None,
        "source_acceptance": None,
        "source_grid": None,
        "working_grid": None,
        "export_grid": None,
        "pipeline_v2": {
            "enabled": True,
            "working_padding_cells": working_padding_cells,
            "allow_ambiguous_mask": allow_ambiguous_mask,
            "background_model": background_model,
            "segmentation_device": segmentation_device,
            "segmentation_memory_limit_gb": segmentation_memory_limit_gb,
            "mask_override": str(mask_override_path) if mask_override_path else None,
            "alpha_policy_requested": alpha_policy,
            "alpha_policy_effective": None,
        },
        "background_removal": None,
        "cleanup": None,
        "lumina": {
            "lut_filename": LUT_FILENAME,
            **DEFAULT_PARAMS,
            "variants": {},
        },
        "final_3mfs": {},
        "status": "running",
        "error": None,
    }
    _write_manifest(files["manifest"], manifest)

    try:
        if not source_image.is_file():
            raise FileNotFoundError(f"source image not found: {source_image}")
        with Image.open(source_image) as image:
            image.convert("RGBA").save(files["source"])

        source_grid = detect_source_grid(files["source"])
        manifest["source_acceptance"] = {
            "source_grid": {
                "width": source_grid["width"],
                "height": source_grid["height"],
            },
            "density_gate": "passed",
            "soft_rendering_policy": "warning-only",
            "warnings": source_grid.get("warnings", []),
            "render_metrics": source_grid.get("render_metrics", {}),
            "recoverable_conditions": [
                "minor_blur",
                "antialiasing",
                "near-identical-tones",
                "whole-cell-gradients",
            ],
        }
        manifest["source_grid"] = dict(manifest["source_acceptance"]["source_grid"])
        manifest["background_removal"] = remove_background(
            files["source"],
            files["background_removed"],
            background_method,
            background_model=background_model,
            segmentation_device=segmentation_device,
            segmentation_memory_limit_gb=segmentation_memory_limit_gb,
            semantic_mask_path=files["semantic_mask"],
            mask_override=mask_override_path,
            alpha_policy=alpha_policy,
            project_root=PROJECT_ROOT,
        )
        effective_alpha_policy = manifest["background_removal"].get(
            "alpha_policy_effective", "semantic"
        )
        manifest["pipeline_v2"]["alpha_policy_effective"] = (
            effective_alpha_policy
        )
        pixel_metadata = refine_pixel(
            files["background_removed"],
            files["working_grid"],
            files["working_grid_preview_8x"],
            expected_source_grid={
                "width": int(source_grid["width"]),
                "height": int(source_grid["height"]),
            },
            validate_source_density=False,
            working_padding_cells=working_padding_cells,
        )
        manifest["working_grid"] = dict(pixel_metadata["working_grid"])
        manifest["perfect_pixel"] = pixel_metadata
        source_alpha_metadata = None
        source_alpha_grid_path = None
        if effective_alpha_policy == "repair":
            source_alpha_grid_path = files["source_alpha_working_grid"]
            source_alpha_metadata = refine_mask_to_grid(
                files["source"],
                source_alpha_grid_path,
                expected_source_grid={
                    "width": int(source_grid["width"]),
                    "height": int(source_grid["height"]),
                },
                working_padding_cells=working_padding_cells,
                square_output=square_output,
            )
        manifest["pipeline_v2"]["source_alpha_working_grid"] = (
            source_alpha_metadata
        )
        cleanup_metadata = finalize_pixel_grid(
            files["working_grid"],
            files["pixel_perfect"],
            files["pixel_preview_8x"],
            background_rgb=manifest["background_removal"]["background_rgb"],
            components_path=files["mask_components"],
            overlay_path=files["mask_review_overlay"],
            alpha_policy=effective_alpha_policy,
            source_alpha_grid_path=source_alpha_grid_path,
            foreground_threshold=manifest["background_removal"][
                "foreground_threshold"
            ],
            background_threshold=manifest["background_removal"][
                "background_threshold"
            ],
            background_color_tolerance=manifest["background_removal"][
                "background_color_tolerance"
            ],
            allow_ambiguous=allow_ambiguous_mask,
            square_output=square_output,
        )
        manifest["cleanup"] = cleanup_metadata
        with Image.open(files["pixel_perfect"]) as final_pixel_image:
            final_width, final_height = final_pixel_image.size
        size_plans = {
            f"{cells}x{cells}": build_pixel_size_plan(
                final_width,
                final_height,
                cells_per_logical_pixel=cells,
            )
            for cells in EXPORT_CELL_VARIANTS
        }
        pixel_metadata["export_grid"] = {
            "width": final_width,
            "height": final_height,
        }
        pixel_metadata["final_output_grid"] = dict(pixel_metadata["export_grid"])
        pixel_metadata["cleanup"] = cleanup_metadata
        pixel_metadata["pixel_size_plans"] = size_plans
        manifest["perfect_pixel"] = pixel_metadata
        manifest["working_grid"] = dict(pixel_metadata["working_grid"])
        manifest["export_grid"] = dict(pixel_metadata["export_grid"])
        lumina_variants: dict[str, object] = {}
        final_3mfs: dict[str, str] = {}
        for cells in EXPORT_CELL_VARIANTS:
            variant = f"{cells}x{cells}"
            lumina_variants[variant] = convert_with_lumina_batch(
                files["pixel_perfect"],
                files[f"lumina_batch_zip_{variant}"],
                files[f"final_3mf_{variant}"],
                PROJECT_ROOT / "Lumina-Layers",
                api_url,
                preview_path=files[f"lumina_2d_preview_{variant}"],
                size_plan=size_plans[variant],
                cells_per_logical_pixel=cells,
            )
            final_3mfs[variant] = str(files[f"final_3mf_{variant}"])
            manifest["lumina"] = {
                "lut_filename": LUT_FILENAME,
                **DEFAULT_PARAMS,
                "variants": dict(lumina_variants),
            }
            manifest["final_3mfs"] = dict(final_3mfs)
            _write_manifest(files["manifest"], manifest)
        manifest["lumina"] = {
            "lut_filename": LUT_FILENAME,
            **DEFAULT_PARAMS,
            "variants": lumina_variants,
        }
        manifest["final_3mfs"] = final_3mfs
        manifest["status"] = "success"
        manifest["finished_at"] = datetime.now().astimezone().isoformat()
        _write_manifest(files["manifest"], manifest)
        return run_dir
    except Exception as exc:
        if manifest["cleanup"] is None and files["mask_components"].is_file():
            component_review = json.loads(
                files["mask_components"].read_text(encoding="utf-8")
            )
            manifest["cleanup"] = {
                "status": "blocked_before_export",
                "ambiguous_component_count": component_review.get(
                    "ambiguous_component_count", 0
                ),
                "components_path": str(files["mask_components"]),
                "overlay_path": str(files["mask_review_overlay"]),
            }
        manifest["status"] = "failed"
        manifest["finished_at"] = datetime.now().astimezone().isoformat()
        manifest["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
        _write_manifest(files["manifest"], manifest)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-image", required=True)
    parser.add_argument("--character-name")
    parser.add_argument("--reference-image")
    parser.add_argument(
        "--official-character-research-status",
        choices=("completed", "not_applicable", "unknown"),
        default=None,
    )
    parser.add_argument("--official-character-research-path")
    parser.add_argument(
        "--official-character-source",
        dest="official_character_sources",
        action="append",
        default=[],
        help="Official character source URL; repeat for multiple sources",
    )
    parser.add_argument("--output-root", default="output")
    parser.add_argument("--background-method", choices=("auto", "rembg", "white"), default="auto")
    parser.add_argument(
        "--background-model",
        choices=("auto", "isnet-anime", "isnet-general-use"),
        default="auto",
    )
    parser.add_argument(
        "--segmentation-device",
        choices=("cpu",),
        default="cpu",
    )
    parser.add_argument("--segmentation-memory-limit-gb", type=float, default=8.0)
    parser.add_argument("--working-padding-cells", type=int, default=2)
    parser.add_argument("--mask-override")
    parser.add_argument("--alpha-policy", choices=ALPHA_POLICIES, default="auto")
    parser.add_argument("--allow-ambiguous-mask", action="store_true")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--square-output",
        action="store_true",
        help="Explicitly pad the prepared and refined canvases to a square",
    )
    args = parser.parse_args()
    run_dir = run_pipeline(
        source_image=args.source_image,
        character_name=args.character_name,
        reference_image=args.reference_image,
        output_root=args.output_root,
        background_method=args.background_method,
        api_url=args.api_url,
        official_character_research_path=args.official_character_research_path,
        official_character_sources=args.official_character_sources,
        official_character_research_status=args.official_character_research_status,
        square_output=args.square_output,
        background_model=args.background_model,
        segmentation_device=args.segmentation_device,
        segmentation_memory_limit_gb=args.segmentation_memory_limit_gb,
        working_padding_cells=args.working_padding_cells,
        mask_override=args.mask_override,
        allow_ambiguous_mask=args.allow_ambiguous_mask,
        alpha_policy=args.alpha_policy,
    )
    print(run_dir)


if __name__ == "__main__":
    main()
