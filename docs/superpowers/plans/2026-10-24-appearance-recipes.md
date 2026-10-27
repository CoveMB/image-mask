# Named Appearance Recipes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (recommended for this coupled workflow), or superpowers:subagent-driven-development if the user selects that method. Steps use checkbox (`- [ ]`) syntax for tracking. This document authorizes no implementation or Git writes.

**Goal:** Save chosen appearance settings, optionally a reference and editable spatial layout, and safely reuse selected parts on another photo.

**Architecture:** One portable JSON codec reads validated saved revisions and returns allowlisted values. Increment 1 loads scalar settings into existing forms; increment 2 adds optional uniformly scaled editable oval/arcs through a separate placement proposal, explicit Add/Replace and guarded Undo. Both retain explicit Apply and target-local masks/protection/reduction; no style catalog or automatic multi-effect transaction.

**Tech Stack:** Existing Python >=3.12,<3.13, standard-library JSON/base64, NumPy, Pillow, current local HTTP server, vanilla JavaScript, pytest/Ruff/mypy and existing Node page harness. No dependency, model, service or schema migration of projects.

**Spec:** [Named appearance recipes design](../specs/2026-10-24-appearance-recipes-design.md). Read the spec and this plan together. [Separate review record](2026-10-24-appearance-recipes-reviews.md).

## Global Constraints

- The user's 2026-10-25 “most flexible and resilient” answer expands the selected direction to optional editable layout transfer while retaining settings-only use. Detailed design/execution approval remains pending. This feature does not depend on soft fade reduction; preserve its target-local saved/draft operands if present.
- Latest inspected local baseline is clean `ed86ca84478846271c9f4da09c02ddbe5a38d2bd`, tree `ead610dced94b17aa6718da8e95405be0300135f`, at `/Users/CoveMB/Code/CoveMB/image-mask/local/reviews/coderabbit-pass/inspectable-processing-cache-preparation/implementation`. It retains the earlier oval/arcs, shared assets and requested exports, and supersedes the I18-only inspection baseline. No remote refresh or hosted-readiness claim.
- The writing checkout `docs/named-local-references` at `df7921d31aa4d3a84596856d8f0b164ae4292c7d` is older. Before execution resolve the settled successor, reconcile I19/cache changes and preserve current delivery/dirty work. Do not implement in the old tree by copying application files.
- 2026-10-25 independent-review refresh: ed86 includes I19 on parent `2edae84a58a9bd2d9e6e51ac4f118a0122b7cfc0` plus the native-review staging correction. The current handoff records parent2eda as published and ed86 as local awaiting publication; this is handoff context, not a fresh provider check. Preserve canonical permanent-data validation and reconcile the settled successor before implementation.
- Portable root keys are exactly `schema_version`, `kind:"appearance-recipe"`, `name`, `sections`, `reference`. Increment 1 writes/reads version1; increment 2 reads1/2 and writes2 only for layout-bearing recipes. Name 1–80 trimmed Unicode characters without control characters; reference is null or the exact PNG object in the spec.
- JSON limit 1572864 UTF-8 bytes; PNG limit 1048576 encoded bytes, longest side 512 and at most 262144 decoded pixels. Keep outer HTTP cap 2000000 bytes. Reject duplicate/unknown keys, unsupported versions, invalid UTF-8, nonfinite/boolean numeric values and excessive nesting before form changes.
- Thumbnail is optional/unchecked, RGB8 PNG, no EXIF/text/private metadata or source path/identity. Label it **Reference from saved source photo — not a target preview**. No remote fetch or hidden file/catalog write.
- Loading modifies forms/drafts only. Never transfer effect-master enable state, areas, masks, locks, WB/source development, framing, acceptance, paths, source IDs or reduction operands. Settings-only loading transfers no geometry/switches; explicit layout Replace transfers internal shape/group switches while preserving target master/protection/reduction. Background/exposure/cleanup/layout inclusion is opt-in. Shading, scalar spatial defaults and spatial layout are mutually exclusive representations.
- Subject-relative widths retain fractional values without integer rounding or geometric clamping. Bounds include every nonzero-alpha sample. Spatial transition remains [0.5, 2*max(native dimensions)] with the same converter-only floating endpoint rule from increment1 through layout/fallback; shading width remains strictly positive without zero correction.
- Layout uses the spec's half-open subject midpoint/max-side normalization and exact bounded floating endpoint correction; no axis stretching, substantive fitting or native-validator relaxation. No source IDs; new unique UUID-v4 IDs per proposal. Maximum32 arcs after Add; preserve target group/master semantics and no processing until Apply.
- No product code, setup, private-photo processing, Git writes or external actions are authorized now. Existing source appearance and human acceptance rules continue to apply when implementation is later authorized.

