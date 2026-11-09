from decimal import Decimal
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from three_mf_center import center_lumina_3mf
from three_mf_xy_scale import CORE_NAMESPACE, apply_centered_xy_scale
from test_3mf_xy_scale import _make_3mf, ROOT_MODEL, OBJECT_MODEL


class CenterTests(unittest.TestCase):
    def test_both_variants_are_centered_without_changing_size_topology_or_materials(self):
        for cells in (2, 3):
            with self.subTest(cells=cells), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "test.3mf"
                _make_3mf(path)
                if cells == 3:
                    apply_centered_xy_scale(path)
                with zipfile.ZipFile(path) as archive:
                    before = {n: archive.read(n) for n in archive.namelist()}
                result = center_lumina_3mf(path)
                self.assertEqual(result["bounds_before_mm"]["size"], result["bounds_after_mm"]["size"])
                for axis in ("x", "y"):
                    bounds = result["bounds_after_mm"]
                    self.assertEqual((Decimal(bounds["min"][axis]) + Decimal(bounds["max"][axis])) / 2, Decimal(90))
                with zipfile.ZipFile(path) as archive:
                    for name, original in before.items():
                        actual = archive.read(name)
                        if not name.endswith(".model"):
                            self.assertEqual(actual, original)
                            continue
                        a, b = ET.fromstring(original), ET.fromstring(actual)
                        for root in (a, b):
                            for vertex in root.iter(f"{{{CORE_NAMESPACE}}}vertex"):
                                vertex.attrib.pop("x")
                                vertex.attrib.pop("y")
                        self.assertEqual(ET.tostring(a), ET.tostring(b))
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                self.assertFalse(center_lumina_3mf(path)["applied"])
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)

    def test_transform_multi_instance_and_unused_mesh_rejected_without_writes(self):
        cases = [
            ROOT_MODEL.replace(b'<item objectid="5"/>', b'<item objectid="5" transform="1 0 0 0 1 0 0 0 1 5 5 0"/>'),
            ROOT_MODEL.replace(b'<item objectid="5"/>', b'<item objectid="5"/><item objectid="5"/>'),
            ROOT_MODEL.replace(b'<component objectid="2" p:path="/3D/Objects/object_1.model"/>', b''),
            ROOT_MODEL.replace(b'<component objectid="1" ', b'<component transform="1 0 0 0 1 0 0 0 1 5 5 0" objectid="1" '),
        ]
        for root in cases:
            with self.subTest(root=root), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "test.3mf"
                _make_3mf(path, root)
                original = path.read_bytes()
                with self.assertRaises(ValueError):
                    center_lumina_3mf(path)
                self.assertEqual(path.read_bytes(), original)

    def test_floating_or_nonmillimeter_mesh_is_rejected_without_writes(self):
        for mesh in (
            OBJECT_MODEL.replace(b'z="0"', b'z="3"').replace(b'z="0.5"', b'z="3.5"'),
            OBJECT_MODEL.replace(b'unit="millimeter"', b'unit="centimeter"'),
        ):
            with self.subTest(mesh=mesh), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "test.3mf"
                _make_3mf(path)
                with zipfile.ZipFile(path) as archive:
                    entries = {n: archive.read(n) for n in archive.namelist()}
                entries["3D/Objects/object_1.model"] = mesh
                with zipfile.ZipFile(path, "w") as archive:
                    for name, data in entries.items():
                        archive.writestr(name, data)
                original = path.read_bytes()
                with self.assertRaises(ValueError):
                    center_lumina_3mf(path)
                self.assertEqual(path.read_bytes(), original)

    def test_oversized_model_rejected_instead_of_scaling_or_hitting_tower(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.3mf"
            _make_3mf(path)
            with zipfile.ZipFile(path) as archive:
                entries = {n: archive.read(n) for n in archive.namelist()}
            entries['3D/Objects/object_1.model'] = OBJECT_MODEL.replace(b'y="50"', b'y="170"')
            with zipfile.ZipFile(path, "w") as archive:
                for n, data in entries.items():
                    archive.writestr(n, data)
            original = path.read_bytes()
            with self.assertRaisesRegex(ValueError, "clearance"):
                center_lumina_3mf(path)
            self.assertEqual(path.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
