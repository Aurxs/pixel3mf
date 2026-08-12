#!/usr/bin/env python3
"""Apply a centered XY-only scale to a multipart 3MF.

Every component's mesh vertices receive the same centered XY compensation, then
the complete model is translated to preserve its original lower-left placement.
Triangle topology, component assembly, material-part mapping, and Z coordinates
remain unchanged. Baking the scale into vertices is deliberate: Bambu Studio's
project importer does not consistently apply a non-uniform top-level transform.
"""

from __future__ import annotations

import argparse
from decimal import Decimal, getcontext
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
import zipfile


getcontext().prec = 40

CORE_NAMESPACE = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
MODEL_RELATIONSHIP_TYPE = (
    "http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"
)
COMPENSATION_METADATA_NAME = "pixel3mf:XYScaleCompensation"
THREE_BY_THREE_XY_SCALE = Decimal(43) / Decimal(42)

_VERTEX_TAG_RE = re.compile(rb"<vertex\b[^>]*>")
_XY_ATTRIBUTE_RE = re.compile(
    rb'(?P<prefix>\b(?P<axis>[xy])=")'
    rb'(?P<value>[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)'
    rb'(?P<suffix>")'
)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _decimal_text(value: Decimal, places: int = 12) -> str:
    rendered = format(value, f".{places}f").rstrip("0").rstrip(".")
    return "0" if rendered in {"", "-0"} else rendered


def _root_model_path(archive: zipfile.ZipFile) -> str:
    try:
        relationships = ET.fromstring(archive.read("_rels/.rels"))
    except KeyError as exc:
        raise ValueError("3MF is missing _rels/.rels") from exc
    except ET.ParseError as exc:
        raise ValueError("3MF package relationships are not valid XML") from exc

    for relationship in relationships:
        if (
            _local_name(relationship.tag) == "Relationship"
            and relationship.get("Type") == MODEL_RELATIONSHIP_TYPE
        ):
            target = relationship.get("Target", "").lstrip("/")
            normalized = str(PurePosixPath(target))
            if normalized not in archive.namelist():
                raise ValueError(
                    f"3MF root model relationship points to a missing file: {target}"
                )
            return normalized
    raise ValueError("3MF package has no root 3D model relationship")


def _mesh_bounds(
    archive: zipfile.ZipFile,
) -> tuple[dict[str, Decimal], int]:
    bounds: dict[str, Decimal | None] = {
        "min_x": None,
        "min_y": None,
        "min_z": None,
        "max_x": None,
        "max_y": None,
        "max_z": None,
    }
    vertex_count = 0
    for member in archive.namelist():
        if not member.lower().endswith(".model"):
            continue
        with archive.open(member) as model_file:
            try:
                iterator = ET.iterparse(model_file, events=("end",))
                for _event, element in iterator:
                    if _local_name(element.tag) != "vertex":
                        element.clear()
                        continue
                    coordinates = {
                        axis: Decimal(element.attrib[axis]) for axis in ("x", "y", "z")
                    }
                    vertex_count += 1
                    for axis in ("x", "y", "z"):
                        minimum_key = f"min_{axis}"
                        maximum_key = f"max_{axis}"
                        current = coordinates[axis]
                        minimum = bounds[minimum_key]
                        maximum = bounds[maximum_key]
                        bounds[minimum_key] = (
                            current if minimum is None else min(minimum, current)
                        )
                        bounds[maximum_key] = (
                            current if maximum is None else max(maximum, current)
                        )
                    element.clear()
            except (ET.ParseError, KeyError, ArithmeticError) as exc:
                raise ValueError(f"invalid mesh XML in {member}: {exc}") from exc

    if vertex_count == 0 or any(value is None for value in bounds.values()):
        raise ValueError("3MF contains no mesh vertices")
    return (
        {key: value for key, value in bounds.items() if value is not None},
        vertex_count,
    )


def _bounds_record(bounds: dict[str, Decimal]) -> dict[str, object]:
    return {
        "min": {
            "x": _decimal_text(bounds["min_x"]),
            "y": _decimal_text(bounds["min_y"]),
            "z": _decimal_text(bounds["min_z"]),
        },
        "max": {
            "x": _decimal_text(bounds["max_x"]),
            "y": _decimal_text(bounds["max_y"]),
            "z": _decimal_text(bounds["max_z"]),
        },
        "size": {
            "x": _decimal_text(bounds["max_x"] - bounds["min_x"]),
            "y": _decimal_text(bounds["max_y"] - bounds["min_y"]),
            "z": _decimal_text(bounds["max_z"] - bounds["min_z"]),
        },
    }


