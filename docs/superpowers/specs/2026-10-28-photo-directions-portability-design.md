# Photo Directions for OpenCode 2 and Antigravity

**Status:** Proposed design for the requested implementation plan; no skill implementation or host evaluation authorized by this document.
**Goal:** Make the existing repository-local `photo-directions` skill usable in OpenCode **2** and Antigravity while preserving Codex behavior and all photographic/privacy safeguards.
**Scope decision:** The user selected OpenCode 2. OpenCode 1 support and migration are excluded.

## Current state and approach

The canonical skill is [SKILL.md](../../../.agents/skills/photo-directions/SKILL.md). Its advice workflow is largely portable, but its invocation wording and image-tool instructions assume Codex. [openai.yaml](../../../.agents/skills/photo-directions/agents/openai.yaml) disables implicit invocation in Codex. The [maintained assisted workflow](../../assistant-workflow.md#photo-directions) owns the advice and concept/privacy contracts.

Keep one skill in `.agents/skills/photo-directions/`, already a documented discovery location for both target hosts. Add one `references/hosts.md` containing only host-specific invocation, image inspection, input selection and output delivery. Keep common advice and concept safeguards in their existing owners. Preserve the skill identity and Codex UI metadata; no runtime code, dependencies, plugins, generated skill copies, symlinks, installer, global configuration or additional discovery directories.

Alternatives considered: independently maintained copies would duplicate policy and create drift; installation/configuration adapters are unnecessary for the documented shared location. A single unqualified workflow would leave the existing Codex tool assumptions unresolved. The recommended shared skill plus one host reference addresses the actual differences without a new executable abstraction.

## Invocation contract

| Host | Explicit entry | Host control and limitations |
| --- | --- | --- |
| Codex | `$photo-directions` | Preserve `policy.allow_implicit_invocation: false` in `agents/openai.yaml`. |
| OpenCode 2 | `@photo-directions` | Add `metadata.opencode/autoinvoke: "false"` to shared frontmatter. This suppresses model-list advertisement; explicit ID loading remains available and permission checks still apply. It is not a general security boundary. |
| Antigravity | `/photo-directions` where supported by the actual surface; otherwise explicitly request the named skill | Current App/CLI documentation describes slash invocation; verify the installed surface before documenting its exact entry. No equivalent host-enforced automatic-selection opt-out was established by the reviewed documentation. |

The shared description names explicit `photo-directions` requests without making `$` the only recognized syntax. Before inspecting any photo or running the workflow, require a direct user invocation or explicit named-skill request. Ordinary editing/advice and skill mentions in reference material do not authorize execution. Automatic discovery or reading by a host never supplies that authorization. Keep Antigravity's distinction between possible automatic loading and prohibited unrequested execution explicit; if real sessions execute the workflow without a user request, compatibility fails and needs resolution, not a relaxed acceptance criterion.

## Inspection and advice

Require an available image-input model and a host-supported way to actually inspect each selected image. OpenCode 2 documents image attachments and its `read` tool for supported raster formats; use its live schema and granted access. A filename, decoded text placeholder or directory listing is not image inspection. Host-resized inputs remain reduced views, not native-detail evidence. An unsupported RAW/TIFF input needs an existing suitable view or separately requested preparation; this skill must not create or repair one.

Use only selected source/result/reference artifacts and existing state. Preserve revision/freshness reporting, saved values versus visual estimates, protected geometry, current-control grounding, normally two useful directions, requested counts, optional extra ideas and honest unsupported-control labels. Missing images or ambiguous identity produce a bounded request or limitation, never a library scan, guessed appearance or project mutation. Private-image inspection through a hosted model still requires applicable direct permission.

## Optional concepts

All hosts use the existing [AI concept boundaries](../../assistant-workflow.md#ai-concept-illustrations). An explicit concept request must identify the allowed inputs. An analysis reference, unrelated conversation image, extra-ideas request or ambiguous native-preview request supplies no generation authority.

Host instructions must inspect the live built-in tool schema and establish exact selected-input control, output-pixel inspection and supported inline delivery before generation. Codex retains its current `view_image`, mutually exclusive input mechanisms and `generatedImage` instructions in the host reference. Antigravity documents a generative image tool, but its installed schema and delivery require observation. No OpenCode 2 built-in generation capability was established: treat concepts as unavailable unless the actual host exposes a suitable built-in tool. Do not install or substitute MCP, SDK, shell/API, browser-provider or paid integrations.

If any required capability is unavailable, retain grounded advice and clearly report the missing concepts; if image inspection itself is unavailable, do not claim photo-specific analysis. Preserve the embedded `AI-GENERATED CONCEPT` watermark, exact adjacent caption, one targeted watermark correction per illustration, no aesthetic retries, explicit partial delivery, separate storage and collision-safe requested copies. A successful generation request is not evidence of a readable watermark or displayed output.

## Verification and boundaries

One coherent instruction/documentation change; the [implementation plan](../plans/2026-10-28-photo-directions-portability.md) defines ordered tasks and synthetic acceptance cases. Validate metadata and links separately from native discovery, model behavior, actual image viewing and optional live generation. Reuse existing [photo-directions QA coverage](../../incremental-plans/photo-directions/qa-plan.md) without changing its historical results or importing its earlier execution/publication authority.

Support is recorded per exact host version, surface and model: advice/invocation, image inspection, and concept generation/delivery have separate outcomes. Advice support may pass with an explicitly unavailable concept capability; full concept support requires actual authorized evidence. A missing host run remains pending. No private-photo evaluation, installation, upgrade, account change, paid run, commit, push or publication is authorized by this planning request.

## Evidence and remaining prerequisites

Checked 2026-10-28. The working tree was clean on `main`, one local commit ahead of the existing `origin/main` ref; no fetch was needed for this local planning scope. OpenCode was not found on the inspected `PATH`; this does not establish absence of every possible installation. Antigravity application metadata reports version 2.28.0; the application was not launched. Its exact surface and exposed tools remain unverified.

- [OpenCode 2 skills](https://opencode.ai/v2/docs/skills/): shared discovery, explicit `@` loading and selection metadata.
- [OpenCode skill parser](https://github.com/anomalyco/opencode/blob/dev/packages/core/src/config/plugin/skill-file.ts): the inspected development source accepts the string `"false"`; recheck applicability to the installed release during execution.
- [OpenCode 2 tools](https://opencode.ai/v2/docs/tools/) and [attachments](https://opencode.ai/v2/docs/attachments/): image reading, media input and model limitations. Context7 returned mixed-version image snippets, so version-2 official pages own these decisions.
- [Antigravity skills](https://antigravity.google/docs/skills): discovery and surface-specific invocation.
- [Antigravity models](https://antigravity.google/docs/models): built-in image generation exists in the product documentation; no exact installed-tool contract or successful generation is inferred.

The updated user instructions require Context7; its previously resolved primary-source libraries were consulted, with official version-specific documentation and owning source used to resolve mixed-version or missing detail. These are planning sources, not native compatibility evidence.
