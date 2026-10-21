# Photo library storage planning review record

Status: two independent reviews complete; five verified material findings addressed in the plan. Reviewer B confirmed closure of its two safety findings in a bounded follow-up. Implementation has not started. This records planning evidence only, not implementation correctness or runtime validation.

The user explicitly requested two independent reviews with different focuses. Both use fresh contexts, read-only source access, no model runs, no recursive delegation and no implementation authority. Reviewer B receives the revised candidate and current source, without reviewer A's report or the author's reconciliation rationale.

## Reviewed source

Application checkout: `/private/tmp/image-mask-background-appearance`, HEAD `037e8fb4f62774fc85e4fe63e5029bcca832d877`. The local remote ref differs only in troubleshooting documentation; no fetch occurred. The baseline records 52 source/test/document hashes and four existing dirty documentation files. The planning checkout itself has no application source.

Private evidence is retained in `local/plans/photo-library-storage/`: `source-baseline.json`, exact `review-1-design.md` / `review-1-plan.md`, `review-1-report.md`, `review-2-design.md` / `review-2-plan.md`, `review-2-report.md`, amended `review-2-amended-design.md` / `review-2-amended-plan.md`, and `review-2-followup-report.md`. These files are retained locally; they are not review messages or external uploads.

## Review A: current-code fit, completeness and precision

Reviewer: `storage_plan_fit_review`. Verdict on its candidate: **revisions required**, three material findings. It independently verified the recorded HEAD and all 52 source hashes.

| Artifact | Reviewed SHA-256 |
|---|---|
| Design | `95ae222709da3262b2bde1a6ddb1375dd686efae06fd8fb87ce5bf499f9ba496` |
| Plan | `065565dd8b092aedbfd2b6de0f55f9939713b37c16f095cc94f3c88a6ffd8370` |

| Finding | Source evidence | Disposition in revised design/plan |
|---|---|---|
| Latest preview can remain falsely Accepted after accepting an older restored result. | `operations.py:210–232`, `1616–1620`; `export.py:225–231`. | Verified. T4 derives status after every acceptance-pointer change, in both directions. Added B accepted → restore A → accept A scenario; latest stays B, footer becomes Draft. |
| Saved recipe can omit actual request overrides for four effects. | `effects.py:607–608`, `760–761`, `802–803`, `869–870`, `1096–1103`, `1238–1242`; restore at `operations.py:1545–1558`. | Verified. T2 names `run_effects` as reconciliation owner for all effects. Preserve consumed draft, save actual effective settings, retain unrelated draft changes, keep explicit digest/acceptance/restore semantics, test overrides and saved-only replay. |
| Mandatory developed-ID rename misses SAM and matte-cache consumers and maintained matting guide. | `operations.py:106–112`, `1139–1145`; `models.py:143–162`; `matte.py:44–61`, `123–126`; `docs/matting.md`. | Verified. Added mandatory source/test/doc owners and real application-path warm-cache reuse assertion to T2/T6. |

The controller verified these three findings against current source and amended the plan. Reviewer A's original verdict is retained; it is not represented as approval of the changed whole document. Its positive assessment: existing locks/publication, one asset resolver, current tile/session caches and no database/automatic asset collection are proportionate.

## Review B: proportionality, safety, recovery and user workflow

Reviewer: `storage_plan_safety_review`. Verdict on its candidate: **revise before implementation**, two material findings. It independently verified both input hashes, HEAD and all 52 source hashes. It did not read reviewer A's report or the author's reconciliation notes.

| Artifact | Reviewed SHA-256 |
|---|---|
| Design | `6c8733fbfad35e501ce71957f26208c7c17a5c8fadb59033693f28401aa30f56` |
| Plan | `2b6ca76ebaf86d4ec5e271160034151677a6a3388c9a75d2217da4e04a718d6c` |

| Finding | Source evidence | Disposition in amended design/plan |
|---|---|---|
| Published-only duplicate lookup and a short-lived lock allow identical pending imports under different names. | `project.py:72–88` protects a project; `project.py:145–158` protects a destination name, not source identity. | Verified. One library lock covers whole import/resume, including pending/published checks and final publication. Pending full-hash matches redirect to their recovery record; malformed records fail closed. Added same-bytes/different-subject and interrupted-pending tests. |
| State-first acceptance can leave an unaccepted JPEG labelled Accepted after preview failure. | `operations.py:188–232`; `project.py:110–132` replaces state before directory sync can fail. | Verified. Durably publish Draft latest preview before changing acceptance; state next; promote only after successful state commit. On failure retain Draft/pending and report actual observed state. Added demotion/state/sync/promotion/receipt fault cases. |

The whole-import lock deliberately serializes imports, a reasonable tradeoff for this single-photo workflow. Existing-photo processing keeps its own locks. This is simpler than adding source reservations, a catalog or a transaction coordinator. Preview demotion adds an ordering rule to existing atomic writers; it does not add a background repair process.

Amended candidate hashes: design `f0c27e4d7561f76fa15c9ac1945641d4e31e268c1002c176fc8624a8a2ff4297`; plan `613f230c47f20c5a331b06a44bfcb7e08eb765bad7feb455d391973bf661d28c`. Reviewer B checked these exact amended hashes and its two material corrections only. Its scoped verdict: “both findings are closed at the plan level”; no residual material contradiction found within those amendments. It reverified the affected source hashes. This is not a third independent review or a repeated whole-plan review.

## Scope and limits

No application code, configuration, ignore rules, photographs or existing projects were changed. No application tests, real inference, native filesystem fault tests or photographic acceptance ran during planning. Final implementation must obtain its own bounded review and execution evidence. The personal meaning of `project_/library` remains a recorded clarification; generic storage design supports either interpretation.
