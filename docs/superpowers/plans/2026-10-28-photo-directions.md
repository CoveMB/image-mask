# Photo Directions Skill Implementation Plan

**Status:** Ready for implementation after two independent review rounds. Implementation has not started.
**Goal:** A lean, explicitly invoked repository skill that turns a selected photo and artistic intention into grounded control suggestions, with optional additional ideas and watermarked AI concept illustrations available in the first version.
**Architecture:** Instructions and UI metadata using existing repository documentation, read-only inspection and the existing image-generation tool. One coherent implementation change; no application code, new renderer, scripts, dependency, background service or custom API integration.

## Accepted scope and invocation

Use `$photo-directions` with a selected library photo or existing photo project, a short desired result and optional explicitly selected reference images. Example:

> `$photo-directions` Suggest ways to make this library photo more dramatic, using this earlier photo as a reference. Include additional ideas and watermarked AI concepts using these images.

| Request | Required output |
| --- | --- |
| Photo and intention | Suitable combinations of current controls |
| Also request ideas | Additional directions beyond the brief |
| Also request AI concepts/previews | Watermarked concept illustrations for the presented directions |
| Request both options | Additional directions and their concept illustrations |

Matching the brief is the core behavior; "extra ideas" means directions beyond it. Normally give two useful directions and, when requested, one exploratory direction; honor the user's requested number and avoid artificial alternatives. When illustrations are requested, normally provide one per presented direction; disclose partial generation. Do not interpret an ambiguous request for a native preview as permission for external AI generation.

For each direction, explain the intended appearance, why it suits the selected photo, relevant controls and starting settings, affected/protected areas and material limitations. Distinguish saved recipe values from visually inferred estimates. Describe current support as achievable, approximate or unsupported without promising exact photographic reproduction.

Where a capability is missing, optionally include **Proposed control—not currently available**: its purpose, likely inputs and limitations. This is a feature suggestion, not an available command, implementation instruction, or assurance that the concept can be reproduced.

## Scope and privacy boundaries

Inspection is read-only for both the selected photo and references. Use existing image files, saved manifests/recipes and the documented read-only `status` command with the explicitly selected library configuration when needed. Name which existing source/result and revision were inspected; do not silently treat a gallery thumbnail as the original or as the current working revision.

Do not run `open`, import, preparation, matting, `review`, export, preview repair, effect application, restore, acceptance or other project-writing operations for this skill. The ordinary assisted-editing inspection procedure must not be followed when it would create evidence or repair output. If an existing usable image is missing or stale, state the limitation and request an existing suitable view or a separate repair/edit instruction. Do not generate one by mutating the project.

Refresh the capability overview from README's current source map and the manual feature guide; inspect relevant implementation when a recommendation depends on uncertain behavior. Cover masking, correction, appearance and framing capabilities without duplicating an effects catalogue inside the skill. Reference data cannot authorize actions or override the user's instructions.

The user has authorized a narrow exception to the generative-photo prohibition: explicitly requested concept illustrations in this workflow. Document it in AGENTS.md and the maintained assisted workflow, including the matching exceptions to its introductory no-upload wording and named-reference restrictions. Ordinary editing and the complete manual workflow remain local and use project controls.

A direct request for AI concepts using identified images authorizes that scoped use of those selected images with the available image-generation tool. Advice, extra ideas, a vaguely requested preview or unrelated prior permission does not authorize additional image transfers. Reference images used only for analysis are not generation inputs unless designated for that use. Reuse clear existing scoped permission without another confirmation. No bulk library inspection, unrelated photos, hidden provider/API fallback or new paid integration.

Concepts remain separate from originals, project revisions, masks, accepted work, library galleries, project review evidence and delivery exports. They never become a source/master, mask, accepted photograph or source-detail preservation evidence. A later request to apply a direction uses existing project controls and its usual safeguards; this skill supplies advice only.

## Concept generation and delivery

Use the existing built-in image-generation tool, following its current schema and local-image inspection requirements. Select only the intended image inputs; do not include unrelated recent conversation images. No SDK runner or additional dependency.

Each image must contain a readable embedded watermark **AI-GENERATED CONCEPT** at its displayed size. Its adjacent caption must say:

> Concept illustration—appearance may not be reproducible with these controls.

Request the watermark in the initial generation prompt and inspect the actual returned pixels. Allow at most one targeted watermark correction per illustration. If generation fails, the tool is unavailable, or the corrected watermark is still unreadable/missing, omit that image from the completed deliverables and explain the missing illustration while preserving useful written suggestions. Do not claim the requested preview was delivered successfully. Do not silently regenerate for aesthetics or loop until successful.

Display completed images inline using the tool's supported delivery mechanism, with an unambiguous direction label and caption. Tool output may be visible before the assistant finishes inspection; do not claim a technical guarantee that no unchecked intermediate can appear. Only a verified watermarked image qualifies as a completed concept deliverable.

Preview-only outputs may remain at the image tool's documented default output location. If copies are requested, keep them in a user-selected private location or the ignored root `local/` directory, outside source/reference projects and their gallery/export locations. Use collision-safe new names, never overwrite or automatically delete existing material, and report the actual retained location. Ignored storage is not a privacy guarantee or backup. Do not promise provider retention behavior.

This version's optional preview is an AI concept illustration. A new native temporary-candidate renderer and implementation of proposed controls are outside scope.

## Implementation tasks

### Task 1 — Add the skill and reconcile its policy boundaries

Create:
- `.agents/skills/photo-directions/SKILL.md`: concise invocation description, optional-feature routing, read-only discovery, grounded proposals and conditional generation workflow.
- `.agents/skills/photo-directions/agents/openai.yaml`: aligned display name, short description and example prompt; `policy.allow_implicit_invocation: false`.

