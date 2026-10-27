# Offline manual review

For managed original ownership, first follow the [configured library and safe
import](library.md) instructions, then open the returned `project/` path with the
same explicit `--config FILE`. This selects shared existing model locations and
leaves the manual masking controls below unchanged. Standalone projects use the
commands below without library configuration.

For an imported photo, the recovery panel reports the latest Result gallery's
Draft/Accepted or pending status. Repair latest Result preview explicitly repairs pending
output from saved layers; polling and restore do not publish it. Keep the matching
library config when opening the viewer. See the [gallery contract](file-contract.md#current-result-gallery)
and [recovery guidance](troubleshooting.md#native-matte-and-export-recovery).

After [explicit environment/model setup](../README.md) and [model cache setup](guidance.md),
open one source/project. From the repository root, use the environment executable
shown below; shell activation is unnecessary. Use your own paths and select guides
from the actual source.

```sh
.venv/bin/blackmask open /path/to/source.tif --project /path/to/new-project --sam-cache /path/to/sam-cache --model-cache /path/to/vitmatte-cache
# Later: reopen saved assets, without needing the original capture path.
.venv/bin/blackmask open --project /path/to/new-project --sam-cache /path/to/sam-cache --model-cache /path/to/vitmatte-cache
```

The command opens the packaged page and keeps one local server running until
Ctrl-C. Manual mask correction requires no account, assistant, network connection,
external editor, support mask or script. Downloading models is a separate, explicit
setup action. Preserve the original capture independently, keep the launch URL
private and do not forward the local port. Use
`open --headless --project /path/to/project` for JSON-only operation; other
documented CLI commands can run in another terminal.

## Source appearance

For a supported SDR-base gain-map JPEG, add `--jpeg-sdr-primary` when creating
the project with `open`, or importing with `import`. This selects the ordinary
SDR image and omits HDR brightness while preserving the complete original.
See the [supported inputs and saved decision](file-contract.md#explicit-sdr-primary-jpeg-import).

Source-development approval is not required. Open a project and start authoring
mask guides. Choose **View → Source** to inspect its RGB8 viewing approximation;
a new project has no Result yet. The saved RGB16 master remains authoritative.

Mask work preserves that master's lighting and colours. Assistance must not
change exposure, white balance, contrast, saturation, colour, sharpening or enable
cleanup, shading or other appearance effects unless you explicitly request them.
Use only the adjustments you request; retain unrelated saved settings and pending
controls. Trimap confirmation is optional; final photographic acceptance remains
a separate explicit action after reviewing the actual masked result.

To retain the look you developed elsewhere, import a supported developed image,
preferably uncompressed RGB16 sRGB TIFF. RAW cannot be used without decoding to
RGB; its conversion settings remain recorded in `source.json`. The tool does not
silently substitute a different white balance when as-shot metadata is unusable:
supported RGB DNGs use their recorded white point and calibration profiles as
described in the [saved contract](file-contract.md#raw-as-shot-white-balance). Otherwise, explicitly
choose a supported rendering or supply a developed TIFF. A different development
requires a separate project, preserving the previous one. The legacy CLI development
review remains optional and does not gate masking; schema-2 projects open without migration; schema-1 projects are refused without writes.

## Author guides and select subjects

Add a stable named SAM group for each subject. Choose whether to retain it and
whether its interior is opaque or uncertain/translucent. Use SAM keep/remove
points or a keep box for that group. Select a role before drawing:

- **Confirmed foreground core** asserts fully opaque source-supported pixels.
- **Confirmed background core** asserts source-visible empty background.
- **Unknown corridor** keeps fine, translucent, defocused or ambiguous detail uncertain.
- **Repair support16** defines allowed changes, with optional inward feather in native pixels.
- **Saved alpha/RGB region lock** copies the selected saved revision’s exact values,
  including partial alpha and corresponding RGB, on repair and full reruns.

Points, rectangles and coarse strokes use the same native rasterizer as the CLI.
SAM hints use points or a keep box; the other roles use points, rectangles or
strokes. Drag on the canvas, or use **Native coordinates** and **Add numeric guide**
with `x,y`, `x0,y0,x1,y1`, or `x,y;x,y;…` for a stroke. A box is half-open: its right
and bottom edges are excluded. Stroke radius and support feather are native pixels,
independent of zoom. Letterbox areas cannot create guides. Choose **Pan only** or
Shift-drag to pan; with canvas focused, arrows pan and +/- zoom. **Fit** resets pan
and zoom; **Native 1:1** gives one displayed pixel per native pixel. A native crop
changes only review, never the master or authoring coordinate system.

Use **Recorded guides** to select and explicitly remove a guide. For locks, remove,
save and prepare before making a new binding; the tool rejects silent lock changes.
Save groups and pending guides before preparation. Saved pending guides survive
reopening. Invalid/conflicting geometry gives an error and preserves accepted work.
**Reload saved inputs** explicitly discards only unsaved browser authoring after
confirmation. Another writer or browser changing the identity makes this authoring
stale; reload before saving rather than overwriting newer work. Export keeps unsaved
browser authoring. Active processing disables guide creation, including canvas
gestures; wait for the operation to finish. Native crop/image loading also blocks
canvas authoring until the displayed pixels and transform agree. Reloading inputs
clears trimap/photo review confirmations and selects the current revision; review
that identity explicitly before approval. Resume requires saved authoring.

## Prepare, review and matte

Choose the permitted write scope as a native half-open rectangle, then **Prepare
saved guidance**. This publishes categorical trimap, quantized support16 and saved
lock assets. It preserves previous alpha and cannot be accepted as a final photo.
Prompted groups generate three native membership candidates. Inspect them with
**Candidate preview**, choose a candidate in its group, save and prepare again.
Candidate score is a model output, not a photographic quality probability.

Optional group morphology needs a retained selected candidate and explicit native
erosion/dilation margins. Inspect **Unreviewed trimap proposal** and **Proposal
unknown boundary**; these suggestions do not replace confirmed categorical cores.
Author actual core/unknown guides against source before the next preparation.

Use **View → Source** to inspect the authoritative **Prepared trimap**, support
and lock overlays; prepared-only revisions have no Result view. Resolve
contradictions and leave fragile areas unknown. Choose **Run full matte** to review
the actual masked photograph. The trimap review checkbox and **Approve prepared
trimap (optional)** let you record a review if useful; neither is needed to run.
A changed draft needs preparation again; saved pending guides cannot be consumed
as if they were already rasterized. All writers share the same nonblocking project
lock; busy/error/review-needed status is visible while comparisons remain readable.

## Make a bounded correction

Inspect matching source/result crops. Mark a NEW confirmed-background core only
where the source supports it. Draw surrounding support with the changed core fully
inside its full-strength interior; feathering must not weaken that core. Add a lock
bound to a saved revision over accepted partial-alpha detail or anatomy to preserve.
Choose a narrow write scope and a larger context rectangle surrounding it. Save
and prepare. Trimap confirmation is optional; review the repaired photograph afterward.

Write a source-supported reason, choose replace/increase-only/decrease-only, then
**Run scoped repair**. Repair consumes the generated immutable support and prepared
guides once. It does not reapply the edit batch. Outside-support and locked alpha/RGB
must remain exact; contradictory cores or incompatible directional policies fail.
Missing/corrupt model, stale input, low disk or an interrupted operation preserves
accepted state and diagnostic artifacts. Fix the displayed cause before retrying.

## Compare, accept and export

After a successful matte or repair, choose **View → Result · saved background**
before comparing the result; the page keeps the previously selected view.
Use **Source / result**, the revision selector, Result and black/gray/white diagnostics and
alpha view on identical native crops. For photographic comparison, set **Candidate
preview → None**, **Canvas authoring mode → Matting guides** and **Overlay → None**.
Exposure and fade shapes remain visible in their authoring modes even with Overlay
set to None. Switching to Matting guides hides those marks without clearing saved
or draft areas; switch back to the effect's authoring mode when drawing again.
Inspect fragile detail, gaps, transparency and seams at native scale. Cached tile
counts describe verified computation reuse, never visual quality. Previews are
RGB8/alpha8 approximations; authoritative saved assets retain RGB16/alpha16 precision.
To save the selected native crop, use **Focused comparison → Save comparison**.
The default saves only a labelled JPEG and exact manifest. **Retain native
inspection evidence** also saves separate PNG crops for correction work. Choose
an optional presentation mode to include the current margin or series form for
the same selected saved revision. These controls retain unsaved forms and do not
accept the photograph or update the Result gallery. Status reports the actual
saved paths or a recoverable failure. **Open saved comparison sheet** opens the
actual JPEG; **Download exact manifest** saves its bound JSON. These links use
only the completed action’s bounded files; see the [comparison contract](file-contract.md#focused-comparisons).

Only after your photographic review, check its separate box and **Accept current
photograph**. Preparation and computational success never imply this acceptance.

**Export accepted result** uses the accepted pointer even when another working
candidate exists. **Export labelled current draft** is explicitly a draft. Both use
the shared renderer. The default delivery contains Result RGB16 TIFF and PNG8 at
full native pixel dimensions, plus the frozen recipe, manifest and notes. PNG8 has
reduced colour precision. Unchecked independent controls opt into black TIFF/PNG,
transparent RGBA8 (8-bit alpha), or complete editable layers at original size.
Editable does not include the other alternatives automatically. Keep original
captures and the editable project independently. Export directories and
revision/status are displayed on success; an intact retry says **Existing delivery**.
The CLI selects the same choices with repeatable `--variant black`,
`--variant transparent`, `--variant editable`. See the
[delivery contract](file-contract.md#requested-result-deliveries).
Optional color cleanup is now available in the same review window. It starts OFF.
Use the cleanup strength, declared native write scope and project-relative grayscale16
support file. The default support is the current saved guide support. To change it,
author support guides, prepare, then run a complete matte/repair. Trimap confirmation is optional.
Enable on an accepted base, or explicitly check candidate comparison. Compare with
cleanup OFF using the same alpha before human appearance acceptance. Strength .35 is
a starting point, never a recommendation for every photo. Optional protected shading
is described below.

Cleanup estimates nearby background only from confirmed empty source pixels. It
approximates decontamination; it cannot recover true missing colors/detail. Repeated
rendering selects saved corrected RGB16 and never compounds correction. Explicit
Disable recovers master-based RGB with applicable saved-value locks.

Alpha changes make enabled cleanup stale. The viewer then shows BASE-to-BASE
comparisons with cleanup OFF on both sides; appearance acceptance and draft export
are blocked. Earlier accepted complete results and exports remain available separately.
Rebuild using separately declared support covering the changed alpha, preserving prior
corrected RGB outside it and exact saved RGB locks inside. Any changed alpha left
outside the rebuild keeps cleanup stale. Broader work needs explicit broader scope.

CLI uses `.venv/bin/blackmask run PROJECT --request FILE` with schema_version=2, kind="effects",
developed_id, base_revision and inputs_digest copied from current review/state, explicit
scope_xyxy, project-relative support_file and candidate_comparison boolean. Optional
color_cleanup={"enabled":true,"strength":0.35} records an explicit override; omitting
it consumes the current recipe section. Editing the recipe alone does not change saved
appearance. The viewer records actual settings in the effects request without rewriting
editable recipe defaults. Both routes save the same revision/effect contracts.

### Repeat an unchanged adjustment

Apply remains explicit. If the current effects request is fully equivalent after
validation, the viewer reports **Reused current result; no new revision**. Acceptance
and pending unrelated settings/areas stay as they were. Changed safety metadata or
unproven equivalence computes normally. A reused result can still have pending
gallery recovery or drafts that block acceptance. See the
[saved reuse contract](file-contract.md#unchanged-effects-results).
Saved-layer integrity checks still run before reuse, including Fade into background's
cold geometry checks. Repeated spatial Disable uses saved shapes and keeps pending edits.

## Restore, resume and continue without an assistant

Select a saved revision and **Restore working inputs**. Acceptance stays unchanged;
explicitly accept the restored complete result if you prefer it. Unsaved file drafts
normally block restore. The explicit replace checkbox preserves their exact previous
bytes under project `recovery/` before replacement, including malformed drafts.
Saved pending authoring records remain under `requests/`; restore also preserves
the pending pointer in recovery and retires it, even when selecting the same revision. If restore makes an
unconsumed pending batch stale, **Load retained pending guides for review** loads it
against current saved guides. Recheck every source region/group/lock and save before
preparing; loading never runs inference or changes acceptance. Consumed batches are
never reapplied merely because an earlier identity was restored.

Select an interrupted operation and **Resume verified work**. Only valid saved
operands/tiles are reused. Stale recovery records require restarting from current
reviewed inputs; original stages remain retained. Closing the foreground server
interrupts active work; reopen the project and use the displayed recovery status.
Existing accepted exports remain usable. See [recovery details](troubleshooting.md).

## Numbered offline use check

This short check is for an existing project with a complete saved matte and local
model caches after setup. Use a source-supported correction that actually needs
work; do not invent a defect or approve a result just to finish the check. If no
correction is warranted, record that limitation rather than changing good detail.

1. From the repository root, run `.venv/bin/blackmask open --project /path/to/project --sam-cache /path/to/sam-cache --model-cache /path/to/vitmatte-cache`.
   Keep this terminal/server running. Open the printed launch URL in your usual
   external browser before closing the assistant; keep the URL private and local.
   Disconnect the network after the page loads. No further download should be needed.
2. Inspect **Source / result** on matching native crops. Use **Native 1:1**; with
   the canvas focused, arrows pan and +/- zoom, or Shift-drag pans. Source-development
   review is optional; preserve its lighting and colours unless a change is requested. Review
   black, gray, white and alpha views; previews have reduced precision.
3. Choose **Confirmed background core** and draw a NEW small core only over
   source-visible empty background needing correction. Exclude uncertain wings,
   webs, fine detail and protected subject pixels; leave ambiguity unknown.
4. Choose **Repair support16** and draw surrounding support. If using **Inward
   feather px**, keep the entire changed core inside the full-strength interior,
   away from the feathered boundary. Do not include unrelated detail merely to
   enlarge the correction. Choose **Saved alpha/RGB region lock**, select **Lock
   saved revision**, and draw over saved partial-alpha detail that must stay exact.
   Keep known cores away from incompatible locked/unknown detail. Numeric geometry
   through **Native coordinates** and **Add numeric guide** is also available.
5. Set a narrow **Write scope x0,y0,x1,y1** containing the intended support and a
   larger **Repair context x0,y0,x1,y1** containing nearby source context. Choose
   **Save groups and pending guides**, then **Prepare saved guidance**. Inspect
   **Prepared trimap**, support and lock overlays against source. Correct conflicts
   explicitly. Trimap confirmation is optional; you can continue directly to repair
   and review the masked result.
6. Enter the actual defect in **Source-supported repair reason**, choose **Replace
   within support** under **Merge**, and choose **Run scoped repair**. Wait for
   completion. On any error, preserve saved work and address the displayed cause;
   success in computation alone does not mean the photograph improved.
7. If cleanup, shading, Local sharpening, Local exposure or Shadow fade was enabled, changed alpha can make it
   **STALE** and switch comparisons to labelled BASE views. Before accepting or
   exporting the current appearance, rebuild each stale effect from its reviewed
   support/protection or explicitly disable it: **Explicitly disable cleanup**,
   **Explicitly disable shading**, **Reset Local sharpening**, **Reset exposure**, or **Reset Shadow fade**. Follow the existing
   [cleanup recovery](#compare-accept-and-export),
   [shading recovery](#protected-inward-shading) and
   [exposure recovery](#local-exposure) and [fade recovery](#shadow-fade) instructions; an amount/opacity change alone
   does not rebuild an alpha dependency. Earlier accepted results/exports stay saved.
8. Compare source, prior saved result and current result on the same native crop,
   with overlays off, on black/gray/white and alpha. Check the corrected background,
   support boundary, locked partial detail, transparency and seams. Only if the
   result is acceptable, check the separate photographic-review box, choose
   **Accept current photograph**, then **Export accepted result**. Otherwise retain
   the earlier accepted result and revise or restore; do not accept automatically.
9. Note the accepted export directory. Select an earlier **Restore saved revision**
   and choose **Restore working inputs (acceptance unchanged)**. Use explicit draft
   replacement only after reviewing its preservation warning. Confirm acceptance
   and the existing export stay intact. Stop the server with Ctrl-C only after work
   finishes; rerun the same open command to reopen saved state. The accepted export
   remains usable independently. Do not reaccept a restored revision unless you
   actually prefer and have reviewed it.

Record what you observed and any step you could not perform. These instructions
do not show that human photographic review, usability testing, or offline use has
occurred. A partial-alpha lock check requires real saved partial detail.

An optional interrupted-recovery check is separate from normal use. If an operation
was interrupted, reopen, inspect **Interrupted operation**, and use **Resume verified
work** only when its saved inputs remain valid. Do not deliberately interrupt a
normal correction just to complete this walkthrough; retain accepted output and
recovery artifacts when testing interruption separately.

Contributors additionally need Node.js to execute the shipped JavaScript coordinate
regression; Node is not required to install or operate the application.

## Optional assistant

[Bounded assisted review](assistant-workflow.md) records an explicit cycle, source-visible defect, at most two repair attempts total, matching comparisons and review-needed disposition through the same commands. Manual controls above remain independent of this optional history. Human approvals remain separate.


## Protected inward shading

Shading starts OFF and does not repair a mask. In the same review window, choose
your photograph's native width, direction (0 right, 90 down), opacity, declared
support and explicit protection. The default uses the current saved guide
protection mask (categorical8); it may be empty. Author saved alpha/RGB lock
guides for the selected details in the existing guide controls, then prepare,
complete matte/repair. Trimap confirmation is optional. No external mask script is needed.
Explicit categorical16 files are also supported. Select hairs, antennae, web,
tips, genuine highlights and bee yourself; automatic attenuation cannot guarantee
their protection. Use the enable/rebuild button only on an accepted mask or with
the explicit candidate-comparison checkbox. W16 stays separate from opacity.

Compare the same native crop at 0%, 12% and 24% with the preview selector. Labels
show the displayed revision, effective opacity, encoded sRGB, width, cleanup
and baked RGB8 preview precision. BASE and stale views label all optional effects OFF. These are
comparison strengths, not defaults or photographic approval. The BASE checkbox
turns all optional effects off. The global opacity button reuses saved W
without a model or mask rebuild; it does not change geometry/protection. Explicit
disable preserves saved layers. Rebuilding one effect never rebuilds the other.

After alpha repair, each enabled dependent effect becomes stale if its saved
alpha differs. Both sides of comparisons then show labelled BASE views. Rebuild
each stale effect only within its declared support, covering all changed-alpha
dependencies, or explicitly disable it before accepting/exporting appearance.
Accepted complete revisions and exports remain saved separately. For a new
protection choice rebuild within explicit support; prior protected W=0 samples
remain protected. Human comparison decides whether shading improves the photo.

CLI uses the existing `.venv/bin/blackmask run PROJECT --request FILE`. Add, for example,
`shading={"enabled":true,"opacity":0.12,"width_px":YOUR_WIDTH,"direction_degrees":YOUR_DIRECTION}`
and `shading_protection_file` to the common effects request. Values shown as
YOUR_WIDTH/YOUR_DIRECTION are placeholders, not executable JSON. For opacity
only, keep geometry identical, set `opacity_only=true`, omit protection file,
and supply the new scalar opacity. Omit cleanup to retain its saved state.
See [the file contract](file-contract.md#optional-protected-inward-shading) for
exact assets, stale rules and editable editor handoff.


## Local exposure

Use **Local exposure** to brighten or darken existing photographed detail in one
selected area. It works offline without models or an external mask editor.
It cannot recover detail absent from the saved matte, recover clipped highlights,
or restore captured sharpness. Final photographic acceptance remains your decision.

1. Complete the matte/repair and load the current working revision. Choose
   **Canvas authoring mode → Local exposure area**. This authoring is separate
   from the matting guides and needs no trimap approval or model pass.
2. Select **Apply area** or **Protect area** and draw a brush or rectangle.
   Brush radius and inward feather are native pixels; protection has hard edges.
   For keyboard authoring, enter a native half-open rectangle and activate
   **Add exposure rectangle**. Review the draft shape list; remove individual
   shapes or clear the draft when needed. Existing saved guide locks always apply.
3. Set EV from -3 to +3 (0.1 steps). Default OFF / 0 EV is unchanged appearance.
   If the complete candidate is unaccepted, explicitly enable candidate comparison.
   **Apply / replace exposure area** saves this one adjustment and replaces its
   previous area. Saved area/protection/settings remain independently recoverable.
4. **Apply amount to saved area** reuses its saved selection and protections.
   It leaves pending area edits unsaved. Saved and draft status are shown
   separately. Unsaved EV and candidate-comparison edits survive unrelated actions
   such as export. If project inputs change, those settings stay visibly stale;
   reload saved inputs before applying them to the new revision. Successful exposure
   application/reset or an explicit reload clears the settings draft; area edits
   remain separate. Repeated application starts from unexposed RGB, so it never
   stacks exposure on previous exposure.
5. **Compare exposure OFF** previews the same alpha with saved cleanup/shading
   retained, with Shadow fade recalculated from the exposure-OFF input. Source/alpha views are unaffected; the BASE checkbox turns all
   optional effects off. Comparison is read-only. [Hide authoring marks](#compare-accept-and-export)
   before judging native black/gray/white
   views, feather edges, noise and highlights. The clipping count is affected
   pixels with at least one channel above linear white before clamping, over
   eligible selected pixels; it is not a photographic quality score.
6. **Reset exposure** saves OFF / 0 EV while retaining the recoverable saved area.
   Reload reopens saved authored geometry; scalar-input areas remain available
   for amount changes. If alpha changed, rebuild the area or reset exposure
   before acceptance/export. Other stale effects require their own recovery.
7. Export a labelled draft for comparison. Native exports with **Include complete
   editable layers at original size** include both selected
   and unexposed RGB16 plus editable support/protection/alpha/settings. Preserve
   them together; the selected foreground already includes exposure once.

CLI/assistant requests use the same `run PROJECT --request FILE` effects operation.
See [the local exposure file contract](file-contract.md#optional-local-exposure)
for authored/scalar inputs, strict field rules, scope coverage and reconstruction.
The exposure-only comparison is distinct from all-effects-off BASE comparison.


## Fade into background

Use **Fade into background** to make a subject disappear toward the chosen
background while keeping its editable mask. The blend can tint or brighten as
well as darken. Choose the background first. Shadow fade remains independent;
this feature does not change its Amount or Preserve highlights. Enabling this
feature switches off Protected inward shading and retains its saved settings.
Enabling inward shading switches this feature off. Disabling either does not
automatically revive the other.

### Oval only

1. Select the working revision and **Canvas authoring mode → Fade shapes**.
   In **Fade into background**, select **Fade ON**, **Use oval**, and clear
   **Use arcs**. Choose **Oval** in **Selected shape**.
2. Position **Centre X/Y**, **Unfaded centre width/height**, and **Rotation**.
   These are native pixels and clockwise degrees. Drag the selected handles or
   enter numbers; Shift-drag pans and the existing zoom controls retain registration.
3. Set **Transition width** and **Fade strength (%)**. Inside the inner oval
   there is no contribution; outward along each ray the fade reaches a plateau
   beyond the transition. Place a disappearing tip beyond the outer boundary.
4. Adjust this feature's **Preserve highlights (%)**. Optional explicit protection
   uses **Optional aligned categorical protection file (project-relative)**: a
   full-size PNG containing only 0/255 (8-bit) or 0/65535 (16-bit). Saved locks and
   previous protection remain protected. A mask boundary alone is not protection.
5. Draft outlines are labelled **Unapplied fade shapes**; images and strength maps
   still show the saved revision. Select **Explicitly compare an unaccepted
   candidate** only when you intend that choice; it starts unchecked. Otherwise
   enabling needs an accepted base. Choose **Apply fade shapes**, then inspect
   the saved photograph and **Compare Fade OFF**. OFF retains Shadow fade and
   the selected background. It creates no revision.

### Arcs only

1. Select **Fade ON**, clear **Use oval**, and select **Use arcs**. Click
   **Add arc**, then the image to place its centre. Keyboard activation of Add
   places it at image centre. New arcs start at zero strength. Up to 32 are retained.
2. Select an arc in **Selected shape**. Set **Centre X/Y**, **Rotation**,
   **Span (endpoint to endpoint)** and **Bend**. Negative bend is supported.
   The middle handle follows the actual curve midpoint. Use **Flip arrow** or
   **Fade direction** to choose which side fades.
3. Set **Transition width**, **End softness** and **Fade strength**. Beyond the
   transition in the arrow direction the contribution stays at its plateau;
   there is no trailing taper. Softness applies laterally near the endpoints.
   Keep a disappearing tip within the core span: tips near a soft endpoint
   receive less fade. Inspect neighbouring branches that enter that soft region.
4. Add another arc for a different petal or branch. Select by the list when
   outlines overlap. **Duplicate arc** creates an independent copy; **Selected
   arc ON** disables just that contribution, **Use arcs** disables the group,
   and **Remove arc** removes only the selected draft arc. Inactive settings
   remain saved. **Cancel / reload saved fade shapes** restores this form without
   discarding unrelated effect drafts. Escape cancels placement or reloads the form.
5. Apply and compare as above. Reopening the project restores saved vectors and
   switches. No drag, numeric edit, map choice or opacity change saves a revision.

### Oval and arcs together

1. Select both **Use oval** and **Use arcs**. Establish a broad oval, then add
   local arcs where more fade is needed. Each keeps its own position and strength.
2. Overlap uses the strongest contribution, once. A weak arc cannot undo a
   stronger oval. Opposing arcs, soft endpoints and arbitrary photographic paths
   can change direction through the combined field; only each shape's specified
   local direction is monotonic. Photo brightness also depends on source colour,
   alpha, protection, highlights and the target background.
3. Use **Saved strength map → Selected shape**, **Combined geometry**, and
   **Effective after protection / highlights**. Selected shows that saved shape's
   strength; disabled shapes/groups show zero. Combined includes shape strengths;
   effective also includes the master switch, protected regions and highlights.
   **Map display opacity** affects only the display. An unapplied new arc has no
   saved map. Check endpoints, junctions, adjacent traces and the full photograph.
4. Apply, inspect **Compare Fade OFF**, and keep the result as a labelled draft
   until a person accepts the photograph. Computational checks do not accept it.

After an alpha change, enabled Fade into background can become **STALE**. Reload
the current form, then Apply to explicitly rebuild from the saved vectors, or
choose **Disable fade**. Disable works on a valid working revision without an
accepted/candidate gate; it retains operands and protection. Invalid or corrupted
saved assets must be recovered from a valid revision rather than silently repaired.
Other stale effects require their own recovery. Earlier accepted work remains saved.

To reduce Fade into background in selected areas, first save its settings, then use
**Reduce fade locally** and **Canvas authoring mode → Fade reduction**. Draw a brush
stroke or enter a half-open native rectangle and choose **Add reduction rectangle**.
Set the native brush radius, inward feather and reduction amount. Select a saved
region to edit its amount/feather, update a rectangle or remove it. Overlaps use
the strongest reduction; 100% restores this effect's input locally. Other effects
remain applied. Feathering stays inside the region, so a narrow region with wide
feather may never reach full reduction. Limits are 128 regions and 8192 total
stroke points per target.

Drawing, numeric changes and **Clear target reduction** only change the draft.
Choose **Apply reduction** to save a new revision; use an accepted base or explicitly
select candidate comparison. **Cancel / reload saved reduction** discards this
target's unapplied edits. Saved coverage displays the stored reduction, while
**Reduction OFF** shows the original fade strength. **Compare Fade OFF** turns off
the entire spatial fade for comparison. These views do not save changes.

A draft retains its original revision identity. If saved inputs change, it stays
visible as stale and must be reloaded before Apply; failed saves and late responses
do not consume newer edits. Reduction cannot repair an old alpha dependency, even
when the effect is disabled. Rebuild the effect explicitly first. Settings changes
and effect OFF retain reduction; clearing it saves an empty reduction in a new
revision. Older software may reject revisions with reduction. Preserve earlier
revisions/exports and use updated software, or restore a pre-feature revision with
compatible tooling. No existing revision is rewritten.

Native export with editable selected retains pre-spatial foreground, alpha, combined weight, protection,
settings, reduction geometry/raster when present, and background as separate editable operands. Transparent viewing RGB
retains the tint toward the selected background; alpha is unchanged. Black/gray/
white diagnostics change the backdrop but keep that same fade target.

Select **Include native editable companion** for a framed or Match series export
to receive a presentation folder **and a native editable folder**. This is opt-in,
even for a saved spatial record that is ON, OFF or zero strength.
Keep both siblings and their names for portable reconstruction. The presentation
contains compact flattened results; its manifest binds all companion files. A
native-only partial result or visible-but-durability-unconfirmed error is still an
error: retain the named folders/stages, inspect them and retry the identical export.
Retry verifies existing bytes and never overwrites a different delivery. The pair
publishes sequentially, so one folder can remain after failure. See the normative
[saved and delivery contract](file-contract.md#optional-fade-into-background).

## Shadow fade

Use **Shadow fade** for soft interior subject fading independently of Local exposure.
It works offline with saved layers and never runs a model. Keep any accepted exposure
adjustment; fade has its own area, settings, protection, comparison and reset.

1. Complete the matte/repair and load the working native view. Choose **Canvas
   authoring mode → Shadow fade area**, then Apply/Protect and Brush/Rectangle.
   Softness is inward feather in native pixels on Apply shapes; Protect is hard.
   For a non-drag route, enter half-open native rectangle coordinates and click
   **Add fade rectangle**. Review, remove or clear draft shapes. Saved locks apply too.
2. Set **Amount** and **Preserve highlights** with sliders or numeric percentages.
   Amount 100% gives at most six stops of linear-light darkening. Highlight
   preservation is tonal: explicitly protect dim hairs, saturated petals and
   translucent detail. It cannot recognize detail or restore absent capture data.
3. For an unaccepted complete candidate, explicitly check candidate comparison.
   **Apply / replace fade area** saves the one area and removes the old one.
   **Apply fade amount to saved area** changes settings using saved operands only;
   pending area edits remain unsaved. Unsaved Amount, Preserve highlights and
   candidate-comparison settings survive unrelated actions such as export and
   failed submissions. If project inputs change, those settings stay visibly stale;
   reload saved inputs before applying them to the new revision. Only a matching
   successful application/reset or explicit reload clears the settings draft.
   These controls are frozen during writers; area/protection drafts remain separate.
   Settings apply afresh without compounding.
4. **Compare Shadow fade OFF** retains cleanup, sharpening, exposure and shading. **Compare
   exposure OFF** retains fade, recalculated from exposure-OFF RGB. BASE disables
   every optional effect; selecting a comparison clears the others. [Hide authoring
   marks](#compare-accept-and-export), then inspect the
   same native crop on black/gray/white and alpha. Source and alpha stay unchanged.
5. **Reset Shadow fade** saves OFF / 0% and retains the saved area, other effects
   and pending area edits. Reload discards unsaved area edits and loads saved geometry.
   Scalar-input areas remain usable for amount changes even without authored shapes.
6. If alpha changed, rebuild fade or reset it. Each other stale effect needs its
   own rebuild/disable before accepting or exporting appearance. Prepared revisions
   still need completed matte; trimap confirmation is optional and acceptance is separate.
7. Export a labelled draft. For recovery layers, select **Include complete editable
   layers at original size** in a native export and preserve selected, unfaded, unexposed, base and source
   RGB16 plus alpha, independent settings/support/protection and any shading W16.
   The selected foreground already contains fade and exposure once. Follow the
   [saved-layer replay order](file-contract.md#optional-shadow-fade); never apply
   fade a second time to the selected export. Decide photographic acceptance only
   after native inspection; synthetic checks cannot supply that decision.

## Background appearance

1. Open a project with a complete matte and choose **Result · saved background**
   in **View**. The revision selector must show the current working revision
   before applying. Prepared-only state still needs matting; trimap confirmation is optional.
2. Under **Background appearance**, choose **Background tone** or enter a six-digit
   `#RRGGBB` colour. **Pure black** selects `#000000`; **Warm dark** selects
   `#120708`. Shortcuts keep the variation slider unchanged.
3. Set **Background variation** with the slider or whole numeric percentage.
   Zero is uniform; 55% gives up to ±0.55 stops and 100% up to ±1 stop over one
   fixed broad wash. Pure black stays exactly black at every strength. New
   projects explicitly start at warm dark / 55%; older saved projects remain
   black until you apply a change. This default still needs your photographic judgment.
4. Unsaved controls do not render. Click **Apply background** and wait for the
   saved revision and saved settings to update. For an unaccepted candidate,
   explicitly select the background candidate-comparison checkbox first.
   Apply changes only the backdrop. Save/prepare pending matting guides first;
   unrelated unsaved exposure/fade areas and values remain in the page.
5. Inspect **Result**, then **Black diagnostic**, **Gray diagnostic**,
   **White diagnostic**, **Source** and **Alpha8 view**. These diagnostics keep
   their original meanings. Compare Shadow fade OFF independently: it retains
   the same background. Exposure OFF also retains it. Global BASE and stale
   foreground-effect comparisons use pure black with all foreground effects OFF.
6. Use **Export labelled current draft** for a labelled unaccepted delivery, or accept the
   inspected photo and export the accepted result. `result_rgb16.tif` is the
   chosen-background image; `result_RGB8_VIEW.png` is a reduced-precision preview.
   Select the black alternative for `black_rgb16.tif` and its PNG view, which
   always use pure black. Request a native editable export to retain
   `background_rgb16.tif`, `background_settings.json`, selected
   `foreground_rgb16.tif`, `alpha16.png`, saved shading W16/opacity and the other
   editable operands. Straight transparent RGBA8 does not include the backdrop.
7. To return to black, select **Pure black** and **Apply background**. To recover
   another appearance, use **Restore saved revision**; it restores that revision's
   background, including legacy absence, without changing final acceptance.
   **Reload saved inputs** discards unsaved controls and reloads saved values.

The background changes flattened partial-alpha colours, including protected
translucent edges; protection preserves underlying foreground RGB/alpha. It does
not freeze their old black composite. The field is generated at native resolution
and saved; crops slice those same pixels and screen resizing happens afterward.
No model, internet, noise generation or photographed-detail synthesis is involved.
RGB8 previews may band; inspect native RGB16 in a suitable colour-managed viewer.
A processed sRGB RGB16 TIFF is not sensor RAW. See the [saved contract](file-contract.md#saved-background-appearance).

## Add presentation margins

In the local review window, open **Framing and margins** and choose **Add margins**.
Enter nonnegative whole
pixels in **Left**, **Right**, **Top** and **Bottom**. **Set all sides** copies the
Equal margins value to all four fields. **Centre image** redistributes the existing
horizontal and vertical totals; an odd extra pixel goes Right or Bottom. It centres
the original image rectangle, not a detected subject. Adjust individual margins
to place the photograph manually; margins cannot recover a cut-off leg or petal.

**Preview framing** uses the selected complete saved revision. Its separate canvas
is a sampled RGB8 layout view, at most 1600 pixels along the long edge, with no
upscaling. It does not display unsaved appearance edits. Changed fields or revision
make the previous preview stale; click Preview again. Keep native views for detail
inspection and all guide/brush coordinates.

**Save margins** explicitly writes this source's preset. Typing, previewing and
**Reset margins** never save it. Reset sets local zeros; **Reload saved margins**
replaces only the framing form. Polling and framing actions preserve unrelated
unsaved guidance and appearance controls. An absent preset means zeros without
creating a file. See recovery below for invalid, stale or uncertain saves.

**Export framed accepted result** and **Export framed draft** use the visible
validated margins, including unsaved edits. They do not silently use or save the
preset. Black and transparent checkboxes independently add alternatives in the
framed output geometry. **Include native editable companion** adds a separate
folder with full native layers; keep both folders for portable editing.

The CLI also creates a separate framed delivery from explicit margins:

```sh
.venv/bin/blackmask export PROJECT --margins 120 180 80 80
.venv/bin/blackmask export PROJECT --margins 120 180 80 80 --framed-transparent
```

The four numbers are **left, right, top, bottom**, in native pixels. They must be
nonnegative integers. For a saved unaccepted revision, add
`--revision rev-NNN --draft`. Omit `--margins` for the existing native export;
`--margins 0 0 0 0` deliberately creates a separate compact presentation.

The command reports the delivery directory, output dimensions and the native
image's rectangle inside the canvas. `result_rgb16.tif` retains the native result's
processed sRGB samples exactly. `result_RGB8_VIEW.png` is an 8-bit viewing copy;
the optional `transparent_RGBA8_VIEW.png` has 8-bit alpha and transparent margins.
The compact bundle includes the frozen recipe, manifest and readable description.
Keep the local project or add `--variant editable` to this same margins command
for a native editable sibling. The presentation's manifest binds that sibling and
freezes its margins; the editable operands retain native coordinates.

Margins extend the saved backdrop's edge and corner colours. Wide margins may
show bands; inspect the resulting composition in a suitable colour-managed viewer.
The photograph is neither resized nor stretched. Original editing coordinates
stay native: the presentation merely places their origin at `(left, top)`.
Framing an accepted revision does not separately approve the composition.
The accepted export button uses the current accepted revision; the draft button
uses the current working revision. The preview uses the revision selected in the
viewer, which can differ from either export target. Check the returned revision
and draft label when comparing deliveries. See
[limits and recovery](troubleshooting.md#framed-export-recovery).

## Match a fixed-size series

Open **Framing and margins → Framing mode → Match series**. First select the
complete saved result in **Compare revision**. This mode uses that selected revision's saved
foreground, alpha and appearance. Unsaved native appearance controls are not rendered.
Switching modes retains both forms' unsaved values and clears their preview; it
does not save, calculate a new preview or export anything.

The first-use settings are editable examples:

| Control | Units and initial value |
| --- | --- |
| Preset name | 1–80 Unicode characters; initially `Portrait series` |
| Output width / Output height | Whole pixels; initially 4000 × 5000 |
| Side margins | Percent on **each** side; initially 15.0%; numeric field and linked slider |
| Minimum top/bottom | Percent of output height on **each** side; initially 5.0% |

Margins range from 0.0% to 45.0%, in 0.1% steps. Output axes are at most 32768
pixels and the canvas at most 100,000,000 pixels. The subject is centred with one
uniform scale. Side margins set the width target; a tall subject is limited by the
vertical clearance and therefore has wider side margins. The image is not stretched,
rotated or cropped to force a match. Equal size does not guarantee equal visual weight.

Choose **Preview framing** and optionally **Show subject bounds**. Status reports
the actual four geometric margins, whether height limits the fit, enlargement and
source-edge contact. Every alpha value greater than zero participates, including
faint disconnected hairs or stray pixels. The outline describes those original mask
bounds; filtered support can extend beyond it. Correct unwanted alpha explicitly in
the native mask workflow. Framing cannot restore already clipped anatomy or invent
detail. Enlargement adds no captured detail, and reduction can make fine features
subpixel or invisible.

The separate preview has a long edge of at most 1600 pixels. It is a reduced RGB8
approximation, not the final TIFF or a native editing surface. Changing settings,
revision or mode clears stale preview pixels. Inspect fine detail in the native
view and inspect the final TIFF in a suitable colour-managed viewer.

Match series regenerates the selected revision's saved **Background** recipe at
the final output dimensions. This produces a continuous fixed canvas and changes
the backdrop beneath partial-alpha edges too. It differs from Add margins, which
extends saved edge pixels. Legacy revisions without a background recipe use black.
Series presets do not override background colour; use the existing Background
workflow to save that appearance in each photo first.

**Save for this photo** saves a complete source-bound settings snapshot;
**Reload saved series settings** replaces only this form with its saved snapshot.
Typing, previewing and exporting never save settings automatically. If a save
reports uncertain durability, retain your edits and explicitly reload before the
next save. Other native guidance/effect forms remain independent.

For manual reuse across photographs:

1. Choose **Download preset file**. This initiates a browser download of
   `series-framing-preset.json`; confirm the file in your browser. It contains only
   the name, output dimensions and margin settings, as described in the
   [portable JSON contract](file-contract.md#fixed-size-series-settings-and-deliveries).
   It contains no photograph, source identity, image path, mask or appearance data.
2. Open another saved photo project and choose **Load preset file**. Select that
   JSON file. A valid file changes only the local series form; cancellation or an
   invalid/oversized file leaves the form unchanged. The metadata limit is 16 KiB.
3. Select that photo's complete revision, preview its fit and save for that photo
   only when desired. A later change to the portable file does not alter either
   photo's saved snapshot or prior exports. There is no global preset catalog.

**Export selected accepted result** requires that the visible selection is still
the current accepted revision. **Export selected revision as draft** always produces
a DRAFT delivery, including when its selected source is accepted. Both use the visible
validated settings, including unsaved edits, and identify the actual selected revision;
neither substitutes the working/accepted pointer silently or accepts the composition.
The transparent checkbox adds a straight RGBA8 viewing copy.

The equivalent explicit CLI operations are:

```sh
.venv/bin/blackmask export PROJECT --series-preset SERIES.json
.venv/bin/blackmask export PROJECT --series-preset SERIES.json --framed-transparent
.venv/bin/blackmask export PROJECT --series-preset SERIES.json --revision rev-NNN --draft
```

The flag is mutually exclusive with `--margins`. Without either flag, the existing
native export behavior applies; project series settings are never loaded implicitly.
The CLI accepts a bounded regular JSON file and rejects symlink aliases.

Each compact delivery contains `result_rgb16.tif`, `result_RGB8_VIEW.png`,
`recipe.toml`, `README.txt` and `manifest.json`, with independent optional
black TIFF/PNG and `transparent_RGBA8_VIEW.png`, beneath a distinct
`exports/rev-NNN[-DRAFT]-series-framed-<identity>/` directory. TIFF is processed
sRGB RGB16 with resampled samples; PNGs are reduced-precision views. Transparent
RGB is straight, with zero RGB wherever quantized alpha is zero. Retain the native
editable project, masks, original capture and accepted dependencies independently.
For an editable handoff, add `--variant editable` to the Match series command or
select **Include native editable companion**. Keep the native sibling and this
presentation together; its manifest freezes the chosen settings and byte binding.
Repeating an intact delivery validates its
actual files and current source/revision authorization before returning without rendering.
See [preservation and recovery](troubleshooting.md#series-framing-recovery).


## Local sharpening

Use Local sharpening to enhance existing captured detail in hair, feathers, petals,
fabric, eyes or translucent regions. It cannot restore missed focus or remove
captured contamination. Start gently and inspect at native scale.

1. Select the current complete revision and **Canvas authoring mode → Local
   sharpening area**. Draw Apply regions with Brush or Rectangle, or enter numeric
   rectangle coordinates. Brush radius and inward feather use native pixels.
   Add hard Protect regions around areas that must remain exact.
2. Set **Amount** (0–100%), **Detail size** (Gaussian sigma, 0.5–8 native pixels;
   distinct from brush radius), and **Noise guard** (0–2% linear luminance).
   Defaults are OFF, 0%, 1 pixel and 0.1%. Noise guard suppresses small differences;
   it is not a denoiser. Larger radii affect wider structures.
3. **Apply / replace sharpening area** replaces the whole adjustment. **Apply
   sharpening amount to saved area** uses the saved geometry and current settings.
   Pending area edits and unrelated effect drafts remain separate. On an unaccepted
   draft, explicitly enable candidate comparison.
4. **Compare Local sharpening OFF** retains cleanup, exposure, Shadow fade,
   shading/spatial fade and background, recalculating downstream RGB from the
   unsharpened input. Source and alpha stay unchanged. Compare creates no revision.
   Inspect black, gray and white diagnostics for halos or noise amplification.
5. **Reset Local sharpening** saves OFF / 0% and retains recoverable operands.
   Changed alpha makes enabled sharpening stale; rebuild the whole area or Reset.
   A new saved RGB lock preserves its selected pixels exactly and changes the
   filtering context for neighboring unprotected pixels. Inspect that boundary.
   Restore retains prior revisions and never grants acceptance.

One settings tuple applies to all authored regions. Cleanup changes recompute
sharpening from the current cleanup-selected input; repeated Apply does not compound
it. Overshoot guards limit new luminance extrema, but do not guarantee invisible halos.

For portable editing, explicitly request editable export. It includes the unsharpened
cleanup-selected RGB and independent support, protection, alpha, settings and authored
area. Replay sharpening, exposure, Shadow fade, then shading/spatial fade and
alpha/background composition. Selected foreground already includes sharpening;
do not apply it twice. Framed and match-series exports bind a complete native companion:
keep both folders together. See the [saved contract](file-contract.md#optional-local-sharpening).
New sharpening records require the updated application; retain pre-feature projects
and exports for older applications. Photographic acceptance remains your decision.
