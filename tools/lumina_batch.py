#!/usr/bin/env python3
"""Convert one pixel-art PNG through Lumina's batch API and keep its ZIP."""

from __future__ import annotations

import argparse
import ast
from decimal import Decimal
import io
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.parse import urljoin, urlparse
import zipfile

import requests
from PIL import Image

from three_mf_xy_scale import THREE_BY_THREE_XY_SCALE, apply_centered_xy_scale


LUT_FILENAME = "Bambulab&PLA&4色&RYBW&红-蓝-黄-白.npy"
EXPECTED_LUMINA_CELL_MM = Decimal("0.42")
DEFAULT_LUMINA_CELLS_PER_LOGICAL_PIXEL = 3
DEFAULT_PARAMS: dict[str, object] = {
    "spacer_thick": 1.2,
    "structure_mode": "Double-sided",
    "auto_bg": False,
    "bg_tol": 40,
    "modeling_mode": "pixel",
    "quantize_colors": 256,
    "enable_cleanup": True,
    "hue_weight": 0.6,
    "add_loop": False,
}


def _format_physical_mm(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


def _variant_geometry_postprocess(
    final_path: Path,
    size_plan: dict[str, object],
    cells_per_logical_pixel: int,
) -> dict[str, object]:
    """Finalize physical pitch without changing Lumina's integer raster."""
    nominal_width = Decimal(str(size_plan["nominal_target_width_mm"]))
    nominal_height = Decimal(str(size_plan["nominal_target_height_mm"]))
    source_pitch = Decimal(str(size_plan["logical_pixel_pitch_mm"]))
    if cells_per_logical_pixel != 3:
        return {
            "applied": False,
            "reason": "XY printability compensation is only required for 3x3",
            "axis": "none",
            "z_unchanged": True,
            "scale_factor": "1",
            "source_logical_pixel_pitch_mm": _format_physical_mm(source_pitch),
            "effective_logical_pixel_pitch_mm": _format_physical_mm(source_pitch),
            "final_target_width_mm": _format_physical_mm(nominal_width),
            "final_target_height_mm": _format_physical_mm(nominal_height),
        }

    result = apply_centered_xy_scale(
        final_path,
        scale=THREE_BY_THREE_XY_SCALE,
    )
    return {
        **result,
        "source_lumina_cell_pitch_mm": _format_physical_mm(EXPECTED_LUMINA_CELL_MM),
        "effective_lumina_cell_pitch_mm": _format_physical_mm(
            EXPECTED_LUMINA_CELL_MM * THREE_BY_THREE_XY_SCALE
        ),
        "source_logical_pixel_pitch_mm": _format_physical_mm(source_pitch),
        "effective_logical_pixel_pitch_mm": _format_physical_mm(
            source_pitch * THREE_BY_THREE_XY_SCALE
        ),
        "source_target_width_mm": _format_physical_mm(nominal_width),
        "source_target_height_mm": _format_physical_mm(nominal_height),
        "final_target_width_mm": _format_physical_mm(
            nominal_width * THREE_BY_THREE_XY_SCALE
        ),
        "final_target_height_mm": _format_physical_mm(
            nominal_height * THREE_BY_THREE_XY_SCALE
        ),
        "raw_batch_archive_is_unscaled": True,
    }


def build_pixel_size_plan(
    logical_width: int,
    logical_height: int,
    *,
    cell_mm: Decimal = EXPECTED_LUMINA_CELL_MM,
    cells_per_logical_pixel: int = DEFAULT_LUMINA_CELLS_PER_LOGICAL_PIXEL,
) -> dict[str, object]:
    """Build and verify an exact integer logical-pixel to Lumina-cell mapping."""
    if logical_width <= 0 or logical_height <= 0:
        raise ValueError("logical grid dimensions must be positive")
    if cell_mm <= 0:
        raise ValueError("Lumina cell size must be positive")
    if cells_per_logical_pixel <= 0:
        raise ValueError("cells_per_logical_pixel must be positive")

    expected_width_cells = logical_width * cells_per_logical_pixel
    expected_height_cells = logical_height * cells_per_logical_pixel
    logical_pixel_pitch_mm = cell_mm * cells_per_logical_pixel
    nominal_width_mm = Decimal(logical_width) * logical_pixel_pitch_mm
    nominal_height_mm = Decimal(logical_height) * logical_pixel_pitch_mm

    # HTTP form parsing and Lumina's core both ultimately use binary floats.
    # Start from the canonical decimal representation, then move upward by the
    # smallest possible float only if Lumina's int(width / cell) would lose a
    # column at a representation boundary.
    transport_width_mm = float(format(nominal_width_mm, "f"))
    cell_mm_float = float(cell_mm)
    simulated_width_cells = int(transport_width_mm / cell_mm_float)
    for _ in range(8):
        if simulated_width_cells >= expected_width_cells:
            break
        transport_width_mm = math.nextafter(transport_width_mm, math.inf)
        simulated_width_cells = int(transport_width_mm / cell_mm_float)
    if simulated_width_cells != expected_width_cells:
        raise RuntimeError(
            "could not encode an exact Lumina target width: "
            f"expected {expected_width_cells} cells, got {simulated_width_cells}"
        )

    # Match Lumina's current aspect-ratio formula exactly.
    simulated_height_cells = int(
        simulated_width_cells * logical_height / logical_width
    )
    if simulated_height_cells != expected_height_cells:
        raise RuntimeError(
            "Lumina aspect-ratio rounding would change the logical grid: "
            f"expected {expected_width_cells}x{expected_height_cells}, got "
            f"{simulated_width_cells}x{simulated_height_cells}"
        )

    return {
        "logical_grid": {"width": logical_width, "height": logical_height},
        "lumina_cell_mm": format(cell_mm, "f"),
        "cells_per_logical_pixel": cells_per_logical_pixel,
        "logical_pixel_pitch_mm": format(logical_pixel_pitch_mm, "f"),
        "expected_lumina_grid": {
            "width": expected_width_cells,
            "height": expected_height_cells,
        },
        "nominal_target_width_mm": format(nominal_width_mm, "f"),
        "nominal_target_height_mm": format(nominal_height_mm, "f"),
        "transport_target_width_mm": transport_width_mm,
        "simulated_lumina_grid": {
            "width": simulated_width_cells,
            "height": simulated_height_cells,
        },
        "exact_integer_mapping": True,
    }


def _read_lumina_nozzle_width(lumina_dir: Path) -> Decimal:
    """Read PrinterConfig.NOZZLE_WIDTH without importing or modifying Lumina."""
    config_path = lumina_dir / "config.py"
    if not config_path.is_file():
        raise FileNotFoundError(f"Lumina config not found: {config_path}")
    tree = ast.parse(
        config_path.read_text(encoding="utf-8"), filename=str(config_path)
    )
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != "PrinterConfig":
            continue
        for statement in node.body:
            target_name = None
            value_node = None
            if isinstance(statement, ast.AnnAssign) and isinstance(
                statement.target, ast.Name
            ):
                target_name = statement.target.id
                value_node = statement.value
            elif isinstance(statement, ast.Assign) and len(statement.targets) == 1:
                target = statement.targets[0]
                if isinstance(target, ast.Name):
                    target_name = target.id
                    value_node = statement.value
            if target_name == "NOZZLE_WIDTH" and value_node is not None:
                value = ast.literal_eval(value_node)
                return Decimal(str(value))
    raise RuntimeError(f"PrinterConfig.NOZZLE_WIDTH not found in {config_path}")


def _validate_lumina_pixel_cell(lumina_dir: Path) -> Decimal:
    actual = _read_lumina_nozzle_width(lumina_dir)
    if actual != EXPECTED_LUMINA_CELL_MM:
        raise RuntimeError(
            "Lumina pixel-cell size changed: "
            f"expected {EXPECTED_LUMINA_CELL_MM} mm, found {actual} mm"
        )
    return actual


def _endpoint(base_url: str, path: str) -> str:
    return urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


def _api_ready(base_url: str) -> bool:
    try:
        response = requests.get(_endpoint(base_url, "/api/health"), timeout=2)
        return response.ok
    except requests.RequestException:
        return False


def _start_api(
    base_url: str, lumina_dir: Path, log_path: Path
) -> tuple[subprocess.Popen[bytes], object]:
    parsed = urlparse(base_url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("automatic API startup requires a local http://127.0.0.1 URL")
    port = parsed.port or 80
    log_handle = log_path.open("wb")
    env = os.environ.copy()
    env["LUMINA_MAX_WORKERS"] = env.get("LUMINA_MAX_WORKERS", "1")
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "api.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=lumina_dir,
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
    )
    return process, log_handle


def _wait_for_api(base_url: str, process: subprocess.Popen[bytes], timeout: int = 120) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _api_ready(base_url):
            return
        if process.poll() is not None:
            raise RuntimeError(f"Lumina API exited with code {process.returncode}")
        time.sleep(0.5)
    raise TimeoutError(f"Lumina API did not become ready within {timeout}s")


def _discover_lut(base_url: str) -> dict[str, str]:
    response = requests.get(_endpoint(base_url, "/api/lut/list"), timeout=30)
    response.raise_for_status()
    matches = [
        item
        for item in response.json().get("luts", [])
        if Path(item.get("path", "")).name == LUT_FILENAME
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one LUT named {LUT_FILENAME!r}, found {len(matches)}")
    return matches[0]


def _discover_local_lut(lumina_dir: Path) -> dict[str, str]:
    matches = list((lumina_dir / "lut-npy预设").rglob(LUT_FILENAME))
    if len(matches) != 1:
        raise RuntimeError(f"expected one local LUT named {LUT_FILENAME!r}, found {len(matches)}")
    path = matches[0].resolve()
    sys.path.insert(0, str(lumina_dir))
    try:
        from utils.lut_manager import LUTManager

        all_luts = LUTManager.get_all_lut_files()
        names = [name for name, item_path in all_luts.items() if Path(item_path).resolve() == path]
        if len(names) != 1:
            raise RuntimeError(f"could not resolve Lumina display name for {path}")
        name = names[0]
        return {
            "name": name,
            "path": str(path),
            "color_mode": LUTManager.infer_color_mode(name, str(path)),
        }
    finally:
        sys.path.remove(str(lumina_dir))


def _preview_form_data(
    lut: dict[str, str], params: dict[str, object]
) -> dict[str, str]:
    """Build the 2D-preview form with the same color parameters as batch conversion."""
    return {
        "lut_name": lut["name"],
        "target_width_mm": str(params["target_width_mm"]),
        "auto_bg": str(params["auto_bg"]).lower(),
        "bg_tol": str(params["bg_tol"]),
        "color_mode": lut["color_mode"],
        "modeling_mode": str(params["modeling_mode"]),
        "quantize_colors": str(params["quantize_colors"]),
        "enable_cleanup": str(params["enable_cleanup"]).lower(),
        "hue_weight": str(params["hue_weight"]),
    }


def _generate_api_preview(
    input_path: Path,
    preview_path: Path,
    base_url: str,
    lut: dict[str, str],
    params: dict[str, object],
) -> dict[str, object]:
    """Ask Lumina for its 2D preview and save the returned PNG locally."""
    with input_path.open("rb") as image_file:
        response = requests.post(
            _endpoint(base_url, "/api/convert/preview"),
            files={"image": (input_path.name, image_file, "image/png")},
            data=_preview_form_data(lut, params),
            timeout=600,
        )
    if not response.ok:
        raise RuntimeError(f"preview HTTP {response.status_code}: {response.text[:1000]}")

    preview = response.json()
    preview_url = preview.get("preview_url")
    if preview.get("status") != "ok" or not preview_url:
        raise RuntimeError(f"preview generation failed: {preview}")

    download = requests.get(_endpoint(base_url, preview_url), timeout=120)
    download.raise_for_status()
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    preview_path.write_bytes(download.content)
    if not preview_path.is_file() or preview_path.stat().st_size == 0:
        raise RuntimeError("Lumina returned an empty 2D preview")

    return {
        "preview_method": "api",
        "preview_url": preview_url,
        "preview_session_id": preview.get("session_id"),
        "preview_dimensions": preview.get("dimensions"),
    }


def _generate_core_preview(
    input_path: Path,
    preview_path: Path,
    lumina_dir: Path,
    lut: dict[str, str],
    params: dict[str, object],
) -> dict[str, object]:
    """Generate the same 2D preview through Lumina core when the API is unavailable."""
    sys.path.insert(0, str(lumina_dir))
    try:
        from config import ModelingMode
        from core.converter import generate_preview_cached

        preview_image, _cache, status_message = generate_preview_cached(
            image_path=str(input_path),
            lut_path=lut["path"],
            target_width_mm=params["target_width_mm"],
            auto_bg=params["auto_bg"],
            bg_tol=params["bg_tol"],
            color_mode=lut["color_mode"],
            modeling_mode=ModelingMode(params["modeling_mode"]),
            quantize_colors=params["quantize_colors"],
            enable_cleanup=params["enable_cleanup"],
            is_dark=True,
            hue_weight=params["hue_weight"],
        )
    finally:
        sys.path.remove(str(lumina_dir))

    if preview_image is None:
        raise RuntimeError(f"Lumina core preview failed: {status_message}")

    preview_path.parent.mkdir(parents=True, exist_ok=True)
    if hasattr(preview_image, "save"):
        preview_image.save(preview_path)
    else:
        from PIL import Image

        Image.fromarray(preview_image).save(preview_path)
    if not preview_path.is_file() or preview_path.stat().st_size == 0:
        raise RuntimeError("Lumina core returned an empty 2D preview")

    return {
        "preview_method": "core",
        "preview_status": status_message,
    }


def _core_fallback(
    input_path: Path,
    preview_path: Path,
    zip_path: Path,
    final_path: Path,
    lumina_dir: Path,
    lut: dict[str, str],
    params: dict[str, object],
    batch_error: str,
    preview_metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    """Use Lumina's current core when its batch endpoint is incompatible."""
    if preview_metadata is None or not preview_path.is_file():
        preview_metadata = _generate_core_preview(
            input_path, preview_path, lumina_dir, lut, params
        )

    sys.path.insert(0, str(lumina_dir))
    try:
        from config import ModelingMode
        from core.converter import convert_image_to_3d

        result = convert_image_to_3d(
            image_path=str(input_path),
            lut_path=lut["path"],
            target_width_mm=params["target_width_mm"],
            spacer_thick=params["spacer_thick"],
            structure_mode=params["structure_mode"],
            auto_bg=params["auto_bg"],
            bg_tol=params["bg_tol"],
            color_mode=lut["color_mode"],
            add_loop=False,
            loop_width=4.0,
            loop_length=8.0,
            loop_hole=2.5,
            loop_pos=None,
            modeling_mode=ModelingMode(params["modeling_mode"]),
            quantize_colors=params["quantize_colors"],
            enable_cleanup=params["enable_cleanup"],
            hue_weight=params["hue_weight"],
        )
    finally:
        sys.path.remove(str(lumina_dir))

    generated = result[0]
    status_message = result[3]
    if not generated or not Path(generated).is_file():
        raise RuntimeError(f"Lumina core fallback failed: {status_message}")
    shutil.copyfile(generated, final_path)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(final_path, final_path.name)
    return {
        "method": "batch-api-core-fallback",
        "batch_error": batch_error,
        "core_status": status_message,
        "preview_path": str(preview_path),
        **preview_metadata,
    }


def convert_with_lumina_batch(
    input_path: str | Path,
    zip_path: str | Path,
    final_path: str | Path,
    lumina_dir: str | Path,
    base_url: str = "http://127.0.0.1:8000",
    start_if_needed: bool = True,
    preview_path: str | Path | None = None,
    size_plan: dict[str, object] | None = None,
    cells_per_logical_pixel: int = DEFAULT_LUMINA_CELLS_PER_LOGICAL_PIXEL,
) -> dict[str, object]:
    input_path = Path(input_path).resolve()
    zip_path = Path(zip_path).resolve()
    final_path = Path(final_path).resolve()
    lumina_dir = Path(lumina_dir).resolve()
    cell_mm = _validate_lumina_pixel_cell(lumina_dir)
    with Image.open(input_path) as input_image:
        logical_width, logical_height = input_image.size
    authoritative_size_plan = build_pixel_size_plan(
        logical_width,
        logical_height,
        cell_mm=cell_mm,
        cells_per_logical_pixel=cells_per_logical_pixel,
    )
    if size_plan is None:
        size_plan = authoritative_size_plan
    elif size_plan != authoritative_size_plan:
        raise ValueError(
            "pixel size plan does not match the authoritative plan derived from "
            f"the final {logical_width}x{logical_height} input image"
        )
    params = {
        **DEFAULT_PARAMS,
        "target_width_mm": size_plan["transport_target_width_mm"],
    }
    preview_path = (
        Path(preview_path).resolve()
        if preview_path is not None
        else final_path.with_name("06_lumina_2d_preview.png")
    )
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    preview_path.parent.mkdir(parents=True, exist_ok=True)

    process: subprocess.Popen[bytes] | None = None
    log_handle = None
    started_api = False
    try:
        try:
            if not _api_ready(base_url):
                if not start_if_needed:
                    raise RuntimeError(f"Lumina API is not reachable at {base_url}")
                process, log_handle = _start_api(
                    base_url, lumina_dir, zip_path.parent / "lumina_api.log"
                )
                started_api = True
                _wait_for_api(base_url, process)
            lut = _discover_lut(base_url)
        except Exception as exc:
            lut = _discover_local_lut(lumina_dir)
            fallback = _core_fallback(
                input_path,
                preview_path,
                zip_path,
                final_path,
                lumina_dir,
                lut,
                params,
                f"API unavailable ({type(exc).__name__}): {exc}",
            )
            geometry_postprocess = _variant_geometry_postprocess(
                final_path,
                size_plan,
                cells_per_logical_pixel,
            )
            return {
                **fallback,
                "api_url": base_url,
                "api_started_by_pipeline": started_api,
                "lut_name": lut["name"],
                "lut_path": lut["path"],
                "color_mode": lut["color_mode"],
                **params,
                "pixel_size_plan": size_plan,
                "xy_printability_compensation": geometry_postprocess,
                "batch_response": None,
            }

        params["lut_name"] = lut["name"]
        params["color_mode"] = lut["color_mode"]

        preview_metadata: dict[str, object]
        try:
            preview_metadata = _generate_api_preview(
                input_path, preview_path, base_url, lut, params
            )
        except Exception as preview_exc:
            try:
                preview_metadata = _generate_core_preview(
                    input_path, preview_path, lumina_dir, lut, params
                )
            except Exception as core_preview_exc:
                raise RuntimeError(
                    "2D preview generation failed: "
                    f"API={preview_exc}; core={core_preview_exc}"
                ) from core_preview_exc
            preview_metadata["preview_api_error"] = f"{type(preview_exc).__name__}: {preview_exc}"

        batch: dict[str, object] | None = None
        fallback: dict[str, object] | None = None
        try:
            form_data = {
                key: str(value).lower() if isinstance(value, bool) else str(value)
                for key, value in params.items()
                if key != "add_loop"
            }
            with input_path.open("rb") as image_file:
                response = requests.post(
                    _endpoint(base_url, "/api/convert/batch"),
                    files={"images": (input_path.name, image_file, "image/png")},
                    data=form_data,
                    timeout=600,
                )
            if not response.ok:
                raise RuntimeError(f"batch HTTP {response.status_code}: {response.text[:1000]}")
            batch = response.json()
            if batch.get("status") != "ok":
                errors = [item.get("error") for item in batch.get("results", [])]
                raise RuntimeError(f"{batch.get('message')}: {errors}")

            download = requests.get(_endpoint(base_url, batch["download_url"]), timeout=120)
            download.raise_for_status()
            zip_path.write_bytes(download.content)

            with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
                members = [name for name in archive.namelist() if name.lower().endswith(".3mf")]
                if len(members) != 1:
                    raise RuntimeError(f"expected one 3MF in batch ZIP, found {len(members)}")
                final_path.write_bytes(archive.read(members[0]))
        except Exception as exc:
            fallback = _core_fallback(
                input_path,
                preview_path,
                zip_path,
                final_path,
                lumina_dir,
                lut,
                params,
                f"{type(exc).__name__}: {exc}",
                preview_metadata,
            )

        geometry_postprocess = _variant_geometry_postprocess(
            final_path,
            size_plan,
            cells_per_logical_pixel,
        )

        return {
            "method": fallback["method"] if fallback else "batch-api",
            "api_url": base_url,
            "api_started_by_pipeline": started_api,
            "lut_name": lut["name"],
            "lut_path": lut["path"],
            "color_mode": lut["color_mode"],
            **params,
            "pixel_size_plan": size_plan,
            "xy_printability_compensation": geometry_postprocess,
            "preview_path": str(preview_path),
            "batch_response": batch,
            **preview_metadata,
            **(fallback or {}),
        }
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        if log_handle is not None:
            log_handle.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("--preview-output", default="06_lumina_2d_preview.png")
    parser.add_argument("--zip-output", default="07_lumina_batch_result.zip")
    parser.add_argument("--final-output", default="08_final.3mf")
    parser.add_argument("--lumina-dir", default="Lumina-Layers")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--no-start", action="store_true")
    parser.add_argument(
        "--cells-per-logical-pixel",
        type=int,
        default=DEFAULT_LUMINA_CELLS_PER_LOGICAL_PIXEL,
    )
    args = parser.parse_args()
    result = convert_with_lumina_batch(
        args.input,
        args.zip_output,
        args.final_output,
        args.lumina_dir,
        args.api_url,
        not args.no_start,
        args.preview_output,
        cells_per_logical_pixel=args.cells_per_logical_pixel,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
