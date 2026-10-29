# Photo directions portability — verification and independent reviews

**Status:** Source/documentation implementation and focused reviews are complete,
including the accepted C2 delivery correction and post-publication documentation/CLI
audit. Native compatibility acceptance remains pending; PR #40 stays draft.

## Authority and C1 comparison

The implementation-chat dispatch authorizes local implementation and four separate
read-only reviews of the [plan](2026-10-28-photo-directions-portability.md) and
[design](../specs/2026-10-28-photo-directions-portability-design.md).
Historical approvals are context only. Compare local base
`24aa7d6827841632873158a289bb62f89aed8799` against the working tree, including
untracked `references/hosts.md` and this report. No fetch was performed.

The candidate includes only the skill, host reference, README, AGENTS' narrow
concept label, assisted workflow and implementation ledger. Codex UI metadata is
an unchanged preserved input. This report is an evidence artifact; final report
updates do not change the reviewed instruction candidate.

## Static verification

- Existing installed skill-creator `quick_validate.py` on
  `.agents/skills/photo-directions`: exit **0**, `Skill is valid!`.
- `rtk proxy git diff --check`: exit **0**, no diagnostics for tracked changes.
  Untracked content receives separate whitespace/link checks.
- Bounded Python/PyYAML contract check: exit **0**, **150 local Markdown links
  and anchors across 10 documents**, no diagnostics. This includes the untracked
  host reference and report, the implementation plan and the maintained
  library/manual/file contracts. It does not recursively validate historical
  design links; the retained design's retired QA link is documented in the ledger.
- Catalog remains **1 → 1** skill; description length **179 → 177** characters.
  OpenCode autoinvoke is the string `"false"`; Codex implicit invocation parses
  as Boolean false and `openai.yaml` is byte-identical to base. No private/local
  paths or planning dependencies were found in the maintained instruction files.
- Desk-check coverage includes positive named invocations, negative ordinary
  advice, adjacent edit requests and ambiguous skill discussion/native-preview
  requests. The explicit guard and concept branch route those requests as
  specified on inspection; no model-behavior pass is claimed.
- No application code, dependencies, formats, renderer, packaging or global
  configuration changed. No application suite was run for this instruction-only
  change. No native session or real/controlled tool generation was run.

## V1–V9 evidence and limitations

| Case | Current evidence | Remaining observation |
| --- | --- | --- |
| V1 — native discovery/invocation | Versioned OpenCode 2 parser and documented discovery/entry; Codex policy retained; Antigravity App/CLI entry is documentation-backed | Fresh root/nested native sessions, actual resolved definition and active host section; no injected file read counts as discovery |
| V2 — ordinary advice and skill discussion | Explicit first-step guard and metadata inspected | Native negative requests and observed lack of workflow/image activity |
| V3 — actual image inspection | Image-model, pixel and reduced-view conditions are explicit | Real pixels received; grounded current-control advice; unsupported/text-only path |
| V4 — directions, extras and references | Counts/routing, saved-versus-inferred values, geometry/protection and proposed controls retained | Native advice behavior with selected synthetic raster and recipe/flattened references |
| V5 — stale/missing/pending state | Read-only constraints and freshness limits retained | Native refusal to repair; complete before/after project and draft inventories/digests |
| V6 — unavailable concepts | Shared fallback retains inspected-image advice and identifies missing concepts | Native unavailable-capability response and absence of alternative integrations |
| V7 — intent, references and exact inputs | Explicit selected-input intent, untrusted references and exclusion of unrelated images retained | Native ambiguity/analysis-only/malicious-reference cases and actual selected tool arguments |
| V8 — real combined journey | Watermark, caption, correspondence, delivery and storage contract retained | Authorized synthetic built-in generation, actual pixels/arguments, inline output, collision-safe copy |
| V9 — controlled output conditions | One targeted watermark correction, no aesthetic retry, missing/partial outcomes retained | Controlled unavailable/failed/partial/unmarked/corrected/persistently unmarked behavior, labelled separately from real tool failures |

These are instruction inspections, not executed V-case passes. No selected or
reference project was opened, modified or generated for this execution; therefore
there is no new before/after fixture-digest or collision-copy evidence. Historical
Codex QA is not renewed evidence for the changed candidate.

## Host outcomes