def _transformed_bounds(
    bounds: dict[str, Decimal], scale: Decimal
) -> tuple[dict[str, Decimal], Decimal, Decimal, Decimal, Decimal]:
    center_x = (bounds["min_x"] + bounds["max_x"]) / 2
    center_y = (bounds["min_y"] + bounds["max_y"]) / 2
    transformed = dict(bounds)
    transformed["min_x"] = center_x + (bounds["min_x"] - center_x) * scale
    transformed["max_x"] = center_x + (bounds["max_x"] - center_x) * scale
    transformed["min_y"] = center_y + (bounds["min_y"] - center_y) * scale
    transformed["max_y"] = center_y + (bounds["max_y"] - center_y) * scale

    # Lumina places the raw model almost flush with the X/Y origin. A centered
    # enlargement would therefore create negative coordinates. Translate the
    # already-centered result so its lower-left placement remains unchanged.
    translate_x = bounds["min_x"] - transformed["min_x"]
    translate_y = bounds["min_y"] - transformed["min_y"]
    transformed["min_x"] += translate_x
    transformed["max_x"] += translate_x
    transformed["min_y"] += translate_y
    transformed["max_y"] += translate_y
    return transformed, center_x, center_y, translate_x, translate_y


def _inspect_root_model(root_xml: bytes) -> tuple[ET.Element, list[ET.Element]]:
    try:
        root = ET.fromstring(root_xml)
    except ET.ParseError as exc:
        raise ValueError("3MF root model is not valid XML") from exc
    build = root.find(f"{{{CORE_NAMESPACE}}}build")
    if build is None:
        raise ValueError("3MF root model has no build section")
    items = list(build.findall(f"{{{CORE_NAMESPACE}}}item"))
    if not items:
        raise ValueError("3MF root build contains no items")
    return root, items


def _existing_compensation(root: ET.Element) -> str | None:
    for metadata in root.findall(f"{{{CORE_NAMESPACE}}}metadata"):
        if metadata.get("name") == COMPENSATION_METADATA_NAME:
            return (metadata.text or "").strip()
    return None


def _add_compensation_metadata(root_xml: bytes, scale_text: str) -> bytes:
    metadata = (
        f' <metadata name="{COMPENSATION_METADATA_NAME}">{scale_text}</metadata>\n'
    ).encode("utf-8")
    resources_marker = b"<resources>"
    if resources_marker not in root_xml:
        raise ValueError("3MF root model has no resources section")
    return root_xml.replace(resources_marker, metadata + resources_marker, 1)


def _transform_vertex_data(
    data: bytes,
    *,
    center_x: Decimal,
    center_y: Decimal,
    scale: Decimal,
    translate_x: Decimal,
    translate_y: Decimal,
) -> tuple[bytes, int]:
    transformed_vertices = 0

    def replace_vertex(vertex_match: re.Match[bytes]) -> bytes:
        nonlocal transformed_vertices
        vertex = vertex_match.group(0)
        seen_axes: set[bytes] = set()

        def replace_coordinate(attribute_match: re.Match[bytes]) -> bytes:
            axis = attribute_match.group("axis")
            seen_axes.add(axis)
            value = Decimal(attribute_match.group("value").decode("ascii"))
            center = center_x if axis == b"x" else center_y
            translation = translate_x if axis == b"x" else translate_y
            transformed = center + (value - center) * scale + translation
            return (
                attribute_match.group("prefix")
                + _decimal_text(transformed).encode("ascii")
                + attribute_match.group("suffix")
            )

        rewritten = _XY_ATTRIBUTE_RE.sub(replace_coordinate, vertex)
        if seen_axes != {b"x", b"y"}:
            raise ValueError("3MF vertex is missing an x or y coordinate")
        transformed_vertices += 1
        return rewritten

    return _VERTEX_TAG_RE.sub(replace_vertex, data), transformed_vertices


