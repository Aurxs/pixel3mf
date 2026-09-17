#!/usr/bin/env python3
"""Build and package the WorkBuddy copy of the canonical Pixel3MF skill."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = PROJECT_ROOT / "skills" / "pixel-art-to-3mf-skill"
TARGET_DIR = PROJECT_ROOT / ".codebuddy" / "skills" / "pixel-art-to-3mf"
OVERLAY_PATH = PROJECT_ROOT / "workbuddy" / "host-adapter.md"
GENERATION_PROMPT_PATH = PROJECT_ROOT / "workbuddy" / "generation-prompt.md"
PACKAGE_PATH = PROJECT_ROOT / "dist" / "pixel-art-to-3mf-workbuddy.zip"
CREATOR_SCRIPTS_DIR = (
    Path.home()
    / ".workbuddy"
    / "plugins"
    / "marketplaces"
    / "workbuddy-builtin"
    / "skills"
    / "skill-creator"
    / "scripts"
)
COPIED_DIRECTORIES = ("references", "assets")


def _expected_skill_markdown() -> str:
    core = (SOURCE_DIR / "SKILL.md").read_text(encoding="utf-8").rstrip()
    core = core.replace(
        "Save the returned image as `01_source.png`.",
        "Save the returned image and register it with `import-candidate`; the candidate is `01_source_attempt_NN.png`. `decide --decision accepted` creates `01_source.png` only after acceptance.",
    )
    core = core.replace("`01_source.png` exists", "a registered `01_source_attempt_NN.png` (generated) or registered `00_user_source_original.*` (direct) exists")
    core = core.replace("Record the untouched-source grid", "Record the original-size source grid after the permitted native background normalization")
    overlay = OVERLAY_PATH.read_text(encoding="utf-8").strip()
    return f"{core}\n\n{overlay}\n"


def _source_files() -> dict[Path, bytes]:
    files: dict[Path, bytes] = {Path("SKILL.md"): _expected_skill_markdown().encode("utf-8")}
    for directory_name in COPIED_DIRECTORIES:
        directory = SOURCE_DIR / directory_name
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                files[path.relative_to(SOURCE_DIR)] = path.read_bytes()
    for name in ("generation-prompt.md", "source-acceptance.md", "pixel-refinement.md"):
        files[Path("references") / name] = (PROJECT_ROOT / "workbuddy" / name).read_bytes()
    return files


def _target_files() -> dict[Path, bytes]:
    if not TARGET_DIR.is_dir():
        return {}
    return {
        path.relative_to(TARGET_DIR): path.read_bytes()
        for path in sorted(TARGET_DIR.rglob("*"))
        if path.is_file()
    }


def skill_tree_matches() -> bool:
    return _target_files() == _source_files()


def _creator_script(name: str) -> Path:
    direct = CREATOR_SCRIPTS_DIR / name
    if direct.is_file():
        return direct
    plugin_root = Path.home() / ".workbuddy" / "plugins"
    matches = sorted(plugin_root.glob(f"**/skill-creator/scripts/{name}"))
    if not matches:
        raise FileNotFoundError(f"WorkBuddy skill-creator script not found: {name}")
    return matches[0]


def sync_skill_tree() -> Path:
    expected = _source_files()
    if TARGET_DIR.exists():
        shutil.rmtree(TARGET_DIR)
    for relative_path, data in expected.items():
        output = TARGET_DIR / relative_path
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)
    return TARGET_DIR


def validate_skill() -> None:
    validator_path = _creator_script("quick_validate.py")
    result = subprocess.run(
        [sys.executable, str(validator_path), str(TARGET_DIR)],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stdout.strip() or result.stderr.strip()
        raise RuntimeError(f"WorkBuddy skill validation failed: {detail}")


def package_skill() -> Path:
    validate_skill()
    PACKAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    packager_path = _creator_script("package_skill.py")
    with tempfile.TemporaryDirectory(prefix="pixel3mf-workbuddy-package-") as tmp:
        tmp_path = Path(tmp)
        result = subprocess.run(
            [sys.executable, str(packager_path), str(TARGET_DIR), str(tmp_path)],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            detail = result.stdout.strip() or result.stderr.strip()
            raise RuntimeError(f"WorkBuddy skill packaging failed: {detail}")
        workbuddy_zip = tmp_path / "pixel-art-to-3mf.zip"
        if not workbuddy_zip.is_file():
            raise RuntimeError("WorkBuddy packager did not create the expected ZIP")
        packaged_files: dict[str, bytes] = {}
        with zipfile.ZipFile(workbuddy_zip) as archive:
            for name in archive.namelist():
                if not name.endswith("/"):
                    packaged_files[name] = archive.read(name)
        temporary_path = tmp_path / PACKAGE_PATH.name
        with zipfile.ZipFile(temporary_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted(packaged_files.items()):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, data)
        temporary_path.replace(PACKAGE_PATH)
    return PACKAGE_PATH


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--package", action="store_true")
    args = parser.parse_args()
    if args.check:
        if not skill_tree_matches():
            raise SystemExit("WorkBuddy skill is out of sync")
        validate_skill()
        print(TARGET_DIR)
        return
    sync_skill_tree()
    validate_skill()
    print(TARGET_DIR)
    if args.package:
        print(package_skill())


if __name__ == "__main__":
    main()
