# Offline manual review

After [explicit environment/model setup](../README.md) and [model cache setup](guidance.md),
open one source/project. From the repository root, use the environment executable
shown below; shell activation is unnecessary. Use your own paths and select guides
from the actual source.

```sh
.venv/bin/blackmask open /path/to/source.tif --project /path/to/new-project --sam-cache /path/to/sam-cache --model-cache /path/to/vitmatte-cache
# Later: reopen saved assets, without needing the original capture path.
.venv/bin/blackmask open --project /path/to/new-project --sam-cache /path/to/sam-cache --model-cache /path/to/vitmatte-cache
```

The command keeps one local server running until Ctrl-C. It opens a packaged page;
no account, assistant, network connection, external editor, support mask or script
is required for manual mask correction. Model downloads are a separate explicit
setup action. Preserve the original capture independently. Do not share the launch
URL or forward the local port. `open --headless --project /path/to/project` retains
JSON-only command use; other documented CLI commands can run in another terminal.

## Develop and review the source

The page shows an RGB8 viewing approximation of the oriented saved master. Check
orientation, white balance and clipping, inspecting the saved master TIFF in a
trusted RGB16 viewer when precision matters. Only then check **I reviewed this
master’s development** and choose **Approve development**. This approves source
development; trimap review and photographic acceptance remain separate actions.
A different development requires a separate project, preserving the previous one.

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

Inspect the authoritative **Prepared trimap**, support and lock overlays against
source. Resolve contradictions and leave fragile areas unknown. Check the trimap
review box and **Approve prepared trimap**. Then **Run full matte**. A changed draft
needs preparation and trimap review again; saved pending guides cannot be approved
as if they were already rasterized. All writers share the same nonblocking project
lock; busy/error/review-needed status is visible while comparisons remain readable.

## Make a bounded correction

Inspect matching source/result crops. Mark a NEW confirmed-background core only
where the source supports it. Draw surrounding support with the changed core fully
inside its full-strength interior; feathering must not weaken that core. Add a lock
bound to a saved revision over accepted partial-alpha detail or anatomy to preserve.
Choose a narrow write scope and a larger context rectangle surrounding it. Save,
prepare, inspect overlays and explicitly approve the prepared trimap.

Write a source-supported reason, choose replace/increase-only/decrease-only, then
**Run scoped repair**. Repair consumes the generated immutable support and prepared
guides once. It does not reapply the edit batch. Outside-support and locked alpha/RGB
must remain exact; contradictory cores or incompatible directional policies fail.
Missing/corrupt model, stale input, low disk or an interrupted operation preserves
accepted state and diagnostic artifacts. Fix the displayed cause before retrying.

## Compare, accept and export

Use **Source / result**, the revision selector, black/gray/white backgrounds and
alpha view on identical native crops. Turn overlays off for photographic comparison.
Inspect fragile detail, gaps, transparency and seams at native scale. Cached tile
counts describe verified computation reuse, never visual quality. Previews are
RGB8/alpha8 approximations; authoritative saved assets retain RGB16/alpha16 precision.
Only after your photographic review, check its separate box and **Accept current
photograph**. Preparation and computational success never imply this acceptance.

**Export accepted result** uses the accepted pointer even when another working
candidate exists. **Export labelled current draft** is explicitly a draft. Both use
the shared renderer and retain editable source/alpha assets; viewing RGBA PNG has
8-bit alpha. Export directories and revision/status are displayed on success.
Optional color cleanup is now available in the same review window. It starts OFF.
Use the cleanup strength, declared native write scope and project-relative grayscale16
support file. The default support is the current saved guide support. To change it,
author support guides, prepare and approve the trimap, then run a complete matte/repair.
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

CLI uses `.venv/bin/blackmask run PROJECT --request FILE` with schema_version=1, kind="effects",
master_id, base_revision and inputs_digest copied from current review/state, explicit
scope_xyxy, project-relative support_file and candidate_comparison boolean. Optional
color_cleanup={"enabled":true,"strength":0.35} records an explicit override; omitting
it consumes the current recipe section. Editing the recipe alone does not change saved
appearance. The viewer records actual settings in the effects request without rewriting
editable recipe defaults. Both routes save the same revision/effect contracts.

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
   the canvas focused, arrows pan and +/- zoom, or Shift-drag pans. Confirm source
   development before its separate approval if it is not already approved. Review
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
   explicitly. Only when reviewed, check **I reviewed the current prepared trimap
   against source** and choose **Approve prepared trimap**.
6. Enter the actual defect in **Source-supported repair reason**, choose **Replace
   within support** under **Merge**, and choose **Run scoped repair**. Wait for
   completion. On any error, preserve saved work and address the displayed cause;
   success in computation alone does not mean the photograph improved.
7. If cleanup, shading or Local exposure was enabled, changed alpha can make it
   **STALE** and switch comparisons to labelled BASE views. Before accepting or
   exporting the current appearance, rebuild each stale effect from its reviewed
   support/protection or explicitly disable it: **Explicitly disable cleanup**,
   **Explicitly disable shading**, or **Reset exposure**. Follow the existing
   [cleanup recovery](#compare-accept-and-export),
   [shading recovery](#protected-inward-shading) and
   [exposure recovery](#local-exposure) instructions; an amount/opacity change alone
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
review the trimap and complete matte/repair. No external mask script is needed.
Explicit categorical16 files are also supported. Select hairs, antennae, web,
tips, genuine highlights and bee yourself; automatic attenuation cannot guarantee
their protection. Use the enable/rebuild button only on an accepted mask or with
the explicit candidate-comparison checkbox. W16 stays separate from opacity.

Compare the same native crop at 0%, 12% and 24% with the preview selector. Labels
show the displayed revision, effective opacity, encoded sRGB, width, cleanup
and baked RGB8 preview precision. BASE and stale views label all optional effects OFF. These are
comparison strengths, not defaults or photographic approval. The BASE checkbox
turns cleanup, local exposure and shading off. The global opacity button reuses saved W
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
   retained. Source/alpha views are unaffected; the BASE checkbox turns all
   optional effects off. Comparison is read-only. Check native black/gray/white
   views, feather edges, noise and highlights. The clipping count is affected
   pixels with at least one channel above linear white before clamping, over
   eligible selected pixels; it is not a photographic quality score.
6. **Reset exposure** saves OFF / 0 EV while retaining the recoverable saved area.
   Reload reopens saved authored geometry; scalar-input areas remain available
   for amount changes. If alpha changed, rebuild the area or reset exposure
   before acceptance/export. Other stale effects require their own recovery.
7. Export a labelled draft for comparison. Exposure exports include both selected
   and unexposed RGB16 plus editable support/protection/alpha/settings. Preserve
   them together; the selected foreground already includes exposure once.

CLI/assistant requests use the same `run PROJECT --request FILE` effects operation.
See [the local exposure file contract](file-contract.md#optional-local-exposure)
for authored/scalar inputs, strict field rules, scope coverage and reconstruction.
The exposure-only comparison is distinct from all-effects-off BASE comparison.