## Review Focus

1. Saving an old selected revision while the current result/draft differs must not leak current values or generate a mismatched thumbnail — Task 2.
2. Applying the first loaded section changes revision identity; the remaining values must survive, be marked stale and require explicit per-section reload — Task 4.
3. Tiny partial-alpha extremities, fractional geometry and changed aspect ratios must preserve uniform geometry or fail clearly, without clipping/distortion — Tasks 1, 5 and 6.
4. Hostile PNG metadata/dimensions and duplicate JSON keys must fail locally before decoding work or form replacement — Tasks 1–3.
5. Overlapping import/create/Apply replies, Add/Replace and Undo must preserve newer drafts and all target protection/reduction/switches — Tasks 3–6.

## File and interface map

| Owner | Responsibility |
| --- | --- |
| New `src/blackmask/appearance_recipes.py` | Standalone codec, bounded thumbnail sanitizer, saved-value selection, width/layout normalization and validated proposals. |
| `series_framing.py` | Extract the existing nonzero-alpha bounds scan for two concrete callers without altering series layout. |
| `spatial_fade.py` | Share transition-width validation if needed to keep target conversion and effect acceptance identical. |
| `viewer.py`, `ui/review.html` | Authenticated read-only endpoints; file controls, safe placement preview, dirty/version guards, sequential loading and Undo import. |
| Existing `export.py`, `effects.py`, `previews.py` | Reuse validated saved layers and canonical rendering. Modify only if extracting a selected-revision renderer prevents duplication; never route through current-only gallery publication. |
| New `tests/test_appearance_recipes.py`; existing series/viewer/page/effects/exposure/shadow/spatial/export/preview tests | Codec/bounds/privacy, saved-revision binding, no mutation and real shipped-page state. |
| `README.md`, `docs/file-contract.md`, `docs/workflow.md`, `docs/assistant-workflow.md` | Versioned standalone format, source reference disclosure, settings/layout boundaries and manual workflow. |

Do not serialize `Recipe.to_dict()` then remove fields. Build the exact allowlisted payload. Do not introduce a generic preset registry, catalog, arbitrary file endpoint, multi-effect Apply coordinator or hidden migration.

## Increment 1 — Complete settings/reference save-load journey

Tasks 1–4 remain internal implementation checkpoints for a complete settings-only workflow. The first increment includes file validation/privacy, saved-revision selection, safe UI loading and sequential use; it is useful if layout transfer is deferred. Its exact v1 interfaces below stay valid when increment 2 adds the alternative spatial section.

### Task 1: Codec, safe reference and subject-relative values

**Files:** create `src/blackmask/appearance_recipes.py`, `tests/test_appearance_recipes.py`; modify `src/blackmask/series_framing.py`, `tests/test_series_framing.py`; narrowly modify `spatial_fade.py`/its tests if extracting shared width validation.

**Interfaces:**

```python
def parse_appearance_recipe(raw: bytes) -> dict[str, Any]: ...
def portable_appearance_recipe(value: dict[str, Any]) -> bytes: ...
def appearance_recipe_form_values(value: dict[str, Any],
    target_subject_bounds: tuple[int, int, int, int] | None,
    target_dimensions_wh: tuple[int, int]) -> dict[str, Any]: ...
def nonzero_alpha_bounds(alpha16: np.ndarray) -> tuple[int, int, int, int] | None: ...
def _canonicalize_portable_interval(value: float, lower: float, upper: float,
    error_budget: float) -> float: ...
```

The first three and the private interval helper live in the new module; `nonzero_alpha_bounds` is extracted from `compute_series_layout` in `series_framing.py` and returns half-open native bounds or None. Form conversion returns exactly `{"sections": <converted loadable sections>, "unavailable": <section-to-reason map>}`; malformed input fails altogether. The private helper applies only the spec's closed-endpoint correction using an internally computed finite/nonnegative budget; callers never accept a budget from the file or HTTP request. Native validators remain unchanged; shading's strict-positive rule does not call the helper at zero. Reuse canonical validators for the spec's exact six sections; if a shared scalar transition validator is required, own it in `spatial_fade.py` and call it from both paths.

