#!/usr/bin/env python3
"""Run source image -> transparent pixel art -> Lumina 3MF."""

from __future__ import annotations

import argparse
import copy
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
GENERATION_METADATA_VERSION = 1
_SENSITIVE_METADATA_KEYS = {
    "access_key",
    "api_key",
    "authorization",
    "bearer",
    "credential",
    "password",
    "secret",
    "secret_id",
    "secret_key",
}
_GENERATION_KEYS = {
    "version",
    "provider",
    "model",
    "logo_add",
    "attempts",
    "selected_attempt",
}
_ATTEMPT_KEYS = {
    "number",
    "created_at",
    "finished_at",
    "file",
    "provider",
    "model",
    "logo_add",
    "prompt_sha256",
    "reference_files",
    "reference_transport",
    "task_id",
    "request_id",
    "submission_mode",
    "objective_validation",
    "visual_decision",
    "visual_reason",
    "cos_objects",
    "cos_cleanup",
    "duration_seconds",
    "status",
    "error",
}
_OBJECTIVE_KEYS = {
    "passed",
    "fully_opaque",
    "pure_white_border",
    "detected_grid",
    "reasons",
}


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


def _contains_sensitive_metadata(value: object, path: str = "generation") -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if normalized in _SENSITIVE_METADATA_KEYS or normalized.endswith("_password"):
                return f"{path}.{key}"
            found = _contains_sensitive_metadata(child, f"{path}.{key}")
            if found:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = _contains_sensitive_metadata(child, f"{path}[{index}]")
            if found:
                return found
    return None


def _require_allowed_keys(value: dict[str, object], allowed: set[str], path: str) -> None:
    unexpected = sorted(set(value) - allowed)
    if unexpected:
        raise ValueError(f"{path} contains unsupported fields: {', '.join(unexpected)}")


def _sanitize_metadata_string(value: str) -> str:
    sanitized = re.sub(
        r"(?i)(authorization\s*[:=]\s*bearer\s+|bearer\s+)[^\s\"']+",
        lambda match: match.group(1) + "[REDACTED]",
        value,
    )
    sanitized = re.sub(
        r"(https?://[^\s?\"']+)\?[^\s\"']+",
        r"\1?[REDACTED_QUERY]",
        sanitized,
    )
    return sanitized


