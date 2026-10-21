# Single-photo black-background workflow — current handoff

Status: independently reviewed; ready for I01 executor preparation only. Date: 2026-10-16.

<!-- substantive:start -->
## Context and candidate

- **Return kind:** new executor preparation for I01 only, after all three planning-review scopes are reconciled. No implementation is authorized by this handoff.
- **Root:** `~/Code/CoveMB/image-mask`; re-resolve on the receiving host. It was not a Git repository on 2026-10-16. No branch/base revision or accepted implementation predecessor exists.
- **Plan:** [plan.md](plan.md), substantive candidate identified in the review record. **Primary source:** [v4 implementation specification](../../../single-photo-black-background-implementation-plan-v4-2026-10-11.txt), SHA-256 `2b41bad662f2ab364e0be8e4c834e554059d10acf668314c288a0c60cef81b76`; read it in full. Supporting reference identities and provenance limits are in the plan. Existing source/reference material must remain unchanged.
- **Selected increment:** I01 — Trusted RGB16 master. One photo becomes a safely stored, identity-bound developed master for explicit human development review. Preserve source capture bytes and true source precision, apply orientation once, validate profile/WB and retain master identity. Include the needed project contract, the nonblocking project lock and safe initial master/draft/development-approval writes, download-free preflight/doctor and synchronized setup/input/provenance docs/tests.
- **Excluded from I01:** model inference/download, segmentation, local repair, viewer, effects, photo-result acceptance and subsequent increments. Source future filenames/interfaces and commands are proposals, not installed capabilities.
- **Completed work:** planning conversion and, only when recorded below, independent planning reviews. No package install, model download, application test/inference, RAW/photo processing or live assisted evaluation occurred in this planning run. Historical v4 reviews/test reports are not current implementation results or approvals.
- **Material choices:** user selects actual local source/project folders and available real RAW/DNG pilot before affected setup/processing. Hardware, OS and available disk figures need live preflight. Any material conflict, incompatible dependency route or changed design returns to the user. Per-photo subject/development/effect choices stay human choices.

## Copy-ready preparation request

Prepare I01 from the saved incremental plan and original v4 source; do not implement it yet. Recheck the selected root, applicable target instructions, every relevant existing/dirty/untracked file and any now-present Git branch/status/comparison. Use read-only Git with optional locking/index refresh disabled if applicable; do not initialize Git, fetch, reset, clean, stash or force a commit. Preserve source/reference files and other work.

Inspect actual code/contracts and confirm the source/plan identities. There was no application at the planning baseline. If work now exists, determine whether it satisfies the intended contribution and identify its exact accepted predecessor/evidence; do not replace it or infer acceptance from its presence. Obtain the setup folder and actual RAW-pilot choices before their affected operations. Source-reported cloud permission is not an instruction to transfer a photo.

Inspect current official package metadata/documentation/advisories for the native ARM64 Python 3.12 image-ingestion environment actually proposed. Record dates, versions, architecture support and implications. Use the source dependency set and initial Transformers 4.57.6/rawpy 0.27.1 compatibility direction; future Torch/torchvision/model setup remains coherent with I02/I03 and must not silently inherit Linux +cpu pins. Documentation lookup is read-only; installation/downloads and private-source transfer need separate actual authority. Preserve TIFF RGB16/profile and grayscale16 routes; reject unsupported RGB16 PNG before an 8-bit conversion.

Produce one concrete I01 packet: exact candidate baseline/comparison; files/interfaces; outcome/exclusions; real input/profile/orientation/WB/precision decisions; shared nonblocking project lock and safe initial master/draft/development-state writes with atomic approval updates; source-integrity and non-8-bit-step TIFF tests; real two-process contention/busy and interrupted/low-disk initial-write checks; proposed commands confirmed against actual layout; documentation/provenance updates; recovery/preservation; future impact on master identity, coordinates and guide/matte consumers; and required independent implementation-review scopes. I02 will extend the same lock/state helpers to processing snapshots and revisions. Include the actual setup permissions needed with that concrete packet. Do not ask for another routine whole-program setup approval.

