# Fade into background plan reviews

Scope: [implementation plan](2026-10-22-fade-into-background.md) and [design](../specs/2026-10-22-fade-into-background-design.md), checked against current repository behavior. Original planning reviews are preserved below; the final section records subsequent authorized implementation reviews.

The user requested two sequential independent passes: Ponytail first, then a fresh review after material findings are addressed. Reviewers are read-only and do not modify application files or authorize implementation. Coordinator owns fixes and verifies decision-relevant findings against the repository.

**Current scope:** the user subsequently approved oval-only, arcs-only and combined use and requested the plan be updated and independently reviewed until implementation-ready. The first two passes below describe the historical oval-only candidate; they do not certify new arc behavior. The renewed reviews appear after that history. The prior reviewed documents were retained under ignored local planning snapshots before amendment.

## Initial self-check

- One new rendering option; explicit acceptance of colour/brightening and tinted transparent RGB with unchanged alpha.
- Ellipse scope and geometric monotonicity distinguished from irregular outline, protection exceptions and final brightness.
- All requirements mapped to implementation tasks, including old-mode replacement, separate 38% Shadow fade, native/presentation backgrounds, complete editable delivery and full petal profiles.
- Existing source ownership and strict persistence/publication contracts retained; no new dependency, source upload or application implementation.
- Commands are future execution checks. The compatible project environment is currently unavailable; no runtime or visual success is claimed.

## Pass 1 — independent Ponytail review

Reviewer: fresh read-only `ponytail_plan_review` agent using the explicitly requested Ponytail review skill. Reviewed current effect operation/inheritance/stale/lock paths, native render/review/export, series sampling/resources, viewer boundaries and connected tests/docs. Expected load: one local user processing one photograph within existing framing limits. No photos opened, application code edited or application tests run.

Candidate SHA256:

- Design: `bc31603a91eec182e81f493683157a275a679024b11fbec709e2179bfb79ad7e`
- Plan: `7710df679ba81464ae3070e0f819a4c6e65ce571c2f8a22d7ffc1b8df2d790a2`

**What this change does:** Adds one elliptical Fade into background mode, replacing inward shading while keeping Shadow fade separate. Preserves source layers and alpha and defines distinct native and series-framed rendering contracts.

**Must fix 1 — distinguish exact rays from raster sampling.** The initial Task 1 test mixed exact geometric rays with nearest-pixel paths. With centre `(60.5,60.5)`, inner radii `(5,40)`, transition 10, rotation 37 degrees, nearest pixels for a 95.625-degree ray at radii 15.30 and 15.35 are `(59.5,75.5)` and `(58.5,75.5)`; W16 falls from 21227 to 14559. This is movement between rays, not a reversal of the continuous geometric field. The incorrect criterion could reject correct rendering or encourage distortion of the ellipse.

Disposition: accepted. Coordinator independently reproduced both W16 values using the specified formula. Design and Task 1 now distinguish exact continuous-coordinate monotonicity (including quantization at the same coordinates) from raster equality at pixel centres. One canonical coordinate evaluator serves rasterization and complete-ray tests. Actual photographic traces still undergo full visual/numerical inspection without claiming arbitrary paths are exact rays.

**Should fix 2 — name the protection request contract.** The initial plan mentioned a generic optional protection file, but existing `run_effects` and two viewer boundaries use specific closed field allowlists. Different choices could reject a protected-flower request or omit its mask. The reviewer requested a shared `spatial_fade_protection_file` name, categorical validation, explicit allowed combinations and an end-to-end protected-region test.

Disposition: accepted. Coordinator verified `effects.py` request validation and `viewer.py` action validation/forwarding. Design and Tasks 2/5 now specify the exact key, both categorical encodings, input identity/path validation, additive retention/omission rules, disable restrictions and a viewer-to-operation test with nonempty partial-alpha protection.

