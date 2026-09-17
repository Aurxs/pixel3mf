# WorkBuddy migration validation — 2026-09-17

## Current status

**The fresh Yoimiya workflow has now completed through both final 3MFs in WorkBuddy**, using Deepseek-V4.1-Flash for orchestration and native hunyuan-image-alpha for drawing. Final run: `output/20260917_182340_yoimiya-e2e-cn2`.

This was a new prompt-to-image run, with no old image or old mask substitution. Attempt 1 passed objective gates but had misaligned eyes; attempt 2 was rejected for a 96 x 96 grid/non-white border; attempt 3 passed 64 x 64 and visual acceptance. The automatic semantic mask required reviewed correction, so this demonstrates a completed workflow with explicit mask review, not unattended reliability. The UI connection recovered after the user confirmed the computer was unlocked; the prior stale UI alone did not prove a lock state.

Final files:
- `08_yoimiya-e2e-cn2_2x2.3mf`
- `08_yoimiya-e2e-cn2_3x3.3mf`
- `05_pixel_preview_8x.png`
- Both `06_lumina_2d_preview_*.png`
- `manifest.json` and `workbuddy_state.json`

## Repairs installed

- WorkBuddy-only generation and source-acceptance references, leaving the Codex core source unchanged.
- Explicit 64 x 64 canvas and concise Chinese close-up/white-margin instructions; text-only native generation defaults. Old coarse reference images had dominated the native image-editing model.
- Exact original candidate preservation, SHA-256 audit, and border-connected near-white normalization (minimum RGB channel 240, channel spread at most 8). Opaque-only; all border pixels must qualify. Enclosed highlights, alpha and dimensions remain unchanged.
- Per-run pinned fenced prompts. An optional fenced identity block keeps research URLs and audit notes out of the image payload.
- `render-prompt --json` supplies the exact prompt, actual original reference paths, and a safe `00_incoming/` output directory. It avoids arbitrary native filenames blocking conversion ownership checks.
- Candidate lifecycle documentation now matches import/decide behavior, including direct-input filenames.
- Background-normalization metadata is accepted and retained by the real pipeline schema.
- ONNX segmentation workers disable unused Numba JIT, avoiding PyMatting import-time temporary-cache probes that triggered WorkBuddy's bulk-delete guard. WorkBuddy safety protections, CPU-only inference and RSS limits remain enabled.
- Delivery requires visual silhouette/hole checks. Zero ambiguous components and status=success alone are insufficient. Simple closed white-background sources can use the existing conservative white mode; images with true enclosed holes still require semantic review or a specifically reviewed mask.

The project instructions were updated in WorkBuddy. Generated project Skill files, the installed local personal Skill copy, and `dist/pixel-art-to-3mf-workbuddy.zip` were synchronized.

## Focused checks

- WorkBuddy-specific suite: 43 checks passed at the interface-repair stage.
- ONNX worker tests: 4 passed after the JIT fix.
- After concise prompt changes, 4 affected prompt/research/package checks passed, including one new identity-block isolation regression.
- Ruff checks passed for changed Python files. No repository-wide slow tests were run.

## Live evidence

- `output/20260917_150938_friendly-rby-robot`: original coarse references, three rejected images, roughly 30-cell grids.
- `output/20260917_151920_robot64`: explicit grid with old references still produced a 30 x 28 source.
- `output/20260917_153338_robot64text`: fresh native text-only image passed 64 x 64 acceptance; real conversion completed after the worker fix, but visual QA found semantic shoulder loss. Retained as diagnostic evidence, not the final deliverable.
- `output/20260917_154450_robot64final`: re-export of that same newly generated robot with the existing white mode; complete 52 x 60 silhouette, preserved eye highlights and continuous black baseline; both final 3MFs produced. The user rejected the robot as an unrepresentative acceptance subject.
- `output/20260917_155008_yoimiya-workbuddy`: old-source regression only, not a fresh-generation acceptance. It exposed false foreground decisions in the hair/body background gaps. The user clarified that this was not the requested end-to-end test.
- `output/20260917_155752_yoimiya-e2e`: genuine NEW Yoimiya generation with the previous long English template. Three returned images were rejected: 94 x 96; 166 x 168/non-pixel style; 64 x 64 but hair touching the canvas top. One intervening provider-unavailable response returned no image. The run is exhausted; no conversion occurred.

Actual native image-service models observed in local logs: `hunyuan-image-alpha-edit` with input references, `hunyuan-image-alpha` for text-only generation. DeepSeek v4.1 Flash is the orchestration model, not the drawing model. Some artifacts conservatively record `workbuddy-native-unknown` because the native tool response omitted model identification.

## Final acceptance evidence

The final source is selected attempt 3 of the fresh run above. Its source grid is 64 x 64; the tight export grid is 35 x 48. The two-model semantic route correctly stopped on ambiguous component 5, but also falsely kept background component 6. A subsequent white-mode export filled actual holes and was preserved under `pipeline_failures/superseded_white_method/`; it is not the final deliverable. WorkBuddy then constructed and applied a specifically reviewed source-resolution binary mask, removing background components 5, 6 and 9 while preserving eye whites, clothing, colors and baseline.

Mask: `output/validation_inputs/yoimiya-e2e-cn2-source-mask-1024.png`.
Audit: `output/validation_inputs/yoimiya-e2e-cn2-mask-audit.json`.
Original review instructions are retained as `workbuddy/cases/yoimiya-cn2-mask-review.txt`.

Final manifest status is success and wrapper status is converted. Both previews were visually inspected. The exported grid has binary alpha [0,255] and a continuous dark bottom baseline. ZIP CRC checks and XML parsing passed for both 3MFs (2 model XML entries each). File sizes: 2x2 = 1,187,884 bytes; 3x3 = 1,798,816 bytes. No physical print was performed.

A 502 response interrupted the orchestration once and was resumed. DeepSeek also spent excessive time repeatedly reasoning about the same white region; an explicit component review resolved this. The host Skill now explicitly prohibits switching to white mode solely to bypass an ambiguity failure where true holes exist.

## Continuation at 18:15

- `output/20260917_181017_yoimiya-e2e-cn`: one genuine native text-only generation via Deepseek-V4.1-Flash, image model hunyuan-image-alpha. The 63 x 64 source has an opaque near-white background; six of 4096 border samples fell below the previous 245 minimum (lowest channel 241, maximum channel spread 6). Original preserved, no 3MF export. Visual review additionally found uneven eye levels.
- Adjusted normalization minimum to 240, retaining the all-border, opacity, chroma and connectivity protections. Extended the existing two focused tests with warm-white noise, dark border and below-floor cases; both pass. Ruff passes.
- Clarified that rectangular source grids within the accepted per-axis range pass; the live model had invented an exact-square rejection. Existing recoverable-noise rules remain unchanged.
- Updated and synchronized the host eye-alignment prompt, project/personal Skill and ZIP. Prepared next-run-yoimiya.txt for up to three fresh images in a new run. No old image may be substituted.
