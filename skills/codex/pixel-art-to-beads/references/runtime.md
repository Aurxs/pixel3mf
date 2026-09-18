# Project runtime

Locate the project containing both `tools/beads/run_workflow.py` and `skills/codex/pixel-art-to-beads/`. Resolve its absolute path as `PROJECT_ROOT`, then use:

```bash
TOOLS_DIR="$PROJECT_ROOT/tools/beads"
PYTHON="$PROJECT_ROOT/.venv/bin/python"
```

On Windows choose the project's `.venv/Scripts/python.exe`, or another compatible Python 3.10+ interpreter. Commands use absolute paths and work from any current directory. The installed skill directory contains instructions and assets, not the executable tools. The project is required; other skills, Lumina and printer profiles are not.

Base packages for existing logical PNGs: Pillow, NumPy, ReportLab. `tools/beads/requirements.txt` declares them. Raw grid recovery additionally needs `perfect-pixel[opencv]`. Optional semantic background removal needs `rembg[cpu]` and psutil. Install only missing packages in a suitable environment when permitted. The optional model may need its first download; the source is processed locally. Respect offline requests.

The renderer requires a CJK TrueType font readable by both Pillow and ReportLab. macOS automatically finds Arial Unicode; supply `--font /absolute/path/to/font.ttf` on other systems if automatic discovery fails. Do not copy a proprietary system font into the skill. Font coverage is checked before export.

Optional segmentation is CPU-only: supported IS-Net models, one worker at a time, six OMP threads, 300-second timeout, 8 GiB RSS limit. `U2NET_HOME` overrides the normal `~/.u2net` model cache. It never searches another skill or a Lumina checkout. Existing usable alpha skips segmentation entirely.

All executable paths resolve under `TOOLS_DIR`. The default palette resolves under the project’s `skills/codex/pixel-art-to-beads/assets/palettes/`. Generation uses the host image-generation tool, not a bundled credential or another skill. If no generation tool is available, existing-art conversion still works; disclose that new-art generation is unavailable.

For PDF inspection, use an available renderer such as `pdftoppm`. Do not make a successful numeric check stand in for layout inspection.

## Provenance

`remove_background.py`, `semantic_segment.py` and `cleanup_pixel.py` are bead-specific snapshots of the user's local pixel preparation implementation, copied on 2026-09-18. All their local imports resolve inside `tools/beads/`. The cache location has been made independent, and semantic finalization preserves detached occupied cells for review. `prepare_source.py` is the supported entry point; do not call the legacy cleanup CLI, which has older white-removal behavior.

Style references are local copies of the user's existing approved pixel-style assets. They convey block construction only. No symlinks or absolute asset paths point to other skills.

MARD data derives from the MIT-licensed `maxcleme/beadcolors` commit `29229889daab404fb30531d4bb785fd73f7f58e3`. The raw source and MIT notice are retained under `assets/palettes/`. The 221-color subset includes groups A-H and M; special-effect groups are excluded. RGB values are community approximations, not manufacturer measurements. Runtime conversion needs no palette download.