- [ ] Add `test_appearance_recipe_strict_roundtrip`: every allowed section and valid combination round trips; exact unknown/duplicate root and nested keys, invalid kind/version/UTF-8, bool/NaN/Infinity, empty sections, shading+spatial and oversize bytes reject. Define a maximum nesting depth of 8 for this shallow format and reject excess before normalization; catch parser recursion errors as bounded validation errors. Include names with `<img>` text to prove they remain plain text later, and reject control characters.
- [ ] Add `test_fractional_width_conversion_includes_faint_bounds`: synthetic alpha with 65535 centre and alpha1 edge establishes bounds100×80, fraction0.005 yields transition0.5. Same bounds preserve0.5; doubled bounds yield1.0. Shading fraction0.0125 yields1.25 without rounding. Add subject-size49 with JSON-roundtripped fraction0.5/49: the independently computed product0.49999999999999994 must load as0.5 under the spec's budget. Use `math.nextafter` fixtures beyond that budget and assert rejection; valid interior values stay exact. Shading zero/negative remains invalid. Empty target reports width sections unavailable while valid shadow/background sections remain loadable. Materially too-small spatial transition0.25 and above native maximum report unavailable, never fit. Assert the extracted scan leaves existing series layout byte-for-byte/numerically unchanged.
- [ ] Add `test_reference_png_is_bounded_sanitized_and_self_contained`: valid RGB8 PNG roundtrip, optional null, base64 errors, forged dimension fields, decoded513-pixel side, >262144 pixels, >1048576 encoded bytes, animation, SVG/URL, malformed/truncated chunks and decompression-bomb header. Inspect returned PNG chunks/metadata to ensure private text/EXIF is removed, and declared/decoded dimensions match. Test combined JSON/base64 maximum and one-byte-over cases, not just each limit separately.
- [ ] Run `rtk proxy .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_appearance_recipes.py tests/test_series_framing.py`; require causal failures for new functions/contracts.
- [ ] Implement strict bounded parsing/serialization, exact per-section fields from the spec and metadata-free PNG re-encoding. Check type/dimensions before full decode, retain Pillow safety limits, reject non-RGB8/multiple frames and re-encode RGB8; do not echo original imported bytes. Inspect format-specific chunks as needed to enforce the exact accepted format without adding a dependency. Reject input rather than allocating on untrusted claimed dimensions.
- [ ] Extract the bounds scan without changing the existing series layout result; implement finite float width conversion using validated target dimensions and the shared interval helper for spatial endpoints. Use `4*(ulp(product)+ulp(endpoint))` for each boundary; reject greater violations and leave native validators strict. Selective target unsuitability is reported per section; structurally invalid data never partially loads. Rerun focused checks and `test_spatial_fade.py` if a validator was extracted; require pass.

### Task 2: Read a chosen saved revision without project mutation

**Files:** modify `src/blackmask/appearance_recipes.py`, `tests/test_appearance_recipes.py`; consume `export.validated_layer_inputs`, `saved_layers`, canonical effect/background/spatial readers and canonical render functions. Only extract a common selected-revision renderer into the existing rendering owner if direct composition would duplicate current processing.

**Interfaces:** produce:

```python
def appearance_recipe_from_revision(project: Path, revision: str,
    expected_manifest_sha256: str, name: str, sections: list[str],
    reference_shape_id: str | None, include_reference: bool) -> bytes: ...
```

Server owns the project path. Bind raw manifest hash and selected revision's actual source/assets throughout validation/rendering. `reference_shape_id` identifies `"oval"` or an actual saved arc ID only for spatial defaults, never enters portable output. Missing sections/settings are errors; do not fabricate defaults from current draft values. Disabled source sections require explicit selection and expose status to the save dialog without transferring enabled state.

