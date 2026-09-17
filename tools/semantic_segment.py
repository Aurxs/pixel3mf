#!/usr/bin/env python3
"""Run an IS-Net foreground mask in a resource-bounded local subprocess."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import numpy as np
from PIL import Image


SUPPORTED_MODELS = ("isnet-anime", "isnet-general-use")
SUPPORTED_DEVICES = ("cpu",)
DEFAULT_THREADS = 6
DEFAULT_TIMEOUT_SECONDS = 300
TARGET_PEAK_RSS_BYTES = 6 * 1024**3


def _providers_for(device: str) -> list[str]:
    if device not in SUPPORTED_DEVICES:
        raise ValueError(f"unsupported segmentation device: {device}")
    return ["CPUExecutionProvider"]


def _predict_mask(
    source_path: Path,
    mask_path: Path,
    *,
    model_name: str,
    device: str,
) -> dict[str, object]:
    if model_name not in SUPPORTED_MODELS:
        raise ValueError(f"unsupported segmentation model: {model_name}")

    import onnxruntime as ort
    from rembg import new_session

    options = ort.SessionOptions()
    options.intra_op_num_threads = DEFAULT_THREADS
    options.inter_op_num_threads = DEFAULT_THREADS

    started = time.monotonic()
    session = new_session(
        model_name,
        sess_opts=options,
        providers=_providers_for(device),
    )
    source = Image.open(source_path).convert("RGBA")
    mask = session.predict(source)[0].convert("L")
    active_providers = session.inner_session.get_providers()

    values = np.asarray(mask, dtype=np.uint8)
    if values.shape != (source.height, source.width):
        mask = mask.resize(source.size, Image.Resampling.LANCZOS)
    mask_path.parent.mkdir(parents=True, exist_ok=True)
    mask.save(mask_path)
    return {
        "model": model_name,
        "requested_device": device,
        "requested_providers": _providers_for(device),
        "active_providers": list(active_providers),
        "fallback_reason": None,
        "duration_seconds": round(time.monotonic() - started, 6),
        "input_size": {"width": source.width, "height": source.height},
    }


def _read_rss_bytes(pid: int) -> int:
    import psutil

    try:
        return int(psutil.Process(pid).memory_info().rss)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return 0


def run_segmentation_model(
    source_path: str | Path,
    mask_path: str | Path,
    *,
    model_name: str,
    device: str = "cpu",
    memory_limit_gb: float = 8.0,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    project_root: str | Path | None = None,
) -> dict[str, object]:
    """Run one model in isolation and enforce elapsed-time and RSS limits."""
    if model_name not in SUPPORTED_MODELS:
        raise ValueError(f"unsupported segmentation model: {model_name}")
    if device not in SUPPORTED_DEVICES:
        raise ValueError(f"unsupported segmentation device: {device}")
    if memory_limit_gb <= 0:
        raise ValueError("memory_limit_gb must be positive")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    source_path = Path(source_path).resolve()
    mask_path = Path(mask_path).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"segmentation source not found: {source_path}")
    root = (
        Path(project_root).resolve()
        if project_root is not None
        else Path(__file__).resolve().parents[1]
    )
    model_dir = root / ".cache" / "rembg"
    model_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = mask_path.with_suffix(mask_path.suffix + ".worker.json")

    env = os.environ.copy()
    env["OMP_NUM_THREADS"] = str(DEFAULT_THREADS)
    env["U2NET_HOME"] = str(model_dir)
    # rembg imports unused PyMatting kernels whose Numba cache probes create/delete
    # dozens of temporary files. This worker uses only ONNX session.predict,
    # so disable that unrelated JIT without changing ONNX or host safety settings.
    env["NUMBA_DISABLE_JIT"] = "1"
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        "--source",
        str(source_path),
        "--mask",
        str(mask_path),
        "--metadata",
        str(metadata_path),
        "--model",
        model_name,
        "--device",
        device,
    ]
    started = time.monotonic()
    process = subprocess.Popen(
        command,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    max_rss = 0
    memory_limit_bytes = int(memory_limit_gb * 1024**3)
    failure: str | None = None
    while process.poll() is None:
        max_rss = max(max_rss, _read_rss_bytes(process.pid))
        if max_rss > memory_limit_bytes:
            failure = (
                f"segmentation exceeded {memory_limit_gb:g} GiB RSS "
                f"(observed {max_rss / 1024**3:.2f} GiB)"
            )
            process.kill()
            break
        if time.monotonic() - started > timeout_seconds:
            failure = f"segmentation exceeded {timeout_seconds}s timeout"
            process.kill()
            break
        time.sleep(0.1)

    stdout, stderr = process.communicate()
    max_rss = max(max_rss, _read_rss_bytes(process.pid))
    worker_failure = failure
    if worker_failure is None and process.returncode != 0:
        message = stderr.strip() or stdout.strip() or "unknown worker failure"
        message = message[-4000:]
        worker_failure = (
            f"segmentation worker exited with code {process.returncode}: {message}"
        )
    if worker_failure is not None:
        raise RuntimeError(worker_failure)
    if not metadata_path.is_file() or not mask_path.is_file():
        raise RuntimeError("segmentation worker did not produce its outputs")

    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata_path.unlink()
    metadata["peak_rss_bytes"] = max_rss
    metadata["target_peak_rss_bytes"] = TARGET_PEAK_RSS_BYTES
    metadata["target_peak_rss_met"] = max_rss < TARGET_PEAK_RSS_BYTES
    metadata["memory_limit_bytes"] = memory_limit_bytes
    metadata["wall_seconds"] = round(time.monotonic() - started, 6)
    return metadata


def _worker_main(args: argparse.Namespace) -> None:
    metadata = _predict_mask(
        Path(args.source),
        Path(args.mask),
        model_name=args.model,
        device=args.device,
    )
    Path(args.metadata).write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--source")
    parser.add_argument("--mask")
    parser.add_argument("--metadata")
    parser.add_argument("--model", choices=SUPPORTED_MODELS)
    parser.add_argument("--device", choices=SUPPORTED_DEVICES, default="cpu")
    args = parser.parse_args()
    if not args.worker:
        parser.error("this module is invoked by run_pipeline.py")
    required = (args.source, args.mask, args.metadata, args.model)
    if not all(required):
        parser.error("worker mode requires source, mask, metadata, and model")
    _worker_main(args)


if __name__ == "__main__":
    main()
