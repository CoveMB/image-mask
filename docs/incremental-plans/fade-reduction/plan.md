# Fade reduction incremental plan

Status: FR1 accepted at Gate 3 by the orchestrator under user delegation. FR2 preparation is authorized after the FR1 commit; implementation awaits its Gate 2 decision. Created: 2026-10-27.

## Purpose and context

Deliver independently editable, soft reduction of Fade into background and Shadow fade. Preserve source RGB16, alpha16, guides, categorical locks, background, framing, unrelated settings and recovery. This is one feature with two independently useful contributions; storage, rendering, controls, tests and documentation ship together within each increment.

Primary source: [Soft Fade Reduction Implementation Plan](../../superpowers/plans/2026-10-24-soft-fade-reduction.md), Tasks 1–6 and settled gate. Supporting [design](../../superpowers/specs/2026-10-24-soft-fade-reduction-design.md), BR1–BR9, and [historical reviews](../../superpowers/plans/2026-10-24-soft-fade-reduction-reviews.md) clarify the source; historical approval/status does not grant authority. Original sources remain unchanged.

Preparation baseline inspected on 2026-10-27: initially clean `main`, HEAD `162fa8b5125a00a1453246a4ddb2a50e45af7a94`; subsequently clean `fade-reduction` at the same HEAD, created by the owning orchestrator. Local `origin/main` matched; this owner did not fetch. FR1 now has an implemented and independently reviewed candidate preserving I19 permanent-context validation, shared revision assets and requested deliveries. Current candidate and executed evidence are recorded in the handoff; the actual Gate 3 decision below accepts FR1.

Source SHA-256 identities:

| Source | SHA-256 |
| --- | --- |
| Primary plan | `88ac176fd101af241e006f162e779b98d904494eed0b31286f786d48b0bc9d08` |
| Design | `784e53d45f0b22aead0668b291cc1575341cee2356af3db3dd470d3bf97530ae` |
| Historical reviews | `6dc63a44fb2285b572d4b548d9a90af2ef5f626d20709de437c9e11481b4b5e2` |

Supplementary QA: **on**, integrated [qa-plan.md](qa-plan.md). The plan, QA and [handoff](handoff.md) form one review candidate, with one set of three distinct plan reports.

**Active Preapproved orchestration**, not a proposed export: the actual human message in owning chat `01a17ba9-9112-7a52-b8da-547737b178e3`, turn `01a17ba9-9c90-7f93-ac2d-9eb16b5fa21c`, message `01a17ba9-9f58-7303-b9f5-57a66c05db20`, was read directly. The human requested sequential feature chats, incremental conversion in preapproval mode, implementation/reviews including Ponytail, commits, pushes, fixes and final GitHub MRs, delegating routine approvals to that orchestrator. This supersedes historical preparation-only authority for this selected work. Gate 2 and Gate 3 still require the orchestrator's actual candidate evaluation and recorded decision. It is not human photographic acceptance, merge/deployment authority, model/download authority, permission for private-photo transfer, or permission to delete evidence. New material product/compatibility choices go through the orchestrator to the human.

Non-goals: appearance recipes, Background light, changed source development, alpha editing, changed feather semantics, model execution, new dependencies/cache/frameworks, pressure/airbrush accumulation, combined-target saves, and in-place migration. Keep existing dependency pins. Names on every authored/generated surface describe domain responsibility or behavior; delivery IDs belong only in work tracking/provenance. Preserve source/history, legitimate domain names and existing public/persisted names. Select concrete names before Gate 2; architecture review checks actual artifacts, including docs.

Evidence: reuse Git baseline, source files, native review records and exact command results. Owned raw logs, actual packages and synthetic projects occupy about 10.9 MB in ignored `local/evaluations/fade-reduction/`, created after collision/symlink checks. No project warning threshold was found. Keep this evidence for Gate 3, FR2 and publication; the handoff records retention decisions and final sizes. Preserve unique inputs, failed fixtures and active consumers; no deletion is authorized.

## Parts and increments

| Part | Purpose | Ordered increments |
| --- | --- | --- |
| Independent fade reduction | Complete each user capability through its full lifecycle | FR1 — Fade into background reduction; FR2 — Shadow fade reduction |

FR2 depends on accepted FR1. Internal source tasks remain implementation steps, not shipping increments. Shared files do not justify combining the two independent outcomes. One owner chat implements both sequentially under the explicit feature-chat assignment; no parallel writer or new controller is needed.

