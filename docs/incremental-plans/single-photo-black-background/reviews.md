# Incremental-plan review record

Date: 2026-10-16. Scope: proposed plan and preparation-only handoff, not application implementation. Three distinct read-only reviewers started with `fork_turns: none`; each received the raw v4 source and the same frozen candidate, its own bounded role, relevant constraints and no other reviewers' conclusions. Reviewers were prohibited from mutation, product/reference execution, recursive delegation and external actions.

## Candidate identities

Primary source SHA-256: `2b41bad662f2ab364e0be8e4c834e554059d10acf668314c288a0c60cef81b76`. All six supporting-document hashes in [plan.md](plan.md) were verified unchanged. Substantive hashes cover exact bytes between the HTML substantive:start/end markers, excluding those markers. Later status/report links outside those markers are administrative.

| Candidate | Artifact | Whole-file SHA-256 at review | Substantive SHA-256 |
| --- | --- | --- | --- |
| Initial frozen draft | plan.md | `e02faabef744fd4a419e76ea191030fba63abdada6fd4f9e0553e4426917770b` | `d2bf4b89285927ec3b0d173edcad8906628a81d77686ae83513d9b8a211fec01` |
| Initial frozen draft | handoff.md | `f10a9635e97fb5c018c4aabdb13a377e3efe40257c5c58896050e0af4c4366cd` | `22fe585bd99319d57992eb3d97b73cf126e57bc22015c9e8371458b306da7930` |
| Corrected reviewed candidate | plan.md | `8d9bd38d36f71a48480d3734f0846b6ae28d949174b6b352a257155571982fd2` | `33637c6f171ee95aaccc2d5d84aac6c5bed6103865c400ed8aeb4a389f9e1a3a` |
| Corrected reviewed candidate | handoff.md | `3fabdc70835161c74d857b1c3ed71d7a386736b68aa815d65edb19971baa8694` | `428bb872836f9d1c354526292ccb69bc94a7e86424938534e9906e118791a0f8` |

## Requirements and source fidelity

Reviewer: independent Codex subagent `/root/source_review`.

Initial report: read the full v4 source, both artifacts and all six selected supporting documents; verified their identities. Found one material sequencing issue: G3 and v4 §3.1/§6.1 require the project lock for every writer, while the draft assigned first-writer transaction safety to I02 despite I01 already creating project/master/recipe files and recording development approval. The independently usable I01 could therefore be interpreted as lacking required writer protection. Smallest remedy: assign initial shared locking, safe project/master/draft/development-state writes and meaningful contention/failure tests to I01; let I02 extend those helpers to processing snapshots/revisions. Other material requirements, exclusions, photographic gates, Gate 2/Gate 3, separate permissions and release evidence remained preserved.

Focused recheck: verified both corrected candidate hashes and unchanged primary source. Confirmed I01's ownership, atomic development approval and contention/interruption/low-disk checks; I02 reuses/extends the helpers, and regrouping/coverage/handoff agree. Finding closed; no directly caused material regression. **No material improvements recommended.**

## Architecture, human reviewability and simplicity

Reviewer: independent Codex subagent `/root/architecture_review`.

**Substitute simplicity review; Ponytail not run** because it was not explicitly authorized.

Initial report: verified both artifacts and six supporting identities; independently found the same P2 first-writer ownership gap. Other cards had coherent acceptance stories: usable base exports belong with I03; repair, resumability and viewer are defensible separate contributions; effect controls, stale handling, preservation and rendering remain coupled. No concrete unnecessary dependency, speculative abstraction or harmful fragmentation warranted another finding.

Focused recheck: verified corrected candidate and unchanged source identities. Confirmed the ownership finding closed and I01's safeguards directly serve its trusted-master acceptance story without unrelated work or harmful enlargement. No directly caused material regression; unaffected initial evidence remains applicable. **No material improvements recommended.**

## Verification quality

Reviewer: independent Codex subagent `/root/verification_review`.

Initial report: read the full v4 source and both frozen artifacts; verified supplied hashes. **No material improvements recommended.** Proposed evidence covered each card, safe intermediates and every v4 §9 row, including nonvacuous partial-value protection, saved-operand model-free/cache-free replay, native geometry, backend failures, offline creation of new guides/support/locks, bounded live assisted repair, combined stale effects and measured release evidence. Labelled stub orchestration does not replace real inference; arithmetic does not establish photographic quality; RGB8 fixtures/history do not establish actual RAW/backend/live success. Missing sources/permissions/runtime proof remain blockers.

Focused recheck: verified corrected plan/handoff and unchanged primary-source hashes. Confirmed the added I01 checks are meaningful: actual competing processes exercise the OS lock and observable busy response; interrupted/low-disk writes must not publish incomplete masters or approval state. Ownership, evidence timing and the handoff agree; I02 extends the same helpers and later operation/resume/viewer verification remains intact. Correction adequate; no material directly caused regression. Unaffected initial conclusions remain valid. This confirms proposed verification adequacy only, not executed tests or runtime behavior.

## Reconciliation and limits

The author validated the duplicate sequencing finding against v4 line 93 and lines 292–294 and retained it once. The correction updates I01/I02, ownership/regrouping tables and the I01 handoff; it does not change source design, add an increment or waive a gate. Each affected role received the corrected candidate for a bounded recheck. No open-ended review rounds or Ponytail invocation occurred.

Author artifact checks are separate from independent reports: ten unique increment IDs, all ten required card fields, existing local links, and preservation of the 95 pre-existing files. Final artifact checks are recorded in the plan after completion. No application test, install/download, inference, live assisted evaluation, Git write or photo processing was performed. Planning-review readiness means I01 executor preparation can start; concrete implementation and verified-result approvals, setup authority and every product/runtime/photographic gate remain outstanding.