- [ ] Add `test_recipe_uses_selected_saved_revision_not_latest_or_draft`: create two synthetic complete saved revisions A/B and conflicting unsaved controls, select A by exact manifest hash, assert only A's selected scalar values and A's rendered reference pixels are exported. Include saved spatial oval/arc choices with unequal transition/amount; selected shape alone supplies defaults, no average or coordinates/ID leak. Exclude thumbnail and assert no thumbnail render runs.
- [ ] Add `test_recipe_export_preserves_project_and_private_boundaries`: hash project state, draft, guide, source, revision and acceptance assets before/after create; all remain unchanged. Decode JSON and PNG to reject source paths/IDs/hashes, groups, locks, alpha, masks, geometry, reduction and metadata. With source state/manifest changing during render or corrupt/stale/missing operands, return no downloadable recipe. Do not refresh gallery or acquire a publication transaction.
- [ ] Run `rtk proxy .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_appearance_recipes.py`; confirm causal failure, then implement saved-only allowlisted extraction. Use the full saved nonzero-alpha bounds for width normalization; empty bounds make width-section saving fail with a clear reason. Preserve source revision's background and effects in an optional reference; resample through the existing saved render pipeline before RGB8 PNG encoding. Never call `_render_latest` for an arbitrary selected revision.
- [ ] Rerun appearance-recipe checks and affected `test_export.py`/`test_previews.py` only if their shared rendering owners changed. Require no mutation and exact selected-revision binding. Update the portable format section in `docs/file-contract.md` with fields/limits and no-project-migration policy.

### Task 3: Bounded authenticated local endpoints

**Files:** modify `src/blackmask/viewer.py`, `tests/test_viewer.py`, `tests/test_appearance_recipes.py`.

**Interfaces:** add `ReviewServer.create_appearance_recipe(data: Any) -> dict[str, Any]` and `ReviewServer.validate_appearance_recipe(data: Any) -> dict[str, Any]` at `/api/appearance-recipe-create` and `/api/appearance-recipe-validate`. Exact create envelope: `developed_id`, `revision`, `revision_manifest_sha256`, `name`, `sections`, `reference_shape_id`, `include_reference`; response `recipe_json` plus the echoed source binding. Exact validate envelope: `recipe_json`, `developed_id`, `revision`, `revision_manifest_sha256`; response sanitized recipe plus target binding and Task 1's `sections`/`unavailable`. Source/target identity is transport-local and never written into portable JSON.

- [ ] Add `test_appearance_recipe_endpoints_are_read_only_and_bound`: valid authenticated create/validate succeed; wrong origin/token, duplicate envelope keys, unknown keys, non-string JSON, malformed imported recipe, stale master/raw manifest, unsupported/incomplete target, oversize outer/inner body and concurrent preview reject with no action/job/project write. An existing project with no matte may validate a file for scalar-only preview, but returns width-dependent sections unavailable and never bypasses normal Apply prerequisites.
- [ ] Define the no-matte validate identity explicitly: `revision` and `revision_manifest_sha256` may both be null only when current `working_revision` is null; bind developed ID and current state/input identity in the response. Otherwise require an actual complete selected target revision and exact raw hash. A partial pair is invalid. Create always requires a complete revision.
- [ ] Run targeted endpoint tests for causal failure. Add route handling to existing token/origin checks and duplicate-key envelope parsing; enforce existing 2000000-byte outer cap plus Task 1's inner limits. Use the bounded preview lock and recheck captured state/source/revision bindings before return; no writer transaction or background job. Derive target bounds/dimensions from actual validated target assets, never imported metadata.
- [ ] Run `rtk proxy .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_appearance_recipes.py tests/test_viewer.py`; require pass. Reuse existing errors/status conventions and keep unrelated endpoint acceptance unchanged.

### Task 4: Safe forms, dirty-state preservation and sequential use

**Files:** modify `src/blackmask/ui/review.html`, `tests/test_viewer_page.py`, `tests/test_viewer.py`, `README.md`, `docs/workflow.md`, `docs/assistant-workflow.md`.

**Interfaces:** add `appearanceRecipePreview` holding the sanitized parsed recipe/reference and target conversion; `appearanceRecipeImportSequence`; and per-supported-section scalar draft `{identity, version, dirty}` tracking where not already present. Add `loadAppearanceRecipeSections(sectionNames)` and `reloadAppearanceRecipeSection(sectionName)`. Both use Task 3 validation/conversion for the current target, confirm replacements and change scalar forms only. Add `exposureAreaDraftBinding` and `fadeAreaDraftBinding`, each `{identity, version}` or null for clean/current saved areas; existing area arrays and dirty flags remain the value owners. Use `markEffectAreaDirty(prefix)` and `effectAreaDraftStale(prefix)` for the two existing area editors, with the same developed/base/input/authoring identity fields as current scalar guards. Spatial retains its single whole-draft identity; never rebind that identity through scalar import.

