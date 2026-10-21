# Framing and margins independent plan review

Date: 2026-10-19 (America/Toronto). Scope: proposed design and implementation plan only; no product implementation, test run, browser/photo evaluation, publication or acceptance.

## Candidate and independence

- [Design](../specs/2026-10-19-framing-and-margins-design.md)
- [Implementation plan](2026-10-19-framing-and-margins.md)
- Reviewer: `/root/framing_plan_review`, one independent read-only agent, fresh context without inherited conversation history. No recursive delegation or external review service.
- Author: primary chat; separately checked requirements, source contracts, links and source-file hashes. Author checks are not independent review credit.
- Application baseline: `037e8fb4f62774fc85e4fe63e5029bcca832d877`. All 23 recorded source/test/config/document hashes matched at review. Four pre-existing dirty application documentation files were preserved. Remote refs were not fetched.
- Local evidence: `local/plans/framing-and-margins/source-baseline.json` records exact checkout identity, paths, status and source hashes. The separate storage design remains a proposal in the inspected source; its execution integration guard was reviewed as practical.

| Artifact | Initially reviewed SHA-256 | Corrected candidate SHA-256 |
|---|---|---|
| Design | `e59e5616c7be4c12c30ad5009b5d7a5dfc28e703e246f4b34d4e3630a9d12c1c` | `966ce48c58cfd56ea2469be6fe458e745df766091e2db3df50597a0e8a2ec55b` |
| Plan | `918fa388bdc771c194a48cca3d8d9ab32225760fe9911cb48baee7d5e33f6215` | `0740e99606555b814e4f1249c25ed75ee8cc8666d9d4d271dfd6c9028ec08dc7` |

## Initial independent findings and corrections

Initial disposition: **corrections required**. The reviewer found the presentation-only architecture suitable and reported three material P2 issues. The author verified each against the current code before editing the planning documents.

1. **Preview request required a digest the browser could not obtain.** Current `viewer.py:109` revision snapshot exposes `draft_digest`, not a revision-manifest hash. Added `revision_manifest_sha256` from exact validated manifest bytes, kept the identities distinct, and required an actual snapshot → request → response test instead of a test-generated digest.
2. **The PNG data-URL display path was incompatible with the current CSP.** `viewer.py:401` permits `img-src 'self' blob:` and `connect-src 'self'`; current `review.html:976` loads a Blob into `createImageBitmap`. Corrected the response to `png_base64` locally decoded to a PNG Blob/bitmap, retained CSP, added bitmap disposal and a real-browser rendering check. A Node harness is not CSP enforcement evidence.
3. **Preset-save failure promised preservation beyond the real commit boundary.** `project.py:125` replaces the destination before directory sync. Corrected the contract/tests to distinguish pre-replacement failure from post-replacement durability uncertainty. The latter re-reads actual state and requires reload before another CAS save; it does not claim rollback or overwrite the visible file. Photo pointers remain unchanged in both phases.

The author additionally bounded simultaneous preview rendering with one nonblocking per-server lock, returning busy before image allocation and releasing on every outcome. This is a small resource safeguard and test obligation, not a queue or worker system; included in the focused recheck.

Other inspected anchors include `export.py` saved-layer rendering and publication, `background.py:80` saved backdrop validation, `project.py:489` native-size invariants, `viewer.py:198` request identity/security, `review.html:699` draft preservation, and `test_background.py:578` saved-only reconstruction/legacy exports. The initial reviewer reported no further material improvements for geometry, precision/alpha/protection, backdrop-only padding, immutable delivery identity or native coordinates.

## Focused closure

The same reviewer verified only the three corrected contracts and the preview concurrency safeguard against the corrected hashes above. Final disposition: **Ready for user review. All three findings are closed. No material improvements recommended.** The reviewer found the preview lock proportionate and confirmed the digest producer/consumer tests, CSP-compatible decoding/browser check and accurate save-failure boundary. Both final document hashes were independently verified. This was a focused closure of material findings, not another broad review of unchanged work.

## Evidence limits and user decisions

Planning artifact link/unfinished-marker checks passed and inspected application hashes remained unchanged. No application or browser tests were run during planning; all test commands describe future verification.

Manual margins plus Centre image are proposed. The optional question about automatic subject centring has not been answered; absence of an answer is not approval. Saved backdrop edge extension and first-version canvas bounds are explicit proposals for plan approval. Implementation, Git/external actions, private-photo use and photographic acceptance require their applicable user authority.
