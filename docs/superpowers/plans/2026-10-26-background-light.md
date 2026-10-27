# Background Light Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL when implementation is authorized: use superpowers:executing-plans for one implementation owner; steps use checkbox syntax. Native execution is recommended because saved identity, rendering and UI callers are tightly coupled. This planning request grants no implementation, Git-write, publication or private-photo-trial authority.

**Goal:** Add one reversible Background light with soft oval and broad directional-gradient shapes, while keeping existing subject fades unchanged.

**Architecture:** Save a light field independently of the base backdrop. Reuse the renderer's separate display/fade-target inputs: compose against the lit backdrop B1, but always calculate the current foreground contribution toward unlit B0. Keep the existing encoded-sRGB alpha stage and all source/mask operands unchanged.

**Tech Stack:** Existing Python 3.12, NumPy, Pillow/tifffile sRGB RGB16 I/O, and localhost HTML/JavaScript controls. No new packages, model calls or processing backend.

**Spec:** [Background light design](../specs/2026-10-26-background-light-design.md). Read both documents. User decision: A, keep the existing fade; there is no B toggle.

## Global constraints

- Planning baseline: local `main`, `db907cf4603b1a8d40eabb7c32aa0937de1852df`, tree `519da182d9efd59fe375f6be51be7555e709d748`, inspected 2026-10-26. Rebind current code before execution and preserve dirty/untracked work. Local sharpening is already present.
- Light changes no source, selected foreground, alpha, protection, or foreground-effect settings/operands. Partial-alpha flattened colour may change naturally; fully opaque output remains identical for fixed foreground/base state.
- One light, one active shape; neutral default, OFF initially. No automatic exposure, contour glow, feature stack, portable-light recipe transfer, dependency changes or migration of existing images.
- B0 remains the spatial-fade target. B1 is the displayed backdrop only. Apply alpha once in the existing encoded-sRGB pipeline; generate/combine backdrop light in linear sRGB as specified.
- Settings/geometry/ranges, native sampling, OFF/zero identity, saved record and export meanings are specified by the design. Unknown/nonfinite/duplicate/stale input fails without replacing usable state.
- New light fields are saved only by explicit Apply, independently of base-background and foreground drafts. Same-source alpha repair inherits light; source/dimension mismatch is rejected.
- No runtime dependency on planning files. No private paths/images in source, tests, docs or deliveries. No claim of visual acceptance from arithmetic checks or AI illustrations.

## Review focus

1. Accidental B1 fade target changes opaque faded pixels: Task 1/2 tests nonzero q, nonblack B0 and enabled light across native and series paths.
2. Translucent/protected edges receive double attenuation or recolouring: Task 1 pins independent partial-alpha arithmetic and exact source/alpha/foreground operands.
3. New settings disappear on unrelated Apply/reload/restore or stale HTTP requests: Task 2/3 verifies real lifecycle and raw-manifest identity under the writer lock.
4. Editable output or framed/series reuse omits light or changes old paths: Task 2 verifies actual delivered members, independent replay, algorithm/identity separation and legacy read compatibility.
5. Controls/docs imply current unsupported behaviour or mix exposure and halo: Task 3 checks actual shipped script, keyboard/manual flows, independent drafts, selected A, and source-faithful exposure guidance.

## File and interface map

| Owner | Planned responsibility |
| --- | --- |
| New `src/blackmask/background_light.py` | Validate settings; generate/sample light; combine base/light; read/write/hash-bind/inherit operands. |
| `src/blackmask/background.py` | Retain existing B0 meaning/math. Add only a narrowly justified shared selection helper if needed; no field rewrite. |
| `src/blackmask/export.py`, `series_framing.py` | Keep B0/B1 separate in native, transparent, diagnostic, framed and series delivery; editable operands and reconstruction metadata. |
| `recipe.py`, `effects.py`, `project.py`, `operations.py` | Optional schema, exclusive request, identity/inheritance/cache/resources/publication and validation. Inspect `assets.py`, `repair.py` and `library.py` for actual affected consumers. |
| `review.py`, `previews.py`, `viewer.py`, `ui/review.html` | All render consumers, metadata, light-only comparison and independent manual/HTTP workflow. |
| New `tests/test_background_light.py`; existing relevant test files | Arithmetic, lifecycle, delivery, UI request/draft/security and current-contract regressions. |
| `README.md`, `docs/workflow.md`, `docs/file-contract.md`, `docs/assistant-workflow.md` | Supported behaviour, mathematical/persistence contracts and complete manual/assisted guidance. |

Proposed functions in the new module (array dtypes/shapes and validation are normative in the design):

