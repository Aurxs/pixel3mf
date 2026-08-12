from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_ROOT / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from three_mf_a1mini_profile import (  # noqa: E402
    PROJECT_SETTINGS_MEMBER,
    normalize_a1mini_3mf,
)


GEOMETRY = b"<model><mesh>lumina geometry stays byte-identical</mesh></model>"
SOURCE_SETTINGS = {
    "printer_model": "Bambu Lab H2D",
    "printer_settings_id": "Bambu Lab H2D 0.4 nozzle",
    "machine_start_gcode": ";===== machine: H2D =====",
    "filament_colour": ["#FFFFFF", "#CF4745", "#F6F450", "#192180"],
    "filament_multi_colour": ["#FFFFFF", "#CF4745", "#F6F450", "#192180"],
    "default_filament_colour": ["#FFFFFF", "#CF4745", "#F6F450", "#192180"],
    "filament_settings_id": ["Bambu PLA Basic @BBL H2D"] * 4,
    "filament_type": ["PLA"] * 4,
    "filament_map": ["1"] * 4,
    "flush_volumes_matrix": [str(index) for index in range(16)],
    "flush_volumes_vector": ["140"] * 4,
    "layer_height": "0.08",
    "prime_tower_width": "230",
    "wipe_tower_x": ["80"],
    "wipe_tower_y": ["250"],
}


def _make_3mf(path: Path, settings: dict[str, object] = SOURCE_SETTINGS) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("3D/3dmodel.model", GEOMETRY)
        archive.writestr(
            PROJECT_SETTINGS_MEMBER,
            json.dumps(settings, ensure_ascii=False).encode("utf-8"),
        )
        archive.writestr("Metadata/model_settings.config", b"<config>extruders</config>")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ThreeMfA1MiniProfileTests(unittest.TestCase):
    def test_normalizes_machine_process_and_filaments_without_touching_geometry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            model_path = Path(tmp) / "model.3mf"
            _make_3mf(model_path)

            result = normalize_a1mini_3mf(model_path)

            with zipfile.ZipFile(model_path) as archive:
                geometry = archive.read("3D/3dmodel.model")
                model_settings = archive.read("Metadata/model_settings.config")
                settings = json.loads(archive.read(PROJECT_SETTINGS_MEMBER))

        self.assertTrue(result["applied"])
        self.assertEqual(geometry, GEOMETRY)
        self.assertEqual(model_settings, b"<config>extruders</config>")
        self.assertEqual(settings["printer_model"], "Bambu Lab A1 mini")
        self.assertEqual(
            settings["printer_settings_id"],
            "Bambu Lab A1 mini 0.4 nozzle",
        )
        self.assertEqual(settings["printable_area"], ["0x0", "180x0", "180x180", "0x180"])
        self.assertEqual(settings["layer_height"], "0.08")
        self.assertEqual(settings["initial_layer_print_height"], "0.08")
        for key in (
            "line_width",
            "initial_layer_line_width",
            "outer_wall_line_width",
            "inner_wall_line_width",
            "internal_solid_infill_line_width",
            "sparse_infill_line_width",
            "skeleton_infill_line_width",
            "skin_infill_line_width",
            "top_surface_line_width",
            "support_line_width",
        ):
            self.assertEqual(settings[key], "0.42", key)
        self.assertEqual(settings["wall_generator"], "arachne")
        self.assertEqual(settings["wall_loops"], "1")
        self.assertEqual(settings["only_one_wall_first_layer"], "1")
        self.assertEqual(settings["top_shell_layers"], "0")
        self.assertEqual(settings["bottom_shell_layers"], "0")
        self.assertEqual(settings["sparse_infill_density"], "100%")
        self.assertEqual(settings["sparse_infill_pattern"], "zig-zag")
        self.assertEqual(settings["infill_direction"], "0")
        self.assertEqual(settings["detect_narrow_internal_solid_infill"], "0")
        self.assertEqual(settings["enable_support"], "0")
        self.assertEqual(settings["brim_type"], "auto_brim")
        self.assertEqual(settings["brim_width"], "5")
        self.assertEqual(settings["travel_speed"], ["700"])
        self.assertEqual(settings["default_acceleration"], ["6000"])
        self.assertEqual(settings["filament_flow_ratio"], ["0.98"] * 4)
        self.assertEqual(settings["filament_max_volumetric_speed"], ["21"] * 4)
        self.assertEqual(
            settings["filament_settings_id"],
            ["Bambu PLA Basic @BBL A1M"] * 4,
        )
        self.assertEqual(settings["filament_colour"], SOURCE_SETTINGS["filament_colour"])
        self.assertEqual(settings["flush_volumes_matrix"], SOURCE_SETTINGS["flush_volumes_matrix"])
        self.assertEqual(settings["flush_volumes_vector"], SOURCE_SETTINGS["flush_volumes_vector"])
        self.assertEqual(settings["enable_prime_tower"], "1")
        self.assertEqual(settings["prime_tower_width"], "170")
        self.assertEqual(settings["prime_tower_rib_wall"], "0")
        self.assertEqual(settings["wipe_tower_x"], ["5"])
        self.assertEqual(settings["wipe_tower_y"], ["160"])
        self.assertIn("machine: A1 mini", settings["machine_start_gcode"])
        self.assertNotIn("H2D", settings["machine_start_gcode"])

    def test_second_application_is_byte_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            model_path = Path(tmp) / "model.3mf"
            _make_3mf(model_path)
            normalize_a1mini_3mf(model_path)
            first_hash = _sha256(model_path)

            result = normalize_a1mini_3mf(model_path)

            self.assertFalse(result["applied"])
            self.assertEqual(_sha256(model_path), first_hash)

    def test_output_copy_leaves_raw_lumina_file_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source_path = Path(tmp) / "raw.3mf"
            output_path = Path(tmp) / "final.3mf"
            _make_3mf(source_path)
            source_hash = _sha256(source_path)

            normalize_a1mini_3mf(source_path, output_path)

            self.assertEqual(_sha256(source_path), source_hash)
            self.assertNotEqual(_sha256(output_path), source_hash)

    def test_missing_filament_colours_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            model_path = Path(tmp) / "model.3mf"
            _make_3mf(model_path, {"printer_model": "Bambu Lab H2D"})

            with self.assertRaisesRegex(ValueError, "filament_colour"):
                normalize_a1mini_3mf(model_path)


if __name__ == "__main__":
    unittest.main()
