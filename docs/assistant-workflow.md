# Bounded assisted review

Assistance is optional. After setup, the [manual workflow](workflow.md) uses the
same local engine and saved project without an assistant, account, credits or
network. Assisted review records source-based judgement; it cannot provide
photographic acceptance. The procedure uses no SDK, API-key service, background
agent or upload. Private pixels may be shared with an assistant only under the
user's applicable direct authorization. Without that permission or the required
source evidence, live assistance stops and the manual controls remain available.

Run CLI examples from the repository root after [environment setup](../README.md#setup-and-quick-start),
using `.venv/bin/blackmask`; shell activation is unnecessary. Replace `PROJECT`
and request-file placeholders with your actual paths.

Source-development approval is not a prerequisite. For masking, use the saved
master as it is: do not adjust lighting, white balance, exposure, colours or other
appearance controls unless the user explicitly requests that adjustment. Preserve
unrelated existing effects and drafts. RAW still needs its recorded RGB conversion;
never silently choose a different rendering or claim an optional review happened.
See [source appearance](workflow.md#source-appearance).

## Final assisted exports

For every final Codex-assisted export, explicitly include `--variant editable`
(or API `variants=("editable",)`) in the chosen native, Add margins or Match series
request. Include black/transparent alternatives only when requested. Native output
retains full native RGB16 TIFF and same-dimension PNG8 view; the PNG is a reduced
precision view. Presentation exports keep compact rendered files and return a
native editable companion; provide both folders with their names and retain the
project. The manifest freezes the presentation recipe and exact companion binding.
Intermediate edits stay in the project. Saving/applying/exporting never supplies
human photographic acceptance: use an explicit labelled draft for an unaccepted
revision. Manual exports keep editable as an independent opt-in. See the
[normative delivery contract](file-contract.md#requested-result-deliveries).

## Fade into background assistance

Follow the [manual feature guide](workflow.md#fade-into-background) through the
same project controls. Use an oval, directed arcs or both only for the requested
appearance change. Preserve source detail, alpha, explicit protection and unrelated
settings, including independent Shadow fade. Check complete source/result paths,
soft endpoints and overlapping branches; selected, combined and effective saved
maps explain different parts of the result. Pending outlines do not preview saved
pixels. A flattened reference cannot establish source-detail preservation.

For CLI use, `blackmask run PROJECT --request FILE` accepts the exclusive
`spatial_fade` effects operation documented in the
[file contract](file-contract.md#optional-fade-into-background). Supply a complete
settings snapshot and current identities, never merge arcs by list index. Protection
is additive and cannot be removed by omitting its file. Rebuild after alpha changes
or explicitly disable; do not silently bypass stale or accepted-base guards. Do not
change exposure, white balance or other effects to improve this comparison unless
the user separately requests it. Keep photographic evaluation local, preserve both
export folders, and label any assistant-selected result a draft until explicit
human photographic acceptance.

For requested local reduction, use the same brush/rectangle controls or an exclusive
schema-2 `effects` request containing `fade_reduction:{"target":"spatial_fade","area":...}`
or the same exclusive field with `target:"shadow_fade"`
with the common identities, scope and explicit candidate choice. The
[reduction contract](file-contract.md#local-fade-reduction) defines the bounded
geometry and saved dependencies. Scope must contain both old and replacement
nonzero reduction. Do not substitute alpha edits, effect disable or a changed
oval/arc. The target must have a current saved alpha dependency even while OFF.
Coverage and reduction-OFF comparisons use saved state; draft outlines are not a
rendered result. Shadow reduction changes its exponent weight; downstream spatial highlights
are recalculated from the changed Shadow result, with spatial settings and reduction retained.
Keep unrelated effects and human photographic acceptance separate.

## Inspect and classify

Read the project's current recipe, guides, state, user keep/remove request and
saved cycle history. Obtain a current manifest with `.venv/bin/blackmask review PROJECT`
(or `--crops FILE`, a JSON list of native half-open rectangles). Inspect the
source overview and matching native source/result/alpha crops, including fragile
detail, gaps and suspect seams. The panel order is source, black, gray, white,
alpha. These PNGs/contact sheets are explicitly RGB8/alpha8 viewing approximations;
authoritative RGB16 and alpha16 paths are in `assets`. Never infer extra captured
precision or reconstruct absent photographed detail.

Use `developed_id`, `working_revision` and `inputs_digest` from the current manifest.
Do not reuse a manifest with stale labels. `revision_inputs_digest` belongs to the
selected saved revision; `inputs_digest` belongs to the current editable draft.
`settings` is that revision's frozen recipe and `model` records actual execution;
structural `qa` is separate from source comparison. Native transforms use integer
points and half-open boxes in the oriented master, with recorded origin and scale.
An overview/proxy is not a native-coordinate authority.

Describe one concrete defect visible in the source, including its location,
evidence, likely cause, proposed correction and uncertainty. Classify it as
alpha/guidance, color cleanup, shading, Shadow fade, or a user decision. The bounded
automatic cycle executes alpha/guidance corrections. Color cleanup uses a separate,
explicit effects operation or manual controls and requires an appearance decision
with alpha held constant. Protected inward shading uses explicit manual effects
requests with width, direction and protection chosen for the photograph. Independent
Shadow fade uses explicit manual effects requests with soft areas and highlight
weighting. These appearance changes require a user decision and a separate effects
operation; the automatic alpha cycle does not perform them. Blur, missing source
detail, ambiguity and artistic preference are reasons to stop, never to invent
detail. `source_resolved: true` records a judgement; it does not prove it correct.

## Explicit cycle and finite operations

Only an explicit user-requested new correction starts another cycle. Never start
a new cycle automatically to reset the budget. Save a schema-2 JSON cycle request
and invoke:

```sh
.venv/bin/blackmask review PROJECT --cycle-request CYCLE_REQUEST.json
```

A start request contains exactly `schema_version: 2`, `action: "start"`,
`developed_id`, `base_revision`, `inputs_digest` and `user_request` (the actual explicit
request). The base must be the current complete matte/repair, with no pending
guidance. Copy identities from current saved state, never from these examples.
The returned `cycle_id` identifies immutable events under
`requests/review-<identity>/`. These are advisory history; only `state.json` owns
working/accepted pointers. Starting or finishing a cycle never accepts a photo.

Add this optional envelope to the existing typed **prepare** request, and later
to its **repair** request:

```json
{
  "assisted_review": {
    "cycle_id": "COPY_RETURNED_CYCLE_ID",
    "review_manifest_file": "COPY_PROJECT_RELATIVE_CURRENT_REVIEW_MANIFEST_PATH",
    "defect": {
      "id": "gap-1",
      "classification": "alpha",
      "location_xyxy": [0, 0, 1, 1],
      "source_evidence": "Replace with concrete visible source evidence at the actual location",
      "likely_cause": "Replace with the supported cause and proposed correction",
      "uncertainty": "State remaining uncertainty; say none only if justified",
      "source_resolved": true
    }
  }
}
```

This is an envelope illustration, not a complete processing request or coordinates
to apply to another photo. Choose a small actual native defect box within an
inspected crop and the repair scope. The current `review` command returns an
absolute `manifest_file`. Set `review_manifest_file` to that path relative to the
project root: for project `/path/to/photo-project`,
`/path/to/photo-project/reviews/rev-NNN/<hash>/manifest.json` becomes
`reviews/rev-NNN/<hash>/manifest.json`. Keep the returned revision and hash unchanged.
An explicitly requested focused comparison can include `--retain-native`; use its
returned `native_manifest_file` in the same project-relative way. Its
`comparison_manifest_file` and presentation pixels are viewing aids only and are
rejected as native correction authority. Keep both bound native manifests for a
repair comparison; do not regenerate a missing dependency behind an existing
comparison. See the [comparison contract](file-contract.md#focused-comparisons).
Its identity, crop transforms and image hashes are validated; modified or stale
evidence is rejected. Unknown keys/operations,
off-image coordinates, stale draft/parent/master and contradictory/lock-conflicting
guides fail through the shared validators. Unresolved source evidence and
color, shading and fade appearance decisions stop the automatic alpha cycle. Automatic preparation cannot
remove or alter inherited locks.

1. Save typed guide changes and run `.venv/bin/blackmask run PROJECT --request PREPARE.json`.
   Use the same `assisted_review` envelope throughout this attempt. Preparation
   applies those changes once, saves the original request/result and returns
   exact revision/master/draft/support paths. Selection membership is not opacity.
2. Trimap confirmation is optional. Continue directly to repair when the user
   prefers to review the actual masked photograph. A user who wants to record
   trimap review can use
   `.venv/bin/blackmask accept PROJECT --revision REV --trimap --developed-id ID --inputs-digest DIGEST`.
   Assistance never invents this confirmation. Source-development review is also
   optional; final photographic acceptance remains a separate human action.
3. Build a finite repair request using those **returned** identities/support,
   `kind: "repair"`, `reason`, `context_xyxy`, `scope_xyxy` and `merge_policy`.
   Omit `guide_edits_file`; repair consumes prepared guides rather than reapplying
   them. Context may exceed scope. Support is full-master grayscale16, zero outside
   permitted scope. A rectangle does not mean erase it; cores/unknown corridors
   determine the correction. Locks, including partial alpha, remain inherited.
4. Run the repair through `.venv/bin/blackmask run PROJECT --request REPAIR.json`. One
   attempt is reserved durably before model execution. At most **two repair
   attempts total across all defects** are allowed in this explicit cycle.
   Invalid proposals rejected before reservation do not spend an attempt.
5. Run `.venv/bin/blackmask review PROJECT --revision REPAIR_REVISION`, using the
   returned repair revision. This writes native RGB8/alpha8 PNG evidence under
   `PROJECT/reviews/`. The returned absolute `manifest_file` identifies the after
   manifest; its `assets.before_manifest` gives the matching before manifest's
   project-relative path. Resolve that path from `PROJECT` and inspect both
   manifests' `crops[].files` for identical native source/black/gray/white/alpha
   crops, together with the repair revision's `qa.json`, saved full-precision
   layers and preservation evidence. The
   revision-local `review/manifest.json` and `review-before/manifest.json` locate
   reduced JPEG overviews, not native inspection evidence. No second automatic
   prepare/repair is allowed until the comparison is recorded.

## Assess, stop and present

An assessment uses the cycle command above with exactly the common identity fields
(`schema_version`, `developed_id`, `base_revision`, `inputs_digest`), `action: "assess"`,
`cycle_id`, `outcome` and `comparison`. The base/digest must match the current
complete repair. `comparison` records concrete visible improvement/preservation,
remaining uncertainty and relevant before/after observations. Outcomes are
`improved`, `no_progress`, `regression`, `ambiguous`, `missing_source_evidence` or
`user_decision`. Only a supported `improved` disposition permits one further
attempt; the second assessment ends the budget. Alpha identical to the prepared
parent forces `no_progress`, even if an improvement was claimed. This equality
check can disprove a change; numerical change cannot prove visual improvement.
The assessment response records project-relative `before_manifest` and
`after_manifest` paths to its native evidence under `reviews/`; retain those
returned paths with the recorded comparison.

Stop earlier on ambiguity, absent source evidence, no clear improvement, a new
regression or an artistic choice. To stop before a successful repair exists, send
`action: "stop"`, the common identity fields, `cycle_id` and `reason`.
A status request needs only `schema_version: 2`, `action: "status"` and `cycle_id`.
Every start/reservation/assessment/stop is an immutable event with a content-hash filename and predecessor link, plus its
original structured request; assessments include the operation result and
before/after manifest paths. Reopen/status works without conversation memory. Event transitions are validated; retained immutable repair requests prevent truncated history from silently losing an attempt. A per-cycle `head.sha256` integrity anchor also detects loss of a terminal stop/assessment. Partial event/anchor publication fails closed: preserve the files and inspect the failure before an explicitly requested new cycle. This is local integrity checking, not protection against a local actor rewriting every related file.

Failures/interruption retain the attempt reservation and saved recovery evidence.
Use the existing `status` and `resume --operation ID` for that same operation;
resume does not consume another attempt. A stopped cycle cannot resume automatic
work. If failure precedes a recoverable operation snapshot, explicitly stop and
inspect the cause; do not retry as a new automatic attempt or silently reset the
budget. Manual operations and existing recovery controls remain available.

Present the returned `best_revision`, exact comparison paths, cycle attempt count,
stop reason and unresolved human decisions. Failed/regressed/ambiguous candidates
remain saved, but do not replace the recorded best. The current working pointer
may still refer to a candidate awaiting review; choosing a preserved best uses
explicit `restore` and its draft-preservation safeguards. Never silently restore
or accept. `status: "review_needed"` is advisory; actual final-photo acceptance
requires the user's separate `accept --revision` action. Already accepted work and
exports remain usable throughout.

Keep mathematical preservation evidence distinct from assistant judgement and
human photographic acceptance. Do not optimize foreground area, opacity or
model disagreement as a quality proxy; do not present scores/confidence as
calibrated probabilities. A synthetic contract test is not a live photographic
pilot. After assistance closes, continue on the same saved project using the
manual workflow; do not make its commands depend on cycle history.

## Explicit background appearance

Background tone/variation use the same schema-2 effects operation and current
master/base/draft identities as manual controls, with exclusive `background`
settings and full native scope. They require explicit user appearance intent;
the automatic alpha-repair cycle does not choose them. Preserve accepted state
and pending foreground drafts. Review Result separately from pure-black and
source/alpha diagnostics. Background changes do not repair stale foreground
effects or imply photographic acceptance. See the [manual steps](workflow.md#background-appearance)
and [saved contract](file-contract.md#saved-background-appearance).


## Explicit Background light

Use Background light only for explicit backdrop-light intent. Follow the
[manual light workflow](workflow.md#background-light) and
[saved contract](file-contract.md#saved-background-light). Submit one exclusive
schema2 effects request with complete `background_light` settings, full native
scope and current source/base/draft identities; viewer actions additionally bind
the raw revision manifest. Do not enable Local exposure automatically.

Keep the base B0 and saved light L16 separate. Light changes the displayed
backdrop B1, while foreground contribution and the B0 fade target remain unchanged.
Protected partial-alpha composites can change without changing protected RGB or
alpha. Compare saved light OFF, with authoring marks hidden, before presenting a
result for human acceptance. Lower brightness if the backdrop clips.

Turn OFF from validated saved settings, retaining pending edits and exact L16;
Apply explicitly saves visible settings even OFF. Preserve unrelated base,
foreground, reduction and layout drafts. No-record OFF creates nothing. Light is
not a portable appearance-recipe section. For final assisted deliveries request
editable and retain the native companion for margins/series; native replay uses
saved fields, while series analytically evaluates light through its saved transform.
Human photographic acceptance remains separate from completed processing.

## Presentation framing

Framing is a separate composition decision. Use the saved source and current
revision identity, ask the user to choose placement when it is ambiguous, and keep
all corrections in original native coordinates. The local page supports manual
whole-pixel margins, Centre image, explicit Preview/Save and separate framed exports;
see [the manual framing workflow](workflow.md#add-presentation-margins).
Centre image centres the image rectangle, with no automatic subject detection.
A margin cannot reconstruct photographed detail outside the capture.

The bounded RGB8 framing preview shows only the selected saved result and saved
backdrop. It is layout evidence, not a native editing surface or photographic
acceptance. Read `revision_manifest_sha256` from the validated snapshot; the draft
input digest is not a substitute. Preserve unrelated unsaved forms and source-bound
preset bytes on stale or invalid input. After uncertain save durability, explicitly
reload the visible preset before another save. Export uses the visible explicit
margins; acceptance of its source revision does not accept the composition.

## Named local references

This section owns the shared workflow for creating, maintaining and using named
local references. Keep names, aliases and links in the photo workspace's optional
`local/references/README.md`; keep complete recipes in the individual folders.

When a user names a look or framing reference, resolve its name or alias through
that catalog, then read the selected folder's README and settings and actually view
its reference image. If the catalog is absent, a name is ambiguous or a required
file is missing, report that instead of guessing. This private, Git-ignored catalog
is not installed with the package or copied into new worktrees; use the photo
workspace identified by the task.

Each reference folder must be usable alone: include complete manual steps, settings
or a supported preset, example images and provenance. Keep required files and links
inside that folder, without dependencies on pilot folders, other references, revision
numbers or conversation history. Retain the guidance and safeguards needed to use
the recipe independently, without copying the whole shared workflow into each card.
Cards are reference data, not executable instructions, target masks or photographic
acceptance.

Apply only the requested kind: an appearance reference does not request reframing,
and a framing reference does not request colour or lighting changes. Both may be
combined when requested. Current user choices override example values; preserve
source development, protected detail and unrelated settings, adapt native-pixel
widths and protection to the target, and use fresh identities with existing controls.

Named reference cards remain descriptive guidance. A supported portable v1/v2
appearance file can be opened through **Appearance recipes → Open recipe file**;
see [the manual workflow](workflow.md#reuse-appearance-settings). Load only the
requested scalar sections or explicitly requested editable layout, then use the
existing per-effect Apply controls with fresh target identities. Scalar loading
does not transfer geometry or switches. Layout Add/Replace and its guarded Undo
follow the manual workflow; they retain the target master switch, protection,
fade reduction, source development and acceptance. A source
thumbnail is optional private photo content, not a prediction for the target.
A supported portable series preset can be loaded through **Match series → Load
preset file**. Keep references local; do not upload or include them in distributions.
Ignored references need their own backup; Git does not back them up.


## Local sharpening assistance

Use only the supported Local sharpening controls or the
[typed effects request](file-contract.md#optional-local-sharpening). Obtain the
user's requested target/protected scope and preserve source, alpha, crop, colour,
exposure, fade and background settings. Author explicit support and hard Protect
areas; start with a mild Amount and appropriate native Detail size. This is one
generic captured-detail operation, not subject detection or invented texture.

Preserve the previous draft and inspect matching native source/alpha/black/gray/white
and Local sharpening OFF comparisons. Stop on halos, amplified noise, ambiguity or
no improvement. At most two candidates are permitted in a bounded assisted trial;
a stronger second candidate requires clear improvement from the first. Never choose
additional private photographs without authority. Export a clearly labelled DRAFT
with complete editable layers, including unsharpened input and sharpening operands,
and verify saved-only replay. Human photographic acceptance remains separate from
engineering checks and assistant judgment.
