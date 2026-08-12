from __future__ import annotations

from decimal import Decimal
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_ROOT / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from lumina_batch import _variant_geometry_postprocess, build_pixel_size_plan  # noqa: E402
from three_mf_xy_scale import (  # noqa: E402
    COMPENSATION_METADATA_NAME,
    CORE_NAMESPACE,
    apply_centered_xy_scale,
)


ROOT_MODEL = b"""<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06">
 <resources>
  <object id="5" type="model"><components>
   <component objectid="1" p:path="/3D/Objects/object_1.model"/>
   <component objectid="2" p:path="/3D/Objects/object_1.model"/>
  </components></object>
 </resources>
 <build><item objectid="5"/></build>
</model>
"""

OBJECT_MODEL = b"""<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">
 <resources>
  <object id="1" type="model"><mesh><vertices>
   <vertex x="10" y="30" z="0"/><vertex x="20" y="50" z="2"/>
  </vertices><triangles><triangle v1="0" v2="1" v3="1"/></triangles></mesh></object>
  <object id="2" type="model"><mesh><vertices>
   <vertex x="12" y="32" z="0.5"/><vertex x="18" y="48" z="1.5"/>
  </vertices><triangles><triangle v1="0" v2="1" v3="1"/></triangles></mesh></object>
 </resources><build/>
</model>
"""

RELATIONSHIPS = b"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>
"""


def _make_3mf(path: Path, root_model: bytes = ROOT_MODEL) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("_rels/.rels", RELATIONSHIPS)
        archive.writestr("3D/3dmodel.model", root_model)
        archive.writestr("3D/Objects/object_1.model", OBJECT_MODEL)
        archive.writestr("Metadata/project_settings.config", b'{"wall_generator":"arachne"}')


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ThreeMfXYScaleTests(unittest.TestCase):
    def test_centered_xy_scale_preserves_topology_materials_and_z(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            model_path = Path(tmp) / "model.3mf"
            _make_3mf(model_path)

            result = apply_centered_xy_scale(model_path)

            self.assertTrue(result["applied"])
            self.assertEqual(result["scale_factor"], "1.02380952381")
            self.assertEqual(result["axis"], "XY")
            self.assertTrue(result["z_unchanged"])
            self.assertEqual(result["bounds_before_mm"]["size"], {"x": "10", "y": "20", "z": "2"})
            self.assertEqual(
                result["bounds_after_mm"]["size"],
                {"x": "10.238095238095", "y": "20.47619047619", "z": "2"},
            )
            self.assertEqual(result["scale_center_mm"], {"x": "15", "y": "40"})
            self.assertEqual(result["geometry_representation"], "baked_mesh_vertices")
            self.assertEqual(result["transformed_vertex_count"], 4)

            with zipfile.ZipFile(model_path) as archive:
                object_xml = archive.read("3D/Objects/object_1.model")
                self.assertNotEqual(object_xml, OBJECT_MODEL)
                self.assertEqual(
                    object_xml.count(b"<triangle"), OBJECT_MODEL.count(b"<triangle")
                )
                self.assertEqual(
                    archive.read("Metadata/project_settings.config"),
                    b'{"wall_generator":"arachne"}',
                )
                root = ET.fromstring(archive.read("3D/3dmodel.model"))
                object_root = ET.fromstring(object_xml)

            item = root.find(
                f"{{{CORE_NAMESPACE}}}build/{{{CORE_NAMESPACE}}}item"
            )
            self.assertIsNotNone(item)
            self.assertNotIn("transform", item.attrib)
            vertices = object_root.findall(f".//{{{CORE_NAMESPACE}}}vertex")
            self.assertEqual([vertex.get("z") for vertex in vertices], ["0", "2", "0.5", "1.5"])
            self.assertEqual(
                min(Decimal(vertex.attrib["x"]) for vertex in vertices),
                Decimal(result["bounds_after_mm"]["min"]["x"]),
            )
            self.assertEqual(
                max(Decimal(vertex.attrib["y"]) for vertex in vertices),
                Decimal(result["bounds_after_mm"]["max"]["y"]),
            )
            metadata = {
                element.get("name"): (element.text or "").strip()
                for element in root.findall(f"{{{CORE_NAMESPACE}}}metadata")
            }
            self.assertEqual(metadata[COMPENSATION_METADATA_NAME], result["scale_factor"])

    def test_second_application_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            model_path = Path(tmp) / "model.3mf"
            _make_3mf(model_path)
            apply_centered_xy_scale(model_path)
            first_hash = _sha256(model_path)

            result = apply_centered_xy_scale(model_path)

            self.assertFalse(result["applied"])
            self.assertTrue(result["already_applied"])
            self.assertEqual(_sha256(model_path), first_hash)

    def test_existing_unknown_build_transform_is_rejected(self) -> None:
        root_with_transform = ROOT_MODEL.replace(
            b'<item objectid="5"/>',
            b'<item objectid="5" transform="1 0 0 0 1 0 0 0 1 5 5 0"/>',
        )
        with tempfile.TemporaryDirectory() as tmp:
            model_path = Path(tmp) / "model.3mf"
            _make_3mf(model_path, root_with_transform)

            with self.assertRaisesRegex(ValueError, "already has a transform"):
                apply_centered_xy_scale(model_path)

    def test_three_by_three_geometry_metadata_reports_129_pitch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            model_path = Path(tmp) / "model.3mf"
            _make_3mf(model_path)
            plan = build_pixel_size_plan(80, 79, cells_per_logical_pixel=3)

            result = _variant_geometry_postprocess(model_path, plan, 3)

            self.assertEqual(result["source_lumina_cell_pitch_mm"], "0.42")
            self.assertEqual(result["effective_lumina_cell_pitch_mm"], "0.43")
            self.assertEqual(result["source_logical_pixel_pitch_mm"], "1.26")
            self.assertEqual(result["effective_logical_pixel_pitch_mm"], "1.29")
            self.assertEqual(result["final_target_width_mm"], "103.20")
            self.assertEqual(result["final_target_height_mm"], "101.91")

    def test_two_by_two_geometry_is_unchanged(self) -> None:
        plan = build_pixel_size_plan(80, 79, cells_per_logical_pixel=2)
        result = _variant_geometry_postprocess(Path("unused.3mf"), plan, 2)

        self.assertFalse(result["applied"])
        self.assertEqual(result["scale_factor"], "1")
        self.assertEqual(result["effective_logical_pixel_pitch_mm"], "0.84")
        self.assertEqual(result["final_target_width_mm"], "67.20")
        self.assertEqual(result["final_target_height_mm"], "66.36")


if __name__ == "__main__":
    unittest.main()