- [ ] Add `appearanceRecipeLoadsOnlySelectedScalars`: import via File.arrayBuffer/fatal UTF-8/server validation; render name using textContent. Assert background/exposure/cleanup default unchecked, no job or guidance write on load, unselected fields/ON-OFF/source/WB/framing/acceptance unchanged, no new shape, and target selected-shape transition/amount only. Existing geometry/protection/reduction drafts remain exact. Dirty included forms show a replacement list and cancel leaves everything unchanged.
- [ ] Add `appearanceRecipeFractionalBackgroundSurvivesApply`: save/load a selected background with `variation: 0.125`, explicitly load that section, then use the shipped Apply handler and saved-state reload. Assert numeric `12.5%`, submitted/saved `0.125`, and unchanged value after reload, colour-only edits and programmatic range synchronization. Include endpoints and empty/nonfinite/out-of-range rejection. Use the actual viewer operation for persistence evidence; a page stub alone does not prove the saved round trip. Include fractional numeric entry/reload in the offline browser journey because the page harness does not establish native input/slider behaviour.
- [ ] Add `appearanceRecipeSequentialApplyKeepsRemainingValues`: load shadow+exposure+shading, apply one through the existing action, then assert preview persists, other values remain present and visibly stale, and `loadAuthoring` has not reset them. Explicitly reload the next section onto the current revision and apply; all three can be completed in sequence. Add `appearanceRecipeScalarReloadCannotRebindArea`: edit exposure/Shadow area or protection on A, use another effect to create B, reload recipe scalars onto B, then assert replace-area Apply rejects the stale A binding without submitting a job; amount-only Apply may use B's validated saved area and must not consume/clear the dirty A draft. Explicit area recovery restores usability. Add spatial-with-no-selected-shape and stale-spatial-draft cases: scalar import leaves stale geometry/identity untouched and keeps values in the preview until explicit reset/re-authoring then current-shape selection.
- [ ] Add `appearanceRecipeLateResponsesCannotReplaceNewerDrafts`: old import, thumbnail creation or Apply response arrives after a newer selection/edit/revision change. Assert no outdated download, preview/form replacement or dirty clearing; failure preserves pending state. For same-revision scalar edits advance versions; completion clears only its submitted unchanged section. Blob URLs are revoked when replaced/closed; a download says initiated, not verified saved.
- [ ] Run `rtk proxy .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_viewer_page.py tests/test_viewer.py`; confirm these cases fail before UI changes.
- [ ] Add save/load controls, supported saved-section selection, saved reference-shape choice, optional thumbnail checkbox/disclosure, sanitized reference preview and explicit selective loading. Use a bounded browser file-size check before reading and Task 3 validation before any form replacement. Source revision and pending-edits exclusion are visible in Save. No automatic enable or Apply.
- [ ] Preserve fractional background variation in the existing form: use a fractional-capable numeric input (`step="any"`), remove `Math.round` from saved-value loading and misleading whole-percent status, and replace the Apply integer-only check with finite bounded numeric validation. Apply reads the numeric value, never the potentially stepped range value; programmatic range synchronization cannot write back a rounded value. An actual slider input may choose a new stepped value. Reuse canonical `validate_background` without narrowing its range or adding a second recipe-specific Apply path.
- [ ] Add narrowly scoped dirty/version tracking for imported scalar forms that lack it. Guard `loadAuthoring` resets and Apply completion by submitted section/version/identity; preserve unrelated dirty scalar values with their old binding/stale message. Preview survives revision refresh; explicit per-section reload refreshes conversion and scalar identity, not geometry. Do not build a new transaction coordinator or silently rebase the remaining sections.
- [ ] Bind exposure/Shadow area drafts independently on their first add/remove/clear/protection edit, incrementing their version on each edit. Reject stale replace-area Apply regardless of scalar identity; leave amount-only use of saved areas available. Scalar loading never updates these bindings. Clear/rebind only after explicit area reload/re-authoring or successful publication matching submitted area identity/version; do not clear on unrelated/amount-only/late completion. For spatial, reject scalar loading while the existing whole draft is stale; require explicit geometry recovery before assignment and never set `spatialDraftIdentity` to bypass it. Test cancellation and a newer area edit surviving older completion through actual shipped-page handlers.
- [ ] Rerun page/viewer checks, then document the full sequential flow and selected-shape-default limitation. Explain widths scale to visible subject bounds, target geometry still needs authoring, and reference is the source example. Add the supported loopback contract to assisted docs without granting source transfers or image acceptance.