Initial verdict: fix 1 and 2 first. Both are addressed before pass 2. No further material complexity reduction was recommended. Implementation, automated suites, browser behavior, photographic results and measured resource use were not checked.

## Pass 2 — fresh independent review of updated plan

Reviewer: separate fresh read-only `updated_plan_review` agent, without the first reviewer's context. Reviewed both updated candidates against root guidance, README/file contract, effect/recipe/project operations, repair and inheritance, render/review/export, series framing, viewer/UI and relevant existing tests. Excluded unrelated dirty QA documents.

Candidate SHA256:

- Design: `34e408205dd9b692cb1a3052692bf2021794e84cde103efa14414e24c75813e2`
- Plan: `c8269c799e63b0ae248ac7279dc06e8362afc3fe1b039636bfa29807b949ebf8`

**P2 — enforce the accepted-base gate.** The new operation required `candidate_comparison` but did not explicitly enforce accepted base or explicit candidate comparison. Existing `run_effects` guards are per effect, not a generic check. An otherwise valid new branch could therefore apply to an unaccepted working revision without an explicit comparison choice. Require the guard for all enabled requests, including amount zero, preserve disable recovery, and add UI/backend tests.

Disposition: accepted. Coordinator verified the separate shading and Shadow fade guards in `effects.py` and existing UI candidate checkboxes. Design and Tasks 2/5 now specify the guard before staging or mode mutation, zero-strength behavior, accepted/unaccepted/explicit-candidate/disable tests, unchanged acceptance, and a separate initially unchecked checkbox. This preserves existing application policy and requires no new product decision.

The reviewer found no other material issues in geometry, native/series colour and alpha handling, protection inheritance, strict persistence, comparison targets, editable exports or bounded resource requirements. Initial verdict: ready after the gate amendment and targeted recheck. Runtime, photographs and acceptance were not evaluated.

Targeted recheck: the same second reviewer checked only the gate amendment against current contracts and confirmed **“Finding resolved. No material improvements recommended.”** The guard, zero-strength case, disable recovery, backend tests and explicit UI choice are consistent; no contradiction was introduced. Earlier unaffected review coverage remains applicable.

Final reviewed SHA256:

- Design: `df0d70f8ed35e909b85c4e43a60e7867d5efcb083701ec7306e18c3852fdee84`
- Plan: `0b8330d11758c964219b65664a1347382b6942205c8e024617aab674db82ba00`

All three material findings across the original two independent passes were addressed for that oval-only candidate. This historical readiness does not cover the subsequent arcs amendment and was never runtime readiness or photographic acceptance.

## Original planning verification

Documentation checks passed: seven implementation tasks, required Superpowers header/constraints/review-focus sections, unchecked execution steps, all relative document links resolving, no trailing whitespace/conflict markers/private source paths in tracked-candidate documents, and `rtk git diff --check` exit zero. Package configuration was inspected; no distribution was built. Application suites were not run for this documentation-only task; the project's compatible `.venv` was absent.

Four pre-existing modified QA-plan documents changed concurrently during review; this task did not edit or revert them. Source HEAD remained unchanged and no application-source changes appeared in status. The new design, plan and review record remain separate files. A private case map was added only under ignored `local/evaluations/fade-into-background/`; no photo bytes or original projects were changed.

## Oval-plus-arcs amendment — self-check

User scope: one Fade into background effect, with oval only, independent arcs only, or both. Retain all previously agreed colour/export, source/alpha/protection, Shadow fade and mode-replacement contracts.

- Added bounded one-sided parabolic arcs, position/rotation/span/bend/direction/transition/end-softness/strength, stable IDs and group/individual switches.
- Defined strongest-wins reduction before one RGB blend, no trailing taper, local monotonicity and explicit limits at softened ends and overlapping shapes.
- Updated exact settings/algorithm, one combined W16, full-field replacement, inactive-state recovery and zero-shape/zero-strength accepted-base behavior.
- Updated render/export/framing tests, selected/combined/effective overlays, keyboard/canvas authoring and honest pending-versus-saved preview state.
- Added full actual-petal and branching checks for all three configurations, overlap seams, soft ends, strict limits and resource observations.
- No shipped spatial format exists to migrate. No application code or photo was changed; the 32-arc cap bounds this proposed local editor without a new dependency/framework.

