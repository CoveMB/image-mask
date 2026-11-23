# Local Tone Curve Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans or superpowers:subagent-driven-development for the execution approach the user authorizes. Steps use checkboxes. This document proposes implementation for user review.

**Goal**

Give each photo one editable luminance curve with its own mask, hard protection and recoverable saved settings.

**Architecture**

Reuse the native effect-area authoring, immutable revision store, and RGB16 foreground pipeline. Run the curve after Local Exposure and before Shadow Fade. The viewer, saved review, gallery and delivery consume the same selected foreground.

**Tech stack**

Python 3.12, the existing NumPy, Pillow and tifffile pins, the loopback viewer’s HTML/JavaScript, pytest and the existing Node page harness. Use the installed application environment and existing dependencies. [Package configuration](../../../pyproject.toml)

**Spec**

[Feature specification](#feature-specification), based on the user’s frog example and the independently reviewed design recommendation. [Repository guidance](../../../AGENTS.md) · [Offline workflow](../../workflow.md) · [File contract](../../file-contract.md)

## Feature specification

Build a point editor first. Three Shadows / Midtones / Highlights controls with fixed input ranges could darken broad shadows and lift midtones through the same spatial mask. Movable points let the user set where the lift ends and create a diagonal highlight interval where RGB passes through exactly. The two interfaces share most of the work below. [Curves reference](https://helpx.adobe.com/photoshop/desktop/adjust-color/color-corrections/adjust-color-and-tone-with-curves.html)

For the frog, start from a synthetic example of 8% → 5.5%, 32% → 38%, and 70% → 70% linear luminance, with the final diagonal segment extending to white. Author a feathered Apply area on the frog and hard Protect areas around the eye reflection and the natural blur above the waterline. Keep the subdued water outside Apply. These points illustrate the intended workflow. Photographic acceptance comes from the user’s native-scale comparison.

The proposed first release uses a small plot and keyboard-editable point coordinates. The editor stores at most six interior points in hundredths of a percent of linear luminance. It implicitly adds (0%, 0%) and (100%, 100%). Input and output coordinates strictly increase. An empty point list is the diagonal. Each photo saves an independent curve and area.

### Decisions before implementation

1. Confirm that numeric point entry and a plot cover the first release. Pointer dragging, histograms, portable presets, per-channel editing and multiple curves would each be additional scope.
2. Approve the fixed endpoints, linear-luminance axis and common-gain gamut policy. Saturated colors with limited channel headroom get less lift, in exchange for retaining their linear RGB ratios before rounding.
3. Approve additive schema-2 compatibility. The updated reader opens existing schema-2 projects without migrating them. Curve-bearing revisions require the updated application for reliable rendering. Preserve earlier revisions and deliveries for older readers.

## Global constraints

- Use the native oriented master, half-open rectangles, native-pixel inward feather, maximum support across overlapping shapes and hard protection. Import registered masks only through the existing project-relative request boundary.
- Copy alpha16 exactly. Positive alpha gates curve eligibility. Effect support controls strength. Use float64, existing sRGB conversion and one ties-to-even RGB16 quantization for the curve stage.
- Preserve developed source, original, previous revisions and accepted state. The curve adjusts existing RGB samples locally. It cannot recover clipped or absent capture detail. Preserve valid reviewed matte and guide scope, including partial-alpha locks.
- Use schema-2 effects, immutable bound assets and the existing writer lock. An alpha change stales an enabled curve until reviewed rebuild or disable. Earlier accepted results remain independently exportable.
- Keep the compact delivery at five files and preserve the request identity, membership and notes of pre-curve deliveries. Treat runtime work, separate downloads, Git writes and private-photo evaluation as separately authorized.
- Use the current checkout as the source baseline. The planning baseline is `0bf8ed5bf08e3317a34bb36b63796668dd96c3fe` on local `main`. Preserve the existing working edits, including the ones in `README.md` and `docs/troubleshooting.md`. Reconcile branch, status, dependencies and source entry points when execution is authorized.

## Review focus

1. A saturated color must follow the feather after the full-strength gain is capped. A half-strength selection must retain headroom when the full-strength result reaches the channel limit (Task 1).
2. A newly locked partial-alpha sample must keep its already selected pre-shading RGB through prepare, matte and repair. Copying base RGB or applying the curve again both fail (Task 2).
3. Refreshed exposure clipping must use the genuinely pre-exposure input. A nonwhite sample under +1 EV differentiates a correct result from a curve applied to the diagnostic input (Task 2).
4. Shadow Fade with a curve and no Exposure record must export genuinely pre-exposure RGB under `unexposed_foreground_rgb16.tif`. Earlier frozen deliveries must still validate and reuse (Task 3).
5. A settings-only write, error or late reply must preserve a newer area draft. A stale area cannot be submitted as a replacement against a newer working revision (Task 4).

## File ownership

| File | Responsibility |
| --- | --- |
| New `src/blackmask/tone_curve.py` | Strict settings, RGB16 kernel, saved-operand validation and stage selection |
| `src/blackmask/effects.py`, `recipe.py`, `project.py`, `operations.py` | Existing effects request, atomic publication, optional recipe, revision validation, lock snapshots, inheritance and stale recovery |
| `src/blackmask/export.py`, `review.py` | Canonical selected layers, stage-correct clipping metadata, frozen delivery identity and editable replay |
| `src/blackmask/viewer.py`, `ui/review.html` | Loopback action, authenticated crop comparison, numeric editor and independent draft bindings |
| New `tests/test_tone_curve.py`, `tests/test_tone_curve_delivery.py`, `tests/test_tone_curve_viewer.py` | Kernel, saved lifecycle, delivery and viewer regressions using existing fixtures and harnesses |
| `README.md`, `docs/workflow.md`, `docs/file-contract.md`, `docs/troubleshooting.md`, `docs/assistant-workflow.md`, `docs/validation.md` | Supported behavior, normative saved/replay contract, recovery, explicit request example and observed evidence |

Reuse `assets.py` for content-addressed rasters, `guidance.py` and `exposure.rasterize_effect_area` for native geometry, and the existing CLI `run --request` dispatch. Use `previews.py` and presentation callers as verification boundaries through their existing shared renderer.

## Task 1 — Implement and verify the RGB16 kernel

**Interfaces**

- `validate_local_tone_curve(settings: object) -> None` raises `ProjectError` unless settings has exactly `enabled: bool` and `points: list[list[int]]`. Each pair has two strict integers in [1, 9999]. Both axes are strictly increasing in the saved order. The list contains zero to six pairs. Validate settings and operand dimensions/dtypes even when OFF.
- `apply_local_tone_curve(foreground: np.ndarray, alpha: np.ndarray, support: np.ndarray, protection: np.ndarray, settings: dict[str, Any]) -> np.ndarray` consumes straight sRGB uint16 RGB, aligned uint16 alpha/support, and boolean protection. Return a separate uint16 foreground.

- [ ] **Write the kernel tests.** In `tests/test_tone_curve.py`, add `test_curve_rgb16_reference_and_exact_exclusions`, `test_curve_gamut_cap_precedes_feather` and `test_curve_rejects_invalid_settings_or_operands`. For points `[[800, 550], [3200, 3800], [7000, 7000]]` and full support, neutral codes 16000, 36000 and 60000 become 13166, 38391 and 60000 per channel. At support 32768, 36000 becomes 37220 at both alpha 18000 and 65535. Repeat that same 36000 sample at zero alpha, zero support, and hard protection and expect 36000 in each. Assert exact black, exact OFF and diagonal identity, and byte-identical input/alpha arrays. For input `[62000, 34000, 8000]` and points `[[2000, 4000], [6000, 8500]]`, full and half support produce `[65535, 36026, 8625]` and `[63800, 35032, 8318]`. Include unordered, duplicate, flat, out-of-range, oversized, boolean, fractional and nonfinite coordinates and mismatched dtype/shape cases.
- [ ] **Run RED.** Run `rtk proxy .venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_tone_curve.py -k 'curve_rgb16 or curve_gamut or curve_rejects'`. Expect failure because the module or kernel is absent.
- [ ] **Implement the kernel.** Use `exposure.srgb_to_linear` and `linear_to_rgb16`. Compute `Y = .2126 R + .7152 G + .0722 B` from linear RGB. Compute `delta = interp(Y, input_knots, output_knots - input_knots)` including the fixed endpoints. For eligible pixels with `Y > 0` and nonzero delta, compute `gain = min((Y + delta) / Y, 1 / max(R,G,B))` and apply `RGB * (1 + support/65535 * (gain - 1))`. Skip exact zero deltas and gains of one so identity spans preserve original codes. Process bounded native row strips with no neighborhood halo. [Existing conversion](../../../src/blackmask/exposure.py) · [NumPy piecewise-linear interpolation](https://numpy.org/doc/2.3/reference/generated/numpy.interp.html)
- [ ] **Run GREEN.** Repeat the Task 1 command and expect all selected cases to pass.

## Task 2 — Publish, inherit and render the saved effect

**Request and record**

Use the common schema-2 `kind: "effects"` envelope with `developed_id`, `base_revision`, `inputs_digest`, native `scope_xyxy` and boolean `candidate_comparison`. The sole effect is `local_tone_curve: {"enabled": true, "points": [[800, 550], [3200, 3800], [7000, 7000]]}`. The action-specific fields are:

| Action | Fields |
| --- | --- |
| Apply/replace | Enabled settings and exactly one area source. Use `tone_curve_area` with `regions`/`protection`, or `support_file` plus `tone_curve_protection_file`. An omitted or false `tone_curve_settings_only` selects replacement. |
| Apply to saved area | Enabled settings and `tone_curve_settings_only: true`. Require validated saved area/protection with current alpha. |
| Disable | Disabled settings with the saved points. Require an existing record. Retain its area, protection, points and alpha dependency, including when stale. |

Protection files are native categorical PNG8 (0/255) or PNG16 (0/65535). Support files are native grayscale16 PNG. Authored shapes use the exposure area contract and zero feather on Protect. Reject replacement fields on settings-only or Disable, incompatible effect fields, invalid registration, unsafe input paths, scope that misses old or replacement support, and empty eligible enabled areas. Enabled writes require an accepted base or explicit candidate comparison. Use the supplied native scope; the viewer declares the full master.

The `local_tone_curve` revision record holds exactly `schema_version: 2`, `enabled`, `settings`, `stale`, `developed_id`, `algorithm: "linear-srgb-local-tone-curve-v1"`, `scope_xyxy`, `candidate_comparison`, `support_sha256`, `protection_sha256`, `alpha_sha256` and `area_sha256`. `area_sha256` is null for scalar-file inputs. Bind logical `effects/tone-curve/{support16.png,protection16.png,alpha16.png}` through shared rasters, and bind `settings.json` and authored `area.json` when present as revision text. `settings.json` is the canonical record. Bind the base alpha as well, including in prepared revisions. Stale means enabled with a different saved alpha dependency.

The optional `[local_tone_curve]` recipe section uses the same two settings fields. Absence means OFF in memory. Apply synchronizes the curve section and preserves unrelated draft values, exact consumed snapshots and immutable revision bytes. Reuse and read-only reopen preserve root recipe bytes. The saved effect record, produced by explicit Apply, controls appearance.

**Interfaces**

- `read_local_tone_curve(project: Path, directory: Path, manifest: dict[str, Any], alpha: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict[str, Any]] | None` validates and returns support, boolean protection and the record. Absence of a record is default OFF.
- `selected_local_tone_curve(project: Path, directory: Path, foreground: np.ndarray, alpha: np.ndarray, manifest: dict[str, Any], *, tone_curve_off: bool = False) -> np.ndarray` selects the validated curve output or incoming RGB.
- `inherit_local_tone_curve(project: Path, parent: str, stage: Path, developed_id: str, alpha: np.ndarray | None = None, rgb_protection: np.ndarray | None = None, *, assets: dict[str, Any]) -> dict[str, Any] | None` carries bound operands, merges new RGB locks, and re-evaluates staleness when new alpha is available.
- `select_post_exposure_foreground(project: Path, directory: Path, foreground: np.ndarray, alpha: np.ndarray, manifest: dict[str, Any], *, effects_off: bool = False, tone_curve_off: bool = False, shadow_fade_off: bool = False, shadow_reduction_off: bool = False) -> np.ndarray` in `effects.py` runs curve then Shadow Fade. Thread `tone_curve_off` through `selected_foreground` and `export.saved_layers`. Keep existing cleanup → Local Sharpening → Local Exposure before this helper and shading or spatial fade → alpha/background after it.

- [ ] **Write the storage and render tests.** Use `test_effects.fixture_project` or `test_sharpening.sharpening_project` to exercise the public operations in `tests/test_tone_curve.py`.
  - `test_curve_effect_replaces_area_and_reuses_current_operands` covers authored and scalar areas, one CLI round trip, absent settings, settings-only Apply preserving the saved area, old-area removal and an exact repeat without a new revision. Compare unrelated parsed draft values and exact consumed snapshots after Apply.
  - `test_curve_rejects_stale_or_corrupt_inputs_without_pointer_changes` rejects a bad scope, misregistered or changed input file, a falsified OFF record and an unbound area after warming validation. Assert the accepted and working pointers on stale rejection or injected failure before state replacement, then restore a complete valid revision.
  - `test_curve_inherits_partial_rgb_lock_and_requires_alpha_rebuild` checks an already adjusted partial-alpha sample through prepare and same-alpha matte/repair, including an RGB lock outside repair support. Change alpha, then assert labelled BASE, refusal to accept or draft-export the stale revision, unchanged latest valid result, and availability of the earlier accepted export. Exercise rebuild and Disable.
  - `test_curve_pipeline_and_pre_exposure_clipping` uses distinguishable operator orders and checks the retained downstream effects on explicit OFF comparisons. Expose neutral code 52428 at +1 EV and use a curve with point `[6000, 3500]`. Assert one clipping pixel at publication and refreshed review. Wrongly curving the pre-exposure input would avert the clip. Include a second sample where the curve visibly operates.
- [ ] **Run RED.** Run `rtk proxy .venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_tone_curve.py -k 'curve_effect or curve_rejects_stale or curve_inherits or curve_pipeline'`. Expect failures at the new request, inheritance or selection boundaries.
- [ ] **Add bound assets and lifecycle.** Use `revision_asset` and existing raster validation. Reject bad record types or algorithm, categorical/registration mismatch, stale-status mismatch, missing hashes, `settings.json` disagreement and authored raster disagreement. Check for unbound area files before warm validation. Reuse the existing saved guide protections and the selected pre-shading lock snapshots, including prepared-parent comparison and repair-scope checks. A hard Protect area preserves the curve input. A saved RGB lock preserves its captured selected-layer sample, even if captured while the curve was ON. A disabled record keeps its bound dependency and must rebuild before enabling if that dependency differs.
- [ ] **Wire the effects transaction.** Extend the existing exclusive dispatch, strict optional recipe handling, draft/parent and file snapshot checks, scope validation, shared-stage asset collection, space preflight and state-last publication. Bind precisely the raster bytes consumed by each file request. Include the curve algorithm, result record, operand hashes and relevant upstream bindings in unchanged-request reuse; advance `EFFECTS_EXECUTION_VERSION` from `validated-effects-v7` to `validated-effects-v8`. An old repeat may compute once when the previous execution identity cannot prove reuse.
- [ ] **Use the shared selection and fix clipping metadata.** Call `select_post_exposure_foreground` in saved selection and the effects and matte/repair overview producers. Add the curve to stale BASE selection, review labels and bindings, and acceptance/export recovery messages. Supply `tone_curve_off=True` where `review.py` reconstructs pre-exposure RGB for the existing clipping count. Verify that the gallery and presentation preview consume the shared selection. [Refreshed review clipping caller](../../../src/blackmask/review.py)
- [ ] **Update the file contract and run GREEN.** Record settings, request variants, asset roles, protection, ordering and legacy/recovery rules in `docs/file-contract.md`. Repeat the Task 2 command and expect all selected cases to pass. Cross-check the added field names against the canonical readers.

## Task 3 — Keep native and presentation deliveries reproducible

- [ ] **Write delivery regressions.** In `tests/test_tone_curve_delivery.py`, add `test_curve_editable_delivery_replays_rgb16` and `test_curve_free_delivery_retains_frozen_identity` using the pattern in `tests/test_sharpening_delivery.py`. Use an active curve and a disabled saved curve. Exercise native editable and both presentation modes with native companions. Isolate the delivered native operands from the project and reconstruct selected and flattened RGB16 exactly. Include curve plus Shadow Fade with no Exposure record, compact-versus-editable membership, and a retry that verifies a companion’s existing hashes without replacing bytes.
- [ ] **Capture or reuse pre-curve delivery evidence.** Use a small curve-free v5 delivery generated by the baseline exporter with the same execution dependencies. Retain it at the same synthetic project path for the post-change retry. Compare the request identity, directory basename, README and member hashes with the frozen baseline. Preserve these expectations in the regression for a curve-free request. [Existing delivery-reuse tests](../../../tests/test_export.py)
- [ ] **Run RED.** Run `rtk proxy .venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_tone_curve_delivery.py`. Expect missing curve-bearing members or incorrect stage pixels; the legacy characterization should pass.
- [ ] **Extend the existing delivery producers and validators.** Keep `requested-result-v5` and add metadata only for curve-bearing revisions. Bind curve identity in presentation records and the complete settings in native editable delivery, including OFF. Ship `uncurved_foreground_rgb16.tif` (after Exposure, before the curve and Shadow Fade), `tone_curve_support16.png`, `tone_curve_protection16.png`, `tone_curve_alpha16.png`, `tone_curve_settings.json` and `tone_curve_area.json` when authored. Keep `unsharpened` and `unexposed` at their respective stages, including the no-Exposure Shadow Fade fallback. `unfaded` includes the curve. `foreground_rgb16.tif` in editable delivery contains the selected pre-shading foreground, so replay from that layer starts at shading or spatial fade and composition. Update the request, member inventory, writer, notes, and pending-byte estimate together. Preserve pre-curve note bytes in the historical validation path.
- [ ] **Document reconstruction and run GREEN.** Update `docs/file-contract.md` at each affected foreground-stage and delivery contract, including companion and precision semantics. Repeat the Task 3 command; expect exact replay and intact legacy retry assertions to pass.

## Task 4 — Expose the control and verify the offline workflow

- [ ] **Write viewer regressions.** In `tests/test_tone_curve_viewer.py`, add `test_curve_viewer_action_and_native_off_crop` using `test_viewer.running` and `test_curve_keyboard_points_and_independent_drafts` using `test_viewer_page.run_page`.
  - Submit real replacement and settings-only requests. Apply on an accepted base, then verify the next enabled settings-only Apply fails on the unaccepted working result with candidate comparison unchecked and succeeds after explicit opt-in. Reject stale manifest or authoring identity. Compare result crop RGB8 with canonical RGB16 selection and display conversion. Check identical alpha view and that OFF comparison creates no revision.
  - In the page harness, add labelled numeric points, verify 8 and 5.50 become `[800, 550]`, and check the unchecked candidate control sends false until selected. Reject blank or duplicate inputs and outputs that fail to increase. Draw keyboard and pointer areas and assert Protect feather zero. Check late replies, failed or unrelated actions, preserved pending area on settings-only Apply, and stale area rejection on replacement. Disable sends saved knots even when draft point values are invalid.
- [ ] **Run RED.** Run `rtk proxy .venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_tone_curve_viewer.py`. Expect missing controls, action fields or comparison route.
- [ ] **Wire the existing loopback action.** Expose saved record/area and stale status in the revision snapshot. Extend action field validation and forwarding in `viewer.py`; bind raw revision-manifest identity through `operations.apply_operation` as for modern appearance actions. Add the existing image route’s `/tone-curve-off` suffix; compare uses the saved curve’s input and recomputes Shadow Fade and spatial highlight protection. Exposure OFF and Local Sharpening OFF recompute the downstream curve with their respective upstream stage disabled. Source and alpha panels remain exact at their display precision.
- [ ] **Build the panel in the existing review page.** Add **Tone curve area** to canvas modes and reuse brush, half-open numeric rectangle, feather, role and region-list controls. Provide **Input luminance (%)** and **Output luminance (%)** rows with 0.01% precision, **Add point**, **Remove point**, and a diagonal reference plot. Sort valid complete pairs by input for submission. Reject blank fields, duplicate inputs, outputs that fail to increase, and more than two decimal places.
  - Provide **Apply / replace tone curve area**, **Apply curve to saved area**, **Disable tone curve**, **Reload saved curve**, and **Reload saved area**. Add **Explicitly compare tone curve on an unaccepted candidate**, unchecked on load and bound to the curve settings draft.
  - Use matching developed/revision/manifest/input/authoring identity and independent edit versions for points and area. Expose saved, unsaved and stale status. Use the mutually exclusive comparison controls and preserve keyboard focus.
- [ ] **Write the operator docs and run GREEN.** Update `README.md` status/source map, `docs/workflow.md` controls, numeric units, overlays, candidate opt-in, OFF comparison and offline checklist, `docs/troubleshooting.md` stale/invalid input and restore instructions, and `docs/assistant-workflow.md` with one schema-2 request example and the manual comparison boundary. Explain that registered scalar masks provide saved support/protection even without authored shapes. Record portability scope in `docs/file-contract.md`. Repeat the Task 4 command and expect both HTTP and page assertions to pass.

## Final verification after implementation

- [ ] Run the settled deterministic suite and the README lint, format and type checks. Use `rtk proxy .venv/bin/python -B -m pytest -q -p no:cacheprovider`, `rtk proxy .venv/bin/ruff check src tests --no-cache`, `rtk proxy .venv/bin/ruff format --check src tests --no-cache`, and `rtk proxy .venv/bin/mypy src`. Report actual exit codes, counts and any prerequisite skips. [Repository commands](../../../README.md)
- [ ] In the supported offline loopback browser setup, exercise one synthetic local adjustment by keyboard, one protected partial-alpha edge, Compare OFF, reopen and native editable export. Reuse the documented isolated browser harness where provisioned. Record the observed browser/environment, RGB16 replay and display limitations in `docs/validation.md`. Check maintained links and validate the documented request example against the installed command and actual control names. Record any unavailable browser evidence explicitly. [Browser setup](../../validation.md#reusable-isolated-browser-setup)
- [ ] Review the settled request-to-export path against the spec and the five review-focus cases. Report actual verification and any outstanding photographic assessment. A later private-photo evaluation requires the applicable authorization and the user’s photographic judgment.

## Plan review

An independent rendering review reproduced the synthetic RGB16 values and checked the pre-exposure clipping and editable replay cases. An independent saved-contract review found two gaps in the first written draft. The plan now specifies explicit candidate opt-in for each unaccepted refinement and distinguishes preserving unrelated recipe values from preserving the exact consumed snapshot bytes. The evidence to date is source inspection, plan review and synthetic arithmetic.