## Source coverage

| Source locator | Obligation | Owner / QA | Disposition |
| --- | --- | --- | --- |
| BR1, BR7, BR9; Tasks 4, 6 | Independent drafts, one target per Apply, explicit clear/reload, late-response/stale guards | FR1 spatial; FR2 both; Q5, Q8 | FR1 implemented; shipped-page and actual browser proof recorded. Both-target FR2 pending. |
| BR2, BR5, BR6; Tasks 1, 5 | Maximum quantized reduction, inward feather, spatial q factor and Shadow exposure-stop factor, exact zero/full paths | FR1 Q1–Q2; FR2 Q7 | FR1 independent geometry/q oracles passed; Shadow pending. |
| BR3; global constraints | RGB/alpha/locks and unrelated operand preservation; downstream highlights may recompute after Shadow | Both; Q2–Q4, Q7–Q8 | FR1 protection-sensitive and lifecycle checks passed; Shadow downstream proof pending. |
| BR4; geometry/saved contract | Stable support stroke/rectangle IDs; exact keys; 128 regions/8192 points before allocation; keyboard path | FR1 Q1, Q5; FR2 reuse | FR1 implemented; bounds, geometry, page and actual keyboard/brush proof recorded. |
| Saved contract; Tasks 2, 5 | Spatial 1→2, Shadow 2→3 only on explicit edit; legacy read/no rewrite; clear stays upgraded; record-selected inventory and geometry replay | FR1 Q3; FR2 Q7 | Spatial compatibility approved and implemented; lifecycle/tamper checks passed, bounded replay repair reviewed. Shadow pending. |
| BR7/BR9; Tasks 2, 5 | Exclusive operation, saved nonstale selected effect, disabled alpha match, old/new scope union, raw hash binding, duplicate-key rejection, reuse and transactional failure | Both; Q3–Q4 | FR1 application/HTTP/writer-lock/failure checks passed; Shadow branches pending. |
| BR8; Tasks 3, 5 | Bound native coverage and reduction-OFF; effect OFF distinct; retained earlier/later effects | Both; Q4, Q6–Q8 | FR1 implemented and exercised through HTTP, page and actual browser; Shadow pending. |
| Consumers/resources/delivery; Tasks 2–3, 5 | Every operand constructor/slice; crop/series/margins/transparent rendering; editable-only inventory; independent reconstruction; resource admission | Both; Q6–Q7 | FR1 source trace and independent crop/series/delivery checks passed; both-target FR2 pending. |
| I19 integration; Tasks 3, 5 | Cache clear preserves permanent reduction/geometry/delivery bytes and subsequent reconstruction | FR1 then FR2 combined; Q6–Q8 | FR1 frozen-delivery/cache-clear/disconnected-child journey passed; FR2 repeats with both targets. |
| Settled gate; verification/acceptance | Full deterministic checks, actual packages, actual offline browser, distinct human photo acceptance | Each increment Q9; human Q10 | FR1 repaired suite: 2230 passed, 3 explicit model-integration skips, exit 0. Static/package/browser proof complete; Q10 remains pending and no private-photo use authorized. |
| Global constraints and delivery recommendation | No scope spill; preserve source/history/pins; two complete increments | Global; Q9 | Enforced through all reviews |

## Increment cards

### FR1 — Fade into background reduction

