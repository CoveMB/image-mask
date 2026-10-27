# Soft Fade Reduction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (recommended for these coupled paths), or superpowers:subagent-driven-development if the user selects that method. Steps use checkbox (`- [ ]`) syntax for tracking. This document authorizes no implementation or Git writes.

**Goal:** Let the photographer softly reduce either existing fade in selected areas while preserving the source, matte, categorical protection and editable recovery.

**Architecture:** Add one bounded reduction-geometry owner and separate saved operands for the two existing effects. Apply reduction inside each canonical effect calculation; carry the operands through existing shared assets, validation, comparisons and requested exports. Deliver complete spatial reduction first, then complete Shadow fade reduction.

**Tech Stack:** Existing Python >=3.12,<3.13, NumPy, SciPy support rasterization, Pillow/tifffile, standard-library local HTTP server, vanilla JavaScript, pytest/Ruff/mypy and the existing Node page harness. No new dependency, model, service or inference.

**Spec:** [Soft fade reduction design](../specs/2026-10-24-soft-fade-reduction-design.md). Read the spec and this plan together. [Separate review record](2026-10-24-soft-fade-reduction-reviews.md).

## Global Constraints

- The user's 2026-10-25 “most flexible” answer confirms independent reduction for both `spatial_fade` and `shadow_fade`. The concrete design/saved-record compatibility and execution remain unapproved; this is a scope clarification only.
- Latest inspected local candidate: clean `ed86ca84478846271c9f4da09c02ddbe5a38d2bd`, tree `ead610dced94b17aa6718da8e95405be0300135f`, at `/Users/CoveMB/Code/CoveMB/image-mask/local/reviews/coderabbit-pass/inspectable-processing-cache-preparation/implementation`. This supersedes the earlier I18-only inspection baseline. No remote refresh or hosted-readiness claim.
- The planning checkout is `docs/named-local-references` at `df7921d31aa4d3a84596856d8f0b164ae4292c7d`; it is not the application baseline. Before execution use the settled successor of the candidate, reconcile I19/cache work and preserve all ongoing delivery and dirty work. Do not guess a branch or copy source files into this older tree.
- 2026-10-25 independent-review refresh: ed86 includes I19 on parent `2edae84a58a9bd2d9e6e51ac4f118a0122b7cfc0` plus the native-review staging correction. The current handoff records parent2eda as published and ed86 as local awaiting publication; this is handoff context, not a fresh provider check. Preserve canonical permanent-context validation and reconcile the settled successor before execution, without borrowing another chat's authority.
- Source RGB16, alpha16, guides, background, framing and unrelated effect operands remain unchanged. Categorical locks remain absolute, including partial-alpha samples. No invented photographic detail.
- `R16 = round(65535 * max_i(amount_i * support_i/65535))`; empty is zero. Missing/zero reduction preserves legacy arithmetic. Maximum 128 regions and 8192 total stroke points per target, validated before allocation.
- Reduction files are `reduction16.png` and `reduction.json`; algorithm is `native-support-max-reduction-v1`. Spatial effect schema 1→2; Shadow fade schema 2→3. Read legacy versions without rewriting. Clear retains the upgraded schema with empty/zero operands.
- No implementation, setup, downloads, private-photo processing, commits, pushes, publication or acceptance changes are authorized by this planning task. Future Git writes and photographic evaluation retain their applicable authorization boundaries.

## Review Focus

1. Rehashed geometry/raster disagreement and disabled effects must fail in cold and warm validation, not survive through a shared-asset shortcut — Tasks 2 and 5.
2. A crop or series sampler dropping reduction produces inconsistent output despite a correct full native preview — Tasks 3 and 5.
3. A late save or target switch must not discard the newer draft or accidentally save another target — Tasks 4 and 6.
4. Alpha repair, no-op reuse and resource failure must preserve accepted work and keep stale dependencies stale — Tasks 2 and 5.
5. Editable requested exports must reconstruct with no original project and without applying reduction twice — Tasks 3 and 5.

## File and interface map

