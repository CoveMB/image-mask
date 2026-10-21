# Independent review of fixed-size series framing

Date: 2026-10-20. Scope: review and bounded repair of the written design, plus a recommendation about delivery structure. No product implementation, new user-owned thread, Git action or external publication was requested or performed in this review.

## Candidate, assignments and evidence

- Reviewed document: [fixed-size series framing design](../specs/2026-10-20-series-framing-design.md).
- Original candidate SHA-256: `f56f87af5b50c037883e8d5d81114ebfbceb3d96ddb02b338f655843c3e5118f`.
- Application comparison baseline: `90829e007f8af677a8ef29694a3f81494b1f07f2` on `framing-and-margins` in the verified application checkout. Remote state was not refreshed.
- `/root/series_rendering_design_review`: fresh-context, read-only review of photographic integrity, continuous geometry, alpha/resampling, background/preview semantics, resource implications and relevant test oracles.
- `/root/series_delivery_design_review`: distinct fresh-context, read-only review of requirement fidelity, UI/API/storage compatibility, export identity, scope and proportional delivery structure.
- Root waited for both final reports before editing, checked their concrete examples and canonical call sites, and owns the document changes. Neither reviewer edited files, ran the application or spawned other agents. Configured model defaults were used.

The application was initially clean. During the reviews, a separate existing framing repair owner modified `tests/test_framing.py`; the original framing handoff records its successful-export-reuse scope. Reviewers excluded those edits and bound their remaining baseline reads to the frozen commit. No permission or completion claim is inferred from that separate task. Before series implementation, reconcile its resulting predecessor and affected export interfaces/evidence.

This record reconciles the material reports; it is not a claim of product correctness or a verbatim command transcript. The independent reports are also retained in their native agent contexts. Current source inspection, official documentation and the two standalone arithmetic checks below are the evidence; no new application test, rendering experiment, browser journey or photographic assessment ran.

## Findings and dispositions

### R1 — Uniform geometry and filter support were underspecified (P2)

Rendering reviewer identified that the original design's independently integer-sized subject rectangle could distort thin features and contradict minimum clearances. A `10000 × 1` subject at uniform scale `0.4` has height `0.4`, whereas resizing its tight crop to `4000 × 1` uses a different vertical scale. For `H=5001` and 5% minimum top/bottom, geometric clearances are `250.05`; integer clearances require 251 each, leaving 4499 rather than ideal 4500.9. Root independently checked these decimal examples; the command exited 0. This was arithmetic validation, not image processing.

