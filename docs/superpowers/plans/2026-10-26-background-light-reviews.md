# Background light planning review

Planning began 2026-10-26. Scope: the [design](../specs/2026-10-26-background-light-design.md) and [implementation plan](2026-10-26-background-light.md), based on local `main` at `db907cf4603b1a8d40eabb7c32aa0937de1852df` (tree `519da182d9efd59fe375f6be51be7555e709d748`). No remote freshness or implementation approval is asserted.

## Decisions and scope

The user explicitly selected A: **keep the existing fade**. Both soft oval and broad directional gradient belong to Background light; the lit backdrop must never become the spatial-fade target. Source/selected foreground RGB, alpha, protection and existing effect operands remain unchanged by light edits. Translucent flattened appearance changes through normal backdrop composition. Existing Local exposure is documented as a separate optional technique, not automatically enabled or newly implemented.

Superpowers brainstorming and writing-plans guided the design and tasks. The incremental-plan skill's coherent-feature criteria informed sizing; no coordinated incremental program was generated. No new Ponytail pass was invoked. Earlier brush/appearance-recipe plans remain unchanged.

## Author checks

Checked requirements, exact field names and interfaces, task dependencies, current owners/callers, legacy and OFF behaviour, source fidelity, partial-alpha cases, diagnostics, native/series/companion replay, HTTP identity and draft preservation. The code already supports separate display/fade-target arguments and the documented Local exposure controls.

Clarified that rendered-pixel identity is distinct from changed saved/export metadata; the directional centre has half linear weight, not half encoded brightness; directional defaults are explicit; zero brightness/black tint must bind zero saved pixels. These are planning corrections, not claims of implemented behaviour.

## Separate independent reviews

| Reviewer | Assigned scope | Finding and disposition |
| --- | --- | --- |
| `background_light_preservation_review` | Fresh read-only builder/plan check: field geometry, compositing, source/alpha/protection, native/crop/diagnostic/transparent/series fidelity. | P2: inverse series mapping omitted pixel-edge to pixel-centre conversion. Fixed design and Task 2 with `x_native=(X+0.5-tx)/scale-0.5`, corresponding y, canonical full-output preview indices, and both-shape scalar registration tests. Reviewer checked the affected correction and confirmed resolved; no other material improvements recommended within scope. |
| `background_light_lifecycle_review` | Fresh read-only plan check: persistence/version compatibility, cache/export/recovery, HTTP/UI drafts, exposure documentation and increment sizing. | P2: Turn light OFF could accidentally save or reject pending edits. Fixed saved-only OFF, exact field inheritance, retained valid/invalid/stale drafts, repeated reuse and no-record handling, with corresponding test obligations. Reviewer confirmed the substantive correction and requested one final wording clarification: “Light OFF comparison creates no revision.” The author applied and checked that exact clarification. No other material improvements recommended within scope. |

Both reviewers inspected the proposed documents against actual local source and did not consult previous verdicts, access private photos, mutate files, run application tests or invoke external review services. Root verified decision-relevant code evidence and applied fixes sequentially. Only affected scopes were revisited; no extra generic review layer was added.

## Increment recommendation

One complete feature increment, with three internal tasks: field/composition, persistence/all consumers, and manual controls/documentation. The central invariant is one unchanged foreground contribution plus a separate lit backdrop. Saving/export/recovery and every renderer must implement it together. Both shapes share that complete contract; a temporary partial release is not required. The reviewer agreed with this sizing. Optional exposure guidance belongs with the workflow documentation and requires no new exposure feature.

## Verification and limits

Documentation checks cover local Markdown links, whitespace, file existence and final source/plan hashes. Product code, maintained user manuals, photos and Git history were not changed. No application/browser/photographic or export-replay tests ran; the plan records those as future implementation obligations. This checkout has no `.venv`, so proposed runtime commands require a verified authorized implementation environment. AI comparison images were explanatory only.

Final reviewed substantive candidate (including the author's exact comparison-wording correction):

- Design SHA-256: `497806d016969c73b5d511388dd14aaa791bb910de1a3b50a920cc9569182a52`.
- Plan SHA-256: `75fc6c9c731292f3652ecc0d019629f6dd11e640ce36c3a41f14a12ee1dc4e32`.

Planning is complete. Implementation, private-photo trials, Git writes and publication remain separate actions requiring applicable user authority; these reviews supply evidence, not that authority.
