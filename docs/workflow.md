# Offline manual review

After [explicit environment/model setup](../README.md) and [model cache setup](guidance.md),
open one source/project. Use your own paths; select guides from the actual source.

```sh
blackmask open /path/to/source.tif --project /path/to/new-project --sam-cache /path/to/sam-cache --model-cache /path/to/vitmatte-cache
# Later: reopen saved assets, without needing the original capture path.
blackmask open --project /path/to/new-project --sam-cache /path/to/sam-cache --model-cache /path/to/vitmatte-cache
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
Appearance effects are not implemented or shown in this release.

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
7. Compare source, prior saved result and current result on the same native crop,
   with overlays off, on black/gray/white and alpha. Check the corrected background,
   support boundary, locked partial detail, transparency and seams. Only if the
   result is acceptable, check the separate photographic-review box, choose
   **Accept current photograph**, then **Export accepted result**. Otherwise retain
   the earlier accepted result and revise or restore; do not accept automatically.
8. Note the accepted export directory. Select an earlier **Restore saved revision**
   and choose **Restore working inputs (acceptance unchanged)**. Use explicit draft
   replacement only after reviewing its preservation warning. Confirm acceptance
   and the existing export stay intact. Stop the server with Ctrl-C only after work
   finishes; rerun the same open command to reopen saved state. The accepted export
   remains usable independently. Do not reaccept a restored revision unless you
   actually prefer and have reviewed it.

Record what you observed and any step you could not perform. These instructions
are not evidence that human photographic, usability or disconnected-network use
has occurred. A partial-alpha lock check requires real saved partial detail.

An optional interrupted-recovery check is separate from normal use. If an operation
was interrupted, reopen, inspect **Interrupted operation**, and use **Resume verified
work** only when its saved inputs remain valid. Do not deliberately interrupt a
normal correction just to complete this walkthrough; retain accepted output and
recovery artifacts when testing interruption separately.

Contributors additionally need Node.js to execute the shipped JavaScript coordinate
regression; Node is not required to install or operate the application.
