## WorkBuddy host instructions

This is the independent **general-pixel-art-to-3mf** workflow. Use the WorkBuddy production workspace containing `tools/cleanup_pixel.py`, `tools/lumina_batch.py`, `profiles/`, `.venv/`, and `Lumina-Layers/`. On the current machine that workspace is `/Users/aurxs/Program/pixel3mf_workbuddy`. Do not execute WorkBuddy tasks in the separate Codex upstream workspace.

### Generation

- Use WorkBuddy's available native ImageGen tool. Inspect its live schema rather than inventing Codex tool names or arguments. A generation request authorizes the first call; keep the common limit of at most two fresh retries for the same failure.
- Read the packaged generation template, render the short pixel-art prompt, and save it beside `00_subject_brief.md`. Native generation may use arbitrary filenames: direct output into a fresh run's `00_incoming/` when supported, then copy the returned local file to `01_source.png` while preserving the original.
- For subject/style images, use the native tool's documented reference-image field. The default style input is the processed corgi, only as a pixel-style reference. Attach user photos separately and label each role. Do not merely place a filesystem path in prompt text and assume the image was attached.
- WorkBuddy generation uses a uniform pure-white, fully opaque background. Do not request a transparent background or pass transparency parameters. Background removal belongs to local postprocessing; preserve white subject features. User-provided direct-conversion files retain their existing alpha.
- Record the actual returned image provider/model, tool arguments excluding secrets, output path and attempt number. Do not label the orchestration model as the image generator. Do not silently switch to TokenHub or another paid provider. If a submitted call has uncertain status, check that call before retrying.

### Refinement and export

- This package includes `scripts/refine_pixel.py` with `--png-only --binarize-alpha`, so it also works with an older WorkBuddy project that lacks these CLI flags. Set `SKILL_DIR` to the absolute path of this installed skill. Run the script with the project's existing `.venv/bin/python`; do not install a second runtime or copy generated files into the skill itself.
- For an inspected plain-white source with a closed dark outline and clearly foreground enclosed whites, the workspace exterior-only `white` background method can preserve white fur better than automatic semantics. Inspect any real internal gaps separately; do not use this route to ignore ambiguous holes. Use `isnet-general-use` or a reviewed mask when the background cannot be separated safely.
- After raw-content preflight, run the packaged refinement helper, then the workspace's `finalize_pixel_grid` function and final visual review. Source gradients, partial alpha or a grid outside 60–85 must not cause early regeneration.
- Use the workspace's independent `tools/lumina_batch.py` for both accepted-grid exports, preserving the project's exact geometry and slicer handling. Merge command metadata into the run manifest and keep previews, raw ZIPs and final 3MFs distinct.
- **Do not use `tools/workbuddy_pixel3mf.py`'s `init-run`, `import-candidate`, `decide` or `convert` for this general workflow.** That existing adapter snapshots the anime prompt and performs source rejection before refinement. Likewise do not call the old `run_pipeline.py`. These remain available for the separate anime skill.
- Technical conversion success is not visual acceptance. Compare the refined preview and Lumina previews with the requested subject, especially white features and internal holes. Keep unresolved segmentation ambiguous and stop before conversion rather than ignoring it.

No changes to the user's model selection, account settings, memories or unrelated skills are needed. This ZIP contains workflow instructions, the corgi references and the refinement helper; it requires the already deployed local Pixel3MF/Lumina project and does not bundle model weights or credentials.