| Host evidence | Discovery/invocation | Visual advice | Concept generation/delivery |
| --- | --- | --- | --- |
| Codex: current tool contracts available; no new skill evaluation session | Pending renewal; explicit-only policy statically preserved | Pending renewal | Pending renewal; built-in tool schema exists, no call authorized/run |
| OpenCode Desktop/bundled CLI metadata: 2.2.0; no active model observed | Pending; bundled `--version` failed before a session when sandbox denied normal log access | Pending; documented V2 image input is not observed model receipt | Pending capability evidence; no suitable built-in generator established, not a claim of absence |
| Antigravity application metadata: 2.28.0; surface/model unobserved | Pending; App/CLI syntax documentation is not installed-surface verification | Pending | Pending live schema, exact input control, pixels and delivery |

OpenCode's startup probe exited **1** with `EPERM` opening its normal user log.
No permission/configuration workaround was attempted. Application metadata and
release source are sufficient for bounded instruction preparation, not runtime
support claims. The current dispatch excludes paid runs, live concept generation,
private image/source transfer, installation and permission/account changes.

## Independent reviews

Four separate fresh-context native subagents inspected C1 read-only, with no
inherited conversation or recursive delegation. Each used `gpt-6-astra` at
`xhigh` effort. Every reviewer checked the seven candidate hashes; no instruction
or ledger input changed during review. The controller reconciled each report
against the actual candidate, primary host evidence and observed command results.

### 1. Requirements and host compatibility

Assignment: `/root/requirements_review`.
**Verdict: No material improvements recommended.**

Reviewed the design, plan/rulings, tracked diff, host reference and maintained
concept contract. Confirmed OpenCode V2 discovery, explicit `@` entry, ID loading
and selection metadata against official documentation and the v2.2.0 parser;
Antigravity App/CLI versus IDE and instruction-versus-platform distinctions were
properly qualified. Codex input-selection exclusivity and delivery were preserved.
A transient documentation-retrieval discrepancy about `@` syntax was resolved by
targeted primary-page retrieval; it was not a finding.

Limits/declined judgments: actual native discovery, automatic execution, image
receipt, model compliance, tool schema, watermark quality, inline delivery and
runtime project preservation were unexercised. Installed metadata/startup evidence
was supplied, not rerun. Other review scopes were left to their assigned reviewers.

Disposition: accepted. Local requirements coverage is supported; native acceptance
remains pending. No fix or deferred material finding.

### 2. Architecture and documentation consistency

Assignment: `/root/architecture_review`.
**Verdict: No material improvements recommended.**

Reviewed shared ownership, host mechanics, current documentation links/contracts,
status commands, packaging boundaries and the stored static checker/result.
Confirmed one skill, no duplicate runtime/configuration, retained Codex UI bytes
and clear canonical privacy/storage ownership. The historical QA locator remains
usable through the explicit Git object in the implementation ledger.

Limits/declined judgments: native/model compliance, actual visual quality and
usability require runtime/human evidence; distribution contents were not evaluated
because no distribution was produced. External API verification was owned by the
requirements reviewer.

Disposition: accepted. No new abstraction, refactor or packaging work is warranted.
No fix or deferred material finding.

### 3. Privacy and image integrity

Assignment: `/root/privacy_review`.
**Verdict: No material improvements recommended.**

Inspected the full candidate, preserved metadata and stored static evidence.
Desk scenarios covered explicit invocation versus ordinary advice/editing/skill
discussion/malicious reference text; hosted inspection permission; stale or
unsupported views; analysis-only/unrelated image exclusion; unavailable generation;
partial output; unreadable watermark and one correction; separate storage,
collision protection and retention honesty. These were desk analysis, not native
or model-behavior passes.

Limits/declined judgments: native enforcement, model receipt of pixels, actual
generation arguments, readable marks, inline delivery, filesystem preservation,
copy collisions and provider retention were not observed.

Disposition: accepted. The instruction safeguards remain intact; operational
compliance and photographic acceptance are not inferred. No fix or deferred
material finding.

### 4. Verification and evidence

Assignment: `/root/verification_review`.
**Verdict: No material improvements recommended.**