Before Gate 2, reassess human review load, coherence, safe intermediate state, compatibility and future contracts. If material choices remain, obtain user answers together. If future cards need revision, stop and return the detailed candidate/baseline, affected cards and proposed reconciliation to the planner; after review, confirm current context and resume I01 at Gate 2.

**Gate 2:** stop for the user's direct approval of the exact concrete I01 implementation packet. No bypass exists. A generic start/continue request, historical source approval or planning-review pass does not authorize implementation.

After actual Gate 2 approval, the executor outside this planning skill implements only the authorized scope, writes material invariant tests before corresponding implementation, runs focused checks and the full relevant suite once on settled inputs, and keeps docs/safeguards with behavior. Separately authorized setup/external actions remain bounded; Git writes, publication and live assisted evaluations are not implied. Obtain fresh independent source/requirements, architecture/reviewability/simplicity and verification-evidence reviews of the complete actual candidate, including relevant new/generated/configuration inputs and connected consumers. Reviewers must not be the author; reconcile supported material findings and renew affected evidence. The architecture reviewer performs “Substitute simplicity review; Ponytail not run” because no explicit Ponytail authorization exists. Do not install or invoke Ponytail implicitly.

**Gate 3:** present exact result candidate/comparison, actual tests/results, independent reports/dispositions, source preservation, unresolved limitations and recovery; stop for direct verified-result approval. No bypass exists. Tests alone do not prove human visual quality, RAW completeness or Mac/model runtime behavior that they did not exercise.

After accepted result evidence is returned, the planner reconciles actual shipped effects separately from preparation and chooses only a dependency-eligible next card. Do not advance from a preparation proposal or assistant-authored approval note.

## Future impact and return evidence

- I02/I03 require an approved master identity, declared sRGB encoding and recorded native orientation/crop coordinates. Development changes invalidate alignment; equal dimensions do not make old guides valid. I01 introduces no model behavior and cannot satisfy future CPU/MPS/real-model gates.
- **Preparation return:** return the detailed I01 candidate and baseline, affected cards/interfaces/acceptance, current official evidence, unresolved material decisions, permissions required, proposed checks and future impact. If reconciliation is needed, use: “Reconcile this I01 preparation return against the saved plan and v4 source; preserve accepted history, obtain affected reviews, and return I01 for current-context confirmation and Gate 2.”
- **Verified-result return:** actual source/plan/candidate identities, exact comparison and preservation, actual check outputs and limitations, independent role/reports/dispositions, accessible direct Gate 2/Gate 3 decisions or actual scoped exceptions, and concrete effects on future dependencies/acceptance/recovery. Missing evidence remains missing.
- **Separate product gates retained:** human development approval before masking; reviewed trimaps; exact protected-region/known-core/precision checks; human photographic acceptance; explicit optional appearance choices; actual RAW, per-model CPU/MPS disposition, live assisted/offline/recovery and fresh-session documentation proof before regular-use readiness. Later cards own those outcomes; I01 preparation grants none of them.

Stop at the first material unresolved decision, missing review/evidence prerequisite or non-bypassed gate. This handoff does not create/message tasks, implement code, grant installation/downloads, transmit photos/private source, mutate Git or publish anything.
<!-- substantive:end -->

## Planning-review disposition

All three independent scopes are reconciled on the corrected substantive candidate: `/root/source_review`, `/root/architecture_review` and `/root/verification_review`. The duplicate first-writer ownership finding was corrected; focused rechecks confirmed closure and adequate I01 writer tests. The architecture reviewer supplied the substitute simplicity assessment; Ponytail was not run because not explicitly authorized. See [actual review identities, candidates and dispositions](reviews.md) and [plan progress](plan.md#progress-and-review-readiness).

I01 executor preparation is ready. This administrative disposition changes no substantive handoff instruction and grants no implementation, setup, photo transfer or Git/external permission. Gate 2 and Gate 3 remain required; no bypass exists.
