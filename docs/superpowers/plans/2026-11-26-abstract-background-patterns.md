# Abstract Background Patterns Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal.** Add seeded irregular waves and ovals plus a generator for broad, free-form tonal regions behind the saved matte.

**Architecture.** Extend the existing Background pattern evaluator and generator. Keep one signed field and the current compositing, preview, export and recovery paths. Bind new geometry to the saved field and select its renderer version from the canonical settings.

**Tech stack.** Existing Python 3.12, NumPy, Pillow, and the shipped HTML review page.

**Spec.** [Approved behavior](#approved-behavior). The comparison base is `1c8dccbc3524fa5cc1a01a0306aae7018c7e22cd` in the current worktree.

## Approved behavior

- Give Waves, Ovals and Mixed an optional smooth, seeded distortion. Bands can change spacing and taper into unpatterned areas. Ovals can become asymmetric while keeping their editable centres.
- Add **Abstract** to Generate pattern. It proposes one editable contour region whose broad tonal shapes vary with the photo seed and Next variation. Large quiet areas and soft edges retain the dark-fog look.
- **Irregularity (%)** runs from 0 to 100 and starts at 0. It affects waves and ovals. Strength and the two existing tones control visibility and colour. The Abstract shape exposes position, rotation, both radii and softness through the existing geometry controls.

## Global constraints

- The pattern stays behind the matte. Preserve source RGB, saved alpha, opaque subject pixels, Lit backdrop fade operands and diagnostic views. Keep existing edit, comparison, authentication, draft and revision guards.
- Zero Irregularity has the existing wave and oval behavior. Omit zero from canonical settings. Existing recipe and manifest bytes, generation seeds, weight bytes, and replay behavior require no migration. Revisions using the new settings require the updated reader. Keep both algorithm versions usable and restore previous revisions normally.
- Use native coordinates and the existing 64-row raster boundary. Keep seeds deterministic with a versioned SHA-256 namespace. Preserve finite validation, signed quantization, tone mapping, qualified dither, and bounded allocations. This plan adds no dependencies or photo data.
- Set `IMAGE_MASK_PYTHON` to the absolute interpreter path in the existing Python 3.12 project environment. Bind `PYTHONPATH="$PWD/src"` for tests that launch application subprocesses so the environment imports the current checkout. The user authorized plan review, implementation and implementation review in that order.

## Review focus

1. Same layout, different amount or effective seed must bind different geometry. Tone, Strength and enable edits continue to reuse saved weights. Task 2.
2. Missing or zero Irregularity must keep legacy quantization and generated proposals exact. Task 1.
3. Crop, native replay, margin and series previews use the same native coordinates, including samples outside the original canvas. Opaque subject contributions stay exact. Tasks 1 and 2.
4. Invalid optional values, malformed contour fields and mismatched algorithm versions must fail before use. Tasks 1 and 2.
5. Abstract selection, Next variation, stale proposals, and the slider must respect existing draft ownership and reopen correctly through the page. Task 3.

## Task 1 — Add deterministic geometry and validation

**Files.** `src/blackmask/background_pattern.py`, `src/blackmask/background_pattern_generation.py`, `tests/test_background_pattern.py`, `tests/test_background_pattern_generation.py`.

**Interfaces.** The existing normalize, sample, make, default-seed and generate functions retain their signatures. `PatternSettings.irregularity` is an optional finite float in [0, 1]. `ContourShape` adds `type="contour"`, `radii_xy` and `softness` with Oval ranges, and a required uint32 `seed` to the shared placement fields. The origin schema remains version 1 and adds style `abstract`.

- [x] Add a legacy raster oracle to `test_pattern_irregularity_preserves_v1_and_crops`. On a 9×7 raster with the existing default `wave()` and `oval()` fixtures, SHA-256 of little-endian uint16 samples is `2aed1a8ce116623cfe3873c04660da1c4bb37167c9be7fd917a74d6eaca1e06c`. Check the same hash with explicit zero. At 121×101, check a nonzero setting changes the field, repeating the settings yields exact pixels, a second seed changes the field, and a non-origin crop equals the matching full-field slice.
- [x] Add `test_abstract_contours_have_both_tones_and_quiet_space` using fixed seeds, native size 121×101, and public generation and raster APIs. Assert there are samples of each sign and neutral, no reserved code zero, and two selected seeds yield different fields. Check a different crop and outside-native coordinates against the same evaluator. Extend invalid-setting coverage for booleans, NaN/range violations, missing contour seed, invalid seed and extra contour keys.
- [x] Implement the canonical settings and geometry. Keep the existing wave/oval operations exact if `irregularity` is absent or zero. For deterministic phases, take five successive four-byte unsigned big-endian integers from SHA-256 of the ASCII string `background-pattern-v2/{purpose}/{seed}/{shape_id}`, multiply each by τ/2³². Use purpose `warp` with the layout origin seed or 0 for a manually authored layout. Use purpose `contour` with the saved contour seed.
- [x] With local coordinates (along, across) and S the shorter native side, set u=along/S and v=across/S for irregular waves and ovals. Scale the displacement by 0.09×S×Irregularity. For the along displacement, sum sine terms with linear coordinates (0.55u+0.30v, 0.21u−0.79v), phases (p0, p1) and amplitudes (1, 0.30). For the across displacement use (−0.34u+0.56v, 0.81u−0.24v), phases (p2, p3) and the same amplitudes. For each term subtract its sine value at the centre, keeping the centre anchored. Each linear coordinate is multiplied by τ before its phase is added. For waves multiply the band weights by `1-a*(1-smoothstep(0.48+0.72*cos(τ*(0.37*u+0.21*v)+p4)))`, using the warped normalized coordinates and Irregularity a. This leaves exact legacy values at zero and creates gradual breaks at high settings. [Low-frequency coordinate warping](https://developer.nvidia.com/gpugems/gpugems3/part-i-geometry/chapter-1-generating-complex-procedural-terrains-using-gpu)
- [x] Sample contours in local coordinates divided by their horizontal and vertical radii. Sum seeded sines using linear coordinates (0.31u+0.13v, −0.19u+0.42v, 0.53u−0.37v), phases (p0, p1, p2), and amplitudes (0.55, 0.30, 0.15). If their sum is f, use `sign(f)*smoothstep((abs(f)-0.18)/0.58)` multiplied by the same elliptical soft envelope as Oval. This creates continuous variations and a neutral interval. Use the existing sum, clip and quantization rules with all shapes. Keep evaluation strip-local within the existing conservative scratch allowance of 192 bytes per sample.
- [x] Implement the generator's Abstract branch with one `abstract-contours` shape. Use the existing hash draws with centre fractions (0.42–0.58, 0.43–0.61), rotation 0–360°, radius fractions (0.72–0.94, 0.72–0.94) each floored at 0.5 px, softness 0.65–0.90, and the proposal seed as the shape seed. Assert the three earlier generator layouts remain exact and the new shape is valid at 1×1.
- [x] Run `rtk proxy "$IMAGE_MASK_PYTHON" -B -m pytest -q -p no:cacheprovider tests/test_background_pattern.py tests/test_background_pattern_generation.py` before and after changes. New cases should fail on unsupported settings and then pass with the legacy cases.

## Task 2 — Save, restore and deliver selected geometry

**Files.** `src/blackmask/background_pattern.py`, `src/blackmask/effects.py`, `tests/test_background_pattern_project.py`, `tests/test_background_pattern_delivery.py`.

**Interfaces.** `pattern_algorithm(settings: PatternSettings) -> str` returns `signed-background-pattern-v2` when settings have positive Irregularity or any contour shape, and `signed-background-pattern-v1` otherwise. The saved revision record schema and bound members stay the same.

- [x] Add `test_abstract_and_warped_pattern_revisions_reuse_only_matching_geometry`. Apply a v1 pattern, apply the same shapes with a positive amount, and then change the effective origin seed without changing the shapes. Assert the revision records select the correct algorithm, the affected fields have distinct hashes, palette-only changes reuse the selected field, and restore reopens the exact earlier draft. Assert legacy reads do not change saved bytes. Test a v2 geometry record falsely labeled v1.
- [x] Key field inheritance by shapes, effective Irregularity and effective warp seed. Compare zero and absent identically, and ignore the origin seed when a warp cannot affect the field. Keep phase settings and arbitrary origin metadata outside the geometry key unless they affect the raster. In the effects execution identity select the normalized algorithm when replacing and the validated parent's algorithm when inheriting. Validate the record algorithm against normalized settings on load before return.
  Retaining an Abstract origin after removing its contour can select v1 raster evaluation. That origin setting still requires the updated reader.
- [x] Add `test_v2_pattern_delivery_matches_preview_and_keeps_opaque_lit_fade` for a contour mixed with an irregular wave. Bind the exact native operands, check preview/export agreement across Add margins and Match series, and compare opaque pixels with pattern OFF on a synthetic project using Lit backdrop fade. Exercise the real preview and export paths. Native replay reads saved weight bytes. Match series reevaluates the saved settings through the existing sampler, retaining its mapped output coordinates. Keep legacy diagnostics exact.
- [x] Run the existing project and delivery suites with `rtk proxy "$IMAGE_MASK_PYTHON" -B -m pytest -q -p no:cacheprovider tests/test_background_pattern_project.py tests/test_background_pattern_delivery.py tests/test_spatial_fade_target.py`.

## Task 3 — Author, preview and document the two controls

**Files.** `src/blackmask/ui/review.html`, `tests/test_background_pattern_viewer.py`, `tests/test_lifecycle_browser.py`, `README.md`, `docs/workflow.md`, `docs/file-contract.md`, `docs/assistant-workflow.md`, `docs/troubleshooting.md`, `docs/validation.md`.

**Interfaces.** The existing Generate route accepts style `abstract`. The existing Preview and Apply settings accept `irregularity` and contour geometry through the canonical validator. The page exposes a range control and an editable numeric **Irregularity (%)** companion, plus **Abstract** as a generator style. No endpoint changes are required.

- [x] Extend the real loopback test to submit Abstract, advance its seed and receive another bound shape. Compare saved preview and reopen. Extend the shipped-page harness to assert keyboard/numeric edits, rejection of invalid irregularity, Cancel/Use preserving scalar settings, stale responses rejected, and saved-only OFF preserving a newer draft. Add coverage for the contour radius and softness controls and the non-applicable shape tone selector.
- [x] Bind both Irregularity fields to the existing versioned draft. Remove the optional key at zero, keep fractional percentages, and retain the amount through Generate, Next variation and Use. Render generated contours as **Contours** with the existing centre, rotation, radius and softness inputs. Use the ellipse as the contour envelope. Label outlines as editable geometry and use Preview for the resulting field. Reuse keyboard, proposal, stale and completion guards.
- [x] Extend the runner-selected `tests/test_lifecycle_browser.py` case to use both changes, preview and apply, and verify the same settings after reload. If the isolated locked Python Playwright target is unavailable, run the equivalent shipped page journey in the installed local Chrome with synthetic input, and report the separate evidence.
- [x] Update workflow and file contract with the exact controls, default, bounds, v1/v2 compatibility and saved replay behavior. Capture actual validation evidence in the validation document. Inspect a synthetic sample of both versions at normal view scale, keeping the two tones and Strength fixed. Check the evaluator's peak allocated scratch on a representative mixed 64-row strip against the existing bound.
- [x] Run `rtk proxy env PYTHONPATH="$PWD/src" PYTHONDONTWRITEBYTECODE=1 "$IMAGE_MASK_PYTHON" -B -m pytest -q -p no:cacheprovider tests/test_background_pattern*.py tests/test_series_framing.py tests/test_framing.py tests/test_review.py tests/test_spatial_fade_target.py tests/test_previews.py tests/test_viewer_page.py tests/test_viewer_coordinates.py tests/test_effects.py tests/test_operations.py tests/test_lifecycle_browser.py` in isolated groups if useful. Run Ruff lint/format and mypy using the existing environment. Verify documentation links and compare against the authorized changes.

## Review sequence

- [x] Independently review the plan for algorithm and saved-geometry correctness, and for authoring and verification coverage. Both independent reviews found no material gaps. The plan clarifies Abstract origin compatibility and the strip scratch verification.
- [x] After implementation, independently review renderer/delivery and authoring/docs. The authoring reviewer identified the tone selector's hidden-state CSS; reproduced and fixed it, added browser coverage, and verified the fix independently and in installed Chrome. The renderer reviewer found no material improvements.