Verified C1 identity, detached HEAD and five tracked/two untracked file inventory.
Inspected the bounded checker and retained stdout/stderr/exit; confirmed the
metadata/count/link evidence and accurate V1–V9/host pending labels. Validator and
`diff --check` small outputs were controller-recorded evidence, not separately
available raw reviewer logs. The controller directly observed both successful
commands and did not rerun unchanged checks merely to generate logs.

Limits/declined judgments: the checker covers selected YAML and inline local
Markdown links, not external URLs, native schema acceptance or model behavior.
Its report hash predates the disclosed result/hash additions; all six
instruction/ledger inputs match C1. No controlled V9 execution, real image,
generation or project-preservation case ran. Primary API claims were covered by
the requirements reviewer.

Disposition: accepted. Evidence supports local instruction/documentation delivery,
with native compatibility and concept acceptance still pending. No fix or deferred
material finding.

### Frozen candidate C1

Base and HEAD are both `24aa7d6827841632873158a289bb62f89aed8799`;
all changes are unstaged/untracked. SHA-256 identifies actual bytes, including the
new host reference. The immutable instruction/ledger inputs are:

| Path | SHA-256 |
| --- | --- |
| `.agents/skills/photo-directions/SKILL.md` | `d07aa8155d2c5f937da905077676f3aaa31dde3144fe505045b4c1730ae2c6ff` |
| `.agents/skills/photo-directions/references/hosts.md` | `79ec96488a33d25295beb4da36b595ea229814ae18db42e70dde44b77194c609` |
| `AGENTS.md` | `05274fc4e3b70abd4c2beddb42bc2e088546bd47c12b4b89f7ddacd0ce68bdc5` |
| `README.md` | `0728df3020cc903516f9ba35b5abefd641cc00c7d754a3cfbf850903e2377fac` |
| `docs/assistant-workflow.md` | `5fa093aa0efffc6f82227eb442d62386bc4b907908dcc4c8f16764c09cb34d6f` |
| `docs/superpowers/plans/2026-10-28-photo-directions-portability.md` | `ccf53d242fe715a2b24adcd0addeeb6070a21f5de84257ce9e7b079692cd67d6` |

Preserved UI metadata SHA-256:
`52e49df495a2b390ff8482eda9c18245afb98588e2a64b24ae7bf57c3f63bfdf`.
The external review packet records this report's initial bytes and the full
tracked/untracked inventory; final dispositions are appended only after all four
reports return. Raw/local evidence remains outside tracked source.

## Remaining action at the C1 handoff

Local implementation, applicable static checks, documentation pass and all four
independent reviews are complete. All declined runtime/human judgments remain
explicit gaps, rather than waived requirements. No fixes were required and no
material findings were deferred. The isolated worktree and all evidence are
retained; no commit, push, PR, merge, publication, setup or deletion occurred.

For native acceptance, the user must next authorize synthetic-fixture preparation
and V1–V7 sessions on the selected existing host/model, with no private photos,
installation or configuration changes. OpenCode startup additionally needs an
approved route for its normal log access. The concrete session/tool/transfer
scope must be reviewed before sending repository instructions or images to a
host/provider. V8 generation needs a later separate approval identifying the
prepared synthetic inputs, host, count and allowed destination; V9 controlled
outcomes must remain distinguishable from actual tool failures.

Reply in this implementation chat to continue evaluation, or authorize the owning
orchestration chat to relay the decision here. No further local instruction work
is blocked; retaining this candidate needs no additional approval. No host is
marked unsupported solely because its evaluation could not run.

## Publication preparation — 2026-10-29

The new direct user grant permits a scoped task branch, commits, normal origin
push and a draft PR against main. It supersedes the C1 no-publication boundary
only for this change. Merge, force push, amend, review replies, installation,
configuration/permission changes, private model-provider transfers, paid sessions
and live image generation remain outside the grant.

The controller verified all six C1 instruction/ledger hashes before updating
these evidence records. The fetched remote main and local HEAD both remain
`24aa7d6827841632873158a289bb62f89aed8799`; no upstream changes require repair.
The five maintained instruction files remain byte-identical to reviewed C1,
and Codex UI metadata is unchanged. Plan/report additions record authority and
publication facts only, so all four scope-specific review verdicts remain
applicable. No finding, fix or new runtime pass is implied by the new grant.