Tight subject cropping also changes boundary sampling unless full transparent filter support is retained. The [pinned Pillow resampler](https://github.com/python-pillow/Pillow/blob/13.0.0/src/libImaging/Resample.c) widens support for reduction and truncates/normalizes weights at finite input boundaries. Its [resize API](https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.resize) supports fractional source boxes; its affine transform API does not supply Lanczos.

**Correction:** design sections 5–6 now require one continuous uniform pixel-edge transform with fractional translation; integer rectangles are buffer envelopes only. Margins are measured against transformed original mask bounds, with filtered support clearly distinguished. All channels use the same fractional mapping and complete transparent sampling neighborhood. S1–S4 now require independent fractional-geometry, thin-subject, zero-padded impulse/edge and scalar-kernel oracles. Numerical tolerance and exact mapping/support implementation belong in the detailed plan before code. The original rendering reviewer confirmed design-level closure on the revised candidate identified below.

### R2 — Alpha and premultiplied colour needed a joint bound (P2)

Rendering reviewer identified that “bound filter overshoot” allows incompatible independent clipping. Negative Lanczos lobes can leave a colour contribution larger than alpha permits; unpremultiplication or compositing then produces clipping/fringes. A positive floating alpha may also quantize to zero in RGBA8 while leaving nonzero RGB.

**Correction:** section 6 requires finite filtered values, clamps alpha first to `[0,1]`, then clamps each RGB16-range premultiplied contribution to `[0,65535*alpha]`. The composed and transparent variants consume the same bounded pair. RGB is zeroed after RGBA8 alpha quantization wherever that quantized alpha is zero. S4 adds actual negative-lobe, contrasting partial-edge, nonblack-background and PNG-readback assertions. This is a testable presentation policy; native rendering and saved protected values are unchanged. The original rendering reviewer confirmed design-level closure on the revised candidate identified below.

### R3 — Preview and export could silently select different revisions (P2)

Delivery reviewer found that the existing viewer previews `viewRevision` but its framed draft export uses `working_revision` and accepted export uses `accepted_revision`. Existing `export_project` captures internally consistent state but has no caller-supplied expected revision-manifest argument. Root checked the canonical handlers and signature. Blindly reusing those handlers would not guarantee that series export uses the subject/layout shown in its preview.

**Correction:** section 4 now binds both series export buttons to the explicitly selected complete revision. Accepted export is enabled only when that selection is the current accepted revision; explicit draft export remains DRAFT. Requests carry expected master/revision-manifest identities with visible settings; canonical validation checks them under the project lock and before publication, including the accepted pointer when applicable. No silent substitution is allowed. S9 includes `selected != working != accepted` and manifest/acceptance changes between request and execution. Add margins retains its established behavior. The original delivery reviewer confirmed design-level closure on the revised candidate identified below.

## Findings not promoted into additional scope

Both reviewers found the current source/effect reuse direction sound. Explicit stale-effect rejection is necessary because the saved-layer reader supports a BASE comparison fallback; this requirement was already present and stays intact. Existing source-bound preset CAS/recovery provides a useful reuse pattern without changing the strict project-state schema.

Including every positive-alpha pixel, labelling enlargement and disclosing approximate reduced previews are reasonable intentional tradeoffs. They are not mathematical proof of photographic quality. Outlier removal, subject selection, automatic visual-weight adjustment, new dependencies and batch processing remain outside the feature.

Backdrop preview statistics require the full requested output grid's normalization even when only a reduced image is allocated. Section 6 now makes the output-size-dependent statistics pass and preview-latency measurement explicit. Regenerating the backdrop changes pixels beneath partially transparent subject edges too; that is part of the user decision below, not a review-approved change to photographic intent.

## Delivery recommendation

Use **one detailed Superpowers implementation plan in one fresh implementation thread, with one persistent owner and sequential checkpoints**:

1. **Usable canonical series export:** settings parser, continuous layout/rendering, resource admission, immutable delivery, CLI and file round-trip tests. Establish precision and sampling oracles before integration.
2. **Selected preset reuse/persistence:** explicit project save/reload and the chosen cross-photo mechanism, with parsing, concurrent-save, uncertain-write and preservation checks.
3. **Complete viewer workflow:** mode/form isolation, explicit selected-revision actions, delayed-response and bitmap lifecycle, production CSP, keyboard journey, complete export/reopen workflow and maintained docs.

The settings parser belongs in the first checkpoint because the CLI consumes it. Each checkpoint produces a testable outcome and carries its own relevant tests; end-to-end checks do not become a separate late testing task. The same owner can retain knowledge of the tightly coupled settings, identity and UI contracts. A final independent code review evaluates the implemented result, distinct from these design reports.

A separate formal incremental-plan/QA/handoff program would presently repeat the same small dependency chain and add coordination overhead. It becomes worthwhile if an app-wide catalog grows into independently useful shared storage, separately released stages or per-stage user gates are wanted, or scope broadens materially. A fresh thread does not require an all-at-once patch: it can complete the three checkpoints sequentially in one coherent feature branch.

No new thread or execution was started by this recommendation. No ledger, controller or scheduler is needed; use plan checkboxes and retained ordinary evidence. Preserve configured models, sequential writes, material-decision gates, and separate Git/publication authority.

## Decisions and readiness at the original review

Still awaiting the user:

- Portable preset file versus an app-wide named catalog. Portable is the current recommendation, not an inferred answer.
- Regenerate the saved background recipe at the output dimensions, including its effect beneath partial-alpha edges.
- Approval of the revised written design, then review/authorization of the detailed implementation plan and its execution method.

The earlier framing program's Gate 2/3 and reviewer amendments are not evidence that this new design/result was accepted. The selected Superpowers workflow requires written-design approval before its detailed build plan. The present request authorizes review and repair of this design; it does not itself answer the two product choices.

## Targeted closure and remaining evidence

Both original reviewers inspected revised substantive design SHA-256 `9e91cf9486ba317271c402eab7360471a46a652f62a0ce5d5e560ee3e53fdec8`:

- Rendering reviewer: **R1 and R2 closed at the design level.** “No material improvements recommended within this targeted scope.” Exact source-box mapping, scale-dependent support, float64 tolerance and bounded-buffer details remain explicit obligations for the detailed implementation plan, not new design defects.
- Delivery reviewer: **R3 closed at the design level.** “No material improvements recommended.” The one-thread/three-checkpoint recommendation and parser placement were confirmed.

Unchanged review coverage remains applicable. Root subsequently changed only the design's review-status checkbox; it did not change the reviewed behavior, source/QA mapping or outstanding decisions. These two independently closed scopes complete the requested design review; they do not approve the feature or certify runtime behavior.

Source/QA reconciliation: corrected R1 maps to sections 5–6 and S1–S3; R2 to section 6 and S4–S5; R3 to section 4 and S9. Existing S6–S8 and S10 continue to cover reproducibility, persistence/recovery, resource/publication safety and native compatibility/human inspection. Preset-specific proof depends on the user's storage choice. Numeric kernel tolerance, bounded-buffer measurements, actual browser runs and photographic validation are planned evidence only.

Retain this review record, the design and native reviewer reports for the future implementation handoff. Existing framing proof, private photo assets and the other task's repair remain untouched; no cleanup or publication occurred. Do not count historical framing passes as new series-framing test results.

Final document verification exited 0: both local cross-links resolve, code fences are balanced, no placeholder markers remain, all ten S1–S10 coverage rows are unique, and replacing only the final review-status checkbox reproduces the exact independently reviewed candidate hash. The final design SHA-256 is `7cea0e2bcfb8c862a16744a248dc019a400b5a9965ee8b0ce68b1ae09a3ddf13`. These are document checks, not application tests.

At final observation, the other framing repair had changes in `src/blackmask/export.py`, `tests/test_framing.py`, `docs/file-contract.md` and `docs/validation.md`. This task did not write those files or review that repair. The future series executor must reconcile that actual predecessor rather than implementing from the earlier clean snapshot.

## Current orchestration checkpoint — 2026-10-21

This section records the resumed orchestration; the preceding review report and candidate hashes describe their original historical scopes. Current task authority requires the preset/backdrop decisions, written-design approval and then approval of a detailed implementation plan before product implementation. Earlier framing approvals and completed reconciliation publication do not approve this feature.

- [x] Read current repository instructions, written design and both original design-review scopes.
- [x] Verify the actual application checkout: local `main` and locally stored `origin/main` at `14e8c83fa3b5a7603c5c240eb96a0081702da0f5`; clean before branch creation. No remote refresh performed.
- [x] Create the explicitly authorized `series-framing` branch from reconciled main. No staging, commit, push, merge, PR, download or other external action performed.
- [x] Reconcile repair `2a6029dfeda8f2aa4fe03f2bb3b9e730cab86404` through predecessor `ee9a3d1`. The persistent owner's read-only pass found no repair blocker; root checked the current canonical cleanup path and independently confirmed all four repair-body hashes and 44/44 full-suite input hashes match the preserved evidence.
- [x] Establish one persistent implementation owner, `/root/series_implementation_owner`, initially read-only. Root owns this bounded planning-document reconciliation; subsequent implementation uses that same owner with sequential writes and configured model defaults. No recursive delegation, controller, ledger or scheduler.
- [x] Resolve cross-photo preset storage: the user selected portable preset files. The project stores an independent snapshot; an app-wide catalog is excluded.
- [x] Resolve output-size backdrop regeneration: the user selected regeneration of the saved recipe at final dimensions, including the disclosed effect beneath partial-alpha edges; the native saved backdrop stays unchanged.
- [x] Obtain approval of the updated written design: the user approved the presented stage on 2026-10-21 and explicitly requested final documentation of controls, portable JSON contents/operation, Match series mechanisms and relevant implementation behavior.
- [x] Use Superpowers writing-plans to prepare the [detailed three-checkpoint plan](2026-10-21-series-framing.md), including exact fractional mapping/support, separate geometry/arithmetic oracle targets, source/QA coverage and evidence obligations.
- [x] Obtain user approval of the detailed plan: on 2026-10-21 the user approved, preapproved intermediate gates and requested finishing and creating the MR for their review. The existing persistent-owner method remains selected; necessary feature commit/push/MR authority is now explicit, with no merge authority.
- [x] Checkpoint 1: precise subject layout, resampling and reproducible safe exports, with relevant tests.
- [x] Checkpoint 2: portable preset reuse, project persistence and recovery, with relevant tests.
- [x] Checkpoint 3: viewer controls, selected-revision consistency, actual browser verification and maintained documentation.
- [x] Independent code review, owner-applied material fixes, relevant final verification and source/QA/evidence reconciliation. Photographic acceptance remains with the user.

Repair evidence remains in the preserved ignored predecessor archive, under `local/plans/framing-and-margins/pr16-feedback/` relative to that archive's checkout; its host-specific location is retained only in local evidence/native reports. The persistent owner verified all seven result/log pairs against the candidate manifest. `deterministic-full-result.json` records exit 0, unchanged inputs and 44 input hashes; `deterministic-full.log` records **699 passed, 3 skipped**, with no deselections. The skips require explicitly installed SAM/ViTMatte caches. Focused RED recorded 3 failures/2 passes (exit 1), GREEN 5 passes (exit 0), and lint, formatting check and mypy each exited 0. The earlier formatting operation records changed inputs honestly; later records bind the final inputs. No baseline suite was rerun on unchanged test inputs. These are inherited results, not current series-framing test, browser, resource or photographic evidence.

The current repair at `export._export_framed` preserves validation and synchronization failures for recovery, and removes only a verified duplicate after durable reuse. Existing `export._foreground_contribution` already owns the required contribution arithmetic; the design now explicitly reuses it. At that prerequisite review, the new caller-supplied expected source/revision identities remained unimplemented series work; they are now implemented and covered by the current plan's checkpoint evidence. Native/Add margins contracts and the three independently reviewed geometry, alpha and revision-binding corrections remain required.

Public documentation was refreshed on 2026-10-21 against the existing pinned stack: [Pillow 13.0.0 modes](https://pillow.readthedocs.io/en/stable/handbook/concepts.html), [resize and fractional in-bounds boxes](https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.resize), [the pinned resampler's support/normalization](https://github.com/python-pillow/Pillow/blob/13.0.0/src/libImaging/Resample.c), [W3C compositing](https://www.w3.org/TR/compositing-1/#simplealphacompositing) and [dragging alternatives](https://www.w3.org/WAI/WCAG22/Understanding/dragging-movements.html). The reviewed direction remains applicable; explicit zero support outside captured pixels and actual precision/latency/resource/browser tests still belong in the detailed plan. No dependency change, new rendering experiment or accessibility certification is implied.

The same persistent owner supplied read-only numerical/resource planning support. Current pinned Pillow source confirms float32 resize boxes/subtraction and scalar pass storage, so the detailed plan separates ideal geometry from effective-box arithmetic and defines pre-integration targets and stop conditions. This is source inspection, not a resampling experiment or precision result. Root owns plan authoring/self-review. The retained interpreter was inspected without installation: Python 3.12.14 ARM64, matching pinned Pillow/NumPy/tifffile, with Ruff/mypy present; this checkout has no `.venv`.

Preserve ignored local data and historical branches without merging photographic/reference ancestry. The unrelated dirty `AGENTS.md` in the separate stack worktree was not touched. The two product decisions, written design and detailed plan are now approved for execution. Photographic acceptance remains with the user; no private-photo evaluation or MR merge is authorized. Product implementation begins after this approval record.

Execution checkpoints and independent review are complete. The [current implementation plan](2026-10-21-series-framing.md) and [maintained validation record](../../validation.md#fixed-size-series-framing) own the final source/test identities, actual browser observations, numerical/resource evidence, full/static results and bounded formatting correction. Their explicit inference, browser, extreme-size, accessibility and photographic limitations remain in force. Git/publication handoff belongs to root; photographic acceptance remains with the user.
