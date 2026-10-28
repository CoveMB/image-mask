# Photo Directions Plan — Independent Review Record

**Outcome:** Ready for implementation. Two independent scopes completed two review rounds; no unresolved material findings or design questions.
**Candidate:** [Reviewed implementation plan](2026-10-28-photo-directions.md).
**Scope:** Plan review and correction only. No skill implementation, policy change, private-photo access, image generation, external review service, application tests or Git writes were performed.
**Baseline:** Local `main` at `89935daefcb3cc261ca6addf6d826045045dc5a5`, initially clean. Remote refs were not refreshed. Later unrelated documentation edits were inspected and preserved.

## Authority and assignments

The user requested independent review, iterated until the plan was ready for implementation. Their accepted feature scope includes a lean explicitly invoked repository skill; optional additional ideas and optional AI concept illustrations implemented in its first version; a narrow generative-photo exception for that purpose; watermarks; and honestly labelled proposed controls for currently unsupported appearances.

Two reviewers received the same original plan and direct-requirements packet, with no inherited conversation history. Both were read-only, with no recursive delegation, private-library access, image generation or external calls. The controller owned all revisions and verified decision-relevant source evidence.

- **Scope/privacy reviewer — `plan_scope_review`:** requirement fidelity, exception boundaries, image/reference authorization, isolation, output honesty, proposed controls and accidental project mutations.
- **Execution reviewer — `plan_execution_review`:** feasible lean file layout, discovery/metadata, current image tool compatibility, watermark delivery, bounded generation/failure behavior and verification/completion criteria.

## Round 1 — Original plan

### Scope/privacy report

**Verdict:** Not ready: one material plan gap.

**P2 — Define inspection as read-only (original section 2).** “Remain advisory” only separated effect application; following the referenced workflow could still mutate photo projects. [Assisted inspection](../../assistant-workflow.md#inspect-and-classify) directs inspection through `blackmask review`, which writes and publishes evidence in `src/blackmask/review.py` (lines 710 and 741 in the reviewed source). Configured `open` also invokes gallery repair through `src/blackmask/cli.py:283` and `src/blackmask/operations.py:1093`. Advice/concept invocation could therefore change selected or reference workspaces unexpectedly.

**Smallest correction:** Inspect existing files and read-only status. Prohibit imports, review/export generation, configured reopen/repair, effect application, restoration and acceptance during the skill. Missing usable images produce a limitation or request for an existing view. Add a pending-gallery case checking both selected and reference workspaces remain unchanged, with concept outputs separate.

This is a plan-boundary defect; implementation-time validation must still prove the skill obeys it. No other material issues were reported in the assigned policy, authorization, output-honesty or proposed-control scope.

### Execution report

**Verdict:** Ready for implementation in the assigned execution scope. “No material improvements recommended.”

The five-file layout is sufficient. The source map supports current-control discovery; the built-in generation tool supports concepts without a new renderer, API integration, scripts or dependencies. Preview-only output can remain at the tool's default location and render inline under the installed guidance.

A numeric watermark correction limit was initially considered a possible gap. On full review, the existing no-retry-loop and written-fallback requirements already bounded intent, so the reviewer treated an explicit one-correction limit as clarification, not a blocker.

Implementation obligations identified:
- Explicit-only metadata and actual explicit invocation need separate verification. `quick_validate.py` checks `SKILL.md`, not `agents/openai.yaml` or host discovery.
- Follow the live image tool schema rather than conflicting installed guidance. Inspect local inputs; select only authorized images.
- Exercise synthetic generation, inspect the embedded watermark/caption and keep output separate.
- Exercise unavailable generation and persistent watermark failure without repeated generation or silent fallback.

The reviewer inspected repository instructions, current documentation/source map, packaging/ignore configuration, installed creator/metadata/validator/imagegen guidance and the live tool contract supplied in the packet. No live checks were run.

## Controller reconciliation and candidate v2

The controller independently inspected the relevant source:
- `review.py` writes the staged manifest and publishes review artifacts.
- Configured headless `open` calls `reopen_project_status`, which calls `refresh_result_preview`.
- CLI `status` calls `operation_status`.
- Existing test source includes `test_read_only_status_of_imported_project_does_not_write` in `tests/test_library.py`, plus unchanged inventory during pending preview status in `tests/test_previews.py`. These tests were inspected, not executed in this plan review.

**Accepted material correction:** Define read-only inspection and verify both selected and reference workspace preservation, including pending recovery and drafts.

**Accepted clarifications:** At most one targeted watermark correction per illustration; honest failed/partial delivery; tool intermediates may be visible before final inspection; separate static, host-invocation and live-generation evidence; exact repository-local file ownership and completion obligations.

The correction did not add application code, dependency, renderer, scripts, or an implementation of proposed controls. No material finding was rejected or deferred.

## Round 2 — Targeted independent re-review

### Scope/privacy report

**Verdict:** “Ready for implementation in the reviewed scope. No material improvements recommended.”

The prior finding is closed by Scope and privacy boundaries and Task 2: inspection excludes project-writing `review` and configured `open`, and verification checks both selected and reference workspaces remain unchanged. Generation provisions preserve the optional features while limiting inputs to authorized images and separating concept output. Actual invocation, generation and preservation remain implementation-time verification.

### Execution report

**Verdict:** “Candidate v2 is ready for implementation within this review scope. No material improvements recommended.”

The reviewer confirmed:
- One watermark correction followed by explicit incomplete-delivery reporting is a clear stopping condition.
- Delivery wording distinguishes inspected completed concepts from potentially visible intermediate tool output.
- Read-only inspection is feasible; CLI status routes and existing unchanged-inventory test cases support the proposed approach.
- Metadata, host invocation, scenario exercises and live generation are separate evidence categories.
- Implementation remains five instruction/metadata files without application machinery.

Actual host discovery, synthetic workflow preservation and live watermark delivery remain implementation verification obligations, not planning blockers.

## Concurrent documentation changes

After round 2, the working tree acquired unrelated edits in `AGENTS.md`, `docs/assistant-workflow.md`, `docs/file-contract.md`, `docs/guidance.md`, `docs/troubleshooting.md`, `docs/validation.md` and `docs/workflow.md`.

The controller inspected their diffs. They clarify maintained controls/contracts and require reporting the documentation pass for feature/control changes. None changes the reviewed read-only or concept-generation boundaries. Task 2 now explicitly includes reporting documents checked, corrections or no-edit reasons, verification and remaining gaps. No unrelated file was edited or reverted by this review.

## Readiness limit

“Ready for implementation” refers to the plan, not to an implemented or operational skill. Neither independent reviewer ran image generation, host discovery or private-photo operations. The final plan retains those separate validation obligations and preserves the user's authority over implementation and external actions.
