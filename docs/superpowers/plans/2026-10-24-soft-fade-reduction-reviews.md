# Soft fade reduction — planning reviews

Date: 2026-10-24. Scope: [design](../specs/2026-10-24-soft-fade-reduction-design.md) and [implementation plan](2026-10-24-soft-fade-reduction.md), independently reviewed from the appearance-recipes feature. This is planning evidence, not implementation or photographic acceptance.

Latest amendment: **2026-10-25**, recorded below. The 2026-10-24 hashes/reports remain historical evidence for unchanged scope; current hashes are in the amendment.

## Reviewed identities

- Application candidate: clean detached `9b01987581680bbce6d503661f3f997e2d0325b5`, tree `1ac4d7d6f413c8aa28e3d522f7613e10596e6cb0`; inspected in the local I18 diagnostic candidate. Both coordinator and reviewer verified the exact candidate. No remote refresh.
- Final design SHA256: `37ea7ec249ee5e9e4cc105e1f12eee69796702d98f035f2e807a03c605f95f7e`.
- Final implementation-plan SHA256: `e44f29009fcdd4db6754c472e90181873c6f29c9b8174ebde3a2a6903f13ef41`.
- Independent reviewer: `/root/brush_builder_review`, a separate read-only agent. No recursive delegation, source edits, builds, tests, external actions or private-image inspection.

## Design builder check

The reviewer checked `spatial_fade_amount`, `apply_shadow_fade`, canonical support feathering/maximum composition, shared assets, stale alpha, operand slicing, resource accounting and requested editable delivery. Result: **nothing important left**; no material design contradiction found. Two complete effect-specific increments were judged independently useful.

## Coordinator self-review

The completed plan was checked using Superpowers writing-plans' spec coverage, step/interface consistency, review-focus and proportion criteria before independent plan review.

| Requirement | Owning task/verification |
| --- | --- |
| BR1 independent targets; BR9 stale/late response safety | Tasks 4 and 6: target/version/identity draft tests. |
| BR2/BR5/BR6 reduction/feather/math and exact endpoints | Tasks 1 and 5: independent numeric expectations and legacy byte identity. |
| BR3 protected partial-alpha/source preservation | Tasks 1, 2 and 5: nonempty affected/protected fixtures and immutable-source assertions. |
| BR4 geometry editing and manual keyboard path | Tasks 1 and 4: bounded native validation and actual-page/browser journeys. |
| BR7 OFF/clear/repair/restore/reuse | Tasks 2 and 5: versioned assets, alpha dependency and failure-preservation cases. |
| BR8 distinct reduction-OFF comparison | Tasks 3 and 5: bound saved native views and upstream/downstream semantics. |
| Shared consumers, resource admission and independent editable reconstruction | Tasks 2, 3 and 5: schema inventories, crops/series and fresh child reconstruction. |

Self-review correction: explicitly added validated `fade_reduction_areas` to `ReviewServer.snapshot` revision entries and snapshot/reload tests, so saving an editable brush also has a defined reopen path. Confirmed new helper/operand names match across tasks; no generic effects framework, recipe schema expansion or implementation against the older planning checkout is implied.

## Independent implementation-plan review

The same independent reviewer reviewed the complete plan after self-review, verified both final document hashes and rechecked source signatures, snapshot ownership, canonical arithmetic, shared inventories, comparisons and existing test foundations.

Result: **No material issues found in the soft-fade implementation plan.** No correction was required after this review. The reviewer specifically confirmed meaningful tests for independent arithmetic, partial-alpha/protection, causal failures, warm/cold corruption, draft races and project-independent reconstruction.

## Increment decision and remaining boundaries

Use **two increments**: complete spatial reduction first, then complete Shadow reduction with both-target interactions. Each includes controls, persistence, validation, rendering, recovery, requested export and its own acceptance gate. No safety/export work is deferred behind a partially usable feature.

The incremental-plan skill's coherence/dependency/risk criteria were used for this assessment; a separate incremental delivery program was not created. The proposed both-target scope and saved-record compatibility still require design approval before implementation. Reconcile the settled successor of I18 and any I19 work before execution. Native sequential implementation is recommended because tasks share canonical owners; execution choice remains with the user.

Documentation/reference checks verified existing owners/test foundations and relative links, with no product imports or application tests. No product code was changed. Computational, browser and human photographic acceptance remain future, separately reported evidence.

## 2026-10-25 scope clarification and current-work renewal

