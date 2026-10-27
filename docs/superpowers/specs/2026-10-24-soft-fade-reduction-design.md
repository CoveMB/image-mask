# Soft fade reduction design

Status: reviewed planning design; implementation is not authorized. On 2026-10-25 the user chose “most flexible” for target scope: retain separately selectable reduction for **Fade into background** and **Shadow fade**, each with its own saved brush area. This confirms the planned target scope, not implementation or saved-format approval.

## Purpose and evidence

The user repeatedly asks for dark petal extremities, gradual transitions, a readable flower centre, an unshaded bee and retained blurred stem detail. A local reduction brush lets them reveal more of an already masked subject without moving a broad fade or weakening unrelated areas. It changes an effect's contribution, not the photographed source or matte.

The current spatial fade combines oval/arc contributions by maximum. A weaker arc cannot undo a stronger contribution. Current effect protection is categorical; it cannot represent partial reduction with a soft boundary. Existing brush/support rasterization already provides registered inward feathering and should be reused.

## Inspected baseline and integration prerequisite

Inspected 2026-10-24: latest located local I18 candidate `9b01987581680bbce6d503661f3f997e2d0325b5`, tree `1ac4d7d6f413c8aa28e3d522f7613e10596e6cb0`, clean detached checkout. This candidate includes shared revision assets, result reuse, requested exports, retained comparisons and the oval/arc fade. The planning checkout is the separate `docs/named-local-references` branch at `df7921d31aa4d3a84596856d8f0b164ae4292c7d`, with unrelated existing planning edits. Do not implement against that older application tree.

Local refs were not fetched; this is local source evidence, not hosted/merge readiness. Before execution locate the settled current successor, confirm the above features remain present, reconcile any I19/cache changes, inspect current instructions/status and renew only affected plan assumptions. Do not copy application files into the planning checkout or alter the ongoing I18/I19 work. This plan requires no merge, commit, setup, photo edit or external action during planning.

2026-10-25 independent-review refresh: inspected the clean local checkout at `local/reviews/coderabbit-pass/inspectable-processing-cache-preparation/implementation`, HEAD `ed86ca84478846271c9f4da09c02ddbe5a38d2bd`, tree `ead610dced94b17aa6718da8e95405be0300135f`, on I19 parent `2edae84a58a9bd2d9e6e51ac4f118a0122b7cfc0`. This includes cache inspection/clear, permanent-context validation and the subsequent native-review staging correction. The current handoff records I19 parent2eda as published and ed86 as a local correction awaiting publication; remote state was not refreshed for this review. Review connected behaviour against this source, then reconcile its settled successor before implementation. Earlier partial-candidate/parser-decision records are historical; no delivery authority or photographic acceptance is inferred.

## Approaches

1. **Recommended proposal: independent effect-reduction operands using existing support geometry.** The same small geometry helper serves both effects, but each effect saves its own area and amount. This supports partial visibility without weakening locks or adding a new rendering pipeline.
2. Restrict the feature to spatial fade. The user selected the more flexible both-target scope instead; spatial remains an independently useful first increment, with Shadow fade following without a broken intermediate state.
3. Change existing protection into a soft mask, or compensate with Local exposure. Rejected: the former changes the meaning of exact locks, while the latter changes upstream colour and can alter highlight-sensitive fading rather than directly reducing it.

## Behaviour contract

