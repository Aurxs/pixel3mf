#!/usr/bin/env python3
"""Center an untransformed Lumina assembly without changing size or materials.

This is a final-export placement step, separate from 3x3 pitch compensation.
It deliberately rejects already transformed/multi-assembly projects rather than
silently rearranging a user-prepared plate. No printer commands are issued.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
import json
import os
from pathlib import Path
import posixpath
import tempfile
import xml.etree.ElementTree as ET
import zipfile

from three_mf_xy_scale import (
    CORE_NAMESPACE, _bounds_record, _inspect_root_model, _local_name,
    _mesh_bounds, _root_model_path, _transform_vertex_data,
)

CENTER = Decimal("90")
EDGE_MARGIN = Decimal("10")
# The pinned tower starts at Y=160 with a 1 mm brim; keep 5 mm clear.
MAX_MODEL_Y = Decimal("154")
TOLERANCE = Decimal("0.000000001")
PRODUCTION_PATH = "{http://schemas.microsoft.com/3dmanufacturing/production/2015/06}path"


def _validate_assembly(archive: zipfile.ZipFile) -> None:
    root_path = _root_model_path(archive)
    root, items = _inspect_root_model(archive.read(root_path))
    if root.get("unit", "millimeter") != "millimeter" or len(items) != 1:
        raise ValueError("centering requires one millimeter Lumina assembly")
    objects = {}
    meshes = set()
    for name in archive.namelist():
        if not name.endswith(".model"):
            continue
        model = ET.fromstring(archive.read(name))
        if model.get("unit", "millimeter") != "millimeter":
            raise ValueError("centering requires millimeter mesh resources")
        for node in model.iter():
            if node.get("transform") is not None:
                raise ValueError("centering refuses pre-existing transforms")
        for obj in model.findall(f"{{{CORE_NAMESPACE}}}resources/{{{CORE_NAMESPACE}}}object"):
            key = (name, obj.get("id"))
            if key in objects:
                raise ValueError("duplicate model object ID")
            objects[key] = obj
            if obj.find(f"{{{CORE_NAMESPACE}}}mesh") is not None:
                meshes.add(key)
    seen = set()

    def visit(key):
        if key in seen or key not in objects:
            raise ValueError("ambiguous, repeated, or missing component reference")
        seen.add(key)
        obj = objects[key]
        components = obj.findall(f"{{{CORE_NAMESPACE}}}components/{{{CORE_NAMESPACE}}}component")
        if key in meshes and components:
            raise ValueError("object contains both mesh and components")
        if key not in meshes and not components:
            raise ValueError("empty model object")
        for component in components:
            target = component.get(PRODUCTION_PATH)
            name = key[0] if target is None else posixpath.normpath(
                target.lstrip("/") if target.startswith("/") else posixpath.join(posixpath.dirname(key[0]), target)
            )
            visit((name, component.get("objectid")))

    visit((root_path, items[0].get("objectid")))
    if not meshes or not meshes.issubset(seen):
        raise ValueError("centering refuses unused or missing meshes")
    if "Metadata/model_settings.config" in archive.namelist():
        config = ET.fromstring(archive.read("Metadata/model_settings.config"))
        if len(config.findall("plate")) > 1 or any(
            _local_name(node.tag) == "assemble_item" or node.get("key") == "matrix"
            for node in config.iter()
        ):
            raise ValueError("centering refuses saved assembly matrices or multiple plates")


def center_lumina_3mf(model_path: str | Path) -> dict[str, object]:
    path = Path(model_path)
    with zipfile.ZipFile(path) as archive:
        _validate_assembly(archive)
        before, count = _mesh_bounds(archive)
        if not all(value.is_finite() for value in before.values()):
            raise ValueError("non-finite model coordinates")
        dx = CENTER - (before["min_x"] + before["max_x"]) / 2
        dy = CENTER - (before["min_y"] + before["max_y"]) / 2
        after = dict(before)
        for axis, delta in (("x", dx), ("y", dy)):
            for end in ("min", "max"):
                after[f"{end}_{axis}"] += delta
        if (after["min_x"] < EDGE_MARGIN or after["max_x"] > 180 - EDGE_MARGIN
                or after["min_y"] < EDGE_MARGIN or after["max_y"] > MAX_MODEL_Y
                or abs(after["min_z"]) > TOLERANCE or after["max_z"] > 180):
            raise ValueError("centered model does not fit A1 mini margins/tower clearance; size is unchanged")
        changed = abs(dx) > TOLERANCE or abs(dy) > TOLERANCE
        if changed:
            with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".3mf", delete=False) as handle:
                temporary = Path(handle.name)
            try:
                written = 0
                with zipfile.ZipFile(temporary, "w") as output:
                    for info in archive.infolist():
                        data = archive.read(info.filename)
                        if info.filename.endswith(".model"):
                            data, vertices = _transform_vertex_data(
                                data, center_x=Decimal(0), center_y=Decimal(0),
                                scale=Decimal(1), translate_x=dx, translate_y=dy,
                            )
                            written += vertices
                        output.writestr(info, data)
                with zipfile.ZipFile(temporary) as verification:
                    actual, actual_count = _mesh_bounds(verification)
                if written != count or actual_count != count or any(
                    abs(actual[key] - after[key]) > TOLERANCE for key in after
                ):
                    raise RuntimeError("centered geometry verification failed")
            except Exception:
                temporary.unlink(missing_ok=True)
                raise
    if changed:
        os.replace(temporary, path)
    return {
        "applied": changed,
        "center_mm": {"x": "90", "y": "90"},
        "bounds_before_mm": _bounds_record(before),
        "bounds_after_mm": _bounds_record(after),
        "size_and_z_unchanged": True,
        "minimum_bed_margin_mm": "10",
        "minimum_tower_front_clearance_mm": "5",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_3mf")
    print(json.dumps(center_lumina_3mf(parser.parse_args().input_3mf), indent=2))