| Owner | Responsibility |
| --- | --- |
| New `src/blackmask/fade_reduction.py` | Exact geometry validation, canonical support reuse, maximum-combination raster and bound reduction reader. |
| `spatial_fade.py`, `shadow_fade.py` | Effect-specific version inventories, record validation, reduction operands and arithmetic. |
| `effects.py`, `operations.py`, `project.py` | Exclusive admission, request/execution/reuse identity, inheritance, stale state, publication and semantic validation. |
| `export.py`, `series_framing.py`, `review.py`, `previews.py`, `viewer.py` | All consumers, requested editable inventories, native/crop/series equivalence, resource admission and bound previews. |
| `ui/review.html`, existing `ui/coordinates.js` | Target-local drafts and controls; reuse coordinate mapping without changing it unless a verified need arises. |
| New `tests/test_fade_reduction.py`; existing fade/effects/operations/repair/assets/export/series/review/preview/viewer/page tests | Independent arithmetic and all consequential lifecycle consumers. |
| `README.md`, `docs/file-contract.md`, `docs/workflow.md`, `docs/assistant-workflow.md` | Supported user controls, compatibility, saved assets and supported assisted request contract. |

Do not expand `recipe.py` or generic `assets.py` merely to carry the new fields: geometry belongs to the saved effect record. Change either only if a concrete consumer requires it, with its own regression. Recheck all fixed `SPATIAL_FADE_FILES`/`SHADOW_FADE_FILES` consumers at the actual execution baseline.

## Increment 1 — Complete Fade into background reduction

This increment is useful on its own. It includes Tasks 1–4 and its settled verification gate; no Shadow-only UI or unsupported target is exposed yet.

### Task 1: Bounded geometry and spatial arithmetic

**Files:** create `src/blackmask/fade_reduction.py`, `tests/test_fade_reduction.py`; modify `src/blackmask/spatial_fade.py`, `tests/test_spatial_fade.py`. Reuse `exposure.rasterize_effect_area` and `guidance` support validation/rasterization without changing their established feather semantics.

**Interfaces:** produce `rasterize_fade_reduction(area: dict[str, Any], developed_id: str, width: int, height: int) -> np.ndarray`; extend `SpatialFadeOperands` with final `reduction16: np.ndarray | None = None`. Its record/weight/protection fields and `spatial_fade_amount(foreground, alpha16, operands)` signature remain unchanged.

- [ ] Add `test_reduction_maximum_feather_and_limits`: author two overlapping support rectangles with different IDs and amounts 0.25/0.75, test empty, permuted and duplicated-geometry lists, and test a 4-pixel inward feather independently at boundary/centre. Assert overlap is 49151, not a sum; same geometry with a new unique ID is idempotent. Duplicate IDs, 129 regions, 8193 stroke points, bool/NaN/unknown keys and out-of-native coordinates reject before raster allocation.
- [ ] Add `test_spatial_reduction_endpoints_partial_alpha_and_protection` using current `operands` fixture and `dataclasses.replace`. For constant original weight16 39321, preserve=0, alpha `[65535,1,32768,65535]`, reduction `[0,65535,32768,65535]`, last sample protected, assert:

```python
np.testing.assert_allclose(actual_q, [[0.6, 0.0, 0.6 * (1 - 32768 / 65535), 0.0]], atol=1e-14)
np.testing.assert_array_equal(q_without_operand, q_with_zero_operand)
np.testing.assert_array_equal(alpha_after, alpha_before)
```

- [ ] Run `rtk proxy .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_fade_reduction.py tests/test_spatial_fade.py` before implementation; confirm failure is the missing new contract, not fixture/setup failure.
- [ ] Implement exact-key document validation, bounded native shapes and max accumulation. Keep one uint16 output plus bounded working arrays; do not retain 128 full-size rasters. Apply the optional aligned uint16 reduction to spatial amount after existing support/protection/highlight calculation. Validate operand dtype/shape even if effect is disabled; retain exact legacy zero path.
- [ ] Rerun the same focused command after code changes; require pass, including existing oval/arc geometry and legacy identity tests.

### Task 2: Durable spatial reduction and exclusive operation

