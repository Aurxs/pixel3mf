#!/usr/bin/env python3
"""Run source image -> transparent pixel art -> Lumina 3MF."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import traceback

from PIL import Image

from cleanup_pixel import cleanup_pixel
from lumina_batch import DEFAULT_PARAMS, LUT_FILENAME, convert_with_lumina_batch
from prepare_square_canvas import prepare_square
from refine_pixel import refine_pixel
from remove_background import remove_background


PROJECT_ROOT = Path(__file__).resolve().parents[1]


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
) -> Path:
    started = datetime.now().astimezone()
    source_image = Path(source_image).expanduser().resolve()
    if character_name is None:
        character_name = source_image.stem
    output_root = Path(output_root)
    if not output_root.is_absolute():
        output_root = (PROJECT_ROOT / output_root).resolve()
    run_dir = _new_run_dir(output_root, character_name, started)

    files = {
        "source": run_dir / "01_source.png",
        "background_removed": run_dir / "02_bg_removed.png",
        "square_prepared": run_dir / "03_square_prepared.png",
        "pixel_perfect": run_dir / "04_pixel_perfect.png",
        "pixel_preview_8x": run_dir / "05_pixel_preview_8x.png",
        "lumina_batch_zip": run_dir / "06_lumina_batch_result.zip",
        "final_3mf": run_dir / f"07_{_slug(character_name)}.3mf",
        "manifest": run_dir / "manifest.json",
    }
    manifest: dict[str, object] = {
        "timestamp": started.isoformat(),
        "character_name": character_name,
        "input_image": str(source_image),
        "reference_image": str(Path(reference_image).expanduser().resolve()) if reference_image else None,
        "files": {key: str(path) for key, path in files.items()},
        "perfect_pixel": None,
        "background_removal": None,
        "cleanup": None,
        "lumina": {"lut_filename": LUT_FILENAME, **DEFAULT_PARAMS},
        "final_3mf": None,
        "status": "running",
        "error": None,
    }
    _write_manifest(files["manifest"], manifest)

    try:
        if not source_image.is_file():
            raise FileNotFoundError(f"source image not found: {source_image}")
        with Image.open(source_image) as image:
            image.convert("RGBA").save(files["source"])

        manifest["background_removal"] = remove_background(
            files["source"], files["background_removed"], background_method
        )
        prepare_square(files["background_removed"], files["square_prepared"])
        pixel_metadata = refine_pixel(
            files["square_prepared"],
            files["pixel_perfect"],
            files["pixel_preview_8x"],
        )
        output_width = pixel_metadata["output_grid"]["width"]
        pixel_metadata["physical_target_width_mm"] = DEFAULT_PARAMS["target_width_mm"]
        pixel_metadata["pixel_pitch_mm"] = round(
            float(DEFAULT_PARAMS["target_width_mm"]) / output_width, 4
        )
        manifest["perfect_pixel"] = pixel_metadata
        manifest["cleanup"] = {
            "removed_isolated_pixels": cleanup_pixel(
                files["pixel_perfect"], files["pixel_perfect"]
            )
        }
        lumina_metadata = convert_with_lumina_batch(
            files["pixel_perfect"],
            files["lumina_batch_zip"],
            files["final_3mf"],
            PROJECT_ROOT / "Lumina-Layers",
            api_url,
        )
        manifest["lumina"] = lumina_metadata
        manifest["final_3mf"] = str(files["final_3mf"])
        manifest["status"] = "success"
        manifest["finished_at"] = datetime.now().astimezone().isoformat()
        _write_manifest(files["manifest"], manifest)
        return run_dir
    except Exception as exc:
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
    parser.add_argument("--output-root", default="output")
    parser.add_argument("--background-method", choices=("auto", "rembg", "white"), default="auto")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    run_dir = run_pipeline(
        source_image=args.source_image,
        character_name=args.character_name,
        reference_image=args.reference_image,
        output_root=args.output_root,
        background_method=args.background_method,
        api_url=args.api_url,
    )
    print(run_dir)


if __name__ == "__main__":
    main()