- [ ] Complete the settled verification gate below for increment 1 before advancing. Do not ship only a codec or forms without its draft/identity safeguards.

## Increment 2 — Optional editable spatial-layout transfer

Depends on complete increment 1. It reuses the file/thumbnail/identity machinery and existing spatial editor; no new product rendering engine, masks, reference image matching or automatic composition inference.

### Task 5: Version-2 layout and validated target proposals

**Files:** modify `src/blackmask/appearance_recipes.py`, `src/blackmask/viewer.py`, `tests/test_appearance_recipes.py`, `tests/test_viewer.py`, `tests/test_spatial_fade.py`, `docs/file-contract.md`. Native spatial validators/renderers remain authoritative and unchanged unless an evidenced extraction is required.

**Interfaces:** extend existing create selection with `sections:[...,"spatial_layout"]`, mutually exclusive with `spatial_fade`/`shading`, and require null `reference_shape_id` for layout. No redundant include flag. Add:

```python
def spatial_layout_from_settings(settings: dict[str, Any],
    source_subject_bounds: tuple[int, int, int, int]) -> dict[str, Any]: ...
def spatial_layout_proposal(layout: dict[str, Any], target_settings: dict[str, Any],
    target_subject_bounds: tuple[int, int, int, int],
    target_dimensions_wh: tuple[int, int], mode: str,
    imported_arc_ids: list[str]) -> dict[str, Any]: ...
def spatial_layout_scalar_defaults(layout: dict[str, Any],
    shape: str | int) -> dict[str, Any]: ...
```

The result is complete validated native spatial settings. The pure helper consumes new UUID-v4 IDs supplied by the endpoint once per proposal. Add `ReviewServer.preview_appearance_layout(data: Any) -> dict[str, Any]` at `/api/appearance-layout-preview`, with the exact envelope/response and identity requirements in the spec. Extend file validation so `spatial_layout` remains a separately labelled preview-only section until this endpoint is used; never pass it through scalar form assignment. Missing bounds make layout unavailable, retaining independent sections.

`spatial_layout_scalar_defaults` returns exactly the three v1 spatial scalar fields for `"oval"` or a valid zero-based integer arc index (not bool). Permit optional `layout_defaults_shape` in the validate envelope only for v2 layout input: preserve the sanitized original recipe but return these derived defaults through existing target conversion, with no layout assignment. This supports explicit **Use settings only** without the source project; it does not persist competing representations or auto-fallback after a failed placement.

