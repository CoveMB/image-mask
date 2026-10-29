# Photo directions host mechanics

Read only the section matching the actual host and exposed tools. The
[shared skill](../SKILL.md) owns the workflow; the
[assisted workflow](../../../../docs/assistant-workflow.md#photo-directions) owns
user-facing invocation and photographic/privacy boundaries. No host's discovery,
automatic loading or permission setting supplies user execution or image-transfer
intent. Observe the actual tool schema before using a tool; do not install a
missing capability or change permissions.

## Codex

Explicit entry is `$photo-directions`; preserve
`policy.allow_implicit_invocation: false` in `agents/openai.yaml`.
Use the exposed image viewer for selected inputs. Inspect each local input with
`view_image` before concept generation.

For the built-in image-generation tool, when every designated input has a local
path, use `referenced_image_paths`. Otherwise use
`num_last_images_to_include` only if its smallest supported selection contains
every intended input and no unselected image. Never supply both mechanisms.
If neither selects exactly the intended inputs, ask for those images to be
attached again. Reuse clear image-specific permission under the shared rules.
Inspect actual returned pixels, then deliver verified concepts with
`generatedImage`, direction labels and the shared skill's exact caption.

These mechanics preserve the existing Codex contract. Tool availability and
successful invocation, viewing and delivery must still be observed in the session.

## OpenCode 2

Use `@photo-directions`. The shared `.agents/skills/photo-directions/SKILL.md`
is a documented project discovery location, including discovery upward from a
nested working directory to the project root. Do not create another skill copy.
Confirm that the resolved ID points to this definition if another source shadows
it. Respect denied access; do not change permission settings to force loading.

Frontmatter `metadata.opencode/autoinvoke: "false"` omits the skill from automatic
model advertisement; it remains registered for explicit ID loading. Where the
live V2 schema agrees, the native loader takes `{"id":"photo-directions"}`.
This is selection control, not a security boundary. Do not use V1
`skill({ name: ... })` or V1 configuration.

For image inspection, use an image-input model with native `read` or user
attachments under the live schema and granted access. V2 documents PNG, JPEG,
GIF and WebP image input. A successful text read or attachment placeholder does
not establish appearance. Inputs can be resized or re-encoded; report reduced
view limitations. Unsupported formats need an existing supported view or a
separate preparation request, never an automatic conversion/export.

No suitable built-in concept generator has been established for this host.
Generate only if the actual session exposes a built-in tool meeting the shared
exact-input, output-inspection and inline-delivery requirements. Otherwise report
the missing concepts while retaining useful inspected-image advice. Do not
substitute integrations or infer absence solely from an unavailable evaluation.

The OpenCode 2.2.0 release parser accepts the string `"false"`; matching installed
desktop and bundled CLI version metadata was observed. Native discovery, model
image input and concept delivery remain unverified. Sources:
[V2 skills](https://opencode.ai/v2/docs/skills/),
[2.2.0 parser](https://github.com/anomalyco/opencode/blob/v2.2.0/packages/core/src/config/plugin/skill-file.ts),
[V2 tools](https://opencode.ai/v2/docs/tools/) and
[V2 attachments](https://opencode.ai/v2/docs/attachments/).

## Antigravity

Explicitly request “Use the photo-directions skill.” App/CLI documentation also
describes `/photo-directions`; use it only where the actual surface exposes that
entry. Do not assume the IDE has the same slash interface. Workspace discovery
uses `.agents/skills/<skill-folder>/`, so this skill needs no copy or installer.

Antigravity may automatically load a matching skill. The shared first-step guard
still requires explicit user intent before inspecting material or executing the
workflow. No equivalent platform-enforced selection opt-out has been established;
do not describe this instruction guard as a host security control.

Require an image-input model and an exposed native image viewer or attachment
mechanism that actually supplies pixels. Inspect its schema and granted access
instead of borrowing Codex parameter names. Observe which selected image and view
were received; unsupported input, text placeholders and reduced views follow the
shared inspection rules.

Product documentation describes a built-in generative image tool. Before using
it, inspect the live schema for exact designated-input selection, returned-pixel
inspection and supported inline delivery. Use only those observed native
mechanics with the shared concept safeguards; otherwise report the missing
capability. Do not invent tool names/parameters or use provider/API/MCP substitutes.

Only application version metadata (2.28.0) was observed locally. The active
surface/model, native invocation, image-input behavior, generation schema and
inline delivery remain pending. Sources:
[Antigravity skills](https://antigravity.google/docs/skills) and
[models and generative image tool](https://antigravity.google/docs/models).
