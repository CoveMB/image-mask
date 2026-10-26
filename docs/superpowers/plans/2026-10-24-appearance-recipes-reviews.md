# Named appearance recipes — planning reviews

Publication status (2026-10-26): reviewed proposal only; implementation is not authorized or claimed. Dated baseline inspection and proposed commands below must be reconciled in a later authorized preparation.

Date: 2026-10-24. Scope: [design](../specs/2026-10-24-appearance-recipes-design.md) and [implementation plan](2026-10-24-appearance-recipes.md), independently reviewed from the brush feature. This is planning evidence, not implementation/runtime or photographic acceptance.

Latest amendment: **2026-10-25**, recorded below. It expands the scope and supersedes the historical one-increment recommendation. Earlier findings and valid unaffected review remain retained; current hashes are in the amendment.

## Reviewed identities

- Application candidate: clean detached `9b01987581680bbce6d503661f3f997e2d0325b5`, tree `1ac4d7d6f413c8aa28e3d522f7613e10596e6cb0`; independently confirmed against the local I18 candidate. No remote refresh.
- Final design SHA256: `0208c67aa814544ec0f3d4091e094b5295bbfe5393161139a7396de216530160`.
- Final implementation-plan SHA256: `69d36d3ece829f63b94707e88fc566f61a38b0a1123691d3685acc2b414d4e41`.
- Independent reviewer: `/root/recipes_builder_review`, separate from the brush reviewer and coordinator. Read-only; no recursive delegation, builds, tests, source mutations, remote queries or private-photo reads.

## Independent design builder check and fixes

| Finding | Source evidence and impact | Resolution |
| --- | --- | --- |
| Loaded sections could be lost/stale after the first Apply | `review.html` scalar identity checks at 1614–1635/1670–1688 bind exposure/fade to the old revision; spatial has whole-draft identity; `loadAuthoring` resets shading scalars around 981–984. Merely loading several forms does not provide a usable sequential workflow. | Persist the validated recipe preview, preserve unrelated dirty scalar values/versions, explicitly reload each remaining section against the current revision, and test a full multi-section Apply sequence. No silent geometry rebase or automatic multi-effect Apply. |
| Integer width rounding contradicted existing controls | `effects.validate_shading` accepts positive float width; `spatial_fade.validate_spatial_fade` accepts transition values starting at 0.5. Rounding alters legitimate saved values. | Preserve finite fractional widths, pass native target dimensions into conversion and reject unrepresentable target values without clamping. Add equal-bounds0.5/fractional-shading and differently-sized-subject tests. |

Coordinator inspected the relevant current source and incorporated both fixes into the design before completing the implementation plan.

## Coordinator self-review

Superpowers writing-plans review mapped portable scope/limits/reference sanitation to Task 1; selected saved-revision/asset identity and privacy to Task 2; authenticated bounded read-only transport to Task 3; selective loading, dirty-state preservation and sequential application to Task 4. The settled gate covers offline browser/manual use, distribution contents and required checks.

Self-review made the conversion result explicit (`sections` plus `unavailable`), passed native dimensions, specified no-matte target identity, exact RGB8/reference limits and nesting8, and excluded current-only gallery rendering. It also verified that proposed source/render/API function owners and current test foundations exist. No product code/test was run or changed.

## Independent implementation-plan review and fix

Reviewed input hashes before correction:

- Design `6c46551f415392470658a2b25165a25919adaf4e5e08a64dda1bccca3fa59463`.
- Plan `dec58ab4ee29367c1fc7de60f27c7b087f002a45e541bba38148af4b76881a88`.

**Material finding: Task 4 assumed independent area identity guards already existed.** Exposure/Shadow area arrays and dirty flags are defined at `review.html:591,593`; stale checks use scalar identity at 1614–1635, while 1677/1692 submit retained area geometry. `exposure.rasterize_effect_area` binds supplied geometry to the current developed source. Thus scalar reload on revision B could admit an area/protection draft authored on A.

