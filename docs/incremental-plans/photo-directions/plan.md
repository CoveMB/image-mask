# Photo directions — incremental implementation plan

Status: both increments implemented, verified and accepted under user delegation; single-MR delivery. Updated: 2026-10-28.

## Purpose and baseline

Deliver the explicitly invoked repository skill `$photo-directions`: photo-specific suggestions using current controls, optional additional ideas, and optional watermarked AI concept illustrations. Both options belong to this program and its single requested MR. Two increments make the advice useful and verifiable before adding the separate image-transfer and delivery boundary; they do not defer an option from the first published version.

Primary source: [Photo Directions Skill Implementation Plan](../../superpowers/plans/2026-10-28-photo-directions.md), SHA-256 `dd5ec8ac8485397a43c64359e18aa93089fbe57d8ce09c868de16cb85cc9d06d`. Supporting [source-plan review record](../../superpowers/plans/2026-10-28-photo-directions-reviews.md), SHA-256 `6fdcead3682b4c25058ef81a57bb56024d946760f4c9a7922fe89fa3a9772f7b`. Preserve these source bytes. Their earlier readiness and preparation-only authority describe that earlier stage, not this program's current execution grant.

Inspected repository: `image-mask`, local `main` at `89935daefcb3cc261ca6addf6d826045045dc5a5`. On 2026-10-28 the orchestrator refreshed the existing remote and reported local `main` and `origin/main` identical (0 ahead/0 behind). Seven pre-existing modified documents are authorized for inclusion and must be preserved: `AGENTS.md`, `docs/assistant-workflow.md`, `docs/file-contract.md`, `docs/guidance.md`, `docs/troubleshooting.md`, `docs/validation.md`, and `docs/workflow.md`. The two source planning documents are untracked. The orchestrator retains the original seven-document patch for preservation checks; do not include local evidence locations in the MR. The selected planning directory was absent, with ordinary in-repository parents and no nested instructions on its path.

QA is **on** in [qa-plan.md](qa-plan.md). It uses this source and the same coordinated plan/handoff candidate. Actual implementation, host and generation evidence is recorded below; no application-suite result is claimed. Existing read-only-status test assertions and maintained contracts were inspected, not run. The executor must revalidate the current host tool schema and official guidance before relying on generation or discovery behavior.

The final implementation changes only `.agents/skills/photo-directions/SKILL.md`, `.agents/skills/photo-directions/agents/openai.yaml`, `AGENTS.md`, `docs/assistant-workflow.md`, and `README.md`, alongside the authorized inherited documentation and planning artifacts. No application code, renderer, scripts, runtime dependency, catalogue, paid integration, model download or native-preview implementation is needed. Names throughout authored/generated material describe photo behavior, not delivery stages; increment IDs remain only in planning and evidence references. Preserve historical names, source text and compatibility; no incidental renaming.

## Authority and sequencing

