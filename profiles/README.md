# Pinned slicer profile

`bambu_a1mini_0.4_0.08_extra_fine_pixel3mf.json` is the complete flattened `project_settings.config` baseline used for final 3MF normalization.

It was derived from Bambu Studio 02.07.01.62's installed official profiles for:

- Bambu Lab A1 mini 0.4 nozzle
- `0.08mm Extra Fine @BBL A1M`
- Bambu PLA Basic on A1 mini

The snapshot also contains the pixel3mf-specific overrides documented in the project README, including a 170 mm prime tower with a 1 mm brim at `X=5, Y=160`. Dynamic Lumina colours and the first source `N×N` flush matrix are applied by the normalizer. Keeping the flattened snapshot in the outer repository makes export deterministic and avoids a runtime dependency on Bambu Studio or edits inside `Lumina-Layers/`.

When intentionally refreshing the snapshot for a newer Bambu Studio release, re-run the 3MF normalization tests and slice both a real `2×2` and `3×3` output before replacing this file.
