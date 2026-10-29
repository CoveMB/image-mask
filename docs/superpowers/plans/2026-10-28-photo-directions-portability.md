# Photo Directions Portability Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` for the recommended native sequential execution, or `superpowers:subagent-driven-development` if the user selects that method. Repository authorization boundaries override automatic implementation, Git or external-action steps. Checkboxes record actual work, not planned success.

**Current status:** Local implementation and focused reviews are complete, including the accepted C2 delivery correction. Native V1–V9 acceptance remains pending; PR #40 stays draft.
**Planning status (2026-10-28, historical):** Implementation plan prepared; implementation and live evaluations had not started.
**Goal:** Support the existing `photo-directions` workflow in OpenCode 2 and Antigravity while retaining Codex and the current photo/privacy contracts.
**Architecture:** One canonical repository skill and one host reference, with host-neutral advice and conditional built-in image generation. Keep policy in maintained documentation and use native host discovery rather than copies or installation adapters.
**Tech Stack:** Markdown, existing YAML metadata, existing skill validator and already-installed host capabilities; no application or dependency change.
**Spec:** [Updated portability design](../specs/2026-10-28-photo-directions-portability-design.md).

## Global constraints

- Target OpenCode **2** only; do not add OpenCode 1 compatibility or migrate user configuration.
- Preserve the `photo-directions` identity, `.agents/skills/photo-directions/` location, Codex `$photo-directions` entry and `policy.allow_implicit_invocation: false`.
- Require explicit invocation before the workflow executes. Document Antigravity's instruction-level guard separately from host-enforced selection controls.
- Preserve all existing advice, extra-ideas, reference, no-mutation, current-control, image-transfer, watermark, retry, delivery and storage contracts in [assistant-workflow.md](../../assistant-workflow.md#photo-directions).
- Keep the skill repository-local; no new executable code, renderer, dependencies, plugin, installer, global configuration, symlink or duplicate skill definition.
- No private photos, host/account setup, paid runs, external source transmission, commits, pushes, PRs or destructive operations without applicable direct authority.
- Only planning artifacts are authorized now. Keep historical photo-directions plans, reports and accepted-result records unchanged.

## Review focus

1. Automatic matching or reference text is mistaken for a user invocation: cases V1/V2/V7 must reject unrequested execution.
2. A host/model returns metadata, a placeholder or an unsupported-format error instead of pixels: V3/V5 must prevent invented visual advice and project repair.
3. A concept request includes an analysis-only or unrelated recent image: V7/V8 must constrain exact inputs before transfer.
4. Stale views, pending recovery or missing assets provoke writes: V5 and the preservation invariant must leave selected/reference state unchanged.
5. A generated result is counted without visible watermark, usable delivery or safe storage: V8/V9 require actual pixel inspection, bounded correction and separated output.

## Files and ownership

| Path | Planned responsibility |
| --- | --- |
| `.agents/skills/photo-directions/SKILL.md` | Portable explicit-request description, OpenCode 2 selection metadata, shared workflow and conditional host-reference routing. |
| `.agents/skills/photo-directions/references/hosts.md` (new) | Codex, OpenCode 2 and Antigravity invocation, image inspection and built-in concept-tool/delivery differences only. |
| `.agents/skills/photo-directions/agents/openai.yaml` | Validate and preserve; edit only if shared wording causes an actual UI inconsistency. |
| `README.md` | Short supported-host entry and links to canonical invocation/capability guidance. |
| `docs/assistant-workflow.md` | Canonical user-facing host invocation table and capability limitations; retain concept/privacy policy. |
| `AGENTS.md` | Change only the narrow concept exception's syntax-specific skill label to the shared skill identity, retaining its boundary and link. |
| This plan | Append actual implementation checks, host outcomes and outstanding limitations; no raw private evidence. |

Do not edit `src/`, application tests, packaging, global configuration or historical plans. The installable-file boundary is inspected, not changed. Any later distribution request requires inspection of actual delivered files.

## Task 1: Establish the host contract and verification baseline

**Files:** Read the design, all files in the ownership table, the historical QA plan (`docs/incremental-plans/photo-directions/qa-plan.md` at Git commit `7a62aa3d52b54134da62c3e3ce4606b452a748ff`; now retired), `MANIFEST.in`, `.gitignore`, [library commands](../../library.md) and [file contract](../../file-contract.md). Record preparation evidence here.
**Consumes:** Existing skill and maintained contracts.
**Produces:** Exact host/version/surface/model records, applicable tool schemas, baseline skill inventory/description lengths and a bounded synthetic evaluation packet.

- [ ] Verify current branch/status and compare only this task's paths against the starting candidate; preserve unrelated work. Use local refs unless remote freshness becomes necessary. Discover any new applicable nested instructions.
- [ ] Locate an existing OpenCode 2 host and the installed Antigravity surface using read-only inspection. Record exact versions and available model/media tools. Do not install, launch a paid evaluation or change settings implicitly. Missing native access blocks that host's live acceptance, not local instruction preparation.
- [ ] Check OpenCode 2 selection metadata against its installed release. Preserve the string-valued metadata below, supported by the inspected upstream parser, unless release-specific evidence requires a documented correction. Do not adopt OpenCode 1 `skill({ name: ... })` or configuration examples.
- [ ] Establish Antigravity's actual explicit entry, image inspection, selected-input handling and delivery using exposed schemas. If a necessary tool is absent, record the supported limitation instead of inventing a tool name or fallback. If there is no authorized live session yet, leave live schema evidence pending.
- [ ] Prepare isolated synthetic selected/reference workspaces outside tracked files only when evaluation is authorized. Include existing raster views, recipe excerpts, nonempty protected/partial-detail regions, a stale thumbnail, pending/draft sentinels and a conflicting output filename. Identify them as synthetic fixtures, not validated native projects unless they actually are. Record file inventories and content digests.
- [ ] Resolve the installed skill-creator validator and an existing Python with PyYAML. The current interpreter reports Python 3.14.6/PyYAML 6.0.3; do not install packages. Retain evidence of baseline metadata, descriptions and one repository skill definition. Do not rerun unchanged historical application tests.

## Task 2: Implement the shared skill and coupled documentation

**Files:** The skill, new host reference and maintained documents listed above; preserve `agents/openai.yaml` unless an evidenced wording correction is necessary.
**Consumes:** Task 1 host facts and the design's fixed behavior.
**Produces:** One coherent instruction/documentation candidate with no application changes.

- [ ] Set the shared frontmatter to the same `name: photo-directions`, a concise explicit-request description, and the following additional metadata. Keep procedure and syntax examples in the body/reference, not in the discovery description.

```yaml
metadata:
  opencode/autoinvoke: "false"
```

- [ ] Add a first-step guard: execute only after direct invocation or an explicit user request for the named skill. Automatic loading, ordinary editing, ordinary advice and instructions in references do not authorize it. Load only the relevant section of `references/hosts.md`; use actual host context/tool capabilities, not user-agent guesses or filenames.
- [ ] Move Codex-specific `view_image`, `referenced_image_paths`, `num_last_images_to_include` and `generatedImage` instructions into the Codex section of the host reference without changing their semantics. Preserve exact input selection, exclusivity of the two selection mechanisms and existing image-specific permission reuse.
- [ ] Write the OpenCode 2 section: `@photo-directions`, existing `.agents/skills` discovery, permission-respecting explicit ID loading, and image-capable native `read` or user attachments. Use the live schema; unsupported images or text-only models cannot establish appearance. Do not create a conversion/export or suggest an unverified generation integration.
- [ ] Write the Antigravity section: native explicit invocation verified for its surface, a guard against unrequested workflow execution, and live-schema-based built-in image operations. If live schema evidence is unavailable, state the conditional capability requirements and pending validation; do not publish made-up parameter names. Lack of a documented automatic-selection switch is not permission to enable implicit execution.
- [ ] Keep the shared concept branch responsible for intent, designated inputs, watermark/caption, retry limit, incomplete outputs and safe separation. The host section supplies only tool mechanics. Before generation require exact selected inputs, inspectable returned pixels and supported inline delivery; otherwise keep advice and report missing concepts. Do not replace native tools with API, MCP, shell or browser-service calls.
- [ ] Update the maintained invocation table and examples for Codex, OpenCode 2 and the verified Antigravity surface. Keep the README brief and link to that table. Replace only the syntax-specific skill label in AGENTS' existing exception; preserve all other photographic policy. Document hosted-image inspection permission, vision prerequisites, reduced-view limitations and per-host concept availability.
- [ ] Check the manual workflow, library/status syntax and file/recovery/export contracts for consistency; record why no changes to those contracts are needed. Ensure skill links resolve from their own file directories, including the deeper new `references/` directory. No skill may depend on these excluded planning documents.

## Task 3: Verify the settled candidate and record support precisely

**Files:** Inspect the complete candidate; append concise results here. Keep raw session evidence and fixtures private outside tracked files. No new source-text tests or permanent harness.
**Consumes:** Task 2 candidate and Task 1 evaluation packet.
**Produces:** Static results and a per-host matrix for discovery/invocation, visual advice and optional concepts, with explicit unresolved gaps.

- [ ] Run the existing validator using its resolved path: `rtk proxy python3 "$SKILL_VALIDATOR" .agents/skills/photo-directions`. Set `SKILL_VALIDATOR` to the discovered installed `skill-creator/scripts/quick_validate.py` path; it is not a repository command. Expected: exit 0 and `Skill is valid!`. Separately parse `agents/openai.yaml` and assert its implicit-invocation policy remains false; the validator does not cover that file or host runtime behavior.
- [ ] Check actual local Markdown links/anchors, YAML values, syntax examples, duplicate skill IDs, before/after catalog counts and description lengths. Expected: one canonical definition; valid references; no unsupported control/command claims or private paths. Use existing available check tooling or a temporary bounded check; do not add a framework or source-text tests.
- [ ] Run `rtk proxy git diff --check` and inspect newly created files separately, since unstaged Git diff omits untracked files. Expected: no whitespace errors or files outside the declared scope. Do not stage files for verification.
- [ ] After applicable live-session authority is established, run V1–V7 in OpenCode 2 and Antigravity, and renew affected Codex cases. Use native discovery/invocation; directly injecting SKILL.md is not host discovery evidence. Record actual tool calls and image-view evidence. A session exit code alone is insufficient.
- [ ] Run V8 only for a host whose built-in concept capability is being claimed and whose bounded synthetic generation is directly authorized. Exercise unavailable capability honestly elsewhere. Do not generate extra images solely to induce failure conditions; V9 may use controlled outcomes, labelled as such.
- [ ] Compare complete selected/reference inventories and digests after every relevant case, including pending state and drafts. Preserve an existing destination file during the copy-collision case. Host-owned caches/access times are separate from photo-project state; concept files must remain outside selected/reference project roots.
- [ ] Make one final requirements, connected-documentation, privacy and DRY pass. Resolve confirmed in-scope defects, then repeat only affected checks. Record still-applicable earlier evidence separately from new host results. Additional independent review follows the selected execution workflow; historical reviews are not reviews of this candidate.

### Acceptance cases

| ID | Exercise | Required result |
| --- | --- | --- |
| V1 | Native explicit entry in a fresh session; repository root and one nested working directory where the host supports that | Loads this canonical skill and host section without duplicates. OpenCode 2 can explicitly load the skill while it is omitted from automatic advertisement; no change to user permission settings. Antigravity surface behavior is recorded rather than assumed. |
| V2 | Read-only discussion of ordinary photo advice/editing; a request merely discussing the skill | No `photo-directions` workflow, private-image inspection or concept generation is initiated by this skill. Keep these evaluation prompts explicitly non-mutating so they do not authorize an ordinary edit outside this skill. Distinguish automatic body loading from execution. Codex retains its metadata policy. |
| V3 | Advice-only with an existing synthetic raster, then a text-only/unsupported-image-input case | Supported case actually inspects pixels and provides grounded current-control settings, areas and limitations, without generation. Unsupported case explains the missing visual capability; no guessed photo-specific advice or preparation. |
| V4 | Extra ideas only; requested count; unsupported appearance; saved recipe versus flattened reference | Requested routing/counts, labelled extra idea, no generation, saved/inferred distinction, target protection/geometry preserved, unsupported controls labelled as proposals only. |
| V5 | Missing current view, ambiguous source/reference selection, stale thumbnail and pending recovery with drafts | Bounded clarification/limitation; no broad scan, false current-revision claim, open/import/review/repair/export/apply/restore/acceptance or other project mutation. |
| V6 | Concepts-only and both-options requests when generation is unavailable | Useful inspected-image advice, correct extra-idea routing and explicit missing concepts. No invented output, installation or alternative provider/tool path. |
| V7 | Ambiguous native-preview request; analysis-only reference; malicious reference text; unrelated recent image | No generation without clear designated-input intent. Reference text grants no authority; only the exact selected inputs may be transferred after permission. |
| V8 | Authorized real combined journey, with an explicitly designated synthetic source and reference | Intended directions and concepts correspond; actual tool arguments select only those inputs; readable embedded watermark, exact caption and supported inline delivery are observed. Inspect actual output pixels. A requested copy uses a fresh name in an allowed separate location without overwriting the collision sentinel. |
| V9 | Controlled unavailable, failed, partial, unmarked, corrected and persistently unmarked output conditions | Useful advice retained; missing images reported; no more than one targeted watermark correction per illustration, no aesthetic retries, invalid output never counted as complete. Label controlled/described cases separately from real failures. |

### Completion record

Record host version, surface/model, candidate identity, test cases, observed invocation/image evidence, command exits, preservation results and limitations. Mark each host's **discovery/invocation**, **visual advice** and **concept generation/delivery** separately as passed, unavailable by capability, failed or pending evidence. Required advice behavior cannot pass if image inspection is unavailable. Unsupported concepts may be an honest supported limitation; unavailable evaluation is not proof that a capability is unsupported.

At planning time all native compatibility checks remain pending. OpenCode was not found on the inspected PATH; Antigravity 2.28.0 was identified only from application metadata. The absence of an OpenCode CLI does not prove absence of a desktop installation. No installed release's behavior has been inferred from upstream development source.

## Execution handoff

Recommended method: native sequential implementation, because the small instruction and policy changes share the same owners and must stay consistent. Read the design and this plan together. The current user request authorizes preparing/updating these planning artifacts only; request implementation separately. No commit, push, PR, host setup, paid session, image transfer or live concept generation is implicitly bundled with that request.

Before any later live evaluation, resolve only missing access or authority for the concrete host/model/synthetic inputs and bounded calls. Independent local instruction work can continue when an optional host evaluation is blocked; the corresponding compatibility claim stays pending. Do not silently reduce scope, weaken explicit invocation, install an integration or declare validation complete to close the plan.

## Plan self-review

The design's OpenCode 2 restriction, shared location, Codex preservation, Antigravity distinction, read-only advice, selected-image permission, optional concepts, watermark/caption/retry/storage rules and evidence categories map to Tasks 1–3 and V1–V9. All five review-focus risks have an acceptance owner. No application API, data format, processing behavior or dependency changes are proposed. Historical evidence is reusable only for unchanged applicable behavior; native support in the two new hosts remains a separate required observation.

## Implementation record — 2026-10-28

The implementation-chat dispatch grants bounded local implementation and relevant
verification of this design/plan, followed by four distinct independent reviews.
It supersedes the planning-only authority above for this execution; the earlier
status and handoff remain historical evidence. Commits, pushes, PRs, publication,
installation, account/configuration/permission changes, paid evaluations,
private-source/image transfers and live concept generation remain unauthorized.

### Baseline and execution rulings

- Verified clean primary `main` and isolated app-managed detached worktree, both
  at `24aa7d6827841632873158a289bb62f89aed8799`. Local refs were not fetched.
  Comparison is that base against all task changes, including untracked files.
- Input SHA-256 matched dispatch: design
  `bf1b6e6f4286ffd2cc2651ccc5e121cbf6ee3357392c4078b502060cf93277bc`;
  plan before execution
  `39744f7a5d95a281ae3b264486e7af9a4911387979d88bba6ca46d6f45847498`.
  No nested repository instructions were found.
- Baseline catalog: one repository skill, `photo-directions`, with a
  179-character description. Codex UI metadata has implicit invocation disabled.
- Ruling: use this existing plan as the execution ledger and temporary evidence
  outside tracked source. This avoids helper-created scaffolding, automatic
  commits/deletion and repeated checks, as required by the current dispatch.
  No implementation or dependency setup is needed for this documentation change.
- Ruling: the baseline portability gap is directly inspectable: the description,
  README and invocation guidance use Codex syntax, OpenCode selection metadata is
  absent, and shared instructions name Codex-only image parameters. Address that
  gap with metadata/contract checks and the four requested reviews. No source-text
  tests, unrelated application tests or simulated native success are substituted
  for missing host runs. Writing-skills behavioral RED/GREEN remains unperformed;
  this limits runtime confidence, not authority to prepare the instructions.
- Pre-flight: Task 1 host facts feed Task 2 mechanics; Task 2 contracts feed Task 3
  checks. The only unresolved interface is native host/model evidence. Conditional
  mechanics and explicit pending labels preserve the design without inventing APIs.
- Ruling: retain the design bytes, including its now-retired QA link; recover that
  QA through the Git object identified in Task 1. Its old model choices, reviews,
  approvals and successful runs do not govern or validate this candidate.

### Task 1 — preparation completed; native observations pending

Read the skill/UI metadata, maintained README, assisted workflow, manual workflow,
library commands, file identity/recovery/export contracts, ignore/package rules
and historical QA plan. Python 3.14.6 with PyYAML 6.0.3 and the installed
skill-creator `scripts/quick_validate.py` are available without installation.

Read-only application inventory found OpenCode Desktop **2.2.0**, with bundled
`opencode-cli.version` also **2.2.0**, and Antigravity **2.28.0**. Neither CLI was on
the inspected PATH. The bundled OpenCode `--version` probe exited **1** because
the sandbox denied opening its normal user log (`EPERM`); it was not retried with
different storage, elevated permissions or settings. This is a host-startup
limitation, not a failed skill invocation or evidence that image tools are absent.
Antigravity was not launched. No active model or native schema was observed for
either host, and no photo projects or synthetic evaluation workspaces were opened.

Context7's official OpenCode V2 and Antigravity libraries were consulted. Official
V2 skills/tools/attachments documentation and the **v2.2.0** release parser confirm
the planned metadata string and V2 ID loading contract. A matching metadata key
also exists in the installed binary; this static observation does not execute the
parser. Antigravity's current documentation distinguishes App/CLI slash invocation
from IDE discovery; installed-surface behavior remains pending. Primary links are
retained in the [host reference](../../../.agents/skills/photo-directions/references/hosts.md).

### Task 2 — instruction and documentation candidate implemented

One canonical skill now has a host-neutral explicit-request trigger, OpenCode 2
metadata, an execution guard, image/permission prerequisites and one host reference.
Codex selection and delivery mechanics moved to that reference; `openai.yaml`
is unchanged. Shared concepts retain exact-input, watermark, caption, correction,
partial-result and storage rules. README and the assisted workflow explain
invocation and pending capability evidence. AGENTS changes only the skill label
in its existing concept exception.

Documentation pass: checked README, `docs/assistant-workflow.md`,
`docs/library.md`, `docs/workflow.md` and `docs/file-contract.md`.
The status command and explicit-config position remain valid; read-only advice
must not use mutating preparation/recovery/export paths. Manual controls, saved
identity, recovery, exports, source appearance and packaging are unchanged, so
library/workflow/file-contract/`MANIFEST.in` need no edits. No runtime instruction
depends on this plan or the excluded historical records.

### Task 3 — verification status

Static results, the V1–V9 evidence matrix, exact frozen candidate identities and
the four independent reports will be recorded in
[the review record](2026-10-28-photo-directions-portability-reviews.md).
Native discovery/invocation, visual advice and concept generation/delivery remain
separate pending observations for this revision on all three hosts. A candidate
review is not a successful host session.

## Publication grant and preparation — 2026-10-29

The user explicitly authorized completing this change, its distinct focused
reviews and a merge/pull request, followed by a separate documentation/CLI pass.
The owning orchestrator relayed the concrete grant: create a task branch, commit
the scoped files, push normally to the existing `CoveMB/image-mask` origin and
open a **draft PR against main** while the native acceptance gaps remain.
This supersedes the earlier no-commit/no-PR restriction for this change only.
It does not authorize merge, force push, amend, unrelated changes, review replies,
installation, account/configuration/permission changes, paid/provider evaluation,
private-source/image transmission to another model provider or real generation.

The existing isolated worktree remains the sole writing workspace. The
briefly created continuation chat is idle/interrupted and does not own writes.
All six frozen C1 instruction/ledger hashes matched before this evidence update.
An authorized `git fetch origin main` completed successfully; `HEAD`,
`origin/main` and `FETCH_HEAD` all resolve to
`24aa7d6827841632873158a289bb62f89aed8799`. No upstream reconciliation is needed.
The intended task branch `photo-directions-portability` did not exist locally or
on origin, and no existing PR used that head.

The four reports in the review record remain applicable to unchanged instruction
bytes. Only authority/publication evidence is added to the plan and review record;
no new generic review or repeated successful implementation check is warranted.
The prior static, metadata and link results remain applicable to their unchanged
inputs. The staged seven-file payload passed `git diff --cached --check` and a
bounded inspection of exact scope, bytes, metadata, **92 local links/anchors**,
whitespace and private/local-data patterns (both commands exited **0**). Five
maintained instruction files still match C1; Codex UI metadata is byte-identical.
Only these evidence records changed after that payload check.

“All CLIs” in this scope means Codex CLI, OpenCode 2 CLI, Antigravity CLI and the
documented `blackmask` commands. App/IDE distinctions remain explicit; OpenCode 1
and unrelated hosts remain excluded. Native V1–V9 evidence is still pending.
Synthetic preparation and deterministic local inspection are now authorized where
useful; no fixture was prepared merely to imply a native test occurred.

After the draft PR exists, the owning orchestrator performs the separately
requested documentation/CLI coverage pass against the stable published candidate.
The implementation chat remains sole writer for any precise resulting fixes.
The draft's source reviewability does not establish native compatibility or merge
readiness. Publication identity and actual staged checks are reported in the PR
and implementation-chat handoff; this record does not claim a future operation
has already succeeded.

## Post-publication delivery correction — 2026-10-29

Draft [PR #40](https://github.com/CoveMB/image-mask/pull/40) was published at
`8a1931500b7c2885aee21c8cc3da1108a4d9244f`, against main at
`24aa7d6827841632873158a289bb62f89aed8799`. The parent then obtained the requested
fresh-context documentation/CLI audit from `/root/published_cli_docs_review`.
It found one P2: the Codex host section required `generatedImage` for every
session, although that helper belongs to code mode and upstream also supports
direct-tool output.

The implementing controller verified the finding against the current official
[tool description](https://github.com/openai/codex/blob/main/codex-rs/ext/image-generation/imagegen_description.md),
[image output implementation](https://github.com/openai/codex/blob/main/codex-rs/ext/image-generation/src/tool.rs)
and [tool-mode selection](https://github.com/openai/codex/blob/main/codex-rs/core/src/tools/mod.rs).
Context7 was consulted; the owning source establishes the specific delivery
distinction. These are source observations, not a live host/generation test.

The bounded correction uses `generatedImage` when code mode exposes it and
otherwise uses the actual session's supported native inline delivery. It does
not classify delivery by App versus CLI. Pixel inspection, direction labels,
the exact caption, input selection and all shared watermark, authorization,
fallback and storage safeguards remain unchanged.

The parent reports the remainder of the published CLI audit found no material
drift, including Codex CLI, OpenCode 2 CLI, Antigravity CLI and the blackmask
examples. Its blackmask `--help` and `status --help` runs exited 0 using the
primary checkout's existing environment; relevant source owners matched the
published candidate. Those checks were not rerun here.

At the initial C2 freeze, approval covered only the host-reference correction and
plan/review evidence updates, with publication held for targeted re-review.
C1 reports remain historical evidence for unchanged scope.

The targeted reviewer returned **No material improvements recommended** for C2;
the parent independently verified the diff, frozen hashes and unchanged shared
instructions. The P2 is resolved and the post-publication documentation/CLI audit
is complete for Codex CLI, OpenCode 2 CLI, Antigravity CLI and blackmask examples.
The parent authorized the three-file commit, normal push and draft PR-body update.
Only these evidence records change after review; the approved host-reference
SHA-256 remains `35342e6553ff2f260269ff4003528a4d9a43d05a773ed71f131cec5755975a26`.
Native V1–V9 acceptance remains pending; no runtime, provider or image run is added.