- [ ] Add `test_layout_v2_schema_and_saved_only_export`: write v1 for scalar-only selections and v2 for layout; accept v1 unchanged, reject v1+layout/unknown versions and competing spatial/shading representations. Save all actual source oval/arcs including disabled geometry but no master flag/source IDs/protection/reduction/native coordinates. Full layout comes from the selected saved revision; thumbnail and settings binding remain the same. Reject invalid disabled shapes and >32 arcs before allocating native fields. Add `test_layout_settings_only_fallback_needs_no_source`: after placement fails, selecting a portable arc derives only its scalar defaults through v1 target validation, with no source lookup/geometry assignment/file rewrite; invalid selector or width rejects, and no fallback occurs without explicit selection.
- [ ] Add `test_layout_transform_preserves_uniform_geometry`: source bounds `(10,20,110,100)`, target `(20,30,220,190)` yield centre `(85,40)` → `(170,70)`, radii `(20,10)` → `(40,20)`, transition7.5→15, arc half-span30→60, bend−10→−20 and softness2→4; rotation37 and strengths/side stay unchanged. Include translated bounds, differing aspect ratios, alpha1 extremities and equal-size return. Assert analytical shape weights at corresponding continuous coordinates agree within floating precision; do not compare different raster sampling grids as identical.
- [ ] Add `test_layout_conversion_boundary_budget_and_rejection`: exercise0.5, native0/max centres, negative bend, span/softness equalities, zero cancellation and finite overflow. Reuse Task1's converter-only helper; assert identical transition results for v1, v2 layout and its scalar fallback at size49 and independent boundary fixtures. Use `math.nextafter` inside and beyond the spec's4-ULP operation-term budget; correction applies only to just-outside values and native validators remain strict. A materially off-canvas centre/thin-target failure returns a field-specific unavailable error with no shapes dropped/fitted; scalar sections remain usable. Repeated conversion starts from portable originals with no accumulated transformation drift.
- [ ] Add `test_layout_add_replace_switches_and_ids`: every source/target arc-group switch combination; Add keeps target oval/highlights/master/group/IDs, imports `source_group && source_arc.enabled`, rejects zero arcs and totals33 while allowing32. Replace copies source layout/internal switches/highlights, retains target master; all new IDs are valid unique UUID-v4 disjoint from target IDs, and count/order match imported shapes. Adding arcs cannot reduce the preexisting maximum fade contribution. Reject invalid target settings or ID lists rather than repairing them silently.
- [ ] Run `rtk proxy .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_appearance_recipes.py tests/test_spatial_fade.py tests/test_viewer.py`; confirm causal failure of new v2/proposal contracts.
- [ ] Implement exact v2 fields from the spec, allowlisted saved layout normalization and fixed-order target conversion with bounded endpoint canonicalization in the converter only. Reuse canonical shape validators and existing subject bounds; normalize/scale every native length including bend/end softness. Generate proposal IDs once at the endpoint, validate final merged settings, and retain separate scalar/layout response paths. No new mutable project format or cache.
- [ ] Add endpoint tests for wrong token/origin, duplicate/extra keys, current revision/raw manifest mismatch, stale input/authoring digest, incomplete/empty matte, invalid native draft/version/mode and late source changes. Captured current bindings/version/mode return with native proposal; use existing bounded preview lock, request limits and failure-before-write behaviour. Endpoint does not render images or start a job. Rerun the focused command and document v1/v2 compatibility; require pass.

### Task 6: Placement review, explicit Add/Replace and exact recovery

**Files:** modify `src/blackmask/ui/review.html`, `tests/test_viewer_page.py`, `tests/test_viewer.py`, `tests/test_spatial_fade.py`, `tests/test_export.py`, `README.md`, `docs/workflow.md`, `docs/assistant-workflow.md`; extend `tests/test_cache_management.py`/`tests/test_library_storage_journey.py` when available in the settled I19 successor.

**Interfaces:** add `appearanceLayoutProposal` (immutable proposed settings plus source/target/mode/draft binding), `appearanceLayoutSequence` and one `appearanceLayoutUndo` snapshot. Add `previewAppearanceLayout(mode)`, `loadAppearanceLayout()`, `undoAppearanceLayoutImport()` and cancel handling. Reuse native outline drawing and existing spatial handles/numeric controls after load. No transform toolbox or saved-map-as-draft-preview shortcut.