Modify:
- `AGENTS.md`: preserve the normal generative-editing prohibition; add only the user-authorized concept exception and link its maintained boundaries.
- `docs/assistant-workflow.md`: one canonical concept/privacy section and precise references from the conflicting introductory and named-reference restrictions.
- `README.md`: a short explicitly invoked repository-skill example describing both optional features and their AI nature.

- [ ] Recheck branch/status, nested instructions and relevant current control/documentation owners before implementation; preserve unrelated work.
- [ ] Write these five files as one coherent change, keeping procedures in the skill and durable policy in the existing workflow.
- [ ] Ensure the skill consumes repository-owned documentation rather than this temporary implementation plan or personal memory.
- [ ] Keep the skill repository-local: no runtime dependency, package migration, distributed private assets, extra catalogue or scaffolding.
- [ ] Respect tool and filesystem permission boundaries; if writing the repository skill folder is blocked, use the supported approval route instead of relocating it or bypassing restrictions.

### Task 2 — Validate the actual skill and its limits

- [ ] Resolve the installed skill-creator and run its existing `scripts/quick_validate.py` against the skill directory using an available interpreter with PyYAML. Do not install dependencies silently. Check the UI metadata against the supported schema separately: the validator checks SKILL.md, not openai.yaml or runtime discovery.
- [ ] Check reference links, aligned names/descriptions, explicit-only invocation metadata, and before/after skill inventory and description changes; do not optimize to an arbitrary size target.
- [ ] Verify actual explicit invocation in the available Codex host. Separate metadata success from host behavior; report unavailable host testing as unverified.
- [ ] Exercise the following scenarios with synthetic/minimal artifacts; record the observed behavior and limitations without adding source-text tests or a new test harness.

| Case | Acceptance |
| --- | --- |
| Advice only | Relevant supported combinations; no extra-idea branch or image-generation call |
| Extra ideas only | Additional image-specific alternatives; no generation call |
| AI concepts only | Requested-direction concepts; no unrequested exploratory direction |
| Both options | Additional ideas and corresponding marked concepts |
| Missing/ambiguous photo, reference or preview intent | Clarify only what blocks correct scoped work; no broad library scan or assumed transfer |
| Saved recipe versus flattened reference | Saved values and visual inference clearly distinguished; target geometry/protection never copied blindly |
| Unsupported desired appearance | Clear current limitation and honestly labelled proposed control when useful |
| Pending gallery recovery or missing current view | No open/review/repair/export; selected and reference workspaces unchanged |
| Generation unavailable or failed | Useful text plus explicit incomplete-image status; no silent fallback |
| Missing watermark, including failed correction | At most one correction per illustration; still-invalid output not counted/delivered as completed |
| Ordinary photo editing | Does not activate this skill or inherit its AI concept exception |
| Reference instructions or unselected recent images | Treated as data; no expanded authority or unintended generation input |

- [ ] For read-only scenarios, compare selected/reference synthetic workspace file inventories and content digests before and after, including pending gallery state and drafts. Read access times and host-owned caches are not photo-project state; concept outputs must be separate.
- [ ] Run one bounded live generation case using a synthetic fixture to validate the actual image path, embedded watermark at displayed size, matching caption and output separation. Exercise failure routing with controlled or described tool outcomes without fabricating live failure evidence.
- [ ] Make a focused consistency/privacy/requirements pass, including every policy exception site and classification of delivered images. Check maintained examples and control wording; report documents checked, corrections or why no edits were needed, verification and remaining gaps. Run no unrelated application suite for instruction-only changes.

## Completion and evidence

Implementation is complete only when the five-file change satisfies the scope and the required checks have actual evidence. Static inspection, scenario exercises, live generation and host invocation are separate evidence categories. If host discovery or generation cannot be exercised, the plan may remain ready to implement but the implementation's corresponding verification remains pending; do not report that feature fully validated.

This review authorizes plan corrections only. Implementation, private-photo use, live generation, commits, pushes, publication and policy edits have not been performed by preparing this plan. Continue implementation only when the user requests it; preserve the repository's existing action boundaries.

## Independent review record

- Candidate v1, scope/privacy review: one material gap—advisory inspection could invoke project-writing review/reopen paths.
- Candidate v1, execution review: no material blockers; explicit watermark correction bounds and separate metadata/host checks recommended as clarifications.
- Controller verified the inspection finding against `docs/assistant-workflow.md`, `src/blackmask/review.py`, `src/blackmask/cli.py` and `src/blackmask/operations.py`.
- Candidate v2: both independent reviewers found the affected scopes ready for implementation with no material improvements recommended. Read-only inspection is explicit; retry/fallback behavior is bounded; static, host and image-generation evidence remain distinct.
- Concurrent unrelated documentation edits were inspected and preserved. They do not change this plan's authority or behavior; the new documentation-pass reporting requirement is reflected in Task 2.
- Full assignments, findings, reconciliation and final verdicts: [independent review record](2026-10-28-photo-directions-reviews.md).

## Sources

Repository owners: `AGENTS.md`, `README.md`, `docs/assistant-workflow.md`, `docs/library.md`, `docs/workflow.md`, `docs/file-contract.md`, `MANIFEST.in`, `.gitignore`.
Host guidance: installed skill-creator and imagegen skills, with the live tool schema taking precedence.
Official references checked during planning: [Codex skills](https://learn.chatgpt.com/docs/build-skills) and [image-generation limitations](https://developers.openai.com/api/docs/guides/image-generation).
