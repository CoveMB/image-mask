# Local sharpening plan review

Publication status (2026-10-26): this implementation is delivered and merged through MR29. The tasks and permission boundaries below record its earlier plan; unchecked boxes do not reopen completed work. See [current delivery and remaining obligations](../../incremental-plans/single-photo-black-background-qa/plan.md#current-delivery-and-remaining-obligations).

## Reviewed candidate and decision

The user requested a plan update, independent review and one new implementation chat with routine work preapproved. The actual grant is message `01a17761-556f-7a82-957c-4fc5f911f865` in chat `01a160cd-a395-7511-80aa-c71111bad696`.

Reviewed documents:

- [Design](../specs/2026-10-26-local-sharpening-design.md), SHA256 `40349c3818d2e95a0d407d7c031977f446d17797c1a624f75932e59c5d2e5198`.
- [Implementation plan](2026-10-26-local-sharpening.md), SHA256 `49cd8f33717a23c1835f008050d426ed689fc85ff3c8ecb888daf3314b2774b4`.

**Orchestrator-approved under the user's current delegation for bounded local implementation.** Both distinct fresh-context read-only plan reviews completed with no material findings. The coordinator read both full reports, checked the connected rendering/lock integration, verified all 100 application baseline hashes and the exact nine preserved SDR modifications, and confirmed both document hashes. No plan corrections or repeated reviews were required.

This decision accepts the engineering plan, including its generic detail scales and verification obligations. It does not claim that sharpening exists, tests have passed for it, an image has improved, or a human has accepted a photograph. The private handoff reserves the implementation checkout and retained runtime; primary planning work stays outside the application candidate.

## Independent architecture and source-fidelity report

Reviewer: `/root/sharpen_plan_architecture`; fresh context, read-only, no recursive delegation.

**No material improvements recommended.** No unresolved material design decision within the reviewed scope.

Verified the bound design/plan hashes, application HEAD `ed86ca84478846271c9f4da09c02ddbe5a38d2bd`, all 100 handoff baseline hashes and exactly nine approved SDR modifications. The reviewer checked:

- Alpha-weighted context, finite Gaussian halo, native-boundary reflection, common-channel gamut limiting, exact excluded RGB and unchanged alpha.
- Both `selected_foreground` and the explicit matte/repair composition path, including ordering and non-compounding behaviour.
- Inherited selected RGB locks, saved operand validation, effects reuse, recovery and warm-cache validation risks.
- Complete editable native and presentation companion operands and standalone replay order.
- Absent-field OFF compatibility, older-reader limitations and local-only authority.

Limitations: source/document review only. No tests, image processing, private-photo inspection or mutations. Runtime, resource, browser and photographic evidence remain implementation gates.

## Independent verification and lifecycle report

Reviewer: `/root/sharpen_plan_verification`; fresh context, read-only, no recursive delegation.

**No material improvements recommended.** No QA blocker within the reviewed scope.

Verified the same document hashes, application HEAD, all 100 baseline hashes and all nine SDR file hashes. The reviewer checked:

- Independent numerical expectations; fine and broad detail; radius/threshold bounds; noise, gamut, partial alpha, nonempty protection and strip/crop edges.
- Non-compounding requests, stale/tampered operands, warm validation, interrupted publication and exported-assets-only native/framed/series reconstruction.
- Real-browser verification beyond handler tests and inspection of actual packaged contents.

These obligations fit the connected exposure/fade validation, recovery, cache, export and controlled-DOM test contracts. Exported-assets-only reconstruction is deliberately stronger than an existing child-process fade test that still reads its project.

Limitations: no tests, models, browser journeys or photo processing were executed and no files changed. The historical full-suite result remains qualified evidence: 1952 passed, 3 skipped and one unrelated viewer-lock failure; it is not a new pass.

## Execution boundaries

One persistent native implementation owner may complete the reviewed local tasks, required checks and verified in-scope fixes without repeating routine approval questions. Independent result reviewers remain read-only; the owner applies fixes sequentially and renews only affected checks/scopes.

Material design, compatibility or scope changes still require a human decision. The new grant does not include commits, pushes, PR/provider actions, paid reviews, installations/downloads, private uploads, permission repair, deletion or merges. Previous provider limits and photographic acceptances remain unchanged. Final photographic acceptance remains human.

## Later review and publication delegation

Direct human message `01a1777b-2a24-7670-bce7-f0111ee6139c` in the same parent chat requests: “Once it will be done make same independent review passes and ponytail as other increments then create the Mr and ad it to the stack”. This later grant supersedes the earlier publication exclusion only for the verified sharpening delivery and its required underlying SDR changes.

After the implementation candidate is actually ready, the parent coordinates three distinct fresh-context read-only result assignments: source fidelity/compatibility; architecture/simplicity with the explicitly requested `ponytail-review`; and verification/lifecycle. Read all relevant reports before fixes. The persistent implementation owner applies verified material fixes sequentially; renew affected scopes/checks and retain applicable unchanged proof. This replaces the plan's earlier two-result-review arrangement without changing its reviewed feature design.

Only after actual preparation, required checks, all three reports and verified material-finding resolution may the parent record delegated result approval, construct the exact ordinary commit(s), publish to the verified existing repository, create the requested open MR against the reconciled live stack tip, attach it and add it to the actual native group. Verify server membership/order/base/head and applicable current CI/provider content evidence. Include the complete proposed shipped delta in reviews; preserve the approved SDR baseline and all unrelated primary planning work.

No publication or result approval has occurred merely from this instruction. Keep existing MRs open. The grant does not permit merges, force pushes or historical stack rewrites, paid reviews, private uploads, installations/downloads, permission repair, cleanup or photographic acceptance. Earlier provider deadlines/counters remain intact; record any applicable finite new-scope bounds before a review-triggering action and do not silently borrow or renew an old budget.

## Implementation result review and SF01 resolution

The actual initial application candidate was bound to manifest SHA256 `883674af1e7530da9ad6a46ccaafbdae37f1fc468ea0052c4973b1f0c58a6716`, with 104 tracked-plus-new files and 23 changed/new paths against `ed86ca84478846271c9f4da09c02ddbe5a38d2bd`. The complete candidate includes the required, already-approved SDR import work. Three distinct fresh-context read-only result assignments completed:

- `/root/sharpen_result_source`: source fidelity and compatibility; one material P2 finding, SF01.
- `/root/sharpen_result_architecture`: architecture and simplicity, with actual `ponytail-review` 5.3.2 use.
- `/root/sharpen_result_verification`: verification and lifecycle evidence.

The coordinator read all three reports before routing a correction to the original implementation owner. SF01 concerned Python dictionary equality accepting Boolean/numeric aliases in the actual saved settings file when only that file and its hash binding changed. Revision reading and editable export could then accept settings that strict standalone replay rejected. The coordinator independently reproduced all four enabled/disabled and cold/warm cases, including the invalid editable export. The earlier general corruption assurance was too broad because its tests changed both record copies; this concrete finding took precedence.

The owner corrected only the sharpening saved reader and its regression tests, reusing the canonical JSON serializer for type-sensitive comparison while preserving harmless formatting differences. Invalid/nonfinite actual JSON retains contextual `ProjectError` handling. The regression run demonstrated 40 original-cause failures before the fix. Afterward, 106 affected checks passed with 39 unchanged arithmetic/registration checks deselected, and 13 extracted-wheel checks passed with 123 deselected. Capture statuses were successful; failed and interrupted earlier evidence remains retained.

The amended candidate is bound to manifest SHA256 `d63bd87172e32d162ef24ad459453970f7147b18e6a3a39fb8eb759216326c6e` and complete patch SHA256 `b993459df5c93c69de6791dc78c36cb00c3546749ff9794287c0769d20abf491`. All 104 live and snapshot file hashes were verified; the other 102 files are byte-identical to the initial reviewed candidate. Each original reviewer completed a targeted renewal of the affected scope. All three reports are clear, SF01 is verified closed, and no material finding remains. The coordinator also verified that the same four retained synthetic projects now reject invalid reading/export while preserving all 392 existing fixture/delivery files.

The initial full suite passed 2067 tests with three explicit installed-model skips. That result remains evidence for unaffected scopes; a new full-suite pass is not claimed for the amendment. Ruff, formatting and source mypy passed. Actual amended wheel/sdist members, source correspondence and private-material exclusions were inspected; membership remains 34/88. Runtime proof uses the retained Pillow 13 core and extracted packages, not installed activation. The earlier real synthetic-browser checks remain applicable to unchanged UI code. The measured peak RSS is kernel-only evidence; broader runtime, accessibility, inference and photographic claims remain separate.

**Orchestrator-approved under user delegation for the exact amended engineering/result candidate**, using the current implementation and later review/publication grants above. The rationale is complete scoped preparation, meaningful checks, all three independent reports, verified material-finding resolution and affected renewals. This releases the reviewed bounded photographic trial and makes later exact ordinary publication eligible after current Git/provider/group prerequisites. It supplies no photographic acceptance, hosted CI/provider result or merge authority.


## Bounded photo trial and local publication preparation

One mild dragonfly draft was produced through project controls. Native ON/OFF inspection showed only a slight change, so no stronger attempt was justified. The source, alpha, protected regions, prior revisions and existing appearance settings were preserved. A complete editable native draft was exported; an actual offline child reconstructed it exactly from delivered files. This remains unaccepted photographic work, and does not restore detail absent from the capture. Three corrected evidence-script failures are retained and do not count as passes.

The exact reviewed 104-file candidate is now ordinary signed local commit 0812857ee755e8b533b4ddb6f3e7e072d7526524, tree 42b29c7dd1d5c66d868d2a43e45eacf3402fe07f, sole parent ed86ca84478846271c9f4da09c02ddbe5a38d2bd. All committed bodies and modes match the approved candidate, and the isolated checkout is clean. Signature verification passed using the existing configured public key; default Git verification lacks an allowed-signers file, so no persistent configuration was changed.

Direct human approval granted a separate two-hour included CodeRabbit window, one allowance inquiry and at most one manual review if automatic coverage does not run. Prior I19 counters and expired deadlines remain unchanged. The exact signed candidate is published in open MR29, appended as the eighth member of existing native stack21 (server ID2459176), above MR28. Server signature, all104 blob paths/modes/object IDs, base/head/order and attached artifact are verified. GitGuardian passes. The first automatic CodeRabbit review covered all 23 changed files on commit0812857 and completed with four verified issues: stale v4/legacy contract wording, Reset blocked by invalid unsaved sharpening settings, incomplete delivered guidance about the already-applied sharpening, and sharpening omitted from the sharpening-only repair-before display despite its ON label. The original implementation owner is correcting these issues, with delivery identities and old exports preserved. Source, Ponytail architecture/simplicity and verification scopes will be renewed only after the actual corrected candidate and checks are frozen. Initial review closure does not close these later findings. No manual request, merge, private upload or photographic acceptance has occurred. No application Actions or test-merge checks are observed.

## CodeRabbit correction result renewal

The original implementation owner corrected only seven files for LSCR01–04. The corrected complete104-file candidate is bound to manifest SHA256 c744d8b011e1a69bc7833824a5f3a4ae25de21185a6eca1ac7256135c7b5def4 and correction patch SHA256 72bf77e5e2a55c012fbf3df21aad83ebca4fbeaf8aebfd46c16e6fc0a73fa4ec against published commit0812857. The parent read all three targeted independent renewals: source fidelity/compatibility, architecture/simplicity with actual ponytail-review, and verification/lifecycle. Each reports no material improvements recommended. The unavailable original source-review context was replaced only for that required scope; architecture and verification contexts were reused. Unchanged numerical/kernel/SF01 proof remains applicable.

Meaningful regressions demonstrated the original Reset, delivery-identity and repair-before failures. After correction,391affected source cases and42extracted-package cases passed, with command and capture statuses verified. The other132unchanged sharpening cases were unselected; this is not a renewed whole-repository result. The actual34-member wheel and88-member sdist, RECORD/dependencies/source correspondence and privacy exclusions were inspected. No setup, inference, photo trial, browser/accessibility acceptance or photographic acceptance was renewed.

**Orchestrator-approved under user delegation for this exact correction candidate**, after verified material-finding closure and all required reports/checks. Ordinary exact child commit is eligible; corrective push remains bounded by actual included-provider eligibility and the unchanged two-hour grant. No manual request, merge or history rewrite is implied.

## Corrective publication and provider settlement

The exact seven-file correction is ordinary signed child commit eac596a17ce39eb9de51af1705f7ff9b03062fc2, tree519da182d9efd59fe375f6be51be7555e709d748, sole parent0812857. All104 committed and remote blob bodies/modes match the approved candidate; server signature is valid. MR29 remains open above MR28 as member8/8 of native stack21, server ID2459176. All original member heads/bases and the order18→20→23→24→26→27→28→29 remain verified. No merge or history rewrite occurred.

Automatic CodeRabbit run f1091f75-e38e-4441-b370-b3f6fb255328 completed on eac596a at19:39:48UTC, range0812857→eac596a, with no actionable comments and exact current-head reviewed coverage. It selected seven correction paths and explicitly deduplicated three as similar to previous changes: the viewer tests, contract documentation and review UI. This is not seven wholly fresh provider file inspections. The retained initial23-path review, the actual three targeted independent renewals, direct tests and provider acknowledgements of both inline corrections establish the scoped finding dispositions. Delivery guidance and repair-before corrections are also identified in the final provider explanation.

GitGuardian passes on the current head. No application Actions or test-merge checks/runs are observed; their absence is not a test pass. CodeRabbit retains a generic18.18%/80% docstring advisory, with no evidenced functional defect or repository percentage gate; no broad docstring churn is recommended. The included allowance inquiry remains1/1used, manual review0/1unused, no outstanding request, no paid use; the original two-hour deadline and every old counter remain intact. Provider content settlement supplies no photographic acceptance. The dragonfly draft and all prior human evidence gaps remain unchanged.
