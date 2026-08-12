#!/usr/bin/env python3
"""Normalize a Lumina 3MF to the pinned pixel3mf A1 mini print profile."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import zipfile


PROJECT_SETTINGS_MEMBER = "Metadata/project_settings.config"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE_PATH = (
    PROJECT_ROOT
    / "profiles"
    / "bambu_a1mini_0.4_0.08_extra_fine_pixel3mf.json"
)
PROFILE_SOURCE = "Bambu Studio 02.07.01.62 official A1 mini profiles"

_FILAMENT_ARRAY_KEYS = {
    "activate_air_filtration",
    "additional_cooling_fan_speed",
    "bed_temperature",
    "bed_temperature_initial_layer",
    "chamber_temperatures",
    "close_fan_the_first_x_layers",
    "complete_print_exhaust_fan_speed",
    "cool_plate_temp",
    "cool_plate_temp_initial_layer",
    "during_print_exhaust_fan_speed",
    "eng_plate_temp",
    "eng_plate_temp_initial_layer",
    "fan_cooling_layer_time",
    "fan_max_speed",
    "fan_min_speed",
    "hot_plate_temp",
    "hot_plate_temp_initial_layer",
    "nozzle_temperature",
    "nozzle_temperature_initial_layer",
    "nozzle_temperature_range_high",
    "nozzle_temperature_range_low",
    "textured_plate_temp",
    "textured_plate_temp_initial_layer",
}

_DYNAMIC_PROJECT_KEYS = {
    "default_filament_colour",
    "filament_colour",
    "filament_multi_colour",
    "flush_multiplier",
    "flush_volumes_matrix",
    "flush_volumes_vector",
}

_REQUIRED_TARGET_VALUES: dict[str, object] = {
    "printer_model": "Bambu Lab A1 mini",
    "printer_settings_id": "Bambu Lab A1 mini 0.4 nozzle",
    "printer_variant": "0.4",
    "print_settings_id": "0.08mm Extra Fine @BBL A1M - pixel3mf Lumina",
    "printable_area": ["0x0", "180x0", "180x180", "0x180"],
    "printable_height": "180",
    "nozzle_diameter": ["0.4"],
    "layer_height": "0.08",
    "initial_layer_height": "0.08",
    "initial_layer_print_height": "0.08",
    "line_width": "0.42",
    "initial_layer_line_width": "0.42",
    "outer_wall_line_width": "0.42",
    "inner_wall_line_width": "0.42",
    "internal_solid_infill_line_width": "0.42",
    "sparse_infill_line_width": "0.42",
    "skeleton_infill_line_width": "0.42",
    "skin_infill_line_width": "0.42",
    "top_surface_line_width": "0.42",
    "support_line_width": "0.42",
    "wall_generator": "arachne",
    "wall_loops": "1",
    "only_one_wall_first_layer": "1",
    "top_shell_layers": "0",
    "bottom_shell_layers": "0",
    "sparse_infill_density": "100%",
    "sparse_infill_pattern": "zig-zag",
    "infill_direction": "0",
    "detect_narrow_internal_solid_infill": "0",
    "enable_support": "0",
    "brim_type": "auto_brim",
    "brim_width": "5",
    "single_extruder_multi_material": "1",
    "enable_prime_tower": "1",
    "prime_tower_width": "170",
    "prime_tower_rib_wall": "0",
    "wipe_tower_x": ["5"],
    "wipe_tower_y": ["160"],
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(data: bytes, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return value


def _is_filament_array(key: str, value: object) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and (key.startswith("filament_") or key in _FILAMENT_ARRAY_KEYS)
    )


def _resize_filament_arrays(settings: dict[str, object], color_count: int) -> None:
    for key, value in list(settings.items()):
        if not _is_filament_array(key, value):
            continue
        template_value = value[0]
        settings[key] = [copy.deepcopy(template_value) for _ in range(color_count)]


def _build_target_settings(
    source: dict[str, object],
    profile: dict[str, object],
) -> tuple[dict[str, object], int]:
    source_colours = source.get("filament_colour")
    if not isinstance(source_colours, list) or not source_colours:
        raise ValueError("Lumina project settings have no filament_colour entries")
    if not all(isinstance(colour, str) and colour.startswith("#") for colour in source_colours):
        raise ValueError("Lumina filament_colour entries are malformed")

    color_count = len(source_colours)
    target = copy.deepcopy(profile)
    _resize_filament_arrays(target, color_count)

    for key in _DYNAMIC_PROJECT_KEYS:
        if key in source:
            target[key] = copy.deepcopy(source[key])

    target["filament_colour"] = copy.deepcopy(source_colours)
    target["default_filament_colour"] = copy.deepcopy(source_colours)
    target["filament_multi_colour"] = copy.deepcopy(
        source.get("filament_multi_colour", source_colours)
    )
    target["filament_settings_id"] = ["Bambu PLA Basic @BBL A1M"] * color_count
    target["filament_type"] = ["PLA"] * color_count
    target["filament_vendor"] = ["Bambu Lab"] * color_count
    target["filament_ids"] = ["GFA00"] * color_count
    target["filament_map"] = ["1"] * color_count
    target["filament_extruder_variant"] = ["Direct Drive Standard"] * color_count

    for key, expected in _REQUIRED_TARGET_VALUES.items():
        target[key] = copy.deepcopy(expected)
    return target, color_count


def _validate_target(settings: dict[str, object], color_count: int) -> None:
    for key, expected in _REQUIRED_TARGET_VALUES.items():
        actual = settings.get(key)
        if actual != expected:
            raise RuntimeError(
                f"A1 mini profile verification failed for {key}: "
                f"expected {expected!r}, found {actual!r}"
            )

    for key in (
        "filament_colour",
        "default_filament_colour",
        "filament_multi_colour",
        "filament_settings_id",
        "filament_type",
        "filament_vendor",
        "filament_ids",
        "filament_map",
        "filament_extruder_variant",
    ):
        value = settings.get(key)
        if not isinstance(value, list) or len(value) != color_count:
            raise RuntimeError(
                f"A1 mini profile verification failed for {key}: "
                f"expected {color_count} entries"
            )

    for key in (
        "printer_model",
        "printer_settings_id",
        "default_print_profile",
        "machine_start_gcode",
        "machine_end_gcode",
        "change_filament_gcode",
        "layer_change_gcode",
    ):
        value = settings.get(key)
        if isinstance(value, str) and "H2D" in value:
            raise RuntimeError(f"A1 mini profile still contains H2D data in {key}")

    if settings.get("filament_settings_id") != [
        "Bambu PLA Basic @BBL A1M"
    ] * color_count:
        raise RuntimeError("A1 mini filament profile IDs were not applied")


def _rewrite_project_settings(
    model_path: Path,
    replacement: bytes,
) -> None:
    with zipfile.ZipFile(model_path, "r") as source_archive:
        infos = source_archive.infolist()
        if PROJECT_SETTINGS_MEMBER not in {info.filename for info in infos}:
            raise ValueError(f"3MF is missing {PROJECT_SETTINGS_MEMBER}")

        handle = tempfile.NamedTemporaryFile(
            prefix=f".{model_path.name}.",
            suffix=".tmp",
            dir=model_path.parent,
            delete=False,
        )
        temporary_path = Path(handle.name)
        handle.close()
        try:
            with zipfile.ZipFile(temporary_path, "w") as target_archive:
                for info in infos:
                    data = source_archive.read(info.filename)
                    if info.filename == PROJECT_SETTINGS_MEMBER:
                        data = replacement
                    target_archive.writestr(info, data)
            os.replace(temporary_path, model_path)
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise


def normalize_a1mini_3mf(
    input_path: str | Path,
    output_path: str | Path | None = None,
    *,
    profile_path: str | Path = DEFAULT_PROFILE_PATH,
) -> dict[str, object]:
    """Apply the pinned A1 mini profile while preserving Lumina geometry and colours."""
    source_path = Path(input_path).resolve()
    target_path = Path(output_path).resolve() if output_path is not None else source_path
    pinned_profile_path = Path(profile_path).resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"3MF not found: {source_path}")
    if not pinned_profile_path.is_file():
        raise FileNotFoundError(f"A1 mini profile not found: {pinned_profile_path}")
    if target_path != source_path:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)

    package_hash_before = _sha256_path(target_path)
    with zipfile.ZipFile(target_path, "r") as archive:
        try:
            source_bytes = archive.read(PROJECT_SETTINGS_MEMBER)
        except KeyError as exc:
            raise ValueError(f"3MF is missing {PROJECT_SETTINGS_MEMBER}") from exc
    source_settings = _load_json(source_bytes, label=PROJECT_SETTINGS_MEMBER)
    profile_settings = _load_json(
        pinned_profile_path.read_bytes(),
        label=str(pinned_profile_path),
    )
    target_settings, color_count = _build_target_settings(
        source_settings,
        profile_settings,
    )
    _validate_target(target_settings, color_count)
    replacement = json.dumps(
        target_settings,
        ensure_ascii=False,
        indent=4,
    ).encode("utf-8")

    applied = replacement != source_bytes
    if applied:
        _rewrite_project_settings(target_path, replacement)

    with zipfile.ZipFile(target_path, "r") as archive:
        verified_bytes = archive.read(PROJECT_SETTINGS_MEMBER)
    verified = _load_json(verified_bytes, label=PROJECT_SETTINGS_MEMBER)
    _validate_target(verified, color_count)

    return {
        "applied": applied,
        "profile_source": PROFILE_SOURCE,
        "profile_path": str(pinned_profile_path),
        "printer_model": verified["printer_model"],
        "printer_settings_id": verified["printer_settings_id"],
        "print_settings_id": verified["print_settings_id"],
        "filament_settings_id": verified["filament_settings_id"],
        "color_count": color_count,
        "filament_colours": verified["filament_colour"],
        "prime_tower": {
            "enabled": verified["enable_prime_tower"] == "1",
            "width_mm": verified["prime_tower_width"],
            "x_mm": verified["wipe_tower_x"][0],
            "y_mm": verified["wipe_tower_y"][0],
            "rib_wall": verified["prime_tower_rib_wall"],
        },
        "project_settings_sha256_before": _sha256_bytes(source_bytes),
        "project_settings_sha256_after": _sha256_bytes(verified_bytes),
        "package_sha256_before": package_hash_before,
        "package_sha256_after": _sha256_path(target_path),
        "raw_lumina_archive_unchanged": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalize a Lumina 3MF to the pinned A1 mini profile"
    )
    parser.add_argument("input_3mf")
    parser.add_argument("--output")
    parser.add_argument("--profile", default=str(DEFAULT_PROFILE_PATH))
    args = parser.parse_args()
    result = normalize_a1mini_3mf(
        args.input_3mf,
        args.output,
        profile_path=args.profile,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