## Amendment pass 1 — independent Ponytail review

Reviewer: fresh read-only `oval_arcs_ponytail_review`, using the explicitly requested Ponytail review skill. Candidate hashes were unchanged from start to finish:

- Design: `51d5960950ae7af65d0dc7bf82d1aae31f2c57fa28d2724903b9ef9a64534cd1`
- Plan: `d65e30d8f9b440c70f4b373b4eca81ff3e8398f9a63c67ed662ae0137e3aa1dc`

**What this change does:** Builds one reversible background fade from an optional oval and up to 32 independent arcs, combines their strengths once, and preserves editable source data and alpha across native/framed/export/UI behavior.

**Must fix 1 — an empty arc list must not disable the oval.** The controls paragraph said an empty arc list produced zero added fade, conflicting with oval-only use and the maximum equation. An implementer could add an empty-list early return that bypassed a valid oval. Require zero contribution from the arc group only and test a master-enabled oval at strength 0.6 with an empty list under either arc-group switch value.

Disposition: accepted. Coordinator verified the contradiction against the maximum equation and corrected the design. Task 1 now requires C=0.6, W16=39321 and q=0.6 beyond the outer ellipse for both empty-list group-switch states, then zero after disabling the oval. Related wording now distinguishes master switches from shape/group switches and retains W on master-only changes.

No additional material findings. Reviewer inspected both complete candidates, geometry/end behavior/max overlap, strict settings/IDs/inactive-state persistence, complete-field replacement, native foreground ownership, effects inheritance/locks, hashing/semantic caches, framing/resources, README/contracts and relevant tests. Assumed one local photo/viewer with bounded concurrency, 32 arcs plus one oval.

Initial verdict: fix 1 first. This correction precedes pass 2. No application edits or suites, photo evaluation or resource measurements occurred. The reviewer correctly noted that an empty tracked Git diff does not validate these untracked candidate documents; direct content/link/whitespace checks are required.

## Amendment pass 2 — fresh independent review

Reviewer: separate fresh read-only `oval_arcs_final_review`, independently checking the updated design/plan against connected owners and existing tests. Candidate hashes remained unchanged:

- Design: `813fbe14162a05164062ce20ba0ff72f825aff1a8639d957bf19db64f9d3f885`
- Plan: `0f63534427836ae007dd997225a8a55e7a579997884f7072ee45f6454f93e95f`

**P2 — resolve actual editable-layer delivery for framed outputs.** The design promises editable unfaded layers with transparent exports, and Task 3 refers to framed editable delivery inventories. Current `file-contract.md` defines compact Add-margins/series-framed bundles without native editable rasters; `_export_framed` only records project-relative native-asset hashes, and existing tests enforce the presentation-only file set. Those references do not deliver editable layers to a recipient. Silently retaining references would weaken the user's explicitly selected requirement, while copying native layers into framed bundles changes their packaging contract and size.

Disposition: verified by the coordinator against `file-contract.md`, `_export_framed` and native export ownership. A material packaging question was presented to the user: retain compact framed output and actually deliver a separate native editable export, or include editable layers inside every framed bundle. The answer must be incorporated consistently with exact delivered files, identity, admission/publication behavior and independent replay tests before readiness. It is not an implicit approval to weaken the requirement.

The reviewer found no other material gap in arc endpoints/plateaus, maximum-before-blend, empty groups, settings/IDs, protection, native P/A/Q sampling order, stale identity or saved-versus-pending UI. Inspected complete candidates and relevant geometry, renderer, inheritance, validation, recipe, framing, viewer/export and existing test definitions. Local HEAD remained `df7921d31aa4d3a84596856d8f0b164ae4292c7d`. No application suites, actual browser/photo evaluation or external actions occurred.