Accepted and fixed in both spec and Task 4. Add independent local exposure/Shadow area identity/version bindings, capture all area/protection edits, reject stale replace-area Apply even after scalar reload, and preserve valid amount-only use of current saved areas without consuming dirty geometry. Clear/rebind only by explicit recovery or matching submitted publication; late completion cannot clear newer edits. Spatial's existing combined draft must reject scalar imports while stale rather than changing its identity. Values remain in the recipe preview until explicit geometry recovery.

The new executed-page regression pins the actual failure: edit area on A → unrelated Apply creates B → reload recipe scalars → old area replacement still rejects; amount-only use of B's saved area remains usable. It also covers stale spatial geometry and late area completion. Coordinator verified the source claim before applying the fix.

## Targeted independent renewal

Only changed Task 4 geometry-binding semantics and their spec/test implications were re-reviewed; unchanged codec/render/endpoint coverage was retained. Reviewer verified the final hashes above and returned: **No material findings in the targeted renewal. The area-binding gap is closed at the planning level.** No narrowly caused contradiction remained.

## Increment decision and remaining boundaries

Use **one increment** with internal codec, saved-source, endpoint and UI tasks. Safe selective reuse and sequential application are one user journey; shipping without the destination identity safeguards would be incomplete. The reviewer confirmed this recommendation after all corrections. Geometry transfer, a catalog and one-click application remain excluded and would require reassessment if requested.

The incremental-plan skill's coherence/dependency/risk criteria were applied; no separate incremental delivery program was created. Settings/reference-only scope remains a proposed default for user approval. Native sequential implementation is recommended; reconcile the settled I18 successor/I19 changes and choose execution before implementation.

Documentation/reference checks are distinct from runtime tests and human acceptance. The plans are reviewed, but no application tests, actual browser journey, private thumbnail rendering or project mutation was performed for this task.

## 2026-10-25 flexibility and resilience amendment

The user answered the settings-versus-layout question with **“most flexible and resilient.”** The revised proposal keeps settings-only reuse and adds optional editable oval/arc transfer, with separate placement preview, explicit Add/Replace, target-local protection/reduction preservation and guarded Undo. Detailed conversion choices remain proposed; implementation is not authorized.

Latest-work refresh: coordinator verified pending I19's recorded 100-body candidate `00b173ef5e90cafbf09a758e0a6db9a503d4a893c141ef6e096a73b7a720d715` on I18 base9b, with zero body/size/mode mismatches. Core spatial/effects/render/viewer/editor files are unchanged. I19 remains a partial candidate awaiting its cache/parser decision; its canonical permanent-data validation informs the integration checks without borrowing its execution authority.

### Builder exploration and self-review

The independent recipe reviewer examined native shapes, maximum composition, switch semantics, spatial identity and recovery. Its material recommendations were incorporated before final review:

- One v2 `spatial_layout` representation, mutually exclusive with scalar spatial defaults/shading; no conflicting simultaneous geometries.
- Half-open subject midpoint/max-side uniform scaling; preserve signed bend, rotation, side and fractional dimensions. No axis stretching, source IDs or implicit fitting.
- Add preserves target group/master/oval/highlights; imported enabled state respects the source group. Replace is explicit, retains master/protection and uses ordinary Apply. Source master state never transfers.
- Separate outline preview; existing saved-only maps cannot stand in for imported appearance. Existing reset is not undo because it drops drafts and clears auxiliary controls.
- Exact guarded one-step Undo, fresh IDs, count limits, stale-draft rejection and preservation of future brush operands.
- No new transformation toolbox without evidence. Explicit settings-only fallback derives scalar defaults from the portable layout without access to its source project.

Coordinator mapped these to Tasks5–6 and their tests, preserved all prior v1 draft/identity fixes, specified exact portable/endpoint fields and supplied independent numeric examples. Settings-only fallback leaves the original file unchanged and requires explicit source-shape and target-shape selection; placement failure never authorizes silent geometry modification.

### Independent updated-plan review and correction

The reviewer verified expanded candidate hashes: design `ea68ebb1510b3bdfe06751cbab13398877d44fc53d7b809b696b115c4a0b58ef`, plan `0626e5ce205362d85e69c6a631309481ec6e100ca0836a91519e9db3d272f95a`.

