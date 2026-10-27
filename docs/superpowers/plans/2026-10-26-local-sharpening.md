# Local Sharpening Implementation Plan

Publication status (2026-10-26): this implementation is delivered and merged through MR29. The tasks and permission boundaries below record its earlier plan; unchecked boxes do not reopen completed work. See [current delivery and remaining obligations](../../incremental-plans/single-photo-black-background-qa/plan.md#current-delivery-and-remaining-obligations).

> **For agentic workers:** Use superpowers:executing-plans for the single persistent implementation owner. The user explicitly selected a new native implementation chat with preapproved routine work. Read the reviewed design and private handoff first; use read-only specialists only for bounded independent review, with no recursive fan-out. Steps use checkbox syntax. Do not ask the user to choose the execution method again.

**Goal:** A generic, reversible local sharpening control for selected captured detail, with complete offline recovery and editable delivery.

**Architecture:** One alpha-aware linear-luminance kernel between cleanup and exposure, with noise/overshoot guards and scoped writes. Integrate it with existing typed effects, masks, revision/lock/cache and delivery contracts; no separate image editor, inference or dependency.

**Tech Stack:** Existing Python 3.12, NumPy, SciPy, Pillow 13 and tifffile, plus the existing localhost HTML/JavaScript viewer.

**Spec:** ../specs/2026-10-26-local-sharpening-design.md

## Global constraints

- Source/master pixels, alpha and registration are immutable under sharpening; protected and zero-support RGB copy exactly.
- Generic selected regions, not species-specific settings. The 0.5–8 native-pixel radius and 0–1 Amount apply across supported source dimensions; evidence must cover both ends.
- Settings exactly: enabled boolean; amount [0,1]; radius_px [0.5,8]; noise_threshold [0,0.02]. Defaults OFF / 0 / 1 / 0.001. No bool-as-number or nonfinite values.
- One adjustment; preserve existing drafts/locks/accepted revisions and saved-only recovery. No automatic acceptance or existing-data cleanup.
- Existing packages only; use retained approved runtime without reinstall/download or global activation claims.
- Original application checkout contains nine unrelated-to-sharpening approved SDR changes. Preserve them, their frozen patch and primary dirty/untracked planning work; implementation baseline is in the private handoff.
- Current grant permits local implementation/checks/fixes and one implementation chat. No Git publication/commits/provider actions or extension of old budgets. No material design waiver.
- Public design/plan use repository-relative paths; private runtime/source/photo locations belong only in the ignored handoff.
- Every shell command starts with rtk; use rtk proxy for exact capture. Preserve underlying exit/capture status; do not count truncated or interrupted output as a pass.

## Review focus

1. Nonlocal filtering with partial alpha can create colour/edge artifacts: Task 1 pins alpha-weighted neighbourhoods, finite halo, chroma/gamut and exact protected partial values.
2. Different detail sizes and JPEG-like noise can overfit one photograph: Task 1 covers fine/wide fixtures, radius extrema, suppression and perfectly sharp steps.
3. Multiple render/lock paths can omit or double-apply the effect: Task 2 covers matte/repair, locks, OFF/base, gallery, native and framed/series consumers.
4. New saved records can invalidate old recovery/export contracts: Task 2 covers absent/OFF legacy, stale/tampered operands, interruption, cache and independent saved-only replay.
5. Manual controls can display stale/unapplied settings: Task 3 covers keyboard/brush parity, displayed revision, unsaved draft preservation and comparison/reset without acceptance changes.

## Task 0: Reserve the correct baseline without touching existing work

**Files:** Read the private handoff, existing checkpoint and frozen source manifest/SDR patch. Create implementation evidence only under its ignored review directory.

- [ ] Verify exact checkout/head/tree/status and all baseline file hashes. Work only in the reserved isolated private application checkout, not the primary documentation branch. No other application writer may run.
- [ ] Preserve pre-feature copies/hash evidence of files to be modified and protected photo states. Retain the existing nine SDR changes in every overlapping file. Do not amend/reset/stash/clean or invent a branch.
- [ ] Verify retained Python/Pillow core and SciPy signature; use the handoff's offline environment and source path. Do not set up another environment or run installs.
- [ ] Read the existing focused/full-suite qualification and current CI/provider limitations. The full suite's recorded viewer lock race is a known baseline qualification, not authorization for adjacent fixes.
- [ ] If baseline/authority differs, reconcile it before writes. Routine in-scope decisions are delegated; a material new tradeoff goes to the human.

## Task 1: Implement and prove the canonical sharpening operation

**Files:** Create src/blackmask/sharpening.py and tests/test_sharpening.py. Reuse src/blackmask/exposure.py conversion/area helpers; modify shared helpers only if strictly required and preserve old arithmetic.

**Interfaces:** Proposed new functions:
- validate_local_sharpening(settings: Any) -> None.
- apply_local_sharpening(foreground: np.ndarray, alpha: np.ndarray, support: np.ndarray, protection: np.ndarray, settings: dict[str, Any]) -> np.ndarray.
- read_local_sharpening(project: Path, directory: Path, manifest: dict[str, Any], alpha: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict[str, Any]] | None.
- selected_local_sharpening(..., sharpening_off: bool = False) -> np.ndarray, following the current exposure/fade reader pattern.

- [ ] Write failing application arithmetic/round-trip tests for exact OFF/zero/empty/protection identity, including nonempty partial-alpha protected samples; invalid settings/registration must fail explicitly.
- [ ] Add independent small-fixture convolution checks for the design's formula, valid-alpha 3×3 extrema, zero denominator/Y, gamut-limited common-channel gain, constant colours and saturated/near-black values.
- [ ] Add fine blurred line, broad texture, smooth/noisy and JPEG-block-like fixtures; test radius 0.5/1/4/8 and threshold 0/0.001/0.02. Verify edge enhancement and noise-threshold suppression without requiring a perfectly sharp step to overshoot.
- [ ] Verify bounded strips against a separate full-frame reference across seams, odd dimensions, corners and cropped observation windows. Observe the native full-image operation before cropping; do not filter cropped previews independently.
- [ ] Run the new targeted tests RED, implement the one kernel/readers, then run GREEN. Capture actual failures/statuses.
- [ ] Measure a representative larger-dimension synthetic operation and account for kernel/support/RGB buffers and disk outputs. Resource failure must preserve usable state.

Target command, from the selected application using the verified retained interpreter: rtk proxy env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src <verified-python> -B -m pytest -q -p no:cacheprovider tests/test_sharpening.py. Substitute only the verified interpreter path from the ignored handoff; expected success is zero failures, not a prewritten count.

## Task 2: Wire persistence, every renderer and complete delivery

**Files:** Modify src/blackmask/recipe.py, effects.py, project.py, operations.py, export.py and review.py; inspect assets.py, repair.py, previews.py, framing.py, series_framing.py and library.py and change only actual consumers requiring integration. Extend tests/test_sharpening.py and relevant existing effects/exposure/shadow_fade/export/project/assets/cache/library tests.

**Consumes:** Task 1 kernel/readers and existing support/protection/identity contracts.
**Produces:** Exclusive schema-2 effects request and hash-bound optional sharpening record, one complete native adjustment, sharpening OFF comparison, inherited/stale/lock-aware selection and reconstructable delivery.

- [ ] Write RED end-to-end tests for apply/replace, old-area removal, amount-only, Reset, repeated non-compounding Apply, missing/OFF legacy byte preservation and invalid/unbound dependencies even OFF.
- [ ] Add strict optional recipe/record/request validation and shared asset registration. Extend effects equivalence/execution identities, effective recipe snapshots and disk/resource estimates. A warm hit must still validate actual operands and source/cleanup/alpha dependencies.
- [ ] Use the one kernel in selected foreground and the explicit prepare/matte/repair review path. Extend enabled-effect sets, lock snapshots, inheritance, stale gates, all-effects BASE and sharpening-only OFF. Prove unrelated pending drafts and acceptance remain intact.
- [ ] Test upstream cleanup changes with current input recomputation; changed alpha must block enabled appearance until explicit rebuild/reset. Test stale request/current-state races and interrupted state-last publication using synthetic projects.
- [ ] Add complete native/editable companion members: unsharpened_foreground_rgb16.tif; sharpening_support16.png, sharpening_protection16.png, sharpening_alpha16.png, sharpening_settings.json and authored sharpening_area.json when applicable. Keep selected/unexposed/unfaded meanings and replay order explicit.
- [ ] Reconstruct sharpening -> exposure -> fade -> shading/spatial/background composition from exported assets alone, with source/project/model paths unavailable, in a real child process using the actual retained Pillow core. Test native and framed/match-series companions, original-size and same-size PNG viewing copies.
- [ ] Exercise actual gallery/review/export consumers and new-reader compatibility. Preserve pre-feature data; do not claim old binaries are universally safe or strip new records. No automatic migration/schema expansion.
- [ ] Run focused affected application tests GREEN; retain still-applicable Task 1 evidence. Do not add a generic effect framework or refactor unrelated code.

## Task 3: Add the generic manual/assisted control and documentation

**Files:** Modify src/blackmask/viewer.py, ui/review.html, tests/test_viewer.py, test_viewer_page.py and test_viewer_coordinates.py as warranted; README.md, docs/workflow.md, docs/file-contract.md and docs/assistant-workflow.md own user/record/assistance contracts. CLI remains the existing typed run operation unless a verified caller requires a change.

- [ ] Write RED viewer request/revision/draft tests for area/amount/reset and exclusive field forwarding. Reuse native coordinate conversion and typed geometry.
- [ ] Add Local sharpening authoring, Amount, Detail size and Noise guard numeric/range controls with equivalent keyboard paths, explicit candidate comparison and clear saved/pending/stale status.
- [ ] Add Compare sharpening OFF that retains other effects, selects one comparison at a time and creates no revision. Reset retains saved area; neither operation accepts the photo.
- [ ] Exercise real browser control submission, native zoom/crop comparison, protection and failure recovery. Source/alpha panels must remain unchanged; status polling must not repeatedly filter the photo.
- [ ] Document supported controls, native units, bounds, limitations, generic examples, recovery and exact native/companion replay. Existing nine-path SDR documentation changes remain intact. Keep personal paths/private evidence out of delivered docs/archives.
- [ ] Run the affected viewer/coordinate and contract checks; inspect actual UI manually for usability. Automated tests do not establish accessibility or photographic quality.

## Task 4: Verify the settled batch and obtain independent result review

- [ ] Run the complete relevant deterministic suite once on the settled tracked-plus-new candidate, with ruff check/format and mypy src using verified existing tools. Do not weaken assertions or describe a qualified failing suite as green.
- [ ] Reuse established packaging commands to build/inspect wheel and sdist without installs/dependency resolution; verify actual delivered contents and runtime parity, including absence of private plans/photos/paths/VCS data.
- [ ] Freeze exact candidate/hash/status and get fresh read-only reviews of source fidelity/compatibility and verification/lifecycle coverage. No recursive fan-out; the one implementation owner applies verified fixes sequentially. If two useful tracks are absent, a single bounded reviewer is enough only if applicable user instructions permit it.
- [ ] Read all relevant reports, verify material claims, fix in-scope findings and renew only affected scopes/checks. Material behaviour/compatibility changes require the user's decision despite preapproval.
- [ ] Record actual review dispositions and the local result gate under this direct user delegation; no invented approval, publication, paid review or inherited provider budget.

## Task 5: Bounded photographic trial and local handoff

- [ ] Only after Task 4, use supported project controls on the current private draft identified in the handoff, with fresh identities and a preserved pre-feature recovery copy. The implementation chat is the sole application/project writer for this trial.
- [ ] Explicitly author target/protected regions; inspect source-visible wings and protect non-target body/head regions. Keep alpha, crop, source development, colour grading, exposure and fade settings unchanged.
- [ ] Produce one mild draft; at most one stronger comparison after clear improvement. Stop on halos, texture amplification, ambiguity or no progress. Preserve all attempts and prior revisions.
- [ ] Inspect native matching source/alpha/black/gray/white and sharpening OFF views. Export a labelled draft with complete editable native layers and verify exact saved-only reconstruction.
- [ ] Report local code/check/review status, real-photo limitations, retained failures and exact result paths. Photographic acceptance remains human; broader private examples are not silently selected or processed.
- [ ] Leave commits, pushes, PR/provider requests, installation and merges untouched. No new monitor/controller/ledger; the parent reuses its existing checkpoint and monitor.

## Plan self-review and execution authority

This plan carries the genericity amendment: the engine and UI are subject-independent, detail scale is broader than the initial example, other effects may be OFF, and verification covers multiple structures/dimensions. The private photo is only a final bounded pilot.

Task/source/contract/verification review precedes dispatch. The user already selected a new implementation chat and preapproved routine implementation; do not ask that question again. Preapproval does not override a material unresolved design finding, data/privacy boundary or photographic acceptance.
