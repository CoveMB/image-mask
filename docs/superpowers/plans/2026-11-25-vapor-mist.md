# Vapor Mist Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` according to the execution method the user authorizes. Track work with the checkboxes below.

**Goal** — Give a photographer one Vapor strength control and a point to keep clear. The subject should emerge from a dark, uneven bank of vapor, with fine detail visible at the chosen point and selected outer edges gradually disappearing.

**Architecture** — Add Vapor as a style of the existing Mist layer. First compare the current Mist and Fade into background controls with a single dark, spatially varied Mist layer. If the single layer passes the visual trial, change how Mist places density and reuse its linear-light blend, protection, comparison and editable maps. This avoids a compound Apply that would replace a photographer’s existing fade or disable inward shading.

**Tech stack** — Python 3.12, the repository’s installed NumPy and Pillow, its loopback HTML/JavaScript viewer, pytest and the existing Node page harness. The effect runs offline.

**Spec** — [Reference and proposed behavior](#reference-and-proposed-behavior) below. The full emerging look includes selective loss of subject contrast. The supplied reference is a finished photograph. Photographic acceptance depends on the user's review of the result. [Mist workflow](../../workflow.md#mist) · [Saved Mist contract](../../file-contract.md#saved-mist)

**Trial decision** — The matching capture and matte were found locally. A
strong dark bank on its own softened the lower petals and preserved the
stamens. The stem and leftmost lower petal remained too distinct. The trial
with saved Fade into background brought them farther into the backdrop.
Implement the Vapor field with one Strength control and keep Fade into
background independently editable for those areas. This keeps both effects
available for the reference treatment and preserves a photographer’s existing
fade when applying Vapor.

## Global constraints

- Apply through Image Mask’s controls. Preserve the source, foreground, alpha, existing effects, hard locks and photographic acceptance. Keep the reference, private crops and local evidence out of tracked files and packages.
- Retain one editable Mist layer per revision. Opening a project, choosing a style or placing a focus point edits no saved pixels. Apply creates a revision. Compare Mist OFF bypasses the whole style on that revision.
- Keep original Mist settings, hashes, rendering and delivery identities for projects using the original style. Make Vapor revisions identifiable to updated readers. Older readers must reject unsupported settings or versions clearly. Confirm this compatibility choice before implementation.
- Use native oriented coordinates, the existing RGB16 pipeline and bounded row processing. Reuse the existing protected preview, framing and export paths. No new model, service or dependency is needed.

## Review focus

| Where a plausible implementation can fail | Decisive check |
| --- | --- |
| The result looks like a gray wash, a halo, or a blurred flower | Compare the focal detail, left petal, lower petals, bank and corners separately at fit and native scale (Tasks 1 and 5). |
| The chosen point clears only one pixel, or moving it causes the texture to jump between preview and export | Test the clear core, continuous feather and sampling of the same native positions at different crop and frame origins (Tasks 2 and 4). |
| A style switch overwrites saved Clear mist strokes, an existing spatial fade, or an unapplied edit | Apply, compare, disable, switch styles, reopen and restore through the viewer and request paths (Tasks 3 and 5). |
| An older saved Mist is silently interpreted as Vapor, especially with Lit backdrop also saved | Exercise both algorithms, OFF records, cache reuse and detached deliveries with both fade targets (Tasks 3 and 4). |
| Thin or partially transparent edges change inside protected areas, especially under frame minification | Use nonempty full, partial and zero-alpha locks and a reduced Match series preview with an affected neighboring pixel (Tasks 2 and 4). |

## Reference and proposed behavior

The stamens are sharp, including the dark tips. The ribbing on the left petal remains readable. The lower petals and stem lose contrast unevenly. A broad charcoal bank is strongest below and right of the flower, with quieter haze above and dark corners. In the supplied 1088 × 1445 PNG, a small background patch near 72% across and 77.5% down has median RGB8 `(53,56,54)`; near the bottom-right corner the median is `(8,11,12)`. These are output observations across a particular backdrop. Sampling that bank does not recover the original fog tint, opacity, lens blur or lighting.

The proposed **Mist → Style → Vapor** starts with the bank directed down and right. **Strength** controls both the visible haze on dark background and the loss of contrast where it crosses brighter petals. **Place clear focus** positions a feathered clear region around the detail of interest. Existing Clear mist brushes and rectangles can preserve a second detail such as the left petal. The existing advanced tint, direction and seed controls can refine the pattern. The style adds no blur, changes no photographic exposure and makes no new subject-mask decisions. On a differently lit subject, the same settings reproduce the treatment rather than the reference pixels.

## Task 1 — Establish which blend reproduces the look

**Use** the current [Mist](../../workflow.md#mist) and [Fade into background](../../workflow.md#fade-into-background) controls. This task produces a local comparison and a decision, before any public format or UI change.

- [ ] Use a small synthetic photo project with a near-black backdrop, a warm subject, fine parallel ridges, a narrow stem and partial-alpha edges. Keep its base revision and render an untreated Result. If the user selects the actual untreated cosmos project, use a separate draft on that project for photographic comparison. Keep the supplied finished PNG read-only and outside the processing chain.
- [ ] From the same base, compare **A**, existing Mist alone using a dark charcoal tint, a wide soft bank below/right and feathered Clear mist, with **B**, the same atmospheric treatment plus an independently directed Fade into background across the lower petals. Use the same framing, lighting and center protection. For each, inspect full frame and matching native crops of the stamens, left ribbing and lower petal boundary. Record which observable differences require a change in *placement* and which would require a different *blend*.
- [ ] Use A’s blend for Tasks 2–5 if a denser bank can subdue the outer subject without making the background too bright or washing out the gold. A dark tint can raise a near-black background and lower a bright petal using the same blend. If B alone achieves the balance, show that discrepancy and revise the design for independent subject attenuation before freezing an algorithm. If both fail primarily on optical softness already present in the reference, record that limitation. Synthetic evidence tests the mechanism; an exact match requires a corresponding untreated source and human judgment.

## Task 2 — Build a repeatable density field around a clear focus

**Files** — [mist.py](../../../src/blackmask/mist.py) and [test_mist.py](../../../tests/test_mist.py). Keep `sample_mist_density(settings, native_size_wh, x, y, footprint_px=1)` as the dispatch point returning a uint16 density array. Native, crop and output-grid callers must use this one definition.

- [ ] Add failing tests for `test_vapor_focus_bank_and_corners`, `test_vapor_sampling_is_registered` and `test_vapor_preserves_clear_locked_and_partial_pixels`. Use a portrait fixture and its rotated placement. Assert a nonempty zero-density core, a stronger primary bank than the upper haze and corners, repeatability at a fixed seed, and identical samples for a native subrectangle evaluated directly or cropped from the full map. Test Strength 0, midpoint and 100. At midpoint an affected dark patch must brighten and a gold patch must recede. Full clearance must preserve every RGB16 input code. Include an off-center focus near an edge and a small landscape frame.
- [ ] Run `rtk proxy .venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_mist.py -k vapor`. Expect failures on the missing Vapor behavior.
- [ ] Implement the closed Vapor settings variant in the existing validator. Save exactly `style="vapor"`, `enabled`, `density` (Strength, 0–1), `focus_xy` (two finite native pixel-edge coordinates within the image), `tint_srgb`, `rotation_degrees` and `seed`. Reuse Mist’s current validation for shared fields. Omission of `style` selects the existing closed schema. Reject mixed layouts, unknown styles, invalid values and unknown keys, including while OFF.
- [ ] Build the field in focus-relative coordinates measured in units of the shorter native axis. Place the broad primary bank down/right of the focus and a weaker diffuse bank on the opposite side. Feather both to the exterior. Modulate them with the existing seeded smooth noise at broad scales. Multiply by a smooth transition from a fully clear focal core and by Strength, then quantize once. Keep existing Clear mist and hard-lock clearance downstream. Feed the resulting density through the existing `blend_mist_into_result` without another alpha multiplication. [Current blend](../../../src/blackmask/mist.py) · [W3C compositing reference](https://www.w3.org/TR/compositing-1/#simplealphacompositing)
- [ ] For calibration, start with the focus on the stamens, a 55° clockwise bank direction, the primary peak approximately 0.45 shorter-axis lengths from focus, a clear core radius of 0.10 tapering to full coverage by 0.27, and tint `#3C403E`. Begin strength comparisons at 40%, 70% and 100%. These are trial values. Freeze the selected defaults, bank dimensions, relative strengths, noise scales and feather equations in the v1 algorithm and contract after the visual comparison. Pin representative native samples with independent expected values and run the focused tests to green.

## Task 3 — Save, compare, disable and restore the style

**Files** — [mist.py](../../../src/blackmask/mist.py) owns settings, maps and validation. [effects.py](../../../src/blackmask/effects.py) owns effect identity and publication. Trace the existing callers in [recipe.py](../../../src/blackmask/recipe.py), [operations.py](../../../src/blackmask/operations.py), [project.py](../../../src/blackmask/project.py) and [cli.py](../../../src/blackmask/cli.py). Extend [test_mist_project.py](../../../tests/test_mist_project.py) through the normal request entry point.

- [ ] Write `test_vapor_revision_round_trip_and_style_switch` and `test_vapor_rejects_mismatched_algorithm_and_stale_base`. Exercise Apply twice, switch both ways, disable, change a lock, reopen and restore. Verify alpha and existing foreground/fade operands byte-for-byte, the prior revision remains recoverable, comparison returns the saved pre-Mist Result, a retry reuses only equivalent work, and a stale or contradictory request cannot publish. Check an existing style-less revision against its original pixels and serialized settings.
- [ ] Run `rtk proxy .venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_mist_project.py -k vapor` and confirm the failure is in save, identity or validation.
- [ ] Keep the exclusive schema-2 `mist` Apply/Disable envelope, its existing four operand files, and the same native map meanings. Pair the Vapor settings with a new algorithm identifier `linear-srgb-vapor-v1` and a distinct effects execution identity. Validate algorithm and settings as a pair before revision or cache reuse, including OFF. Select the algorithm from the applied replacement or inherited saved record, as appropriate. Preserve the old identity for ordinary Mist. Reuse the publication, space preflight, lock regeneration and restore paths. Check row scratch estimates against the final field.
- [ ] Run the focused tests to green, including a failure before publication and restore after visible publication, using the existing fault-injection fixtures. Verify CLI request parsing retains its duplicate-key, stale-base and scope checks for Vapor.

## Task 4 — Reproduce saved pixels in previews and detached exports

**Files** — [review.py](../../../src/blackmask/review.py), [framing.py](../../../src/blackmask/framing.py), [series_framing.py](../../../src/blackmask/series_framing.py) and [export.py](../../../src/blackmask/export.py). Extend [test_mist_delivery.py](../../../tests/test_mist_delivery.py) and the existing [Lit backdrop cases](../../../tests/test_spatial_fade_target.py). Native replay consumes saved density16 and clear16. Transformed grids dispatch through the versioned sampler.

- [ ] Add `test_vapor_detached_replay_and_version_precedence` for Native, Add margins and Match series at fractional scale, including reduced preview, ON, OFF, zero strength and Lit backdrop. Replay from the detached delivery and its native editable companion. Compare the full RGB16 result with the exported TIFF. Check exact native placement in Add margins, legacy v6/v7 identities, diagnostic/transparent output, and conservative protection where the resampling footprint touches locked partial alpha. Include a corrupt settings/map binding.
- [ ] Run `rtk proxy .venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_mist_delivery.py -k vapor` to establish RED.
- [ ] Carry the selected algorithm into editable manifests and replay instructions. Reserve `requested-result-v8` for any saved Vapor record, including OFF and Vapor with Lit backdrop, after checking that identifier is still free at execution. Preserve v5–v7 selection for older combinations. Use saved maps on native or integer-translated in-capture pixels and the same versioned field for newly sampled coordinates. Retain existing footprint filtering and clearance rules. Only change a rendering caller if its contract assumes the old settings layout or algorithm.
- [ ] Run the new cases to green. Verify native replay with procedural regeneration disabled, frame replay after separating the pair from the project, and rejection of a mismatched companion. A display-size preview is an approximation; use full native/exported pixels for exact assertions.

## Task 5 — Add the control and verify the photographic workflow

**Files** — [review.html](../../../src/blackmask/ui/review.html), [viewer.py](../../../src/blackmask/viewer.py), [test_mist_viewer.py](../../../tests/test_mist_viewer.py), [README](../../../README.md), [workflow](../../workflow.md#mist), [file contract](../../file-contract.md#saved-mist), [assistant workflow](../../assistant-workflow.md#explicit-mist), [troubleshooting](../../troubleshooting.md#mist-recovery) and [validation](../../validation.md#mist).

- [ ] Write `test_vapor_keyboard_focus_apply_compare_and_reopen` using the existing page harness and saved-revision routes. Exercise pointer and numeric focus placement, slider/number synchronization, switching styles with existing Clear mist shapes, unapplied edits during a late save response and opening a historical revision. Run `rtk proxy .venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_mist_viewer.py -k vapor` to establish RED.
- [ ] Add **Style** in the existing Mist panel. The ordinary style remains the first-use choice. Vapor shows **Strength**, **Place clear focus** and keyboard-editable native X/Y, defaulting to the midpoint until placed. Label direction as the bank’s bearing; retain tint and seed under advanced controls. Hide ordinary Mist controls whose values Vapor does not consume. Reuse Apply, Compare Mist OFF, Turn Mist OFF, Clear mist authoring and existing stale-draft handling. Switching styles edits the draft, retains authored clear shapes, and a saved switch can be recovered by restoring the earlier revision.
- [ ] Run the focused viewer tests to green. Exercise the loopback UI with keyboard and pointer on a synthetic project, including moving the focus away from center, applying, comparing the same crop with Mist OFF, reopening and exporting. Record which checks used a real browser.
- [ ] Document the final calibrated defaults, ranges, closed request example, saved identities, compatibility, protected regions, OFF comparison and editable replay in the maintained documents above. Run the README’s full pytest, Ruff check, Ruff format check and mypy commands once on settled inputs with `rtk proxy`. Record failures or unavailable checks separately.
- [ ] For photographic acceptance, compare the untreated base, Vapor Result and reference at identical framing. Inspect stamen tips for preserved contrast, left-petal ridges for clear detail, lower petals and stem for gradual recession, and the bank for dark corners and broad irregular variation without a visible focal ring. Keep a synthetic acceptance record separate from the photographer’s judgment. Without a corresponding untreated source, report the demonstrated look and the outstanding visual comparison.

Completion means the control can be placed, applied, compared, reopened and replayed offline. Keep the example as an editable draft for the user's photographic review.