- **BR1 — Independent target:** choose either `spatial_fade` or `shadow_fade`. Editing/saving one target leaves the other target's reduction, settings and geometry unchanged. Never offer a combined target that silently writes both.
- **BR2 — Reduction semantics:** 0% leaves the selected fade unchanged; 100% removes its contribution in the full-strength brush core. Partial strength reduces the effect, not final pixel brightness. Recover pre-selected-effect appearance only; existing masks, earlier effects and later effects still apply.
- **BR3 — Preservation:** source/master RGB16, alpha16, matting guides, background and framing stay unchanged. Existing categorical protection/locks remain absolute, including nonzero partial-alpha samples. Reducing upstream Shadow fade can legitimately change downstream spatial highlight weighting; keep downstream settings/operands unchanged and recompute through the existing pipeline.
- **BR4 — Geometry:** reuse native `support` stroke and rectangle shapes with existing coordinate/radius/feather validation. Per shape set reduction `amount` in [0,1]. Use stable shape IDs. Add, select, remove, clear and adjust saved/draft shapes; rectangles and numeric controls provide keyboard alternatives. No pressure, airbrush accumulation, arbitrary splines or new segmentation.
- **BR5 — Combination:** let each canonical support field be `S_i` (uint16/65535), and shape reduction be `a_i`. Save `R16 = round(65535 * max_i(a_i*S_i))`; empty list is zero. Repeated identical strokes and order changes do not build up reduction. Retain the existing feather profile; do not silently modify shared guide rasterization. Feather stays inside the authored boundary; a feather wider than a narrow stroke may never reach full strength, which must be visible in the map and instructions.
- **BR6 — Rendering:** for spatial fade, `q_new = q_existing * (1 - R16/65535)` before the existing background blend. For Shadow fade multiply its current exposure-stop weight by that factor before `exp2`; do not interpolate a previously darkened RGB result. Apply once, with exact zero/full endpoints. Missing/zero reduction uses the existing arithmetic path, preserving legacy bytes. Alpha is eligibility, never another multiplier on reduction.
- **BR7 — Recovery:** Apply replaces the selected saved reduction snapshot. Clear removes its reduction through an explicit new revision; effect OFF retains operands. Existing amount-only, shape/area replacement and background changes retain reduction unless explicitly replaced. Same-master alpha repair retains geometry but observes the existing stale/rebuild contract. A reduction-only edit cannot clear unrelated stale state or serve as an implicit alpha rebuild.
- **BR8 — Inspection:** show selected target, saved versus unapplied reduction, reduction coverage and a read-only **Compare reduction OFF** view. This comparison restores only the selected fade's original contribution; it does not turn the fade off. Existing Fade OFF/BASE comparisons remain distinct. All comparison routes retain the same native crop, source identity and current saved state.
- **BR9 — Save safety:** brush/numeric edits affect drafts only. Apply binds master, base revision, input digest, raw revision-manifest hash and target. The viewer requires `revision_manifest_sha256` and forwards it through the existing under-lock `expected_revision_manifest_sha256` guard; a matching revision name/input digest alone is insufficient. Reduction saves enter the existing strict duplicate-key JSON decoder before any action starts, including nested target/area keys. Apply rejects stale selections, invalid geometry, unsupported targets and incomplete candidates before publication. Existing accepted-base or explicit candidate-comparison rules remain. Late success may clear only the submitted target/version; failed submissions preserve drafts. Target switching retains both drafts; explicit reload resets only its named target. No model execution.

## Saved contract and compatibility proposal

Add `src/blackmask/fade_reduction.py` as the shared domain owner. Proposed interfaces:

```python
def rasterize_fade_reduction(area: dict[str, Any], developed_id: str,
                            width: int, height: int) -> np.ndarray: ...
def read_fade_reduction(project: Path, directory: Path, manifest: dict[str, Any],
                        effect: str, alpha: np.ndarray) -> np.ndarray | None: ...
```

The reduction document has exactly `schema_version: 1` and `regions`. Each entry has exactly `shape` (an existing support stroke/rectangle including its ID and feather) and `amount`. Validate unique IDs across all entries; reject booleans as numbers, nonfinite/out-of-range values, extra keys and wrong native coordinates. Limit each target to 128 regions and 8192 total stroke points, checked before raster allocation; these are proposed bounded first-version limits, not performance guarantees. Bind native identity/dimensions through the effect record and alpha dependency, not imported paths.

Per affected effect retain the original support/weight and save `reduction16.png` plus `reduction.json` in its existing effect directory. The new effect-record version adds `reduction_sha256`, `reduction_area_sha256` and `reduction_algorithm: "native-support-max-reduction-v1"`. Proposed versions: spatial record 1→2; Shadow fade record 2→3. Keep the existing main effect algorithm unchanged; bind the new reduction algorithm into execution/reuse identity. New readers support legacy versions as zero reduction without rewriting them. Only an explicit reduction edit creates the new record version; once upgraded, clear saves empty geometry/zero field rather than downgrading. Unsupported future versions and unbound/missing/extra reduction assets fail closed, including disabled effects and warmed validation caches.

Recompute and compare the saved reduction raster against its bound authored geometry. All newly generated revisions use the existing content-addressed asset and publication machinery. Record-selected asset inventories must be used consistently in inheritance, cold/warm validation, restore, matting/repair propagation, export/reuse allowlists and resource admission. No direct-file assumption may bypass shared assets.

Extend `SpatialFadeOperands` with an optional `reduction16` operand, defaulting to `None` for legacy callers. Carry it through every constructor/slice in export, native crops, review, viewer and operations. Keep `weight16` as the unreduced geometric field; project geometry validation must still check it against the oval/arcs. Apply reduction through `spatial_fade_amount`, which also feeds series sampling. Shadow fade's reader/selected-render path loads its reduction and passes it into an optional final parameter of `apply_shadow_fade`; existing exposure-only behaviour is unchanged.