Readiness at this pass: pending the user packaging decision and a targeted review of the resulting amendment. Other unchanged coverage remains applicable.

## Amendment verification and readiness

Direct checks passed for candidate links, whitespace, conflict markers, absence of private source paths, seven implementation tasks, required Superpowers sections, unchecked execution steps, obsolete-algorithm removal and the explicit empty-arc regression contract. A standalone standard-library calculation verified the documented arc anchor values, both fade directions, bend extremes, lateral softness and maximum quantization; this is design arithmetic, not an application test.

The user subsequently selected: “Keep the framed bundle compact and also deliver a separate native editable export (Recommended).” This resolves the packaging decision without weakening editable-layer delivery.

## Packaging amendment and targeted recheck

The design and Tasks 3–6 now require an actual native companion for every framed export whose revision contains a spatial record, including OFF/zero-strength settings. Native-only exports remain single-folder; legacy no-record framing retains its exact behavior. Compact member sets remain unchanged. The companion carries the real existing native layers and four new spatial operands; the compact manifest binds its exact manifest and complete file inventory. Portable reconstruction tests copy only the two delivered folders, with the original project unavailable; native/exact-margin replay is owned by Task 3 and active-series replay by Task 4.

The amendment specifies one writer lock and a shared native helper, native-first durable publication, explicit partial/uncertain results, exact collision-safe reuse, no destructive rollback, combined disk admission, sequential scratch accounting, and visible paths for both outputs. Native recipe/notes remain native editable material; no source/project tree or local evaluation metadata is added. This is layer/render portability, not a new full-project import/history feature.

Candidate submitted to the existing second independent reviewer for affected-scope recheck:

- Design: `395d74e23e30fc0b0a4181dee4475698839263558a065012352a9229a24cb6dc`
- Plan: `367b025e0dbfb1782a6dde8bc7266389be515b4079ec1f066b20e3c6f671adfa`

Targeted independent recheck by `oval_arcs_final_review`: **“No material improvements recommended.”** The earlier P2 is resolved. The reviewer checked actual native/framed exporter ownership, series resource/sampling contracts, viewer status handling, canonical file contracts and relevant test definitions. Both start/end hashes matched the candidate above. Actual portable files, complete identity binding, native-first durability, partial results/retry, admission, privacy, legacy compatibility and task ordering were covered. Prior unchanged geometry, persistence and UI coverage remains applicable.

Coordinator verification: the amendment matches the user's selected separate-companion option, keeps the current compact file inventory, reuses the canonical native exporter under one lock, and assigns independent replay and interrupted-publication tests to their implementation owners. Direct checks passed for all three planning documents' relative links, whitespace, conflict markers, final newlines and absence of private absolute source paths. Seven implementation tasks remain unchecked; the obsolete wording that implied editable rasters inside framed folders is removed.

**Final status: ready for implementation planning handoff.** Both requested independent stages and the targeted resolution pass are complete, with no unresolved material plan findings or design decisions. This is planning-only evidence: no application code, tests, actual browser/photo evaluation or export replay was executed. Runtime correctness, resource observations and human photographic acceptance remain future implementation checks. Application implementation still requires the user's subsequent execution instruction; no Git writes or external publication are authorized by this plan.

## Documentation completion clarification

The user's subsequent request to ensure proper feature documentation strengthened Task 6 and the completion criteria: a discoverable practical offline guide for oval/arcs/both, actual control/overlay/export/recovery steps, assisted-use guidance, canonical asset contracts, and observed evidence/limitations in `docs/validation.md`. Written steps must be checked during the already-required browser/offline and paired-replay verification, avoiding duplicate expensive runs. Task 7 cannot declare completion with those documentation deliverables outstanding.

