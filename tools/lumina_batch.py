#!/usr/bin/env python3
"""Convert one pixel-art PNG through Lumina's batch API and keep its ZIP."""

from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from urllib.parse import urljoin, urlparse
import zipfile

import requests


LUT_FILENAME = "Bambulab&PLA&4色&RYBW&红-蓝-黄-白.npy"
DEFAULT_PARAMS: dict[str, object] = {
    "target_width_mm": 55.0,
    "spacer_thick": 1.2,
    "structure_mode": "Double-sided",
    "auto_bg": False,
    "bg_tol": 40,
    "modeling_mode": "pixel",
    "quantize_colors": 256,
    "enable_cleanup": True,
    "hue_weight": 0.0,
    "add_loop": False,
}


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


def _core_fallback(
    input_path: Path,
    zip_path: Path,
    final_path: Path,
    lumina_dir: Path,
    lut: dict[str, str],
    batch_error: str,
) -> dict[str, object]:
    """Use Lumina's current core when its batch endpoint is incompatible."""
    sys.path.insert(0, str(lumina_dir))
    try:
        from config import ModelingMode
        from core.converter import convert_image_to_3d

        result = convert_image_to_3d(
            image_path=str(input_path),
            lut_path=lut["path"],
            target_width_mm=DEFAULT_PARAMS["target_width_mm"],
            spacer_thick=DEFAULT_PARAMS["spacer_thick"],
            structure_mode=DEFAULT_PARAMS["structure_mode"],
            auto_bg=DEFAULT_PARAMS["auto_bg"],
            bg_tol=DEFAULT_PARAMS["bg_tol"],
            color_mode=lut["color_mode"],
            add_loop=False,
            loop_width=4.0,
            loop_length=8.0,
            loop_hole=2.5,
            loop_pos=None,
            modeling_mode=ModelingMode(DEFAULT_PARAMS["modeling_mode"]),
            quantize_colors=DEFAULT_PARAMS["quantize_colors"],
            enable_cleanup=DEFAULT_PARAMS["enable_cleanup"],
            hue_weight=DEFAULT_PARAMS["hue_weight"],
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
    }


def convert_with_lumina_batch(
    input_path: str | Path,
    zip_path: str | Path,
    final_path: str | Path,
    lumina_dir: str | Path,
    base_url: str = "http://127.0.0.1:8000",
    start_if_needed: bool = True,
) -> dict[str, object]:
    input_path = Path(input_path).resolve()
    zip_path = Path(zip_path).resolve()
    final_path = Path(final_path).resolve()
    lumina_dir = Path(lumina_dir).resolve()
    zip_path.parent.mkdir(parents=True, exist_ok=True)

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
                zip_path,
                final_path,
                lumina_dir,
                lut,
                f"API unavailable ({type(exc).__name__}): {exc}",
            )
            return {
                **fallback,
                "api_url": base_url,
                "api_started_by_pipeline": started_api,
                "lut_name": lut["name"],
                "lut_path": lut["path"],
                "color_mode": lut["color_mode"],
                **DEFAULT_PARAMS,
                "batch_response": None,
            }

        params = DEFAULT_PARAMS.copy()
        params["lut_name"] = lut["name"]
        params["color_mode"] = lut["color_mode"]

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
                zip_path,
                final_path,
                lumina_dir,
                lut,
                f"{type(exc).__name__}: {exc}",
            )

        return {
            "method": fallback["method"] if fallback else "batch-api",
            "api_url": base_url,
            "api_started_by_pipeline": started_api,
            "lut_name": lut["name"],
            "lut_path": lut["path"],
            "color_mode": lut["color_mode"],
            **DEFAULT_PARAMS,
            "batch_response": batch,
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
    parser.add_argument("--zip-output", default="06_lumina_batch_result.zip")
    parser.add_argument("--final-output", default="07_final.3mf")
    parser.add_argument("--lumina-dir", default="Lumina-Layers")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--no-start", action="store_true")
    args = parser.parse_args()
    result = convert_with_lumina_batch(
        args.input,
        args.zip_output,
        args.final_output,
        args.lumina_dir,
        args.api_url,
        not args.no_start,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