def _sanitize_metadata_values(value: object) -> object:
    if isinstance(value, dict):
        return {key: _sanitize_metadata_values(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_sanitize_metadata_values(child) for child in value]
    if isinstance(value, str):
        return _sanitize_metadata_string(value)
    return value


def _validate_generation_schema(value: dict[str, object]) -> None:
    _require_allowed_keys(value, _GENERATION_KEYS, "generation_metadata")
    attempts = value.get("attempts")
    assert isinstance(attempts, list)
    for index, attempt in enumerate(attempts):
        path = f"generation_metadata.attempts[{index}]"
        if not isinstance(attempt, dict):
            raise ValueError(f"{path} must be an object")
        _require_allowed_keys(attempt, _ATTEMPT_KEYS, path)
        objective = attempt.get("objective_validation")
        if objective is not None:
            if not isinstance(objective, dict):
                raise ValueError(f"{path}.objective_validation must be an object or null")
            _require_allowed_keys(objective, _OBJECTIVE_KEYS, f"{path}.objective_validation")
            grid = objective.get("detected_grid")
            if grid is not None:
                if not isinstance(grid, dict):
                    raise ValueError(f"{path}.objective_validation.detected_grid must be an object or null")
                _require_allowed_keys(
                    grid,
                    {"width", "height"},
                    f"{path}.objective_validation.detected_grid",
                )
        error = attempt.get("error")
        if error is not None:
            if not isinstance(error, dict):
                raise ValueError(f"{path}.error must be an object or null")
            _require_allowed_keys(error, {"type", "message"}, f"{path}.error")
        cleanup = attempt.get("cos_cleanup")
        if cleanup is not None:
            if not isinstance(cleanup, list):
                raise ValueError(f"{path}.cos_cleanup must be a list")
            for cleanup_index, item in enumerate(cleanup):
                if not isinstance(item, dict):
                    raise ValueError(f"{path}.cos_cleanup[{cleanup_index}] must be an object")
                _require_allowed_keys(
                    item,
                    {"key", "deleted", "error"},
                    f"{path}.cos_cleanup[{cleanup_index}]",
                )


def validate_generation_metadata(value: object | None) -> dict[str, object] | None:
    """Validate JSON-safe WorkBuddy generation provenance before persisting it."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("generation_metadata must be a JSON object")
    if value.get("version") != GENERATION_METADATA_VERSION:
        raise ValueError(
            f"generation_metadata.version must be {GENERATION_METADATA_VERSION}"
        )
    attempts = value.get("attempts")
    if not isinstance(attempts, list):
        raise ValueError("generation_metadata.attempts must be a list")
    selected_attempt = value.get("selected_attempt")
    if selected_attempt is not None and (
        not isinstance(selected_attempt, int) or selected_attempt <= 0
    ):
        raise ValueError("generation_metadata.selected_attempt must be a positive integer or null")
    sensitive_path = _contains_sensitive_metadata(value)
    if sensitive_path:
        raise ValueError(f"generation_metadata contains a sensitive field: {sensitive_path}")
    _validate_generation_schema(value)
    sanitized = _sanitize_metadata_values(value)
    try:
        encoded = json.dumps(sanitized, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("generation_metadata must contain only finite JSON values") from exc
    return copy.deepcopy(json.loads(encoded))


def _prepare_run_dir(
    output_root: Path,
    character_name: str,
    started: datetime,
    requested_run_dir: str | Path | None,
) -> Path:
    if requested_run_dir is None:
        return _new_run_dir(output_root, character_name, started)
    run_dir = Path(requested_run_dir).expanduser().resolve()
    manifest_path = run_dir / "manifest.json"
    if manifest_path.exists():
        raise FileExistsError(
            f"run directory already contains a pipeline manifest: {manifest_path}"
        )
    if run_dir.exists():
        allowed_names = {
            "workbuddy_state.json",
            "01_source.png",
            "references",
            "pipeline_failures",
        }
        unexpected = [
            entry.name
            for entry in run_dir.iterdir()
            if entry.name not in allowed_names
            and not entry.name.startswith("00_")
            and not entry.name.startswith("01_source_attempt_")
        ]
        if unexpected:
            raise FileExistsError(
                "requested run directory contains files not owned by the WorkBuddy "
                f"orchestrator: {', '.join(sorted(unexpected))}"
            )
        entries = list(run_dir.iterdir())
        if entries:
            symlinks = [entry.name for entry in entries if entry.is_symlink()]
            if symlinks:
                raise FileExistsError(
                    "requested run directory contains unsafe symbolic links: "
                    + ", ".join(sorted(symlinks))
                )
            state_path = run_dir / "workbuddy_state.json"
            if not state_path.is_file():
                raise FileExistsError(
                    "non-empty requested run directory is not owned by the "
                    "WorkBuddy orchestrator"
                )
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise FileExistsError("WorkBuddy run ownership file is invalid") from exc
            valid_owner = (
                isinstance(state, dict)
                and state.get("version") == 1
                and state.get("run_id") == run_dir.name
                and state.get("max_attempts") == 3
                and state.get("route") in {"generate", "edit", "direct"}
                and isinstance(state.get("attempts"), list)
                and isinstance(state.get("pipeline_attempts"), list)
            )
            if not valid_owner:
                raise FileExistsError("WorkBuddy run ownership does not match the directory")
    else:
        run_dir.mkdir(parents=True)
    return run_dir


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
    run_dir: str | Path | None = None,
    generation_metadata: dict[str, object] | None = None,
    source_provenance: dict[str, str] | None = None,
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
    validated_generation_metadata = validate_generation_metadata(generation_metadata)
    if source_provenance is not None:
        if not isinstance(source_provenance, dict) or set(source_provenance) != {
            "original_path",
            "sha256",
        }:
            raise ValueError(
                "source_provenance must contain exactly original_path and sha256"
            )
        if not re.fullmatch(r"[0-9a-f]{64}", str(source_provenance["sha256"])):
            raise ValueError("source_provenance.sha256 must be a lowercase SHA-256 digest")
        validated_source_provenance = dict(source_provenance)
    else:
        validated_source_provenance = None
    run_dir = _prepare_run_dir(output_root, character_name, started, run_dir)
    research_output_path = None
    if research_path is not None:
        research_output_path = run_dir / "00_official_character_research.md"
        if research_path != research_output_path.resolve():
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
        "generation": validated_generation_metadata,
        "source_provenance": validated_source_provenance,
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
        if source_image != files["source"].resolve():
            with Image.open(source_image) as image:
                image.convert("RGBA").save(files["source"])

        try:
            source_grid = detect_source_grid(files["source"])
        except Exception as exc:
            manifest["source_acceptance"] = {
                "source_grid": None,
                "density_gate": "failed",
                "reason": str(exc),
            }
            raise
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
    parser.add_argument("--run-dir")
    parser.add_argument(
        "--generation-metadata",
        help="Path to a JSON file containing validated generation provenance",
    )
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--square-output",
        action="store_true",
        help="Explicitly pad the prepared and refined canvases to a square",
    )
    args = parser.parse_args()
    generation_metadata = None
    if args.generation_metadata:
        generation_metadata_path = Path(args.generation_metadata).expanduser().resolve()
        generation_metadata = json.loads(
            generation_metadata_path.read_text(encoding="utf-8")
        )
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
        run_dir=args.run_dir,
        generation_metadata=generation_metadata,
    )
    print(run_dir)


if __name__ == "__main__":
    main()