The direct user instruction in the current orchestration chat on 2026-10-28 begins “orchestrate its implementation” and expressly includes multiple focused review passes, a Ponytail pass, a new branch from current main plus the relevant uncommitted documentation, and one MR. The start condition was completion of [the prerequisite chat](codex://threads/01a180b8-10ef-7051-8e2c-8136125f844d); the orchestrator verified it completed and idle. The later direct user instruction requires **GPT-6.1 Sol (`gpt-6.1-sol`) for subsequent implementation and reviewer dispatches**. This already-running planning assignment may finish; it creates no child agents.

Routine Gate 2 concrete-plan and Gate 3 verified-result decisions are delegated to the orchestrator under this scoped execution grant. Record each actual decision as **orchestrator-approved under user delegation**, with candidate, comparison, evidence and rationale. Actual increment decisions are recorded in the execution record below. Permission does not supply missing preparation, reviews or verification and is not human inspection of unseen results. No new launcher adoption is required.

New material scope, behavior, architecture, public-interface or compatibility decisions remain user-owned. Private-photo transfer still requires applicable image-specific permission; this program verifies generation only with a synthetic fixture. No merge, deployment, destructive cleanup, new installation, new paid service, permission change or unsolicited provider message is authorized. Host approval boundaries remain effective. Keep one implementation writer; preserve all existing work.

| Part | Coherent outcome | Order |
| --- | --- | --- |
| Photo directions | Grounded advice, then optional illustrated advice | I01 — Read-only photo advice → I02 — Watermarked concept illustrations |

I01 is accepted locally before I02 preparation. Publish one combined MR after both increments; do not manufacture an MR stack or early publication requirement.

## Source coverage

| Primary-source locator | Obligation | Owner and check |
| --- | --- | --- |
| Accepted scope and invocation | Explicit-only invocation; current controls; two useful directions normally, requested counts respected; optional extra ideas; settings, regions, limits and achievable/approximate/unsupported classification | I01; Q1–Q4 |
| Accepted scope and invocation | Clearly labelled proposed controls remain unavailable suggestions; never implement or advertise them as commands | I01; Q3 |
| Scope and privacy boundaries, first two paragraphs | Selected source/result/revision identity; read-only photo/reference discovery; no broad scan, repair or project-writing inspection; missing/stale views stay unresolved | I01 and preserved by I02; Q4–Q5 |
| Scope and privacy boundaries, capability paragraph | Refresh capability advice from maintained README source map/manual guide; inspect uncertain implementation; distinguish recipes from visual estimates and preserve target geometry/protection | I01; Q3–Q4 |
| Scope and privacy boundaries, exception/input paragraphs | Narrow authorized concept exception, including introductory upload and named-reference restrictions; exact selected generation inputs; no implicit permission or unrelated recent images | I02; Q6–Q7 |
| Concept generation and delivery | Live tool schema; local input inspection; embedded watermark and exact caption; one targeted watermark correction; partial/unavailable/failed output honesty; no aesthetic regeneration | I02; Q7–Q9 |
| Concept generation and delivery; Scope and privacy boundaries | Inline verified concepts; separate tool/default or explicitly selected private copies; collision-safe retention; no source/project/gallery/export/acceptance use; no provider-retention promise | I02; Q5, Q7–Q9 |
| Task 1 | Repository-local instruction/metadata implementation; maintained policy owner; explicit-only metadata; no runtime reliance on plans, personal memory or private assets | I01/I02; Q1, Q6, Q10 |
| Task 2; Completion and evidence | Creator validator, separate metadata and actual host checks, all listed scenarios, unchanged-workspace proof and one real synthetic generation case; distinct evidence categories | Owning increments in Q1–Q10; no unrun result counted |
| Task 2 documentation pass; source exclusions | Maintained examples/control wording checked; no unrelated application suite, new harness, extra renderer/dependencies, private-photo use or automatic deletion | Global, orchestrator; Q10 and final reconciliation |
| Current direct request | Preserve and include the inherited seven-document changes; focused independent reviews, Ponytail, GPT-6.1 Sol and one MR | Global; comparison/preservation checks, required reviews and publication handoff |

## I01 — Read-only photo advice

**Outcome.** An explicitly invoked, useful advice skill that inspects only selected existing photo/reference artifacts, explains grounded combinations of current controls, and adds beyond-brief ideas only when requested. Its intermediate documentation promises text advice only; AI concepts are not enabled or claimed in this increment.

**Files.** Add the two skill files; add the advice-only entry/example in `README.md` and a concise maintained advisory section in `docs/assistant-workflow.md`. Preserve all inherited edits. No generative-policy exception in `AGENTS.md` yet. Before Gate 2, confirm actual anchors, metadata schema and the read-only `status` command with the explicitly selected configuration if needed; no command should be invented from this plan.

**Acceptance.** Q1–Q5 and applicable Q10 demonstrate invocation metadata, current-capability grounding, normal/extra-idea routing, honest unsupported requests, selected revision identity, recipe-versus-inference distinction, protected target geometry and no project mutations. Missing/ambiguous selection or stale/missing image produces a precise limitation or request for an existing suitable view. The skill must not call `open`, import/preparation/matting, `review`, export, repair, apply, restore or acceptance to obtain one. Ordinary editing does not implicitly activate the skill. Host discovery and observed invocation are separate from file validation; missing host proof remains pending.

**Review and recovery.** Prepare a concrete comparison against the preserved baseline, including relevant inherited-document interactions. Three distinct fresh-context read-only reports cover requirements/source fidelity, architecture/reviewability/simplicity, and verification. The architecture assignment includes the explicitly requested bounded `ponytail:ponytail-review` pass for this exact candidate. The owner validates and fixes material findings after all dispatched reports return, then renews only affected checks/reviews. Read-only advice must preserve project state; a discovered mutation is a defect, not permission to repair or erase evidence. Do not reset existing work.

**Gate and future impact.** The orchestrator records actual Gate 2 and Gate 3 decisions under delegation after required evidence. I02 can proceed only when I01's accepted contents and still-applicable proof are identified. Its safe predecessor is usable text advice with unchanged local-editing policy. Reassess advice wording, host discovery and routing after I02 changes shared skill files.

## I02 — Watermarked concept illustrations

**Outcome.** Add explicitly requested concepts to the accepted advice skill, including both optional features together, without turning the advice workflow into photo editing or expanding input authority.

**Files and coupling.** Update the same skill and metadata, `README.md`, `AGENTS.md`, and `docs/assistant-workflow.md`. Add the narrow exception and canonical concept/privacy boundaries together, including precise exceptions at the introductory upload wording and named-reference restriction. These safeguards cannot be postponed from generation. Final metadata/example describes both options honestly; ordinary editing and offline manual work remain unchanged.

**Acceptance.** Q6–Q10 plus affected Q1–Q5 on the combined candidate. Generation uses only explicitly designated image inputs through the current built-in tool; analysis-only references and unselected recent conversation images stay out. A direct clear scoped request is reused without another confirmation. Every completed image has readable embedded **AI-GENERATED CONCEPT**, its direction label, and the caption **Concept illustration—appearance may not be reproducible with these controls.** Inspect actual pixels at displayed size. At most one targeted watermark correction per illustration; no aesthetic retry. Failed, unavailable or still-unmarked images are omitted from completed deliverables and reported as missing while preserving useful text. Do not promise that unchecked tool intermediates can never appear.

One real bounded synthetic generation case must exercise actual input selection, inline output, watermark/caption, output isolation and preserved selected/reference workspaces. The executor owns the combined advice + extra ideas + concept journey; branch cases must distinguish concepts-only from both-options behavior and failure/partial delivery. Controlled or described failures are clearly labelled and cannot stand in for real generation evidence. Concepts remain separate from originals, masks, revisions, accepted work, galleries, review evidence and delivery exports. Copies require a selected private destination or ignored root `local/`, collision-safe names and actual retained-location reporting; never overwrite/delete or promise provider retention.

**Review, gates and recovery.** Use I01's identified accepted candidate as the increment comparison and inspect the complete main-to-final publication candidate for interactions with inherited documents. Obtain three distinct reports with the same scopes and architecture-owned Ponytail pass, naming both comparisons where applicable. Gate 2/3 decisions remain delegated; missing actual host/generation evidence blocks claims of full validation. Unauthorized disclosure cannot be undone by reverting instructions: stop before transfer when scope is unclear. Failed output must not mutate or replace photo work. Retain failure evidence without deleting assets.

**Future impact.** No further feature increment is planned. After the last repair, reconcile the final documentation, skill behavior, evidence references and single-MR scope; renew only evidence affected by changed inputs.

## Progress and reviews

| Item | Actual state | Next action |
| --- | --- | --- |
| Coordinated plan, QA and handoff | Three independent planning scopes passed | Retained with actual results |
| I01 | Implemented, verified and Gate 3 accepted | Accepted predecessor retained |
| I02 | Implemented, verified and Gate 3 accepted | Single MR and human final review |

| Required planning scope | Actual report | Disposition |
| --- | --- | --- |
| Requirements/source fidelity | `/root/plan_requirements_sol`, GPT-6.1 Sol | No material improvements recommended |
| Architecture/reviewability/simplicity | `/root/plan_architecture_sol`, GPT-6.1 Sol | No material improvements recommended |
| Verification quality | `/root/plan_verification_sol`, GPT-6.1 Sol | No material improvements recommended |

These are three assignments/reports for the coordinated artifact set, not three reports per document. The source plan's two earlier reports remain historical support and do not replace this conversion review or any implementation review. Planning architecture review assesses simplicity without claiming an implementation Ponytail pass. Record actual reviewer identities, inspected candidate and dispositions here or in scoped review notes after dispatch. Administrative result notes do not by themselves invalidate unchanged substantive review.

## Final reconciliation and retention

The orchestrator reconciled every coverage row against the final candidate, increment decisions, actual checks and independent reports. Confirm all inherited documentation remains included and unaltered except authorized necessary changes; reuse its successful unchanged checks when applicable. Inspect actual files selected for commit/MR for private/local evidence, personal paths, VCS data, dependencies and unsupported claims. Packaging changes are outside scope; the skill must remain repository-local and no maintained runtime flow may depend on excluded planning files.

Final delivery is one open MR on the verified existing destination, with current required CI and any actually expected provider reviews reconciled; merge remains human-owned. Host invocation, synthetic generation and human photographic acceptance are different claims: this advice feature cannot accept a photograph. No separate certification program is warranted for these instruction/metadata changes.

**Evidence retention and cleanup review — completed**, after relevant verification/reviews and outside the two increments; actual disposition is recorded below. Reuse source/review documents and concise candidate-bound proof; avoid duplicate archives. Keep durable proof, hold artifacts with active consumers, mark only concrete reproducible temporary material as cleanup-candidate, and mark uncertain ownership unknown. For new captures select owned paths, estimate size before large copying and preserve unique or failed inputs; there is no invented size threshold. Record actual retained location, reason, owner/consumer and review event when needed. No deletion or compaction is authorized or performed. Optional storage disposition does not block otherwise demonstrated behavior; missing required evidence does.

Human final review and merge take place separately in the single authorized MR. See [handoff.md](handoff.md).

## Execution record

### Planning reconciliation — 2026-10-28

Three separate fresh GPT-6.1 Sol reviewers inspected the same frozen substantive candidate: plan `423a6ac9c8ed6dbe9289a4a4e21194b7b4e512d0f870f5f810998816f5ec0203`, QA `a0995f243b10d0c266654a5fa502ab9653d1d8c7c5f612f071059402caf85a53`, handoff `4e7ecd1b2d08e5457191a1217e70af60d5c86fa435842a77a1134eac61190e1c`. Requirements preserved all options and exclusions; architecture confirmed safe useful boundaries and canonical policy; verification confirmed separate host, static, scenario and live-generation proof. Each returned no material improvements. The controller checked their decision-relevant source claims and reconciled all three before implementation. No findings required changes. These reports prove planning review only.

### I01 Gate 2 — orchestrator-approved under user delegation

Concrete comparison: preserved seven-document baseline on main `89935da` to the advice-only candidate on new branch `photo-directions`; source plans remain unchanged. Sole writer `/root/photo_skill_worker_sol` uses GPT-6.1 Sol and owns the two skill files, README and assisted-workflow advice section. No generation or AGENTS concept exception yet.

Preparation found the selected skill directory absent, no nested instructions, maintained README/source-map and manual owners usable, and actual CLI syntax `blackmask [--config FILE] status PROJECT`. Installed creator validator and separate YAML checks are available with Python 3.14.6/PyYAML 6.0.3; no installation or application run is needed. Current official skill guidance and live schema remain applicable (**still valid**, 2026-10-28); validator success will not establish host discovery. Synthetic selected/reference views, saved-value excerpt and nonempty pending/draft sentinels are prepared outside the repository, with whole-workspace digests. They are explicitly synthetic exercise workspaces, not validated native projects.

Acceptance remains Q1–Q5 and applicable Q10, then three independent result scopes, including the actual Ponytail architecture pass. No material product question is unresolved. Approval permits implementation and bounded verification; it does not pre-approve results or waive missing evidence.

### I01 Gate 3 — orchestrator-approved under user delegation

Accepted candidate: SKILL `99f147dd9884abbe19145e5c44735884532785dd14dd7742b26f4345afd065ad`, metadata `c415bd6ae16b13a3d4c41f1cb9410f93dd5a54b2a8bea84ae937149c8ecc5d6d`, README `4a4c7b1eb977a2b232bb5abc5c1e700b49a44b798e2f051372986714b913e77e`, assisted workflow `3d91822ed405764fe8db209504354c5b2686204bfc4f2bbc0b054aa19de12a51`. AGENTS retains only its inherited documentation-pass change. Copies and original baseline patch are retained in the orchestration session's private evidence directory.

Creator validator, separate supported YAML/UI metadata checks, 63 local links/anchors and diff formatting passed. Repository skill count changed 0→1; discovery description is 145 characters and UI description 48. Seven successful actual Codex CLI 0.162.1 sessions using GPT-6.1 Sol exercised explicit discovery/invocation, advice-only/extras-only, requested count, saved/inferred reference values, unsupported appearance, missing current result, ordinary-advice exclusion, and ambiguous thumbnail plus absent reference. Two visual cases used direct image attachments; raw event logs do not expose image viewing consistently. Initial host startup failed on sandbox access to host state; the supported escalation succeeded while inner sessions stayed read-only.

All seven selected/reference fixture files, nonempty pending/draft sentinels and the additional thumbnail preserved inventory/content digests. No project-writing command occurred. Fixtures are synthetic exercise workspaces, not validated native projects; the read-only sandbox is a secondary safeguard. No application suite, real photograph or photographic acceptance is claimed. See [QA results](qa-plan.md#execution-results).

Three distinct fresh Sol result reviewers completed on the frozen candidate: `/root/i01_requirements_sol` (source fidelity), `/root/i01_ponytail_sol` (actual `ponytail:ponytail-review` architecture/simplicity pass), `/root/i01_verification_sol` (observed verification). Requirements and Ponytail found no material improvements. Verification identified an unexercised ambiguous-thumbnail/reference case; the controller added one focused native check, the same candidate passed, and that reviewer closed the gap. All three final reports recommend no material improvements. No code repair was needed; unaffected reviews remain applicable. The controller inspected live skill/docs, observed outputs, command results and preservation evidence before accepting I01. Generation and its policy remain unimplemented until I02.

### I02 Gate 2 — orchestrator-approved under user delegation

Preparation rechecked the live built-in image-generation schema and the three conflicting policy sites: AGENTS normal edit prohibition, assisted-workflow introductory no-upload wording and named-reference no-upload wording. The schema supports local `referenced_image_paths` or the smallest necessary recent-image inclusion, never both; all selected local inputs require inspection. This is **still valid** against current available tools and previously checked official guidance on 2026-10-28.

The sole Sol writer updates the same skill/metadata/README/advisory section plus the AGENTS exception. Preserve I01 advice and explicit-only invocation. Canonical privacy/output boundaries live in the assisted workflow; the skill owns conditional generation procedure. Both optional modes are independently requested. Exact captions, visible watermark checks, one targeted correction, partial/failure reporting and output separation are coupled with permission wording in this increment. No API runner, image processor, added dependency or new control implementation.

Verification renews changed static/metadata/link checks and actual native invocation. A focused ambiguous-preview case must not infer AI-transfer authority. Controlled, explicitly described tool outcomes exercise unavailable/failed/partial/missing-mark/correction/aesthetic and copy-collision branches without pretending to be live results. One bounded live combined journey uses the prepared synthetic source, one brief direction plus one extra idea, and one initial concept per direction; only a failed watermark permits one targeted correction. No reference image is designated as a generation input for that journey. Inspect actual output pixels and caption/direction association, and exercise one collision-safe requested copy outside photo/reference roots. Preserve complete input inventories.

After useful evidence is collected, freeze the final five-file candidate for three independent Sol result scopes; architecture includes the actual Ponytail pass. Missing actual generation or host proof remains a real verification gap. No material design question is unresolved; this approval is not acceptance of unseen results.

### I02 Gate 3 — orchestrator-approved under user delegation

Accepted final implementation: SKILL `b90b39a723d522683deca65f9fec886cc29519feb32290f9b3c8153055ba61ef`, metadata `52e49df495a2b390ff8482eda9c18245afb98588e2a64b24ae7bf57c3f63bfdf`, AGENTS `846147c9433f81159794d590c694e56b2c55d9770879c43b19fc4b813fa1cbf7`, README `b929ce0e0ed5c107b1708a106e41ccf57195ca7fe42100e5cfcdac5c5833842c`, assisted workflow `aa15e0351bfb7ac9d86dabd098482eba56a0df15e5d2b982b31a0fe942f47e4d`. Comparison includes accepted I01 and the combined main-to-final scope. Source plans and inherited documentation remain preserved.

Creator validation, supported metadata and 73 local links/anchors passed; repository skill count remains one, description 179 characters and UI description 42. Three additional native Sol sessions passed: ambiguous preview intent asked for an explicit choice before generation; ordinary advice did not load the skill; nine controlled tool-outcome cases gave correct unavailable/failed/partial/correction/copy decisions. Controlled outcomes are hypothetical behavior evidence, not live generation failures.

The real synthetic combined journey produced exactly two concepts from two initial built-in calls, with zero correction calls or aesthetic retries. Exact arguments included only the selected synthetic source; analysis-only reference and previous generated image were excluded. Both output PNGs were independently inspected by controller and verification reviewer: readable embedded `AI-GENERATED CONCEPT`, matching direction labels and exact adjacent caution captions. They are AI illustrations, not project renderer results. An apparent worker-view omission was investigated; identical returned/default bytes and independent original-detail views disconfirmed an artifact defect. No speculative repair or regeneration was introduced.

The first completed output was copied with exclusive creation to a new name when the requested name existed; copied bytes match the verified generated file and the old file is unchanged. All seven selected/reference fixture files and the separate scenario thumbnail retained inventory/content digests. Outputs remain in tool-default/private evidence storage, outside photo/reference roots and Git. No private photo, application processing or human photographic acceptance was exercised.

Three independent fresh Sol scopes completed on the frozen candidate: `/root/i02_requirements_sol`, `/root/i02_ponytail_sol` (actual Ponytail pass) and `/root/i02_verification_sol`. All final reports recommend no material improvements. The verifier withdrew the tentative artifact concern after disconfirming evidence. No implementation repair remained. Controller acceptance follows actual output inspection, exact argument/audit review, preserved-scope check and reconciled reports.

### Final documentation, scope and retention reconciliation

The final five implementation files agree on explicit invocation, independent optional modes, current-control advice, selected inputs, watermark/caption, bounded failure handling and ordinary-photo safeguards. The inherited documentation pass covers trimap optionality, JPEG SDR-primary import, effects bases, B0/B1 export behavior, comparison controls and recovery; its successful unchanged checks (157 local links and 31 CLI examples/options) remain applicable to those preserved changes. A reverse-check of the original inherited patch against the final working tree passed. All source-coverage rows have owners and the evidence categories shown in QA; no application code, package or dependency was added.

Retain the source/review plans and concise result records in Git. **Keep** synthetic fixtures, baseline/candidate snapshots, raw native-session outputs, exact tool arguments and copy/inventory receipts in the private orchestration evidence directory while this MR is under review; owner is the orchestrator, consumer is review/reproduction. **Keep** the two tool-default generated files and requested private copy. **Hold** the initial startup failure and viewing-ambiguity evidence so limits remain inspectable. The extra byte-identical inspection copy is a later cleanup candidate only after its review consumers finish. No deletion, compaction, overwrite or provider-retention assurance occurred. Generated/private evidence is excluded from the proposed Git files.

The Git publication boundary remains one open MR to the existing repository, with current provider status assessed there. Implementation acceptance is not human photographic acceptance, merge approval or a claim about unexercised application runtimes.

Final publication inspection checked all 15 selected text files: no private fixture/log/image content, personal paths or secret-pattern matches were found. Five planning/result files passed 21 local link/anchor checks and whitespace/newline checks; the tracked diff formatting check passed. These final result-note additions change no links, metadata or behavior.

The pre-publication refresh found main advanced to `800f16c` through the comparison-publication-validation merge (PR #38). Its changes affect comparison publication validation, associated tests and three file-contract sentences; the skill prohibits that writing operation. They do not change current controls, read-only status, metadata or the reviewed five-file implementation. These upstream changes belong to main, not this feature's application scope, and must be preserved during integration.
