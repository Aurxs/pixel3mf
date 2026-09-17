#!/usr/bin/env python3
"""Build the separate WorkBuddy general-subject skill and importable ZIP."""

from pathlib import Path
import shutil
import zipfile


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    source = root / "skills/general-pixel-art-to-3mf"
    target = root / "workbuddy/skills/general-pixel-art-to-3mf"
    files = {Path("SKILL.md"): (source / "SKILL.md").read_bytes()}
    for folder in ("references", "assets"):
        for path in (source / folder).rglob("*"):
            if path.is_file():
                files[path.relative_to(source)] = path.read_bytes()
    files[Path("scripts/refine_pixel.py")] = (root / "tools/refine_pixel.py").read_bytes()
    for path in list(files):
        if path.suffix == ".md":
            text = files[path].decode().replace(
                "tools/refine_pixel.py", '"$SKILL_DIR/scripts/refine_pixel.py"'
            ).replace(
                "the app's bundled Python/Pillow runtime", "the WorkBuddy project's Python/Pillow runtime"
            ).replace(
                "For the built-in image tool, request real transparency in the prompt.",
                "For native WorkBuddy ImageGen, use its documented transparency controls when exposed; otherwise express the request in the prompt and verify the output.",
            )
            if path == Path("SKILL.md"):
                start = text.index("For new isolated-subject images,")
                end = text.index("\n\n## Stage boundaries", start)
                text = text[:start] + (
                    "Generate on a uniform pure-white, fully opaque background in WorkBuddy. "
                    "Do not request transparent generation or pass transparency parameters. "
                    "Remove background locally only after a source exists; preserve intended white subject details."
                ) + text[end:]
                text = text.replace(
                    "For a generated source with real transparency, including partial alpha:",
                    "For the WorkBuddy-generated white-background source, first create a reviewed background-removed derivative using the workspace segmentation tool. Pass that derivative to the packaged helper:"
                ).replace("/absolute/path/to/01_source.png ", "/absolute/path/to/02_bg_removed.png ")
            elif path == Path("references/generation-prompt.md"):
                start = text.index("Choose one background instruction")
                end = text.index("```text", start)
                text = text[:start] + (
                    'WorkBuddy background instruction: "Opaque PNG on uniform pure white RGB (255, 255, 255), alpha 255 everywhere. No background texture, shadows or checkerboard."\n\n'
                    "Always use this instruction in new-generation payloads. Do not request transparent generation or add transparency parameters. Background removal is a later local processing step.\n\n"
                ) + text[end:]
                text = text.replace("<selected background instruction>", "Opaque PNG on uniform pure white RGB (255, 255, 255), alpha 255 everywhere. No background texture or shadows")
            elif path == Path("references/source-acceptance.md"):
                text = text.replace("## Select preparation", "## Select preparation\n\nNew WorkBuddy generations use opaque white backgrounds. Select the opaque-background preparation branch below. Existing alpha applies only to user-provided files or local derivatives, not a requested generator capability.")
            elif path == Path("references/pixel-refinement.md"):
                text = text.replace("For a generated source with real transparency", "For a user source or prepared derivative with real transparency")
                text = text.replace("For generated transparent artwork", "For a prepared cutout")
            files[path] = text.encode()
    files[Path("SKILL.md")] += (
        "\n\n" + (root / "workbuddy/general-host-adapter.md").read_text()
    ).encode()
    if target.exists():
        shutil.rmtree(target)
    for path, content in files.items():
        out = target / path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(content)
    package = root / "dist/general-pixel-art-to-3mf-workbuddy.zip"
    package.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, content in sorted(files.items()):
            entry = zipfile.ZipInfo(f"{target.name}/{path.as_posix()}", (1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, content)
    print(target)
    print(package)


if __name__ == "__main__":
    main()