**Files:** modify `src/blackmask/fade_reduction.py`, `spatial_fade.py`, `effects.py`, `project.py`, `operations.py`, `viewer.py`; tests in `test_fade_reduction.py`, `test_spatial_fade.py`, `test_effects.py`, `test_repair_operations.py`, `test_assets.py`, `test_viewer.py`.

**Interfaces:** produce `read_fade_reduction(project: Path, directory: Path, manifest: dict[str, Any], effect: str, alpha: np.ndarray) -> np.ndarray | None`; `spatial_fade_files(record: dict[str, Any]) -> tuple[str, ...]` selects the saved schema's inventory. Add exclusive existing-schema-2 operation field `fade_reduction: {"target": "spatial_fade", "area": <reduction document>}`; existing developed/base/input/scope/candidate fields remain mandatory.

The `/api/action` viewer envelope additionally requires `revision_manifest_sha256` for every reduction target. Extend `ReviewServer.start_action`'s exact-field admission and `ReviewServer.execute`'s forwarding to pass this hash as `operations.apply_operation(..., expected_revision_manifest_sha256=...)`, retaining the existing under-project-lock check. It is a viewer binding, not a new field in the persisted schema-2 operation. Extend the existing duplicate-key decoder predicate to include `fade_reduction` actions; strict preview parsing alone does not protect saves.

- [ ] Add `test_spatial_reduction_revision_contract_and_recovery` through the real public effects operation with a nonempty accepted matte. Assert original RGB/alpha and unrelated effects retain hashes, version becomes 2 only on explicit reduction edit, both new files/hashes bind, OFF/settings/shape/background changes inherit them, clear saves zero/empty, and restore returns the saved bytes. Add alpha-change rejection and same-alpha repair propagation cases with nonempty protected partial pixels.
- [ ] Add `test_spatial_reduction_corruption_reuse_and_failure`: corrupt file bytes, then separately change authored geometry while rehashing the manifest; both must reject in cold/warm and disabled states. Reject mixed operations, unsupported target, stale base/alpha, incomplete effect, missing/extra files and too-small declared scope. A changed amount cannot reuse old output; a validated no-op can. Simulated low disk/publication interruption leaves state/acceptance and previous assets unchanged.
- [ ] Add save-route regressions in `test_viewer.py`: capture the raw revision hash, replace the same named revision with another internally valid manifest while retaining root recipe/guides and the input digest, then submit the old hash. Require rejection before publication with project/accepted state unchanged. Missing/malformed hashes reject at admission. Send raw HTTP JSON with duplicate reduction target and area keys; require rejection before an action starts, not merely after conversion to a dict. Repeat for Shadow in Task5; Task4's failed-Apply page case must preserve the authored draft on the stale-manifest error.
- [ ] Run the new selected cases in `test_fade_reduction.py` and `test_spatial_fade.py`; require causal failure before storage/admission implementation.
- [ ] Implement record-selected asset inventories, shared-asset reads/inheritance and recomputation checks. Extend `_effects_request_identity`'s effect recognition so reduction never triggers default cleanup; bind target/geometry/algorithm and dependencies into execution and reuse identity. Require a saved nonstale selected effect, including disabled-alpha matching. Validate scope over old/new reduction; UI will send full native scope. Preserve all other recipe sections and stale flags.
- [ ] Account for reduction plus scratch in existing admission before compute/staging; keep publication transactional. Pending I19's `_validate_cache_context` already follows canonical revision and delivery validators; carry schema-selected reduction assets through that path. Keep the combined cache-clear/export reconstruction check with Task3 after its export consumers exist. Do not change cache parser policy or add a parallel exception list. No new cache system.
- [ ] Run `rtk proxy .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_fade_reduction.py tests/test_spatial_fade.py tests/test_effects.py tests/test_repair_operations.py tests/test_assets.py tests/test_viewer.py`; require all pass. Extend documented version/file tables in `docs/file-contract.md` in this task.

### Task 3: Spatial rendering, requested delivery and comparison

**Files:** modify `src/blackmask/export.py`, `series_framing.py`, `review.py`, `previews.py`, `viewer.py`; tests in `test_export.py`, `test_series_framing.py`, `test_review.py`, `test_previews.py`, `test_viewer.py`, `test_spatial_fade.py`.