**One material finding:** floating endpoint handling was specified for layout but omitted from v1 transition widths. JSON roundtrip of `0.5/49`, multiplied by49, produces `0.49999999999999994`; the native minimum is0.5. Layout transfer and its settings-only fallback could disagree on a valid value.

Coordinator independently reproduced the arithmetic using only standard-library math/JSON, with no product import or application test. The same false strict rejection appeared at subject sizes49,98,103,107; observed deficits were within the documented operation-term budget. The independent centre example also returned `(170,70)` and transition15 as planned. These are planning arithmetic checks, not runtime feature evidence.

Fixed in spec and Task1: introduce the common converter-only closed-endpoint rule in increment1, reuse it in v2 and fallback, keep interior values unchanged, reject larger violations and leave shading's strictly positive boundary/native validators unchanged. Add the size49 causal regression, independent beyond-budget fixtures and equal transition-result assertions across the three paths.

### Targeted renewal and current decision

Reviewer checked only the affected shared correction and test mapping at the final hashes below. Result: **Finding closed. No material findings in this targeted renewal.** No narrowly caused contradiction was found; unchanged Add/Replace, protection, preview, Undo, privacy and identity review remains applicable.

Current design SHA256: `430989a909e7261b082821e2b6cc87ce2dc5e27d9e1b5a7882969a028783bbd8`.

Current plan SHA256: `319482bdbcd29bb9a014a31836cf631a8a3b54c087f0f063a6e217c712985714`.

Use **two increments**: complete v1 settings/reference reuse, then optional v2 editable layout transfer with full placement/merge/recovery/compatibility checks. This supersedes the earlier one-increment assessment because the user expanded the scope. The reviewer confirmed both outcomes are independently useful and their safety/testing belongs within each increment. This remains a Superpowers-plan sizing assessment using the incremental-plan criteria, not an unsolicited separate delivery program.

All review work was read-only; no application tests/builds, product edits, image rendering, private-photo inspection or external mutation occurred. Current source/layout conversion details still require design approval and reconciliation with the settled work before implementation.

## 2026-10-25 separate Ponytail pass

Explicitly requested by the user. Independent read-only reviewer `/root/ponytail_recipes_plan` applied Ponytail Review to this plan/spec and their connected application owners, separately from the brush plan. Expected load: one local photographer using native-resolution photos. No recursive delegation, product edits, application tests, builds, private-photo inspection or external actions occurred.

Input design SHA256: `430989a909e7261b082821e2b6cc87ce2dc5e27d9e1b5a7882969a028783bbd8`.

Input plan SHA256: `319482bdbcd29bb9a014a31836cf631a8a3b54c087f0f063a6e217c712985714`.

**What this change does:** It saves selected appearance settings and an optional reference thumbnail. Its second increment adds optional editable layout placement, Add/Replace and Undo.

### Must fix — corrected in the plan

1. **Preserve fractional background settings through Apply.**
   - **What this is:** Recipes accept canonical background settings and load them into existing controls.
   - **Problem:** The backend permits `variation: 0.125`, but existing Apply requires a whole percentage. Loading 12.5% therefore rejects, while the saved-load rounding path changes it to 13%.
   - **Fix:** Preserve fractional numeric percentages, accept finite bounded values and stop programmatic slider synchronization/reload from rounding them. Add a shipped-page and actual persistence round trip for `0.125`, plus a real browser check of numeric/slider behaviour.
   - **If skipped:** A supported recipe value is rejected or silently changed during the main reuse journey.

Evidence at I18 `9b01987581680bbce6d503661f3f997e2d0325b5`: `background.py:22–32` permits finite variation in `[0,1]`; `ui/review.html:398–399` sets whole-percent steps, `1012–1013` rounds saved load and synchronizes the range, `1195` rounds the saved status, and `1717–1720` requires an integer percentage. The reviewer confirmed the relevant background/editor bodies also match the inspected I19 checkout; the coordinator inspected the validators and connected controls before accepting the finding. No settled I19 result is inferred.