The user answered the target question with **“most flexible.”** Both independent brush targets remain in scope, as already planned; this is not an implementation grant. The two-increment recommendation is unchanged.

Current integration context was refreshed against pending I19 candidate `00b173ef5e90cafbf09a758e0a6db9a503d4a893c141ef6e096a73b7a720d715`, on I18 base `9b01987581680bbce6d503661f3f997e2d0325b5`. Coordinator verified all 100 recorded file bodies, sizes and modes against its candidate map with zero mismatches; the core fade/effects/render/viewer/editor files equal I18. The I19 cache/parser decision remains pending, so this is an inspected integration target, not accepted delivery or borrowed authority.

Self-review added the concrete dependency on I19's canonical `_validate_cache_context` → revision/delivery validation and a synthetic cache-clear journey retaining permanent reduction, geometry and export bytes with independent reconstruction. No parser-policy change or cache exception list was added.

The original brush reviewer independently reviewed this changed integration scope at design hash `2dd40147083ceb677f5a01cd859d0b85883aacbf08d29f962f5481a269456ace` and plan hash `7e8b0bee2e2323216a47609ba4020afe58daad1368a2b32c6937bcd09795935e`. Result: **No material findings in the cache-integration update.** The reviewer confirmed `operations.py:2447–2542` delegates permanent delivery validation to the canonical owners and cache removal remains confined to inspected predictions; it did not independently rehash the complete candidate map. Unchanged arithmetic/UI review was reused.

Coordinator clarified task ordering afterward: Task2 owns admission/dependency preservation; Task3 owns the combined cache-clear/export test after export consumers exist; Task5 repeats it with both targets. This changes no acceptance outcome and retains the targeted review's observation that Task3 supplies the necessary export functionality.

Current design SHA256: `2dd40147083ceb677f5a01cd859d0b85883aacbf08d29f962f5481a269456ace`.

Current plan SHA256: `396eaf0e6744bbcf9facb762c147001f785e42bdcda8f6b334ada21f992b7bd5`.

No material planning issue remains. Two increments are still the useful boundary. Only documentation/source inspection was performed; application checks and photographic acceptance remain future work.

## 2026-10-25 separate Ponytail pass

Explicitly requested by the user. Independent read-only reviewer `/root/ponytail_brush_plan` applied Ponytail Review to this plan/spec and their connected application owners, separately from recipes. Expected load: one local photographer using native-resolution photos. No recursive delegation, product edits, application tests, builds, private-photo inspection or external actions occurred.

Input design SHA256: `2dd40147083ceb677f5a01cd859d0b85883aacbf08d29f962f5481a269456ace`.

Input plan SHA256: `396eaf0e6744bbcf9facb762c147001f785e42bdcda8f6b334ada21f992b7bd5`.

**What this change does:** It adds separately editable reduction areas for Fade into background and Shadow fade. Each increment includes persistence, rendering, controls, comparisons and editable exports.

### Should fix — both corrected in the plan

1. **Bind Apply to the exact saved revision reviewed.**
   - **What this is:** Apply replaces a saved reduction snapshot; preview already requires its raw revision-manifest hash.
   - **Problem:** The listed Apply identities omitted that hash. A valid replacement of the same named revision's reduction assets/manifest could retain the root recipe/guides and input digest, admitting an old draft against changed saved content.
   - **Fix:** Require the captured `revision_manifest_sha256` in the viewer envelope and forward it to the existing under-lock `expected_revision_manifest_sha256` guard. Test same-name changed-manifest rejection and preservation of state/drafts.
   - **If skipped:** Reduction saves have weaker stale-selection protection than existing spatial-fade saves.

2. **Reject duplicate keys on reduction saves.**
   - **What this is:** New reduction saves use `/api/action`, while their preview has explicitly strict JSON decoding.
   - **Problem:** The current action decoder reparses effects strictly only when `spatial_fade` is present. Duplicate `target` or `area` keys would otherwise silently retain their last value before dictionary validation, potentially selecting the other fade.
   - **Fix:** Include `fade_reduction` in the existing strict-decoder predicate. Test raw HTTP duplicate target/area keys and require rejection before an action starts.
   - **If skipped:** Ambiguous save requests can choose a different effect even though equivalent preview input rejects.

Evidence at I18 `9b01987581680bbce6d503661f3f997e2d0325b5`: `operations.py:75–80` hashes root recipe/guides; `viewer.py:476–477,695–710` admits/forwards raw revision hashes only for spatial effects; `operations.py:287–302` owns the reusable under-lock guard; `viewer.py:955–971` selects strict action decoding. The coordinator inspected these owners before accepting either finding. This pass did not refresh remote refs or certify a settled I19 result.

