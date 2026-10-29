# Photo Directions Portability Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` for the recommended native sequential execution, or `superpowers:subagent-driven-development` if the user selects that method. Repository authorization boundaries override automatic implementation, Git or external-action steps. Checkboxes record actual work, not planned success.

**Status:** Implementation plan prepared; implementation and live evaluations have not started.
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

**Files:** Read the design, all files in the ownership table, [existing QA plan](../../incremental-plans/photo-directions/qa-plan.md), `MANIFEST.in`, `.gitignore`, [library commands](../../library.md) and [file contract](../../file-contract.md). Record preparation evidence here.
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