**Interfaces:** consume Task 1 operands and Task 2 inventory. Add `ReviewServer.preview_fade_reduction(data: Any) -> dict[str, Any]` at authenticated `/api/fade-reduction-preview`: exact fields `developed_id`, `revision`, `revision_manifest_sha256`, `crop_xyxy`, `target`, `view`; `view` is `"coverage"` or `"off"`; only OFF permits optional `panel` in `result|black|gray|white`. Increment 1 accepts only `spatial_fade`. Reuse the existing preview lock, byte cap, duplicate-key handling, raw revision binding and response image contract from `preview_spatial`.

- [ ] Add `test_spatial_reduction_crop_series_and_requested_delivery`: unequal fractional alpha, nonzero protected pixels, nonuniform source/background and reduction cross a crop edge. Assert whole/crop q equivalence; independently compute premultiplied foreground/alpha/q sampling for Match series; preserve transparent and add-margins semantics. Flat-only requested variants contain no unexpected editable bundle. Requested editable variants contain record-selected reduction assets even when OFF.
- [ ] Extend the existing fresh-process editable reconstruction test: make the source project unavailable to the child, use only delivered operands, and compare against independently expected native/series rendering. This must fail if reduction is dropped or applied twice; changing only the exported reduction must change only the corresponding effect contribution.
- [ ] Add `test_reduction_preview_binds_saved_native_identity`: coverage reflects R16; OFF differs from Fade OFF and removes only the reduction. Bad target/view, stale manifest, source change during rendering, bad crop, duplicate envelope and concurrent preview reject with no mutation. Native crop/gray/white/black bindings match saved results.
- [ ] Run those new tests and demonstrate causal failures. Then propagate reduction through every `SpatialFadeOperands` constructor/slice and every saved render/export path; keep original geometric weight validation unchanged. Reuse `spatial_fade_amount` for series, not a second reduction formula. Use schema-selected delivery/reuse inventories and resource estimates.
- [ ] Implement preview as a read-only saved-operand view: coverage shows saved reduction; OFF constructs spatial operands with `reduction16=None`, preserving spatial settings/protection and all earlier effects. All captured source/state identities are rechecked before response.
- [ ] Extend `tests/test_cache_management.py` and `tests/test_library_storage_journey.py` if present in the settled successor: inspect/clear one eligible synthetic prediction, assert all permanent reduction/geometry/shared/export bytes unchanged, then independently reconstruct requested editable output with the project absent. Run those affected checks after the export integration; Task2's admission work alone is not expected to supply the finished export journey. Repeat this combined case with both reductions in Task5.
- [ ] Run `rtk proxy .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_spatial_fade.py tests/test_export.py tests/test_series_framing.py tests/test_review.py tests/test_previews.py tests/test_viewer.py`; require pass.

### Task 4: Spatial controls and complete first increment

**Files:** modify `src/blackmask/ui/review.html`, `tests/test_viewer_page.py`, `tests/test_viewer.py`, `README.md`, `docs/workflow.md`, `docs/assistant-workflow.md`.

**Interfaces:** JavaScript `fadeReductionDrafts` is a map keyed by supported target, each containing `{area, identity, version, dirty}`. Add `markFadeReductionDirty(target)`, `reloadFadeReduction(target)` and `applyFadeReduction(target)`; payload matches Task 2. No write occurs on drawing or numeric change. Reuse existing native coordinates and target comparison binding.

Capture the raw revision-manifest hash in each draft identity and send that captured hash in Apply's viewer envelope; never refresh it from newer state without explicit reload. Retain the existing authoring digest and Task2's backend guard as well as the target/version completion guard.

Extend `ReviewServer.snapshot` revision entries with validated `fade_reduction_areas: {target: area}` through shared-asset readers; legacy saved effects supply empty documents, absent effects omit the target. Bind the raw revision hash as for existing exposure/fade areas. Add `viewer.py` to this task's modified files; `reloadFadeReduction` consumes this saved state, never an arbitrary path.