- **Outcome:** a photographer can draw, inspect, save, reopen and remove spatial-fade reduction, retaining precision, protections and independently editable export operands. Complete source Tasks 1–4 together.
- **Exclusions:** no Shadow target controls/arithmetic/schema change, recipes or Background light. No generic framework or recipe schema expansion.
- **Predecessor:** current settled application at the baseline above; no feature predecessor. Exact first preparation is in the handoff.
- **Owners/interfaces:** new `fade_reduction.py` for geometry/read binding; `SpatialFadeOperands.reduction16=None`, `spatial_fade_files(record)`, `spatial_fade_amount`; existing effects, project, operations, export, series, review, previews, viewer and shipped page; their application tests and four canonical docs. No generic `assets.py`/`recipe.py` changes absent a concrete necessity and regression.
- **QA:** Q1–Q6 and Q9. Feature owner owns synthetic reduction save → requested editable export/companion creation and freeze → cache inspect/clear → unchanged permanent/delivered hashes → disconnected reconstruction of those retained deliveries, including native, margins and series identities. Exact numeric and failure expectations are in QA.
- **Review focus:** reduction is applied once after canonical spatial weighting; saved unreduced geometry stays valid. Closed inventory and replay must reject rehashed corruption even OFF/warm. The same frozen candidate includes UI and all exports, avoiding an unsafe intermediate state.
- **Safe state/compatibility:** complete spatial reduction is useful without FR2. Legacy spatial schema 1 remains readable without rewriting; explicit edits create schema 2 and two new assets. Older applications may reject those revisions; immutable older revisions/accepted exports remain recoverable. Clear keeps schema 2 and zero/empty operands. No old-reader support or in-place migration promise.
- **Acceptance:** source-derived q example `[0.6,0,0.6*(1-32768/65535),0]`; exact missing/zero parity, an additional protection-sensitive sample with alpha=32768, W=39321 and R=32768 whose protected q remains zero while its unprotected control is nonzero, bounded geometry, save failures leaving state unchanged, independent export replay and native crop/series consistency. Q5 and actual browser demonstrate draft transitions; automation does not establish human photographic quality.
- **Recovery:** failed validation/admission publishes nothing; staged interruption retains prior accepted work and visible recovery evidence. Explicit restore selects older saved inputs without changing acceptance. Do not delete new/old revisions to recover. Code rollback alone does not make new-schema revisions readable to old software.
- **Gates/reviews:** concrete FR1 Gate 2 approved as recorded below. All three independent fresh-context read-only result reports (requirements, architecture/simplicity, verification) are complete. Architecture included the expressly requested bounded `ponytail:ponytail-review` against baseline-to-FR1; its warm-replay finding was fixed and closed by targeted architecture and verification renewals. No material finding remains. The repaired full suite passed; the orchestrator accepted the returned candidate/evidence at Gate 3 below. No additional generic layer or external paid review.
- **Future impact:** FR2 reuses bounded helper, storage contract, target-local drafts and comparison endpoint; it must separately validate Shadow exponent math and downstream highlights. Reconcile accepted FR1 bytes and checks before FR2 preparation.

### FR2 — Shadow fade reduction

- **Outcome:** independently reduce Shadow fade through saved exposure-stop weighting; retain both target drafts and complete both-target recovery/render/export behavior. Complete source Tasks 5–6 together.
- **Exclusions:** no cross-target save, pixel interpolation of faded RGB, source/alpha changes, recipe feature, Background light or unrelated cleanup.
- **Predecessor:** actual FR1 Gate 3 approval and continuing candidate correspondence, not a plan/status label. Product comparison is accepted FR1 to FR2; full feature comparison remains baseline to final feature.
- **Owners/interfaces:** shared reduction owner; final optional `apply_shadow_fade(..., reduction16=None)`; `shadow_fade_files(record)` including optional old `area.json`; keep `read_shadow_fade` tuple stable. Carry keyword-only `shadow_reduction_off=False` through saved layer/foreground selection; expose Shadow in existing operation/preview/draft map. Update connected storage/render/resource/export/UI/test/doc consumers.
- **QA:** Q3–Q4 for Shadow, Q6 with both targets, Q7–Q9. Feature owner owns upstream Shadow OFF → downstream highlight recalculation, independent-target save/reopen, cache clear and disconnected delivered-operand reconstruction on the combined candidate.
- **Review focus:** factor belongs inside the Shadow exposure-stop exponent; changing upstream RGB may change downstream pixels while spatial settings/reduction hashes stay exact. No second geometry/raster pipeline.
- **Safe state/compatibility:** legacy Shadow version 2 remains readable; explicit reduction creates version 3; clear retains version 3. No rewrite, silent dropping or weakened disabled-alpha dependency check. Spatial capability stays complete.
- **Acceptance:** independent linear-sRGB scalar oracle uses `2**(-3*(1-R/65535))` for amount .5/support 1/preserve 0; full reduction copies original foreground bytes exactly. One target's save/clear/reload cannot alter or clear the other's newer draft; saved OFF comparisons rerender the pipeline correctly. Repeat protected partial-alpha/export/resource/failure contracts with both operands present, including protected alpha=32768 and nonfull R=32768 with nonzero support/amount so ignored protection changes the expected RGB.
- **Recovery:** as FR1; disabling an effect retains operands and does not silently repair stale alpha or revive another effect. Prior accepted versions/exports remain preserved.
- **Gates/reviews:** prepare exact FR2 packet after FR1 acceptance; orchestrator approves Gate 2/Gate 3 under the same direct grant. Three distinct frozen-candidate implementation reviews, with Ponytail inside architecture against accepted FR1→FR2; no extra review set. Renew affected prior proof only.
- **Future impact:** provides a settled predecessor for later appearance-recipe planning; those feature requirements are not implemented here. Final package/current GitHub checks and any expected provider review remain separate publication obligations.