```python
validate_background_light(settings: Any, width: int, height: int) -> None
normalized_background_light(settings: Any, width: int, height: int) -> dict[str, Any]
sample_background_light(shape: tuple[int, int], settings: dict[str, Any],
                        x: np.ndarray, y: np.ndarray) -> np.ndarray
make_background_light(shape: tuple[int, int], settings: dict[str, Any]) -> np.ndarray
combine_background_light(background16: np.ndarray, light16: np.ndarray,
                         *, enabled: bool) -> np.ndarray
validate_background_light_bindings(project: Path, directory: Path,
                                   manifest: dict[str, Any]) -> None
read_background_light(project: Path, directory: Path,
                      manifest: dict[str, Any]) -> np.ndarray | None
save_background_light(stage: Path, developed_id: str, shape: tuple[int, int],
                      settings: dict[str, Any]) -> dict[str, Any]
```

`shape` is native (height,width), even for sampling inverse-mapped output positions. x/y have equal shape and finite values; output is that shape plus RGB, uint16. Generation does not suppress the field when OFF; composition does. Reuse existing revision asset and inheritance helpers for saved files. Preserve existing renderer signatures where adequate; `render_background(..., background16=B1, fade_background16=B0)` already expresses the main invariant. Do not invent a general effect framework or change unrelated arithmetic to simplify wiring.

## Task 1: Implement the field and prove selected-A composition

**Files:** create `src/blackmask/background_light.py`, `tests/test_background_light.py`; inspect/reuse conversion helpers in `exposure.py` and rendering in `export.py` without changing their established math.

**Consumes:** spec's strict settings, native coordinates and shared sRGB conversions. **Produces:** the first five interfaces above and deterministic light/B1 arrays.

- [ ] Write failing tests `test_light_validation_and_inactive_geometry`, `test_oval_scalar_oracle_and_native_sampling`, `test_directional_monotonicity_reverse_and_width`, and `test_light_zero_off_and_black_tint_identity`. Assert unknown keys/type/mode, bool-as-number, nonfinite values, zero/negative sizes and invalid inactive geometry reject. Cover singleton/odd dimensions, rotations, bounds, >native broad shapes, strip seams and fractional controls.
- [ ] Use independent scalar smoothstep/sRGB arithmetic for expected values. Assert oval centre/outer boundary, softness 1, and gradient positions -width/2, 0, +width/2 give weights 1, 0.5, 0. Reverse twice restores the field; along any light-to-dark ray values cannot rise. Match native full-grid samples and crop slices exactly.
- [ ] Add `test_light_keeps_faded_opaque_pixels_exact` with alpha 65535 and nonzero spatial q including q=1; compare selected-A ON/OFF bit-for-bit using B0 as the fade target. Use a tinted, nonblack B0 to catch accidentally substituting black. Cover Shadow fade and inward shading separately.
- [ ] Add `test_light_partial_alpha_oracle_and_protected_operands` with alpha [0,1,16384,32768,65534,65535], nonempty protected partial values and nontrivial RGB/q/H. Independently calculate `round(P+B1*(1-A))`. Assert exact alpha/source/foreground/protection/weight preservation, endpoint identities, single attenuation and base/light saturation handling. A test that uses only opaque pixels or q=0 is insufficient.
- [ ] Run the new tests RED; implement the bounded 64-row generation/sampling and composition helpers; run GREEN. Assert OFF/zero returns exact base values rather than trusting decode/encode round trips.
- [ ] Measure representative synthetic native dimensions with the existing runtime and account for saved RGB16 light plus working buffers. Record resource limits; no photo/model or full-image float64 mesh is necessary.

## Task 2: Save, inherit and render the light throughout the workflow

**Files:** new module's reader/writer plus `recipe.py`, `effects.py`, `project.py`, `operations.py`, `export.py`, `series_framing.py`, `review.py`, `previews.py`, `viewer.py`; change `assets.py`, `repair.py`, `framing.py`, `library.py` only where an actual consumer requires it. Extend `tests/test_background_light.py`, `test_background.py`, `test_export.py`, `test_series_framing.py`, and affected asset/cache/project/review tests.

**Consumes:** Task 1 light and combination functions. **Produces:** exclusive saved light operation, complete inherited operands and every supported output using selected A.

