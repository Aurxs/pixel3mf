# Pixel3MF WorkBuddy project instructions

## General-subject workflow

For the explicitly selected `general-pixel-art-to-3mf` skill, load `.codebuddy/skills/general-pixel-art-to-3mf/SKILL.md`. It uses the processed corgi style reference, native WorkBuddy ImageGen, the skill-packaged Perfect Pixel helper, and the workspace cleanup/Lumina tools. Review pixel quality after Perfect Pixel. Do not route this skill through the anime `workbuddy_pixel3mf.py` candidate/accept/convert state machine or apply the 60–85 source-density rule. Use the existing WorkBuddy project workspace and runtime.

The remaining instructions below describe the original anime `pixel-art-to-3mf` workflow; they do not override the separate general workflow.

Use `/Users/aurxs/Program/pixel3mf_workbuddy` as the only WorkBuddy production workspace for this project. Treat `/Users/aurxs/Program/pixel3mf` only as the upstream baseline repository and never run WorkBuddy tasks there.

Load the project-level `pixel-art-to-3mf` Skill for pixel-art generation, creative editing, source preparation, or layered 3MF conversion. The project Skill takes precedence over the personal discovery copy.

- Use Plan mode for an unapproved creative generation request or budget. An explicit request to execute a real generation already authorizes that run; proceed in Default mode within its stated budget.
- Use Ask mode for inspection, diagnosis, and artifact review; do not write files in Ask mode.
- Use Default mode for an approved direct conversion or an already approved plan.
- Preserve every stage gate and its context boundary. Do not inspect post-generation references before a source exists, and never add detector results or conversion settings to an image-generation prompt.
- Use `tools/workbuddy_pixel3mf.py` for run initialization, prompt rendering, TokenHub generation or WorkBuddy-candidate import, source decisions, and conversion. Do not recreate the Python pipeline in shell commands.
- Treat `convert` as the deterministic Stage 3/4 implementation boundary. Do not preload Lumina reference details into model context; the wrapper enforces the semantic and ambiguity gate before Lumina.
- If a submitted TokenHub task becomes uncertain, resume that task instead of starting another paid attempt. Resolve pending private-COS cleanup before continuing.
- Never enable `--allow-ambiguous-mask` automatically. Present the overlay and component report when the pipeline blocks on ambiguity.
- Keep WorkBuddy Default Permissions enabled. Request only project file access, `.venv/bin/python`, localhost port 8000, TokenHub/COS network access, Keychain reads, and the initial IS-Net model download.
- When TokenHub is unconfigured, WorkBuddy's default image generator may be used as the explicit provider. Read the updated local `.codebuddy/skills/pixel-art-to-3mf/SKILL.md`. Render the isolated prompt and original reference paths with `render-prompt --json`, use its `output_dir` for the native tool, make exactly one image per attempt, register it with `import-candidate`, and preserve the shared three-attempt limit. Never switch providers after a TokenHub task was submitted or attach a rejected image to a retry.
- Present the final pixel preview, both Lumina previews, both final `08_*.3mf` models, and `manifest.json`. Clearly label the `07_*.zip` files as unmodified Lumina archives.