def _archive_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def apply_centered_xy_scale(
    input_path: str | Path,
    output_path: str | Path | None = None,
    *,
    scale: Decimal = THREE_BY_THREE_XY_SCALE,
) -> dict[str, object]:
    """Bake one centered XY-only mesh scale and return audit metadata."""
    input_path = Path(input_path).expanduser().resolve()
    output_path = (
        Path(output_path).expanduser().resolve()
        if output_path is not None
        else input_path
    )
    if not input_path.is_file():
        raise FileNotFoundError(f"3MF not found: {input_path}")
    if scale <= 0:
        raise ValueError("XY scale must be positive")

    scale_text = _decimal_text(scale)
    with zipfile.ZipFile(input_path, "r") as source_archive:
        root_model_path = _root_model_path(source_archive)
        root_xml = source_archive.read(root_model_path)
        root, build_items = _inspect_root_model(root_xml)
        existing = _existing_compensation(root)
        if existing is not None:
            if existing != scale_text:
                raise ValueError(
                    "3MF already has a different XY compensation marker: "
                    f"{existing}"
                )
            if output_path != input_path:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(input_path, output_path)
            return {
                "applied": False,
                "already_applied": True,
                "axis": "XY",
                "z_unchanged": True,
                "scale_factor": scale_text,
                "scale_percent": _decimal_text(scale * 100, places=9),
                "root_model_path": root_model_path,
                "build_item_count": len(build_items),
                "output_sha256": _archive_sha256(output_path),
            }
        if any(item.get("transform") for item in build_items):
            raise ValueError(
                "3MF build item already has a transform; refusing to bake around an ambiguous center"
            )

        bounds_before, source_vertex_count = _mesh_bounds(source_archive)
        (
            bounds_after,
            center_x,
            center_y,
            translate_x,
            translate_y,
        ) = _transformed_bounds(bounds_before, scale)
        rewritten_root = _add_compensation_metadata(root_xml, scale_text)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.NamedTemporaryFile(
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            dir=output_path.parent,
            delete=False,
        )
        temporary_path = Path(temporary.name)
        temporary.close()
        transformed_vertex_count = 0
        try:
            with zipfile.ZipFile(temporary_path, "w") as target_archive:
                for info in source_archive.infolist():
                    with source_archive.open(info, "r") as source_member:
                        with target_archive.open(info, "w") as target_member:
                            if not info.filename.lower().endswith(".model"):
                                shutil.copyfileobj(source_member, target_member)
                                continue
                            if info.filename == root_model_path:
                                transformed_root, count = _transform_vertex_data(
                                    rewritten_root,
                                    center_x=center_x,
                                    center_y=center_y,
                                    scale=scale,
                                    translate_x=translate_x,
                                    translate_y=translate_y,
                                )
                                transformed_vertex_count += count
                                target_member.write(transformed_root)
                                continue
                            for line in source_member:
                                transformed_line, count = _transform_vertex_data(
                                    line,
                                    center_x=center_x,
                                    center_y=center_y,
                                    scale=scale,
                                    translate_x=translate_x,
                                    translate_y=translate_y,
                                )
                                transformed_vertex_count += count
                                target_member.write(transformed_line)
            if transformed_vertex_count != source_vertex_count:
                raise RuntimeError(
                    "3MF vertex rewrite count mismatch: "
                    f"expected {source_vertex_count}, rewrote {transformed_vertex_count}"
                )
        except Exception:
            temporary_path.unlink(missing_ok=True)
            raise

    try:
        with zipfile.ZipFile(temporary_path, "r") as verification_archive:
            verification_root = ET.fromstring(
                verification_archive.read(root_model_path)
            )
            verification_items = verification_root.findall(
                f"{{{CORE_NAMESPACE}}}build/{{{CORE_NAMESPACE}}}item"
            )
            if len(verification_items) != len(build_items) or any(
                item.get("transform") for item in verification_items
            ):
                raise RuntimeError(
                    "3MF build structure changed during XY compensation"
                )
            if _existing_compensation(verification_root) != scale_text:
                raise RuntimeError("3MF XY compensation marker verification failed")
            verified_bounds, verified_vertex_count = _mesh_bounds(
                verification_archive
            )
            if verified_vertex_count != source_vertex_count:
                raise RuntimeError("3MF vertex count changed during XY compensation")
            if any(
                _decimal_text(verified_bounds[key])
                != _decimal_text(bounds_after[key])
                for key in bounds_after
            ):
                raise RuntimeError(
                    "3MF mesh bounds do not match the requested XY compensation"
                )
        os.replace(temporary_path, output_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    return {
        "applied": True,
        "already_applied": False,
        "axis": "XY",
        "z_unchanged": True,
        "geometry_representation": "baked_mesh_vertices",
        "scale_factor": scale_text,
        "scale_percent": _decimal_text(scale * 100, places=9),
        "transformed_vertex_count": transformed_vertex_count,
        "scale_center_mm": {
            "x": _decimal_text(center_x),
            "y": _decimal_text(center_y),
        },
        "placement_translation_mm": {
            "x": _decimal_text(translate_x),
            "y": _decimal_text(translate_y),
        },
        "lower_left_placement_preserved": True,
        "root_model_path": root_model_path,
        "build_item_count": len(build_items),
        "bounds_before_mm": _bounds_record(bounds_before),
        "bounds_after_mm": _bounds_record(bounds_after),
        "output_sha256": _archive_sha256(output_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input")
    parser.add_argument("--output")
    parser.add_argument("--scale", default=_decimal_text(THREE_BY_THREE_XY_SCALE))
    args = parser.parse_args()
    result = apply_centered_xy_scale(
        args.input,
        args.output,
        scale=Decimal(args.scale),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