- [ ] Write RED lifecycle fixtures for first Apply, repeated non-compounding Apply, replace geometry, OFF retaining exact field bytes, missing legacy record, same-source alpha repair, stale foreground, restore, prepared-only restrictions and changed source/dimensions. Assert base assets and foreground/mask/effect operands remain unchanged and accepted pointers never change implicitly. Pin rendered-pixel identity for absent/OFF light separately from legitimately changed revision/export metadata.
- [ ] Add strict optional recipe/manifest support and exact asset inventory. Implement the remaining listed interfaces using existing path/asset/hash/profile validators. Check recipe/record/settings agreement, valid OFF assets, exact zero fields for zero brightness/black tint, unknown/unbound files, symlinks and tampering before cache reuse. Validate source registration and reject unknown algorithms; do not regenerate native light on read. For an enabled-only change, inherit exact L16 instead of regenerating authoritative saved pixels.
- [ ] Extend exclusive request validation, effective recipe snapshots, normalized identities, execution fingerprints, cache contexts, resource estimates and inherited asset references. Same-input reuse must still check current permanent assets. Light-only Apply must not consume pending base-background/foreground drafts; base-only Apply must not consume pending light edits.
- [ ] Wire B0/B1 through every consumer in the design's table, including unpublished matte/repair/effects review generation, saved review/gallery, native crop, all OFF comparisons and actual export. Preserve Source/Alpha, diagnostic black/gray/white, transparent and BASE meanings. Inspect actual imports/callers rather than only testing `render_background` directly.
- [ ] Extend `render_series` with keyword `background_light_settings: dict[str, Any] | None = None`, validated against native dimensions. Use `x_native=(X+0.5-tx)/scale-0.5` and the corresponding y conversion from series pixel-edge layout to light pixel-centre coordinates. Reduced previews choose full-output integer X/Y by the design's existing background sampling formula before that inverse. Keep the existing output B0 as fade target in identity and resampled branches, including nonzero q/protected samples and preview/transparent/black variants. Do not alias B0 and an in-place-mutated B1.
- [ ] Add actual native/crop/review/gallery and native/Match-series/Add-margins export round trips. Assert Add margins copies the native result exactly and extends B1 edge pixels. Add independent scalar registration oracles for both shapes at non-unit scales (including 10), fractional translation and unequal full/preview dimensions; catch the 4.5-output-pixel error from omitting half-centres at scale 10. Verify subject-relative placement, supported dimensions and no fallback to native-sized output normalization. Distinguish sampled preview correspondence from exact whole-image downsampling.
- [ ] Extend native editable member inventory with light RGB16/settings and bound record. Keep B0's filename/meaning. Update export algorithm/schema identity only where validators require it; prove old deliveries are preserved and new identities cannot collide with incompatible old output. Existing compact/default exports must not acquire editable-only members.
- [ ] Reconstruct an exported native Result from delivered B0/L16/foreground/alpha/active effect operands in a separate child process with source/project/model/cache unavailable and analytic native generation disabled. Test ON, OFF and legacy; test companion metadata supports the documented framed/series reconstruction without silently treating native light pixels as an output-grid field.
- [ ] Exercise writer contention, low disk, stale identities, changed/rehashed operands, interruption before state publication, restore of complete orphan revisions, and rebuildable cache clearing. Preserve newer drafts and usable accepted state. Reject partial results; never convert failure to acceptance or delete recovery data.
- [ ] Run focused affected suites GREEN, including existing no-light regression cases. Record any unrelated baseline failure separately; do not weaken preservation assertions.

## Task 3: Deliver manual controls and accurate documentation

**Files:** `src/blackmask/viewer.py`, `src/blackmask/ui/review.html`; tests in `test_viewer.py`, `test_viewer_page.py`, `test_viewer_coordinates.py` and `test_background_light.py`; the four maintained documentation owners above.

**Consumes:** Task 2 saved operation and output semantics. **Produces:** offline, keyboard-accessible light editing, comparison/recovery and documented alternatives.

