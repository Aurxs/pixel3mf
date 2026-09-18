# Prepare an existing source

Commands use `PYTHON` for a compatible interpreter and `SKILL_DIR` for this skill's absolute path. Use a new output directory. The tool retains the original and a lossless PNG derivative.

For raw or enlarged pixel artwork:

```bash
"$PYTHON" "$SKILL_DIR/scripts/prepare_source.py" /absolute/source.png /absolute/run/prepared
```

This calls Perfect Pixel with automatic grid detection, center sampling and no forced square. It thresholds sampled alpha at 128 only after refinement, tight-crops fully transparent outer rows/columns and saves `04_pixel_perfect.png` plus `05_pixel_preview_8x.png`. A detected grid different from the prompt is not an automatic failure; judge the refined result.

A known final logical grid skips this tool and goes to `bead_pattern.py`. If it needs preparation, use `--logical` to avoid redetection and preserve its existing canvas. Logical input must have binary alpha.

## Background choices

- Usable existing transparency: preserve it; no segmentation.
- Intentional opaque background: preserve it; no segmentation.
- Opaque background explicitly needing removal: add `--remove-background`. The bundled IS-Net worker keeps source RGB and passes semantic confidence through cell sampling. Ambiguous components block acceptance; inspect the saved diagnostic overlay.
- A reviewed foreground mask: add `--mask /absolute/mask.png`. It must be binary and match the EXIF-oriented source dimensions. It takes precedence over segmentation.
- Never globally erase white. White fur, eyes, clothing and intentional scenery remain opaque.
- A painted checkerboard is not transparency. Remove it with an appropriate reviewed mask/segmentation or regenerate a fresh source within the retry limit.

After semantic removal, inspect the complete contour, pale subject areas and holes. If alpha was already usable, omit removal rather than running a second mask. Raw partial alpha is supported by the normal refinement route; the optional semantic-removal route requires opaque/binary input or a reviewed mask.

## Acceptance

Review the final enlarged preview against the original subject brief. Check recognition, complete silhouette, coarse readable cells, background intent and alpha. The tool labels output `needs_visual_review`, never automatically accepted. Keep prep metadata and failed candidates. No 60–85 density gate, Lumina sizing or 3MF cleanup rules apply.

Shrinking an accepted grid changes the design. If the user requires a smaller target, prepare a separate derivative, preserve aspect ratio, inspect the lost detail and record the change. The chart tool only offers non-destructive padding through `--canvas`; it intentionally rejects implicit shrinking or stretching.