This clarification changes documentation obligations only; geometry, rendering, persisted settings and paired-delivery semantics remain unchanged. Prior independent reports remain applicable to those scopes; no additional independent review of this documentation clarification was run. The updated plan SHA-256 is `f0e23e211adaf627357fc217410c161b5b8fd8a57f92a795bd114814721e966a`; the independently reviewed design hash remains unchanged. The plan remains a seven-task Superpowers implementation plan, not a separately structured feature-increment delivery plan.

## Implementation execution

The subsequent user instruction authorized the bounded seven-task implementation,
documentation and verification in an isolated worktree with one persistent owner.
A later instruction selected the existing environment and authorized an MR after
implementation, followed by waiting for CodeRabbit and addressing appropriate
findings. No merge, model download, private upload or recovery deletion is authorized.

The implementation was isolated from the original dirty checkout. The first
review covered all 28 tracked/untracked feature files against baseline `df7921d`;
after repair, the owner checkpoint was integrated with current main `1704b8e`.
The second review covered the complete committed plus worktree candidate against
that main, including connected callers and documentation, rather than HEAD alone.
Settled checks passed: Ruff lint/format, mypy (22 source files), pytest 923 passed /
3 optional model-cache skips, exit 0, and whitespace checks. Exact environment
limitation: Pillow 12.3.0 versus the repository pin 13.0.0, as selected by the user.
The [validation record](../../validation.md#fade-into-background--implementation-evidence)
separates synthetic/reconstruction checks, real browser observations, private photo
evaluation, measured resources and pending human/branching-photo acceptance.

### Implementation stage 1 — explicit Ponytail review

Fresh read-only `fade_ponytail_review` used `ponytail:ponytail-review` and checked
the complete implementation and connected behavior. Two concrete material findings:

1. Spatial OFF comparisons checked only the viewed revision for stale effects,
   unlike the ordinary image route's working-or-viewed policy. An earlier accepted
   revision could show unrelated effects while labelled BASE. Owner reproduced
   and unified foreground, shading, background and effective-map stale handling,
   with working manifest identity rechecks and earlier-revision regressions.
2. Reusing a native companion left a new complete duplicate staging folder after
   each successful export. Owner reproduced and added cleanup of only the current
   verified duplicate after durable reuse. Failed, uncertain and older evidence
   remains preserved; repeated-layout/retry and injected-failure tests cover it.

Both findings were verified and repaired; RED 5 failed, focused GREEN 2 stale
comparison tests and 6 reuse/recovery tests passed. No finding was rejected or
deferred. The full integrated suite above includes these fixes.

### Implementation stage 2 — different regular engineering review

Fresh read-only `fade_engineering_review` formed its own conclusions without
reading the Ponytail report. One P2 finding: after switching from spatial fade
back to inward shading, retained disabled spatial metadata replaced native
manifest/README reconstruction instructions with a formula omitting H. Actual
pixels were correct, but following those instructions differed by up to 3425
channel levels at four pixels.

Owner verified and fixed selection of instructions by active mode and clarified
the file contract, including H before series sampling. New native/margin/series
regressions copy delivered folders, make the original project unavailable, and
follow the actual delivered formula with nonempty affected partial-alpha pixels.
RED 3 failed; GREEN 3 passed. The affected export/reconstruction suite then passed
280 tests, exit 0, with no warnings; Ruff lint/format and mypy22source also passed.

The same regular reviewer independently rechecked only this repair and concluded:
**“F1 is resolved. No material improvements recommended.”** No other material
finding remained and none was rejected or deferred. Unchanged scopes were not
repeated. Review reports, exact inventories, patches, raw logs and dispositions
remain in ignored local evidence.

These reviews establish code-review outcomes, not exact-pin certification,
real-model inference, full HTTP/export memory measurements, accessibility
certification, editable branching-photo evaluation or human photographic acceptance.