- [ ] Add RED HTTP tests for the actual light `effects` action, exact raw-manifest envelope and under-lock recheck, candidate consent, full scope, mutually exclusive inputs, token/origin/body guards and duplicate keys including nested geometry. Extend duplicate-aware parsing on the real action path and forwarding through `ReviewServer.start_action` and `ReviewServer.execute`; a preview-only validation test is insufficient.
- [ ] Add labelled Light ON, shape, Brightness, colour, oval centre/radii/angle/softness and directional centre/angle/transition width/Reverse controls with canvas handles and numeric alternatives. Defaults/ranges follow the spec. Include independent saved/pending/error state, Apply, read-only OFF comparison, save OFF and reload-light actions. Unknown/blank/nonfinite input fails visibly without clamping or erasing drafts.
- [ ] Execute the actual shipped script in existing page tests: switching shape preserves its session drafts; applying saves only active geometry; invalid/busy/stale failures preserve inputs; unrelated actions/polling do not reset them; explicit light reload affects only light. Turn light OFF must submit only the current saved settings with enabled=false, retaining valid/invalid/stale pending light drafts and their status. Test exact field inheritance, repeated OFF reuse and absent-record OFF producing no record. Explicit Apply of changed OFF settings remains a separate save. Check fractional brightness survives load/Apply/reload unchanged and base-colour shortcuts do not disable light. Bind delayed images/comparisons to the visible saved revision.
- [ ] Verify comparison selection cooperates with existing one-comparison-at-a-time behaviour and native zoom/crop controls. Light OFF comparison creates no revision. Existing foreground-OFF comparisons retain B1 but never use it as fade target. Base-background settings and their pending edits remain independent.
- [ ] Write the full oval and directional walkthroughs, chosen-A translucent/opaque explanation, black-base distinction, unit/default/range meanings, clipping/banding caveats, export/recovery and Add-margins/Match-series difference. Replace old copy promising a fully black Result whenever base is black. Explain which shape's geometry is saved and recoverable through history.
- [ ] Add the design's **Gentle local exposure on the subject** walkthrough to the existing Local exposure documentation, with +0.1–0.3 EV as optional examples, protection, feathering, amount-to-saved-area, exposure OFF, clipping/noise checks and Reset. Validate every named control against current code. Do not build a second exposure control or claim colour/foreground identity when that separate adjustment is enabled.
- [ ] Document the exact schema, B0/B1 math, native/series/export replay and typed assistant request in their canonical owners; README links rather than duplicates those contracts. Ensure earlier planned appearance-recipe base settings leave light untouched if that feature has landed; do not extend its portable format here.
- [ ] Run affected tests GREEN and inspect real-browser controls with keyboard/native zoom, hidden overlays and failure recovery. Script/HTTP tests alone do not prove usability or photographic quality.

## Verification commands and finish criteria

Use the actual authorized implementation checkout/runtime. README currently documents `.venv/bin/python`, `.venv/bin/ruff`, `.venv/bin/mypy`, but this planning checkout has no `.venv`; no setup or installation is authorized here. The following are proposed commands after verifying those executables, not claims they ran:

```sh
rtk proxy .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_background_light.py
rtk proxy .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_background.py tests/test_export.py tests/test_series_framing.py tests/test_viewer.py tests/test_viewer_page.py tests/test_viewer_coordinates.py
rtk proxy .venv/bin/ruff check src tests --no-cache
rtk proxy .venv/bin/ruff format --check src tests --no-cache
rtk proxy .venv/bin/mypy src
rtk proxy .venv/bin/python -m pytest -q -p no:cacheprovider
```

During implementation use targeted cases for RED/GREEN; run the complete relevant suite once after the coherent batch, without repeating successful unchanged inputs. Add affected lifecycle owners discovered during wiring to the focused checks. Preserve actual child/capture statuses and distinguish deterministic/stub, real-browser, exported-child replay and human-photo evidence.

- [ ] Self-review the settled tracked-plus-new candidate against every design obligation and connected caller; remove only unnecessary changes/duplication introduced here.
- [ ] Obtain bounded read-only independent reviews of (1) composition/source preservation and (2) persistence/delivery/UI recovery. The implementer fixes verified material findings sequentially; renew only affected checks/scopes.
- [ ] Check documented links/controls and actual installable contents with established packaging checks. No planning files, private photographs/paths, hidden downloads or extra dependencies may ship.
- [ ] Record completed/blocked evidence, exact baseline and retained recovery state. Human photographic acceptance requires a separately authorized trial and remains distinct from engineering completion. Do not claim the illustrative AI comparison is validation.

## Increment assessment and handoff

**Recommend one feature increment**, with the three internal testable tasks above. Acceptance is one complete Background light control with both placement shapes and the same preservation/recovery promise. The expensive and risk-bearing change is the single B0/B1 separation through persistence and every renderer. Both small field profiles use that contract; delivering a temporary partial schema/UI solely to separate them would add compatibility and review work without reducing that risk. Do not split persistence, consumers, editable export, tests or documentation into later repair increments.

If the owner deliberately wants photographic feedback on an oval-only release first, a later plan revision can separate the directional mode as a useful follow-up. That is not the current recommendation or a deferral of the requested gradient. The earlier two plans remain independently sized and unchanged. This is an assessment using the incremental-plan skill's coherent-feature criteria, not a new coordinated incremental program or implementation approval.

Native execution with one owner is recommended; independent reviewers stay read-only. No execution method, implementation chat or external action is activated by this plan. Ordinary engineering defaults are proposals in the design; the user's A decision is settled and must not be reopened as a request to add B.

Plan self-review: settings/interfaces and task consumers match; all design requirements map to Tasks 1–3 or the final verification obligations. Preserve separate colour spaces, no-light identities, stale/OFF validation, all output paths, independent drafts and existing exposure scope. Review reports and any subsequent corrections belong in the companion review note.