The spec and Task4 now keep the numeric input authoritative, permit fractional entry, remove integer-only rejection and misleading rounding, and retain canonical backend validation and the ordinary Apply path. Actual user slider edits may still select stepped values. The regression includes saved persistence, colour-only edits, range synchronization, reload, valid endpoints and invalid input; page stubs are explicitly insufficient for persistence/browser evidence.

The reviewer independently renewed only this correction and its directly affected contract/tests, verified both final hashes, and confirmed the finding closed with no directly caused contradictions. Unchanged codec, identity, layout, privacy, recovery and increment assessments remain applicable.

Final design SHA256: `d1b753112a392cd7047c1c4c5556ae24c0ebf60f752ad60dd515797ea6497bd6`.

Final plan SHA256: `064bd93cad70974f4d7b9d89900c2cba0137b50fe1022694cbdbef184233ebe0`.

Freshness correction: the later I19 handoff at `2026-10-25T05:44:18.549160+00:00` resolves its native/stored+deflate compatibility choice and releases amended implementation. Earlier “decision pending” statements above are historical. Final verification/settlement is still pending; reconcile the settled successor before execution without borrowing that handoff's authority.

**Verdict: Planning-level pass. No material improvements recommended.** Keep two increments: complete settings/reference reuse, then optional editable layout transfer. Strict validation, shared rendering/bounds, draft bindings and explicit placement address concrete risks; no additional catalog, generic framework or rendering engine is justified. Documentation link/fence/whitespace checks passed; product behaviour was not exercised.

**Not checked:** Implementation, runtime tests, browser behaviour, photographic acceptance or final I19 integration. Required future implementation/design gates remain unchanged.

## 2026-10-25 additional fresh independent review

The user explicitly requested another independent review of each plan and appropriate fixes. Fresh reviewer `/root/recipes_independent_renewal` received only this feature's plan/spec, current source locations, constraints and acceptance questions. It did not read earlier review reports/verdicts and did not review the brush plan. This was a separate read-only general plan review, not another Ponytail invocation.

Reviewed input design SHA256: `d1b753112a392cd7047c1c4c5556ae24c0ebf60f752ad60dd515797ea6497bd6`.

Reviewed input plan SHA256: `064bd93cad70974f4d7b9d89900c2cba0137b50fe1022694cbdbef184233ebe0`.

Both reviewer and coordinator verified the application checkout clean at `ed86ca84478846271c9f4da09c02ddbe5a38d2bd`, tree `ead610dced94b17aa6718da8e95405be0300135f`. This includes I19 and its later local native-review staging correction. Provider/publication status was read from the current handoff only, not refreshed remotely; earlier pending-parser statements in this history no longer describe the latest local source.

The reviewer read the complete plan/spec and inspected current validators, rendering, subject bounds, viewer endpoints, draft/completion handlers, tests and maintained contracts. It specifically checked sequential-Apply resets, strict native geometry limits, Add's group-switch semantics and exact guarded Undo. It returned **“No material improvements recommended.”** No behavioral correction was required.

The coordinator refreshed the two documents' baseline paragraphs to the reviewed local source. This changes no feature behavior, interface, compatibility decision or test expectation. The two-increment recommendation remains: complete settings/reference reuse first, then the distinct placement/merge/compatibility/recovery workflow for editable layouts.

Current primary documentation was checked for the existing defensive choices: Python JSON needs explicit duplicate/nonfinite/resource handling; Pillow opening is lazy and `verify()` alone does not decode pixels. The already-planned bounded decoding/validation remains necessary. [Python 3.12 JSON documentation](https://docs.python.org/3.12/library/json.html), [Pillow Image documentation](https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.verify). No new dependency or feature was added.

Final design SHA256: `1ed85c4ebb9426fd705e4d216f3d18c6689eaaa0b7fdd4027782098ea8c0f1d1`.

Final plan SHA256: `42f647f5caf4f04225e7133f85e3902e8c0eff74e363cef695f556b650042fab`.

Result: no unresolved material finding; retain two increments. Only planning documents were edited. Documentation links/anchors, fences, whitespace and recorded identities were checked after the edits. Product imports, runtime tests, builds, private-photo access, browser/photographic acceptance and external actions were not performed. Planned application checks remain future verification.