- [ ] Add actual shipped-page scenarios `reductionDraftSurvivesLateApply`, `reductionClearIsExplicit`, and `reductionKeyboardRectangleAndComparison`. With submitted version v1 then edited v2, assert v2 survives completion/failure. Assert drawing sends no job, clear sends only on Apply, unchanged source/matte fields remain untouched, and stale/mismatched view blocks authoring. Select/remove/strength edits preserve stable IDs. Add snapshot tests for legacy-empty, new shared saved areas, absent target and rehashed corruption rejection; reload/reopen recovers the exact authored document.
- [ ] Run `rtk proxy .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_viewer_page.py tests/test_viewer_coordinates.py tests/test_viewer.py`; confirm new interaction cases fail for the missing controls before implementing.
- [ ] Add **Reduce fade here** controls: brush/keyboard rectangle, native radius, inward feather, reduction strength 0–100%, shape select/remove/clear, explicit Apply/reload, saved/draft status, coverage and **Compare reduction OFF**. Only spatial target is available in this increment. Validate values with the same bounds as the backend. Label wide-feather/no-full-core behaviour; comparisons show saved operands, draft outlines are not a rendered result.
- [ ] Guard response clearing with submitted target, base identity and version. Preserve drafts on failure and keep current candidate-comparison and authoring-busy rules. Update docs with source-preserving semantics, OFF versus reduction OFF, limits and old-reader compatibility/recovery.
- [ ] Rerun focused page/viewer checks. Then run the settled gate below once for increment 1; perform the offline synthetic browser journey with brush and keyboard rectangle, saved reopen, comparison, cancellation/failure and legacy project opening. Human photographic quality remains a separately scoped acceptance check.

## Increment 2 — Complete Shadow fade reduction

Depends on accepted increment 1, not on appearance recipes. Deliver Tasks 5–6 and the settled gate. Its own completion is useful: local reduction of exposure-stop fading while preserving the spatial effect's settings and independent reduction.

### Task 5: Shadow arithmetic, persistence and all consumers

**Files:** modify `src/blackmask/shadow_fade.py`, `fade_reduction.py`, `effects.py`, `project.py`, `operations.py`, `export.py`, `series_framing.py`, `review.py`, `previews.py`, `viewer.py`; tests in `test_shadow_fade.py`, `test_fade_reduction.py`, `test_effects.py`, `test_repair_operations.py`, `test_assets.py`, `test_export.py`, `test_series_framing.py`, `test_viewer.py`.

**Interfaces:** add final optional `reduction16: np.ndarray | None = None` to `apply_shadow_fade`; produce `shadow_fade_files(record: dict[str, Any]) -> tuple[str, ...]` (including optional existing `area.json`). Preserve `read_shadow_fade`'s existing tuple interface; its reader validates reduction through Task 2's helper, and `selected_shadow_fade` supplies it to arithmetic. Permit `target="shadow_fade"` in the existing new operation/preview. Add keyword-only `shadow_reduction_off: bool = False` through `saved_layers`, `selected_foreground`, `selected_shadow_fade` for saved comparisons, keeping existing OFF options unchanged.

- [ ] Extend the independent scalar oracle in `test_shadow_fade.py` with reduction in the exponent, not RGB interpolation. Add `test_shadow_reduction_exposure_stops_and_exact_endpoints`: foreground gray30000, amount0.5, preserve0, support65535, reduction `[0,32768,65535]`, nonzero partial alpha and a separate protected pixel. Compute expected sRGB from independent linear conversion times `2 ** (-3 * (1 - R/65535))`; allow only the existing documented quantization tolerance. Assert full reduction copies original RGB exactly and zero/missing reduction preserves legacy bytes.
- [ ] Add the shadow versions of Task 2 lifecycle/corruption/reuse/failure tests, including version2 legacy→3, optional old area.json, disabled effects, both reductions saved together and alpha repair. Assert spatial operand/settings hashes remain unchanged when only shadow reduction changes; do not assert unchanged downstream highlight-sensitive pixels.
- [ ] Extend Task 3 fresh-process delivery and series tests with both reductions. A shadow reduction OFF comparison must rerender upstream shadow then recalculate existing downstream spatial highlights; preserve spatial reduction and all categorical locks.
- [ ] Run the new shadow/fade-reduction cases; confirm causal failure. Implement the optional factor inside `apply_shadow_fade`'s exposure-stop weight, retain the zero path, add version3 binding/inventory and update every inheritance/validation/reuse/delivery/resource consumer. Reuse the shared reduction document/raster owner; do not add a second support format.
- [ ] Run `rtk proxy .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_shadow_fade.py tests/test_fade_reduction.py tests/test_effects.py tests/test_repair_operations.py tests/test_assets.py tests/test_export.py tests/test_series_framing.py tests/test_viewer.py`; require pass. Extend `docs/file-contract.md` for version3 and reconstruction.

