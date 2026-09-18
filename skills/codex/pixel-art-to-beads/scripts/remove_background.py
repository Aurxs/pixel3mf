#!/usr/bin/env python3
"""Build a semantic foreground-confidence mask while preserving source RGB."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from semantic_segment import SUPPORTED_DEVICES, SUPPORTED_MODELS, run_segmentation_model


FOREGROUND_THRESHOLD = 0.80
BACKGROUND_THRESHOLD = 0.20
BACKGROUND_COLOR_TOLERANCE = 12
ALPHA_POLICIES = ("auto", "preserve", "repair")


def _alpha_profile(image: Image.Image) -> dict[str, object]:
    alpha = np.asarray(image.getchannel("A"), dtype=np.uint8)
    values = [int(value) for value in np.unique(alpha)]
    binary = set(values).issubset({0, 255})
    has_transparency = bool(np.any(alpha < 255))
    has_zero_alpha = bool(np.any(alpha == 0))
    has_foreground = bool(np.any(alpha == 255))
    return {
        "values": values,
        "binary": binary,
        "has_transparency": has_transparency,
        "has_foreground": has_foreground,
        "has_zero_alpha": has_zero_alpha,
        "usable_binary": binary and has_zero_alpha and has_foreground,
        "foreground_pixels": int(np.count_nonzero(alpha == 255)),
        "transparent_pixels": int(np.count_nonzero(alpha == 0)),
    }


def _sample_background_rgb(rgba: np.ndarray) -> np.ndarray:
    border = np.concatenate(
        (rgba[0, :, :3], rgba[-1, :, :3], rgba[:, 0, :3], rgba[:, -1, :3]),
        axis=0,
    )
    return np.median(border, axis=0).astype(np.uint8)


def _background_like(
    rgba: np.ndarray,
    background_rgb: np.ndarray,
    tolerance: int = BACKGROUND_COLOR_TOLERANCE,
) -> np.ndarray:
    difference = np.abs(rgba[:, :, :3].astype(np.int16) - background_rgb.astype(np.int16))
    return np.max(difference, axis=2) <= tolerance


def _exterior_mask(candidate: np.ndarray) -> np.ndarray:
    count, labels = cv2.connectedComponents(candidate.astype(np.uint8), connectivity=8)
    if count <= 1:
        return np.zeros_like(candidate, dtype=bool)
    border_labels = np.unique(
        np.concatenate((labels[0], labels[-1], labels[:, 0], labels[:, -1]))
    )
    return np.isin(labels, border_labels[border_labels != 0])


def _enclosed_background_review_mask(
    rgba: np.ndarray,
    probability: np.ndarray,
    background_rgb: np.ndarray,
) -> np.ndarray:
    candidate = (
        _background_like(rgba, background_rgb)
        & (probability > BACKGROUND_THRESHOLD)
    )
    exterior = _exterior_mask(candidate)
    return candidate & ~exterior


def _count_enclosed_background_review_components(
    rgba: np.ndarray,
    probability: np.ndarray,
    background_rgb: np.ndarray,
) -> int:
    enclosed = _enclosed_background_review_mask(
        rgba, probability, background_rgb
    )
    count, _ = cv2.connectedComponents(enclosed.astype(np.uint8), connectivity=8)
    return max(0, count - 1)


def _has_suspicious_existing_alpha(
    rgba: np.ndarray,
    background_rgb: np.ndarray,
) -> bool:
    candidate = _background_like(rgba, background_rgb) & (rgba[:, :, 3] > 8)
    return bool(np.any(candidate & ~_exterior_mask(candidate)))


def _refine_exterior_near_white(
    image: Image.Image,
    threshold: int = 245,
) -> tuple[Image.Image, dict[str, int]]:
    """Legacy color-key path: remove only stable exterior-connected near-white."""
    rgba = np.asarray(image.convert("RGBA")).copy()
    alpha = rgba[:, :, 3]
    near_white = np.all(rgba[:, :, :3] >= threshold, axis=2)
    traversable = ((alpha <= 8) | near_white).astype(np.uint8)
    kernel = np.ones((3, 3), dtype=np.uint8)
    padded = np.pad(traversable, 1, constant_values=1)
    stable = cv2.erode(padded, kernel, iterations=1)[1:-1, 1:-1]
    count, labels = cv2.connectedComponents(stable, connectivity=8)
    if count <= 1:
        return Image.fromarray(rgba, "RGBA"), {
            "removed_exterior_near_white_pixels": 0,
            "preserved_interior_near_white_components": 0,
        }
    border_labels = np.unique(
        np.concatenate((labels[0], labels[-1], labels[:, 0], labels[:, -1]))
    )
    exterior_core = np.isin(labels, border_labels[border_labels != 0])
    interior_core = (stable > 0) & near_white & ~exterior_core
    protected = cv2.dilate(
        interior_core.astype(np.uint8), kernel, iterations=1
    ).astype(bool) & near_white
    exterior = cv2.dilate(
        exterior_core.astype(np.uint8), kernel, iterations=1
    ).astype(bool) & (traversable > 0) & ~protected
    removable = near_white & (alpha > 8) & exterior
    rgba[removable] = 0
    preserved = near_white & (rgba[:, :, 3] > 8)
    preserved_count, _ = cv2.connectedComponents(
        preserved.astype(np.uint8), connectivity=8
    )
    return Image.fromarray(rgba, "RGBA"), {
        "removed_exterior_near_white_pixels": int(removable.sum()),
        "preserved_interior_near_white_components": max(0, preserved_count - 1),
    }


def _load_mask(path: Path, size: tuple[int, int]) -> np.ndarray:
    mask = Image.open(path).convert("L")
    if mask.size != size:
        raise ValueError(
            f"mask size {mask.size[0]}x{mask.size[1]} does not match "
            f"source size {size[0]}x{size[1]}"
        )
    return np.asarray(mask, dtype=np.float32) / 255.0


def remove_background(
    input_path: str | Path,
    output_path: str | Path,
    method: str = "auto",
    white_threshold: int = 245,
    *,
    background_model: str = "auto",
    segmentation_device: str = "cpu",
    segmentation_memory_limit_gb: float = 8.0,
    semantic_mask_path: str | Path | None = None,
    mask_override: str | Path | None = None,
    alpha_policy: str = "auto",
    project_root: str | Path | None = None,
) -> dict[str, object]:
    if method not in {"auto", "rembg", "white"}:
        raise ValueError(f"unsupported background method: {method}")
    if background_model not in {"auto", *SUPPORTED_MODELS}:
        raise ValueError(f"unsupported background model: {background_model}")
    if segmentation_device not in SUPPORTED_DEVICES:
        raise ValueError(f"unsupported segmentation device: {segmentation_device}")
    if alpha_policy not in ALPHA_POLICIES:
        raise ValueError(f"unsupported alpha policy: {alpha_policy}")

    source = Image.open(input_path).convert("RGBA")
    rgba = np.asarray(source).copy()
    alpha_profile = _alpha_profile(source)
    if (
        mask_override is None
        and alpha_profile["has_transparency"]
        and not alpha_profile["binary"]
    ):
        raise ValueError(
            "existing alpha must be binary (only 0 and 255); provide a binary "
            "--mask-override or regenerate the pixel source"
        )
    if mask_override is None and not alpha_profile["has_foreground"]:
        raise ValueError("source alpha contains no opaque foreground pixels")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mask_path = (
        Path(semantic_mask_path)
        if semantic_mask_path is not None
        else output_path.with_name("02_semantic_mask.png")
    )
    mask_path.parent.mkdir(parents=True, exist_ok=True)
    existing_alpha = rgba[:, :, 3].astype(np.float32) / 255.0
    model_runs: list[dict[str, object]] = []
    fallback_model_used = False
    repair_candidate_pixels = 0
    repair_approved_pixels = 0
    repair_ambiguous_pixels = 0
    background_rgb: np.ndarray | None = None
    legacy_metadata = {
        "removed_exterior_near_white_pixels": 0,
        "preserved_interior_near_white_components": 0,
    }

    def run_model(model_name: str, suffix: str) -> np.ndarray:
        model_path = mask_path.with_name(mask_path.stem + suffix + ".png")
        model_source_path: str | Path = input_path
        neutralized_path: Path | None = None
        if alpha_profile["usable_binary"]:
            # Segmentation models may inspect RGB hidden below alpha=0. Present
            # them with a deterministic white composite without changing the
            # user's source pixels or using hidden RGB as evidence.
            neutralized_path = mask_path.with_name(
                mask_path.stem + suffix + "_opaque_input.png"
            )
            model_rgba = rgba.copy()
            transparent = model_rgba[:, :, 3] == 0
            model_rgba[transparent, :3] = 255
            model_rgba[:, :, 3] = 255
            Image.fromarray(model_rgba, "RGBA").save(neutralized_path)
            model_source_path = neutralized_path
        try:
            metadata = run_segmentation_model(
                model_source_path,
                model_path,
                model_name=model_name,
                device=segmentation_device,
                memory_limit_gb=segmentation_memory_limit_gb,
                project_root=project_root,
            )
        finally:
            if neutralized_path is not None:
                neutralized_path.unlink(missing_ok=True)
        metadata["transparent_rgb_neutralized"] = bool(
            alpha_profile["usable_binary"]
        )
        model_runs.append(metadata)
        result = _load_mask(model_path, source.size)
        model_path.unlink(missing_ok=True)
        return result

    if mask_override is not None:
        probability = _load_mask(Path(mask_override), source.size)
        override_values = np.unique(np.rint(probability * 255.0).astype(np.uint8))
        if not set(override_values.tolist()).issubset({0, 255}):
            raise ValueError("mask override must be binary (only 0 and 255)")
        used = "mask-override"
        effective_alpha_policy = "mask-override"
    elif alpha_policy == "preserve":
        if not alpha_profile["usable_binary"]:
            raise ValueError("alpha-policy preserve requires useful binary alpha")
        probability = existing_alpha.copy()
        used = "existing-alpha"
        effective_alpha_policy = "preserve"
    elif alpha_profile["usable_binary"]:
        primary_model = (
            "isnet-anime" if background_model == "auto" else background_model
        )
        secondary_model = (
            "isnet-general-use"
            if primary_model == "isnet-anime"
            else "isnet-anime"
        )
        primary = run_model(primary_model, "_primary")
        source_foreground = existing_alpha >= 0.5
        primary_candidates = source_foreground & (primary <= BACKGROUND_THRESHOLD)
        repair_candidate_pixels = int(primary_candidates.sum())
        probability = existing_alpha.copy()
        if repair_candidate_pixels:
            secondary = run_model(secondary_model, "_secondary")
            agreed_background = primary_candidates & (
                secondary <= BACKGROUND_THRESHOLD
            )
            disagreement = primary_candidates & ~agreed_background
            probability[agreed_background] = 0.0
            probability[disagreement] = 0.5
            repair_approved_pixels = int(agreed_background.sum())
            repair_ambiguous_pixels = int(disagreement.sum())
            fallback_model_used = True
        used = "existing-alpha-repair"
        effective_alpha_policy = "repair"
    elif alpha_policy == "repair":
        raise ValueError("alpha-policy repair requires useful binary alpha")
    elif method == "white":
        background_rgb = _sample_background_rgb(rgba)
        legacy, legacy_metadata = _refine_exterior_near_white(source, white_threshold)
        legacy_rgba = np.asarray(legacy)
        probability = legacy_rgba[:, :, 3].astype(np.float32) / 255.0
        used = "near-white"
        effective_alpha_policy = "semantic"
    else:
        background_rgb = _sample_background_rgb(rgba)
        primary_model = (
            "isnet-anime" if background_model == "auto" else background_model
        )
        primary = run_model(primary_model, "_primary")
        probability = primary.copy()
        review_count = _count_enclosed_background_review_components(
            rgba, probability, background_rgb
        )
        if background_model == "auto" and review_count > 0:
            secondary = run_model("isnet-general-use", "_secondary")
            review = _enclosed_background_review_mask(
                rgba, probability, background_rgb
            )
            # The general model adjudicates every enclosed background-coloured
            # component, including components the anime model called foreground.
            # This catches white gaps between hair strands without color-keying
            # eyes, white hair, clothing, or highlights globally.
            probability[review] = secondary[review]
            fallback_model_used = True
        used = "isnet"
        effective_alpha_policy = "semantic"

    if effective_alpha_policy == "semantic" and method != "white":
        assert background_rgb is not None
        background_candidate = _background_like(rgba, background_rgb)
        exterior = _exterior_mask(background_candidate)
        removed = exterior & (probability > 0)
        probability[exterior] = 0.0
        legacy_metadata = {
            "removed_exterior_near_white_pixels": int(removed.sum()),
            "preserved_interior_near_white_components": int(
                _count_enclosed_background_review_components(
                    rgba, probability, background_rgb
                )
            ),
        }

    probability = np.clip(probability, 0.0, 1.0)
    mask_u8 = np.rint(probability * 255).astype(np.uint8)
    rgba[:, :, 3] = mask_u8
    Image.fromarray(mask_u8, "L").save(mask_path)
    Image.fromarray(rgba, "RGBA").save(output_path)
    return {
        "method": used,
        "background_model": background_model,
        "segmentation_device": segmentation_device,
        "semantic_mask": str(mask_path),
        "mask_override": str(Path(mask_override).resolve()) if mask_override else None,
        "alpha_policy_requested": alpha_policy,
        "alpha_policy_effective": effective_alpha_policy,
        "source_alpha": alpha_profile,
        "background_rgb": (
            [int(value) for value in background_rgb]
            if background_rgb is not None
            else None
        ),
        "background_color_tolerance": BACKGROUND_COLOR_TOLERANCE,
        "foreground_threshold": FOREGROUND_THRESHOLD,
        "background_threshold": BACKGROUND_THRESHOLD,
        "fallback_model_used": fallback_model_used,
        "model_runs": model_runs,
        "repair_candidate_pixels": repair_candidate_pixels,
        "repair_approved_pixels": repair_approved_pixels,
        "repair_ambiguous_pixels": repair_ambiguous_pixels,
        "transparent_rgb_neutralized_for_models": bool(
            alpha_profile["usable_binary"] and model_runs
        ),
        "white_threshold": int(white_threshold),
        "background_connectivity": 8,
        "narrow_bridge_guard_radius": 1,
        **legacy_metadata,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("output")
    parser.add_argument("--method", choices=("auto", "rembg", "white"), default="auto")
    parser.add_argument("--background-model", choices=("auto", *SUPPORTED_MODELS), default="auto")
    parser.add_argument("--segmentation-device", choices=SUPPORTED_DEVICES, default="cpu")
    parser.add_argument("--segmentation-memory-limit-gb", type=float, default=8.0)
    parser.add_argument("--semantic-mask")
    parser.add_argument("--mask-override")
    parser.add_argument("--alpha-policy", choices=ALPHA_POLICIES, default="auto")
    parser.add_argument("--white-threshold", type=int, default=245)
    args = parser.parse_args()
    metadata = remove_background(
        args.input,
        args.output,
        args.method,
        args.white_threshold,
        background_model=args.background_model,
        segmentation_device=args.segmentation_device,
        segmentation_memory_limit_gb=args.segmentation_memory_limit_gb,
        semantic_mask_path=args.semantic_mask,
        mask_override=args.mask_override,
        alpha_policy=args.alpha_policy,
    )
    print(json.dumps(metadata, ensure_ascii=False))


if __name__ == "__main__":
    main()