The publication payload is exactly the seven paths identified above, including
the host reference and this report; raw/local evidence stays outside it. Existing
validator/metadata/link results are reused for unchanged inputs. The actual staged
payload passed `git diff --cached --check` and a bounded exact-scope, byte-identity,
metadata, **92 local-link/anchor**, whitespace and private/local-data-pattern
inspection; both commands exited **0**. All five maintained instruction files
match C1 and Codex UI bytes are unchanged. These two evidence records are the only
subsequent edits; their new result text introduces no links or runtime instructions.

Synthetic fixture preparation is now authorized when useful; native provider
sessions and actual generation still need their concrete authority. No fixture
preparation or V1–V9 execution is claimed. OpenCode's historical log-access denial
has not been bypassed. All three hosts retain separate pending discovery,
visual-advice and concept-delivery outcomes.

The parent owns the requested **post-publication** documentation/CLI pass for
Codex CLI, OpenCode 2 CLI, Antigravity CLI and the related blackmask commands.
The implementation chat will stop mutations at the published checkpoint and
remain sole writer for any precise follow-up fixes. Draft publication is for
source/documentation review, not a declaration of runtime support or merge readiness.

## Post-publication documentation/CLI audit and local correction

Published comparison: draft [PR #40](https://github.com/CoveMB/image-mask/pull/40)
at head `8a1931500b7c2885aee21c8cc3da1108a4d9244f`, base main
`24aa7d6827841632873158a289bb62f89aed8799`.
The parent assigned `/root/published_cli_docs_review`, a fresh-context read-only
`gpt-6-astra` reviewer at `xhigh`, after publication.

**Finding P2:** `references/hosts.md` required the code-mode `generatedImage`
helper for every Codex session. Direct-tool sessions can lack that helper, so
the unconditional instruction could obstruct an otherwise supported native
inline delivery. The parent verified upstream support for both output paths;
the implementing controller independently corroborated the finding in the
official source links retained in the implementation plan. Context7's response
did not establish this exact distinction; the tool description and implementation
own the correction.

**Local disposition:** corrected only the delivery sentence: use
`generatedImage` when code mode exposes it; otherwise use the actual session's
supported native inline delivery. Actual-pixel inspection, direction labels and
the exact adjacent caption remain explicit. The shared skill and every
authorization, selected-input, watermark, retry, missing-output and storage
requirement are unchanged. This is a tool-mode distinction, not an App/CLI rule.

The parent reports no other material documentation/CLI drift and blackmask
`--help`/`status --help` exits of 0, with relevant source owners matching the
published candidate. Those supplied results were not rerun by the implementation
controller and do not establish native model/image behavior.

The earlier four C1 reports are preserved as historical scope-specific evidence.
The host-reference bytes differ from C1 and the initial published head; only the
delivery delta and its evidence records required targeted re-review. No generic
review was added. `rtk proxy git diff --check` exited **0**. A bounded check of the
three affected files exited **0**: **10 local links/anchors** resolve, whitespace
and local-path checks pass, HEAD remains the published head, and no staged or
untracked files exist. Eleven external links were excluded from that static
check; the three owning Codex sources were inspected separately. Unchanged skill
metadata validation and application tests were not repeated. These checks do not
exercise native/model/image delivery.

Frozen correction C2 was the working-tree diff against the published head above.
The corrected host reference SHA-256 is
`35342e6553ff2f260269ff4003528a4d9a43d05a773ed71f131cec5755975a26`.
The external evidence packet identifies all three actual candidate file hashes
and its exact diff, including the final evidence text. The publication hold at
that freeze was released by the targeted disposition below.

### Accepted C2 disposition

`/root/published_cli_docs_review` returned **No material improvements recommended**.
It verified the actual three-file diff, every frozen hash, published HEAD and
exact unstaged scope. The parent independently checked those inputs, the unchanged
shared skill/README/AGENTS/assisted workflow/UI metadata and retained checks.
The P2 is resolved; pixel inspection, labels, caption, missing-capability fallback
and all shared safeguards remain intact. The completed documentation/CLI audit
covers Codex CLI, OpenCode 2 CLI, Antigravity CLI and the blackmask examples.

The parent authorized committing the three scoped files, normal-pushing the
existing branch and updating draft PR #40. Only compact evidence/status updates
follow this review; the approved host-reference hash above remains unchanged.
No material finding remains open. Native V1–V9/model/image acceptance is still
pending, and neither the audit nor publication supplies that evidence.