- [ ] Add `appearanceLayoutPreviewCancelKeepsDraftExact`: start with nonempty dirty spatial/auxiliary controls, choose Add or Replace, preview and cancel. Assert original draft, chosen shape, dirty/binding/version, protection/candidate controls and any reduction draft remain exact; no action/write. Preview label is **Placement preview — effects not applied**. Stale spatial draft blocks proposal/load until explicit recovery. Superseded import/mode/target replies cannot replace the current proposal.
- [ ] Add `appearanceLayoutAddReplaceAndUndo`: test both modes and switches, Replace confirmation/cancel, source with disabled groups and current inward-shading disclosure. Load only modifies spatial draft with a new monotonic version; no implicit master enabling or Apply. Save exact pre-load draft/selected shape/dirty identity/auxiliary protection and candidate controls. Undo with matching target and post-load version restores values exactly while advancing version; newer shape edit, any related control edit, another load, Apply or identity change invalidates Undo. Existing `resetSpatialFromSaved` is not used for undo; it clears controls and loses prior drafts.
- [ ] Add `appearanceLayoutLateReplyAndProtectedApply`: current draft is edited while preview/confirmation awaits; load refuses without discarding either user's state or source recipe. Existing area/scalar stale guards from increment1 remain operative. Explicit Apply produces ordinary saved native spatial geometry, with unchanged source/alpha/protection/reduction and expected global-mode behaviour. Read/reopen and requested editable export reconstruct from native stored operands, not portable fractions or original source files.
- [ ] Run `rtk proxy .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_viewer_page.py tests/test_viewer.py tests/test_spatial_fade.py tests/test_export.py`; demonstrate new cases fail causally before interaction changes.
- [ ] Implement explicit opt-in layout save/load, Add/Replace selection, bound outline preview, descriptive unavailable-field errors and **Use settings only** with explicit portable-shape selection/current target shape. Require confirmation for Replace even when the current draft is clean; any overwritten dirty spatial data is listed. Keep target master, protection/reduction and unrelated forms unchanged. Generate no new arcs through `addSpatialArc` because that auto-enables the group; install the already validated merged proposal once. Existing shape controls provide all post-load editing.
- [ ] Implement guarded one-step Undo snapshot/version semantics and invalidate it on subsequent relevant mutation/Apply; cancellation before load requires no restoration. Preserve the recipe preview for retry on another valid target or settings-only reuse. No silent fit, source matching or fabricated hidden detail.
- [ ] Run focused checks and one synthetic I19 cache inspect/clear journey: preserve ordinary loaded native layout, target protection/reduction, accepted history, all permanent deliveries; reconstruct editable output afterward from delivered assets with original project unavailable. Reuse `_validate_cache_context`'s canonical revision/delivery path; do not alter cache parser policy or create exception lists. Complete the settled gate for increment2 and document limits, maximum combination and native compatibility.

## Settled verification, acceptance and execution handoff

- [ ] Self-review applicable spec sections against Tasks 1–6; inspect every changed reset/completion/undo handler and cross-effect caller for lost drafts. Keep one codec/bounds/render owner and no unnecessary format/framework/catalog work.
- [ ] Run the repository's documented commands once on settled inputs for each increment:

```bash
rtk proxy .venv/bin/python -m pytest -q -p no:cacheprovider
rtk proxy .venv/bin/ruff check src tests --no-cache
rtk proxy .venv/bin/ruff format --check src tests --no-cache
rtk proxy .venv/bin/mypy src
```

Expected: successful exits, no new diagnostics; record actual optional skips and limitations. Verify matching local Python/Node before execution; this plan does not install dependencies. Do not rerun unchanged successful checks without a material reason.

- [ ] Run an actual offline browser journey on two synthetic projects: save selected old revision, download/reopen with/without reference, keyboard navigation and cancel, different subject sizes, dirty confirmation, multiple sections applied sequentially, absent geometry and stale target. Increment2 adds v1/v2, Add/Replace, disabled groups, off-canvas rejection, placement Cancel, exact Undo and shape editing/Apply/reopen. Confirm no network requests beyond localhost and no project changes before explicit Apply. Page-harness tests are not browser/usability evidence.
- [ ] Inspect actual wheel/sdist contents using the existing packaging procedure and installed backend: no recipes/private thumbnails, planning files or local paths bundled. Regression-check existing series presets and manual no-assistant workflow; no model evaluation is needed for this feature.
- [ ] Conduct one bounded independent implementation review under the selected workflow; fix verified material findings and rerun only affected checks. Record human usefulness/appearance acceptance separately. No product-quality claim follows merely from a source reference thumbnail matching itself.
- [ ] Report actual implementation/checks and limitations. Preserve source recipe files and project histories. Commit/push/PR only with separate explicit authorization and after all required gates; no unconditional Git write step is implied by this plan.

**Incremental-plan assessment, revised 2026-10-25:** two increments. Tasks1–4 deliver complete safe settings/reference reuse; Tasks5–6 add optional editable layout transfer with its own placement/merge/recovery/compatibility acceptance story. The user expanded scope to geometry; settings-only remains useful and safe if layout is deferred. Do not split codec, UI and safety into separate shipping increments or defer their tests. A catalog and one-click multi-effect Apply remain excluded. This is a sizing assessment within the requested Superpowers plan, not an unsolicited new incremental artifact set or modification to I18/I19 coordination.

**Recommended execution:** native implementation with `superpowers:executing-plans`, because selected-revision rendering, endpoint identity and per-section UI state are tightly coupled and benefit from one persistent implementer. Keep independent review read-only. The user approves the proposed scope and chooses execution before implementation.