## Progress and review readiness

| Increment | Factual status | Evidence | Decision / next action |
| --- | --- | --- | --- |
| FR1 | Gates 2 and 3 orchestrator-approved under user delegation | Handoff: 2230 passed/3 skipped, actual browser, repaired packages/static checks, candidate inventory | Accepted; orchestrator commits the exact owned change |
| FR2 | Preparation authorized after FR1 commit | Source Tasks 5–6; no result | Prepare concrete Gate 2 packet on committed FR1 |

| Plan scope | Reviewer/report | Candidate | Disposition |
| --- | --- | --- | --- |
| Requirements/source fidelity | `/root/fade_plan_source`, final native report | Initial frozen candidate below | No material improvements recommended; full raw sources, BR1–BR9, current contracts and technical sources inspected. Unaffected by the later verification-only strengthening. |
| Architecture/reviewability/simplicity | `/root/fade_plan_architecture`, final native report | Initial frozen candidate below | No material improvements recommended; complete increment boundaries, real geometry/asset/render/viewer/cache owners and naming inspected. Ordinary plan simplicity review; Ponytail not invoked. Unaffected by verification-only corrections. |
| Verification quality | `/root/fade_plan_verification`, initial report and targeted final renewal | Initial then corrected frozen candidate below | Two material test-plan findings validated and fixed; targeted renewal closed both. No material improvements recommended. |

All three distinct fresh-context read-only assignments are complete. Each read the raw source and coordinated candidate fully, verified hashes and inspected relevant owning source; none changed files or ran product imports/tests/builds. Reports are retained in the native review-agent returns above. Historical source reviews supply context, not independent credit for this candidate.

Initial frozen candidate SHA-256: plan `d3b28e158e53ab9abd357ead0632d32fa36d1e4f4d9523bb2989d1dce5332bf1`; QA `f5336b78ea3a66c529aae4340663b139227ce7f76f285f1e985fd3e4ff508ddd`; handoff `5951cde72ec9dc200442dd01110b5d4db4c5ef3bcb88f7237ef1dd8deefc6612`.

After collecting every report, the owner verified and corrected:

1. Protection test sensitivity: the source endpoint example's protected full-reduction pixel could pass with protection ignored. Retained the original example and added a distinct protected partial-alpha/nonfull-reduction sample, nonempty intersection assertion and unprotected control for both spatial and Shadow checks. Current `test_spatial_fade.py` protection cases exercise the old operand path, so they cannot substitute for this new-path assertion.
2. Cache/export order: `operations._validate_cache_context` checks only deliveries already present. The corrected combined journey creates/freezes reduction-bearing native/margins/series deliveries and companions before inspection/clear, verifies preserved hashes, then reconstructs those retained deliveries without re-export or copied project state. This matches the existing storage journey's required ordering.

Corrected substantive candidate verified by the verification reviewer: plan `b7bd3cdd1ac25c6a16be3d8647c96933af3702d62c979e40424d4286e848daa9`; QA `44c351b3d06c62284a3e7ffabd3b64e89b1ec3f1bca2e1b1ebf87d1289b3bb85`; handoff `f7a923ffa9d301ab8c46e4e4d6b2d8ebe4bde16d6c7b483f5ba6b6da6c8ec2bd`. Renewal covered only the two corrections and affected consistency; source/architecture assessments remain applicable because no product requirement, ownership, increment boundary or compatibility policy changed. No material findings remain. The subsequent status/report text is administrative and changes no substantive preparation or QA contract. These are planning-level findings and closure, not executed tests or Gate 2 approval.

## Decisions and remaining obligations

The direct grant covers the selected source design, ordinary repairs and eventual open PR creation. The orchestrator must evaluate the concrete compatibility policy, evidence and each increment before progression. Human photographic acceptance remains outstanding with the human; no synthetic check can close it. Human code inspection is deferred to final GitHub results, so behavioral evidence and independent reviews retain all their scope.

