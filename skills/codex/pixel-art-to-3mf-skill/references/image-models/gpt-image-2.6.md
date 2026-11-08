# GPT Image 2.6 — API parameter profile

Load only in Stage 1 after the user selects the GPT Image 2.6 API route. This is transport configuration, never visual-prompt content. Read the adjacent `gpt-image-2.6.json` for machine-readable values. This profile supports only Sunburst and Flare; no other model family is currently adapted. Do not modify installed system skills or their bundled CLI.

## Selection and defaults

| Setting | Default | Supported workflow overrides |
|---|---|---|
| model | `gpt-image-2.6-sunburst` | `gpt-image-2.6-flare` |
| quality | `high` | `low`, `medium`, `high`, `auto` |
| complexity | `high` | `low`, `medium`, `high` |
| size | `1024x1024` | `1536x1024`, `1024x1536`, `auto` |
| background | `opaque` | `transparent`, `auto` only on user request |
| output_format | `png` | PNG only for this pixel workflow |
| n | `1` | One output per recorded attempt |
| augment | enabled | Disable only when the user asks |

These are workflow defaults, not a claim that the API lacks other formats or batch sizes. The 2.6 guide specifies high as the default complexity. It is independent of rendering quality. If the client has no complexity field, omit it for the default high; an explicit low/medium request must be transmitted using a client supporting that field, not silently ignored. Do not place it in the prompt as a substitute.

Do not infer 2.6 support for `xhigh`/`max` quality or custom-resolution limits from documentation naming only 2.5. Do not send `input_fidelity`, legacy `style`/`response_format`, or invented seed/steps/CFG options. GIF, SVG, streaming and compression are outside this PNG workflow.

## Prompt and references

Keep the CLI's default augmentation: **do not add `--no-augment` by default**. With no extra augmentation fields, the bundled CLI sends `Primary request: ` followed by the complete skill prompt. Do not add style, composition, palette or lighting CLI fields by default, since these belong in the skill prompt. For a direct client, apply that same prefix once; do not double-wrap an already augmented prompt. Save both raw and effective prompts.

Use `/images/edits` when there are references (the normal workflow), preserving their order. Supply image bytes through multipart `image[]`, or the documented JSON `images` list with base64 data URLs/file IDs; a local filename is not a remote image input. Up to 16 references. Use `/images/generations` only when there are none. Do not send previous generated attempts as reference inputs. The final augmented prompt must fit the 32,000-character limit.

The API returns base64 image data. Decode `data[0].b64_json` and save as `01_source.png`; do not request URL response format. Record the requested model and any model identity actually returned separately. Do not claim the server disclosed an identity if it did not.

## Bundled CLI mapping

Use the imagegen skill's installed `scripts/image_gen.py` with the `edit` subcommand and repeated `--image` arguments. Pass `--model`, `--quality`, `--size`, `--background`, `--output-format png`, `--n 1`, `--prompt-file`, and `--out` explicitly. Leave augmentation enabled. For a source without references, use `generate`.

The bundled CLI currently does not expose `complexity`. For default high, omission is valid. If the user requests low/medium complexity, use the configured OpenAI client with `complexity` as a request field (or SDK `extra_body` when its typed signature lacks the field), preserving this profile's effective prompt and reference ordering. Never modify the shared bundled script to add a flag. An unsupported client option should be resolved before sending the request, not retried as image failure.

## Credentials, failure and downstream behavior

Use only `https://api.openai.com/v1` and `OPENAI_API_KEY` loaded from the user's environment/configuration. This adapter does not support third-party proxies or arbitrary base URLs. Keep keys and image base64 out of logs and saved request metadata. Save only effective non-secret parameters, raw/effective prompt and reference paths.

Honor explicit user overrides within this profile. If the user asks for another model, say it is not yet adapted rather than substituting. Authentication, quota, network and unsupported-parameter errors are transport issues: resolve or report them without repeated image generation or a model switch.

For normal white-first processing, explicitly request `background=opaque`. Transparent output is opt-in and requires the matching alpha-preservation workflow; never silently switch background modes. Model parameters do not replace Stage 1 visual instructions or later processing rules.

## Official sources

- https://developers.openai.com/api/docs/guides/image-generation#gpt-image-26
- https://developers.openai.com/api/reference/resources/images/methods/edit
- https://developers.openai.com/api/reference/resources/images/methods/generate