Expose validated authored reduction documents in the existing `ReviewServer.snapshot` revision entries as `fade_reduction_areas`, keyed by available effect target. An existing legacy effect receives an empty version-1 reduction document; an absent effect has no entry. Use the same raw revision binding and shared-asset resolution as other saved effect areas. This is local read-state for explicit reload, not a portable recipe or unvalidated file reader.

Proposed exclusive schema-2 effects operation: existing identity/scope/candidate fields plus `fade_reduction: {target, area}`. It requires an existing nonstale saved selected effect and never changes its ON/OFF state. Permit editing a disabled effect only with its saved alpha matching current alpha; do not let a disabled stale dependency become current implicitly. The declared scope covers the union of old and new nonzero reduction regions; using full-native scope is the UI default. A true no-op may reuse only after all saved operands and source identities validate. Include selected target, normalized reduction geometry, raster/dependency bindings and algorithm identity in reuse admission. Do not weaken existing exclusive background/spatial/exposure operations.

Old application versions may reject new effect records. Preserve all old immutable revisions and accepted exports; users reopen new revisions with the updated application or restore a pre-feature revision using compatible tooling. No in-place migration, silent data dropping or promise of old-reader support. Approval of this compatibility policy is part of design approval before implementation.

## Consumers, resources and editable delivery

Canonical owners to update: `effects.py` (admission, identity, inheritance/publication), `spatial_fade.py`, `shadow_fade.py`, `project.py` (semantic/inventory validation), `operations.py` (inheritance and repair), `export.py`, `series_framing.py`, `review.py`, `previews.py`, `viewer.py`, `ui/review.html`, and necessary recipe/read-state exposure. `assets.py` owns generic assets; change it only for an evidenced hard-coded inventory, not speculatively. Keep one reduction helper, not a generic effects framework.

Native editable exports include the actual reduction raster, authored document and record hashes for every saved new-schema effect, even when disabled. Update I17 requested-variant inventory: a flattened export request does not automatically add an editable bundle. An explicitly requested editable delivery must reconstruct independently of the project, using reduction once. Preserve spatial companion bindings, native/add-margins/Match-series differences, partial alpha and transparent output semantics.

Update disk and memory admission before raster allocations/publication, including two bytes per retained reduction sample, scratch needed by canonical rasterization and export stages. Retain existing reserve and image limits; reject excessive geometry/request size through bounded existing request admission before computation. No new cache or model. Pending I19's `_validate_cache_context` resolves revision assets and `_delivery_members`/`_validate_delivery`; preserve that canonical dependency path. Its synthetic cache-clear journey must retain every reduction/geometry/delivery byte and independently reconstruct exports afterward. Reduction operands are required revision assets, never disposable sole copies; do not introduce a separate cache exception list or alter I19's selected parser policy.

## Verification and acceptance

Use independent expected arithmetic, not only round trips through the production helper. Cover zero/one/partial reduction, nonempty protected and affected regions, partial alpha, overlap/order/duplicate invariance, feather limits, real geometry changes and exact legacy identity. Exercise actual public requests and failure-before-publication, shared assets, same-alpha/RGB-lock repair, changed-alpha stale state, OFF/clear/restore, reuse collisions, cold/warm corruption and late UI responses.

Check native whole/crop equivalence, gray/white/black diagnostics, series resampling and transparent/add-margins outputs. Reconstruct requested editable deliveries in a fresh process with the original project unavailable. Test reduction on both stages together and upstream highlight recalculation without asserting unchanged downstream pixels.

Use existing executed-page tests plus an actual offline browser journey for brush, keyboard rectangle, target switching, comparisons, save/reopen and failed Apply. Human photographic review on suitable copies of a flower/bee image must confirm no new halos or cutoffs; it remains separate from numeric tests. This planning request authorizes no photo processing; obtain applicable scope before that evaluation.

## Delivery recommendation

**Two feature increments:** (1) complete spatial-fade reduction, including helper, storage, UI, all render/export consumers, docs and its checks; (2) complete Shadow-fade reduction plus both-target interactions. The first is useful if the second is deferred. Do not split either into a shipping renderer/storage change followed by later safety/export repairs. Internal tasks are not separate release increments. Keep this independent from appearance recipes.

Current primary-source precedent, checked 2026-10-24: [darktable drawn masks](https://darktable-org.github.io/dtdocs/en/darkroom/masking-and-blending/masks/drawn/) documents feathered brush opacity and editable/reusable native shapes. This supports the interaction; the reduction algebra, compatibility and lifecycle above are project-specific proposals, not claims about darktable internals.