The source's historical unavailable `.venv` command assumption is amended to reuse a retained pinned interpreter without modification, installation or downloads. Current metadata matches all 41 lock pins; loaded Pillow/core is 13.0.0; package/runtime details and command limits are in the handoff. These probes are not application test passes.

## Final scope reconciliation

FR1 implementation, repaired full verification and all required result-review scopes are complete; the orchestrator accepted FR1 at Gate 3. Source coverage above distinguishes exercised FR1 obligations from unimplemented FR2 obligations and pending human photographic acceptance. Count approved amendments separately from achieved behavior. After accepted FR1, FR2 needs its own preparation and approvals. The eventual feature deliverable is one open PR against verified `main`, after both increments and orchestrator publication approval; no merge or deployment.

### Evidence retention and cleanup review

**Reviewed 2026-10-27**, outside the two increments: keep current durable proof; hold predecessor archives and failed fixtures for active Gate 3/FR2/publication comparisons. Shared runtime and preexisting build/metadata have unknown other consumers and remain untouched. Owned evidence is about 10.9 MB; the handoff records paths and final census. No destructive cleanup authority follows from acceptance or completion; optional storage disposition is not product acceptance. Planning sources/outputs remain for GitHub review and are excluded from actual installable packages.

Next: the orchestrator commits the accepted FR1 candidate and sends its immutable predecessor identity to the same feature owner. That owner prepares FR2 for the next Gate 2 decision, without implementing Shadow yet. No human decision is needed.

### FR1 Gate 2 decision — 2026-10-27

The owning orchestrator `01a17ba9-9112-7a52-b8da-547737b178e3` evaluated the raw sources, coordinated artifacts, current owners and three actual plan-review reports, and approved FR1 under the direct human delegation recorded above. Approved artifact hashes: plan `7445409e8bc6b1d01eb81f3cea0df1b02fed47578f7f9fc2974bb78829f77eba`; QA `c24fd9a2d213c3bff74192e6a91a6d9c9ee8f25665ecca770411976754eb7997`; handoff `99d742b012c089df530557c77209b3bc29408b3ef0c864868c26d9bf6b4a60a2`.

Approval includes spatial schema 1→2, bounded geometry, coupled persistence/render/export/UI/docs, Q1–Q6/Q9 with corrected protection/cache checks, and the retained pinned runtime without changing environments. Baseline is `162fa8b5125a00a1453246a4ddb2a50e45af7a94` on `fade-reduction`. Complete meaningful RED/GREEN, settled checks, browser/package evidence and three independent result scopes; architecture includes Ponytail review. The orchestrator will poll the final Gate 3 return and handle the increment commit. No further parent messaging attempts or Shadow implementation are authorized at this stage.

### FR1 Gate 3 decision — 2026-10-27

The owning orchestrator `01a17ba9-9112-7a52-b8da-547737b178e3` evaluated the final 24-file candidate, actual independent reports and targeted renewals, relevant source changes, complete repaired test log, synthetic browser, package and disconnected reconstruction evidence. **FR1 is accepted at Gate 3, orchestrator-approved under the direct human delegation above.** No material improvements remain recommended in the required review scopes.

Accepted pre-decision inventory: `local/evaluations/fade-reduction/fr1-gate3-candidate.json`, SHA-256 `45fcb7a015ca4b01004f9549a0430271afe4065b892b773b443960a794e4c582`, against `162fa8b5125a00a1453246a4ddb2a50e45af7a94` on `fade-reduction`. All 24 disk hashes matched; all 21 product/test/public-document hashes matched the renewed reviewed candidate. The complete log hash matched its inventory: 2230 passed, 3 explicit model-asset integration skips, exit 0. Ruff, formatting, source typing and whitespace checks passed. The warm-preview replay defect is fixed and closed by architecture/Ponytail and verification renewals; unchanged source-fidelity coverage remains applicable. These approval/status edits affect only the three existing planning records and do not invalidate tested or packaged inputs.

The orchestrator may commit this owned increment, then authorize the same feature owner to prepare FR2 against that immutable commit. FR2 implementation still requires its concrete Gate 2 decision; feature publication follows accepted FR2. Human photographic acceptance, real model inference and large-photo latency/peak memory remain unverified. This engineering approval supplies none of them and grants no merge, deployment, private-photo processing, installation or evidence deletion.