### Task 6: Independent targets and complete second increment

**Files:** modify `src/blackmask/ui/review.html`, `tests/test_viewer_page.py`, `tests/test_viewer.py`, `README.md`, `docs/workflow.md`, `docs/assistant-workflow.md`.

**Interfaces:** reuse Task 4 map/functions; expose a two-option target selector. Each target's identity/version/dirty/area is independent. The helper validates supported targets; never infer a combined operation from visible controls.

- [ ] Add `reductionTargetsKeepIndependentDrafts` and `lateSpatialSaveCannotClearShadowDraft` shipped-page cases. Assert switch-away/switch-back retains both areas, saving one submits one target, clear/reload affects one target, and changing working revision leaves other draft visibly stale. Test amount-only Apply/OFF retention and both comparison labels.
- [ ] Run the focused page tests for causal failure, expose Shadow fade target using the established controls, and guard completion with target/version/identity. Keep disabled-effect stale-alpha rejection visible and preserve drafts after rejection.
- [ ] Rerun page/viewer checks; update documentation and perform the settled gate once on this increment. An actual offline browser journey exercises both targets in sequence, no accidental cross-save and reopen/export. Record synthetic usability evidence separately from any separately authorized human flower/bee assessment.

## Settled verification, completion and execution handoff

- [ ] Reconcile all spec BR1–BR9 requirements with tasks and inspect connected callers once. Remove unnecessary changes; confirm exact legacy arithmetic, all asset consumers and no duplicate rendering path. Review only changed/affected assumptions if the candidate advanced.
- [ ] Run the repository's documented checks once per settled increment, after focused checks and on the same final inputs:

```bash
rtk proxy .venv/bin/python -m pytest -q -p no:cacheprovider
rtk proxy .venv/bin/ruff check src tests --no-cache
rtk proxy .venv/bin/ruff format --check src tests --no-cache
rtk proxy .venv/bin/mypy src
```

Expected: successful exits, no new diagnostics; explain optional skips and unexercised live/model/photo behaviour. Discover/verify matching local runtime before execution; this plan installs nothing. Do not repeat successful checks absent relevant input changes.

- [ ] Review actual offline distribution contents with the existing packaging procedure and installed build backend; exclude planning/private reference files. Run the offline browser journey and record exact inputs/outcomes. Automated page tests alone do not prove browser usability or photographic quality.
- [ ] Obtain a bounded independent review of the implemented increment under the selected execution workflow, fix verified material findings, and renew only affected checks. Preserve separately required implementation/result gates if later converted with the incremental-plan skill.
- [ ] Report implemented scope, actual check results, remaining human acceptance and compatibility limits. Make no commit/push/PR unless explicitly authorized; any authorized commit uses the settled files only and a clear short message.

**Incremental-plan assessment:** two increments because spatial and Shadow reduction are independently useful user capabilities with different arithmetic/persistence/consumer risks. Storage, rendering, UI and safe export are internal tasks within each, not independently shippable increments. Do not split further merely by file or test layer. Formal incremental-plan conversion can use these two boundaries after design approval; this planning request does not create a parallel delivery program or alter I18/I19 handoffs.

**Recommended execution:** native implementation with `superpowers:executing-plans`, sequentially, because the tasks repeatedly touch the same effect admission, asset validation, export and UI state paths. Separate independent reviews stay read-only. The user chooses/approves execution before any implementation begins.