Both corrections are now explicit in BR9 and Task2, including viewer/test ownership and real save-route regressions. Task4 captures the draft's raw hash rather than silently taking a newer one; Task5 repeats the safeguards for Shadow. No second locking, decoder or rendering framework was introduced. These are bounded plan corrections under the earlier request to review and fix each plan, not product implementation or automatic acceptance of unverified reviewer suggestions.

The reviewer independently renewed only these changed scopes and confirmed both findings closed, both final hashes matched, and no directly caused contradictions. Unchanged arithmetic, asset, export, resource and increment assessments remain applicable.

Final design SHA256: `91e342211c313c59b78c08425224c3fb65b5aa02f315598e72e6b6b1bae93aaf`.

Final plan SHA256: `62174a97d9b663e8dd059ad1ec8135b1f5a6a94b03b7cdd2015ce979b5b3e8b3`.

Freshness correction: the later I19 handoff at `2026-10-25T05:44:18.549160+00:00` resolves its native/stored+deflate compatibility choice and releases amended implementation. Earlier “decision pending” statements above are historical. Final I19 verification/settlement is still pending; this plan must reconcile its settled successor before execution and gains no authority from that handoff.

**Verdict: Planning-level pass. No material improvements recommended.** Keep two increments: complete spatial reduction, then complete Shadow reduction. Further splitting would separate working controls from their safety obligations. Documentation link/fence/whitespace checks passed; product behaviour was not exercised.

**Not checked:** Implementation, runtime tests, native latency/peak memory, browser usability, photographic acceptance or final I19 integration. Required future implementation/design gates remain unchanged.

## 2026-10-25 additional fresh independent review

The user explicitly requested another independent review of each plan and appropriate fixes. Fresh reviewer `/root/brush_independent_renewal` received only this feature's plan/spec, current source locations, constraints and acceptance questions. It did not read earlier review reports/verdicts and did not review recipes. This was a separate read-only general plan review, not another Ponytail invocation.

Reviewed input design SHA256: `91e342211c313c59b78c08425224c3fb65b5aa02f315598e72e6b6b1bae93aaf`.

Reviewed input plan SHA256: `62174a97d9b663e8dd059ad1ec8135b1f5a6a94b03b7cdd2015ce979b5b3e8b3`.

Both reviewer and coordinator verified the application checkout clean at `ed86ca84478846271c9f4da09c02ddbe5a38d2bd`, tree `ead610dced94b17aa6718da8e95405be0300135f`. This includes I19 and its later local native-review staging correction. Provider/publication status was read from the current handoff only, not refreshed remotely; earlier pending-parser statements in this history no longer describe the latest local source.

The reviewer read the complete plan/spec and traced geometry/rasterization, effect admission, stale-alpha handling, inheritance, shared assets, saved rendering, previews, requested delivery, reconstruction tests and I19 permanent-context validation. It returned **“No material improvements recommended.”** The two increments remain justified by their different arithmetic and downstream interactions, with complete persistence/UI/recovery/export obligations inside each.

One nonblocking locator correction was reported: Task2 named `_run_action`, which does not exist. The coordinator verified `ReviewServer.execute` at current `viewer.py:503` and its forwarding at `695–710`, then corrected the plan to name `ReviewServer.start_action` and `ReviewServer.execute`. No behavior, interface contract or test expectation changed. Both documents' baseline paragraphs were refreshed to the exact reviewed local source; no broader re-review was needed for these factual corrections.

Current primary documentation was also checked: Python's default JSON decoder retains the last duplicate key, so the already-planned strict `object_pairs_hook` path remains necessary. [Python 3.12 JSON documentation](https://docs.python.org/3.12/library/json.html#repeated-names-within-an-object). This check introduced no new scope or dependency.

Final design SHA256: `e78cd6ae8fb8c3920c3efa7a6ee4f9cdf30704074ab8d9a2ac1132f9459ef767`.

Final plan SHA256: `75110d6602ed733eab988af25122d0eef7417bb7a41b14e014c7802cda6ee500`.

Result: no unresolved material finding; retain two increments. Only planning documents were edited. Documentation links/anchors, fences, whitespace and recorded identities were checked after the edits. Product imports, runtime tests, builds, resource measurements, browser/photographic acceptance and external actions were not performed. Proposed application checks remain future verification.
