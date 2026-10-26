# Photo project recovery

- **Missing profile:** explicitly assume sRGB only when correct, or supply a trusted
  sRGB TIFF. An assumption never overrides an incompatible embedded high-depth ICC.
- **Unsupported profile/compression/RGB16 PNG:** export a single-page contiguous
  uncompressed RGB16 sRGB TIFF through a trusted full-precision application. The importer
  recognizes a conservative canonical ICC representation; an sRGB name alone is
  insufficient. Do not convert high-depth data through Pillow RGB8.
- **Multi-frame PNG/MPO or multi-image JPEG (including Ultra HDR gain maps):**
  export a single-image SDR JPEG/PNG8 or trusted uncompressed sRGB RGB16 TIFF.
  Gain maps are not decoded; the importer refuses to silently use only the base image.
- **Camera white balance multipliers unavailable:** supported RGB DNGs can use
  their stored `AsShotWhiteXY` and calibration profiles automatically, without
  substituting daylight. The error means the reader's multipliers are unavailable
  and no supported white-point fallback succeeded; it does not establish that the
  capture is corrupt. An accompanying metadata diagnostic identifies malformed or
  unsupported inputs. Explicitly choose a daylight preview or supply a trusted
  developed TIFF when needed. See the [supported fallback and saved provenance](file-contract.md#raw-as-shot-white-balance).
- **Busy:** let the existing writer finish or inspect its status. A dead process
  releases flock automatically. Never delete/recreate the lock while writers run.
- **Low disk:** move the new project to storage with 10 GiB reserve plus pending
  writes; arrange storage yourself. No automatic deletion is performed.
- **Interrupted/incomplete creation:** retain the capture and diagnostic project.
  No state means no published usable project; no incomplete master can be approved.
  Create at a new empty location. Inspect retained files before any separately
  authorized cleanup. Initial creation cannot resume. Restore is available only for
  existing valid projects with a saved revision.
- **Failed approval:** reopen the project and inspect its actual state. Before
  atomic replacement, failure preserves old state. After replacement, the update
  may be visible even if a later directory sync fails; never infer success/failure
  solely from the CLI exit. Reopen validates assets and actual acceptance state.
- **Stale identity/corrupt master:** do not bypass validation.
  Restore an independently retained correct copy or create a fresh project from
  the unchanged capture; human acceptance never follows from restore. Scoped alpha repair does not repair corrupt master/project data.
- **Moved capture:** reopen uses retained master; locate the original by SHA-256
  before future source-dependent recomputation. Same filename is insufficient.

The [local review window](workflow.md) supports the manual workflow; [bounded assisted review](assistant-workflow.md) uses the same local operations.
Live photographic defect/repair acceptance remains pending. Processing works offline
after explicit package/model setup. Preserve independent backups; ignored local data is not Git backup.

A publication collision means another tool/editor created a project asset while ingestion ran. Its bytes are preserved. Keep the incomplete project for inspection and choose a new empty destination. Do not delete an arriving file to force publication.


## Preparation recovery

- **Missing/corrupt SAM:** inference never downloads. Inspect the explicit cache;
  retain mismatched files for diagnosis and select a new empty cache for a separately
  authorized setup. Do not replace weights/configs with same-name alternatives.
- **Stale request:** from the repository root, run `.venv/bin/blackmask open --headless --project /path/to/project`
  to obtain actual master/base/draft digest. Finish external
  edits, inspect source/trimap intent, and submit a fresh request. Newer text remains
  untouched. Typed edits already published need not be submitted again.
- **FG/BG/lock/core-support conflict:** resolve the typed assertions from the source.
  No last-layer overwrite or automatic shrinking of protection occurs. Remove a
  lock explicitly before changing its binding. A new prepare-only project has no
  saved alpha to lock.
- **Interrupted/failed prepare:** reopen actual state. The prior working revision
  remains authoritative until state advances. `.prepare-*` or a complete orphan is
  not accepted/working solely because it exists. Inspect retained diagnostics;
  retry with current identities. Preparation cannot resume; saved revisions can be restored. No automatic cleanup.
  A failed pointer write may leave effective root guides updated; inspect them.
- **MPS failure:** retry explicitly with recipe device `cpu`, preserving geometry.
  Auto remains CPU; upstream implicit MPS fallback must be disabled. One synthetic
  successful MPS smoke is not photographic or regular-use acceptance.
- **Prepared revision rejected by accept:** expected. Run native matting first;
  preparation never substitutes for a final result. Trimap confirmation is optional.


## Native matte and export recovery

- **Result gallery pending:** read `--config FILE status PROJECT`, resolve the reported
  storage/collision problem, then use `--config FILE preview repair PROJECT` or the
  viewer's Repair latest Result preview button. Repair uses saved layers without models or
  the original. Unknown files and failed temporaries remain preserved. Native work
  and actual acceptance survive a later JPEG failure.
- **Gallery name too long:** existing names/pending imports remain frozen and usable.
  Status reports required/available bytes; exact-name JPEG publication and acceptance
  changes are blocked. No rename/alias/migration command exists. See the
  [gallery contract](file-contract.md#current-result-gallery).
- **Gallery acceptance warning:** conservative Draft can remain after uncertain state
  sync or failed promotion. Inspect actual pointers and repair explicitly; a receipt
  or filename never grants photographic acceptance.

- **Trimap approval missing/stale:** a missing approval does not block matting or
  repair. A supplied stale/corrupt record is rejected rather than silently used.
  Preserve it, finish typed edits and prepare a new revision; confirmation of the
  new trimap is optional. A morphology proposal never counts as known guide values.
- **ViTMatte missing/corrupt:** use explicit pinned setup only after authorization;
  local inference never downloads or substitutes another checkpoint. Preserve invalid
  existing assets and select a new cache rather than overwriting them.
- **MPS/non-finite failure:** explicit MPS fails visibly; retry a newly prepared and
  reviewed CPU request with identical geometry. Auto stays CPU. No resolution reduction.
- **Interrupted matte:** reopen state; accepted layers remain separate and usable.
  `.matte-*` and complete orphans are not pointer authority. Use `status` then `resume --operation` as described below; stale input requires
  a fresh current reviewed request.
- **Final acceptance rejected:** require current complete matte and unchanged drafts,
  master/development and saved review assets. Prepared-only state never qualifies.
- **Export collision:** keep prior delivery; an intact matching requested delivery
  reuses before rendering or staging. Different bytes, malformed metadata or an
  incomplete directory fail without overwrite. A newer candidate has a
  different revision; explicit unaccepted output must use `--revision ... --draft`.
- **Missing black, transparent or editing layers:** default export contains the
  Result TIFF/PNG pair and compact text files. Select the independent variant
  controls or repeat `--variant black`, `--variant transparent`, `--variant editable`.
  Editable adds native layers to native output, or a separate native companion
  with explicit margins/series settings. Keep both folders. A completed primary
  whose native companion is missing or damaged fails without recreating it; retain
  available files and recover the intact pair. Native PNG8 retains the
  TIFF's full dimensions but has reduced colour precision.
- **Earlier export format:** retain its existing path and files. Current export
  uses a new versioned identity, with no legacy lookup, recreation or migration.


## Framed export recovery

- **No saved preset:** zeros are the default; use Save margins only when you want
  to retain a layout. Reset is local until saved. Native exports ignore the preset.
- **Invalid, foreign or symlinked framing.json:** preserve the file for explicit
  recovery. Do not overwrite it automatically. Native work and explicit valid
  preview/export margins remain usable; Save stays disabled until resolved.
- **Stale preset:** another client saved first. Your fields remain visible. Note
  any desired values, use Reload saved margins, then reapply your changes and save.
- **Durability unconfirmed:** replacement may already be visible. Keep your edits,
  use Reload saved margins to inspect the actual file, and retry only after resolving
  the storage error. The application does not promise rollback after replacement.
- **Preview busy, stale or unavailable:** wait for the current preview, choose a
  complete saved revision, then Preview framing again. Unsaved effect controls do
  not appear until their own operation is applied. Fields and the prior image remain
  available; an old image is labelled stale and cannot author guides.

- **Invalid or excessive margins:** use four nonnegative integer pixel counts in
  left/right/top/bottom order. Each output axis is limited to 32768 pixels and the
  total to 100,000,000 pixels. Reduce margins; the application does not resize the
  native photograph to fit. `--framed-transparent` requires explicit `--margins`
  or `--series-preset`.
- **Visible edge bands:** margins repeat the saved backdrop's nearest edge and
  corner colours. Reduce margins or review a different saved backdrop; foreground
  detail is never stretched into the added area.
- **Busy, low space or stale inputs:** finish the competing write, provide room
  above the existing 10 GiB reserve and operation budget, or reopen the saved
  project before retrying. Stale enabled effects need their existing explicit
  rebuild/disable workflow. Framing cannot bypass it.
- **Delivery collision:** preserve the existing directory. Missing, different,
  extra, symlinked or directory members prevent reuse. Do not repair a delivery by
  overwriting individual files. A changed revision, geometry or requested variant
  has a different presentation identity; identical retries validate exact files.
- **Publication durability unconfirmed:** a complete directory may already be
  visible after exclusive rename when the parent-directory sync fails. Preserve
  it and retry the identical export to validate and sync it. An error before
  publication leaves the prior delivery intact and retains a `.export-*` stage.
  Failed stages are diagnostic evidence, not accepted results, and remain preserved.
  A normal intact retry creates no stage. If an identical destination appears
  during fresh work, only that attempt's verified duplicate stage may be removed
  after the existing delivery validates and its parent-directory sync succeeds. Earlier
  stages are retained. If duplicate cleanup fails, the error identifies the durable
  delivery and the remaining stage; partially removed stage files may be incomplete.

## Repair and restore recovery

- Repair support must be the current prepared revision's returned support asset.
  Use its exact returned absolute path or project-relative equivalent. Prepare
  edited guidance first, then submit repair without repeated
  guide edits. An unrelated or symlinked support file is rejected.
- Feathered support cannot change a confirmed core. Revise support explicitly
  inside the authorized scope, or correct a genuinely erroneous core through
  typed guide edits and preparation. Trimap confirmation is optional. Never expand scope or remove locks
  merely to make a request pass.
- Stale draft/reference/parent errors preserve newer text and final acceptance.
  Inspect actual state before a new operation. Failed temporary revisions and
  cache work are retained; there is no automatic cleanup. Use the supported resume command for unchanged inputs.
- `replay --revision` verifies saved repair operands without models or cache.
  Missing or modified immutable operands/dependencies are errors; restore from
  your independent backup, never regenerate accepted operands with a model.
- Restore rejects unsaved draft text by default. Explicit `--replace-drafts`
  retains old bytes, including malformed current TOML/JSON, in the returned
  `recovery/restore-*/` directory. Saved target drafts and immutable master/source/
  state/revisions must still validate. On failure,
  final acceptance is unchanged but working drafts may be partly restored.
  Preserve that recovery directory, inspect its request and saved files, then
  explicitly restore a validated revision or recover your text. Restoring a
  revision does not accept it; final photographic acceptance is separate.


## Resume interrupted matte or repair

```sh
.venv/bin/blackmask status /path/to/project
.venv/bin/blackmask resume /path/to/project --operation ACTUAL_RETURNED_OPERATION_ID --model-cache /path/to/installed-vitmatte
```

`status` reports the saved working/accepted pointers, `writer_busy`, and retained
operation IDs with their progress and errors. It returns without waiting for the
writer. A saved `running` operation with no active writer is reported as `failed`,
with interruption-recovery guidance. `stale` means the saved inputs/dependencies
no longer match: finish current edits, prepare and review them, then start a new
request. Resume never replaces edited drafts or infers acceptance. Older completed
operations become stale when their working parent changes; those records preserve
history rather than indicate damage.

Resume verifies original request, source/master records, draft snapshots,
any supplied trimap approval and all consumed immutable support/lock/parent dependencies.
Completed tiles avoid repeat inference. A verified complete output stage or
published orphan can finish publication without loading a model. Incomplete or
invalid stages remain retained; incomplete/unknown tile entries are misses.
A backend change starts a new whole tile generation; predictions from different
devices never mix. A changed model/package/preprocess identity misses affected
cache entries. No original, accepted revision, export, failed stage or cache file
is automatically deleted.

The saved master supports resume even if the capture moved. If supplying
`--source /path/to/moved-capture`, its SHA-256 must match the original record;
resume does not rewrite the source locator. Keep independent originals/backups.
Space checks reserve 10 GiB plus conservative pending writes. On low disk,
arrange storage then retry; never fill the disk to test recovery. Preparation and
initial project creation do not resume. All calculations still require human
photographic review and explicit final acceptance.


## Local review window

Keep the foreground `blackmask open` terminal running. If browser launch fails, open
its printed local URL; keep the URL private. A server restart uses a new port and
capability: use its new printed URL. Reloading the original launch URL retains access.
Use `--headless` for JSON-only automation. No browser or assistant is needed for the
existing CLI commands; another terminal shares the same project lock.

Busy means another writer is active; comparisons/status remain readable. Do not
remove the writer lock file. Wait or stop the owning foreground process, then reopen
and inspect recovery. A visible stale authoring identity means reload current inputs
before saving. Existing source/revisions/accepted exports and failed stages remain
preserved; no automatic cleanup runs.

A malformed recipe/guide draft is shown as a draft error. Select a validated saved
revision and explicitly enable draft replacement to preserve the exact broken bytes
in recovery before restore. Saved pending authoring stays retained; load an
unconsumed stale batch with **Load retained pending guides for review**, recheck it
against source and save/prepare. Do not assume its former scope or lock binding is
still appropriate. Native coordinate boxes must be nonempty and half-open; support
must cover changed cores at full strength. See [manual workflow](workflow.md).


A malformed `viewer-draft.json` pointer or missing/damaged retained authoring record
is shown as a draft error while the review page remains available. Approvals and
processing reject these unresolved edits. Choose a valid **Restore saved revision**,
check **Preserve current draft bytes in recovery, then replace drafts**, and choose
**Restore working inputs (acceptance unchanged)**. The CLI equivalent is
`.venv/bin/blackmask restore /path/to/project --revision rev-NNN --replace-drafts`
from the repository root.
Recovery retains the exact old pointer bytes under `recovery/restore-*/`; the active
pointer is marked unreadable and retired. Existing request records are preserved.
This recovers saved inputs, not missing accepted dependencies; use an independent
backup for those. Reinspect the restored inputs before processing or accepting.


## Shadow fade recovery

An empty enabled selection needs nonzero support over nonzero alpha outside
protection. Use Apply shapes, then **Apply / replace fade area**; amount-only
requires a saved area. Changes to Softness/geometry need an area rebuild.
If a replacement removes old regions, its scope must include both old and new
support; viewer whole-adjustment actions use full-image scope.

STALE fade means alpha changed. Rebuild its area or **Reset Shadow fade**;
amount/preserve-only edits cannot refresh alpha. Other stale effects retain their
own recovery requirement. BASE disables all optional effects while stale and
acceptance/export remains blocked. Earlier accepted revisions stay retained.
Reset preserves the saved area and unsaved browser area edits. Reload explicitly
discards unsaved area edits and restores saved geometry/settings. Busy/stale-view
errors save no replacement; wait for the writer, reload and recheck the current view.

Clipping warnings belong to exposure before fade. Strong fade can darken displayed
white while exposure still reports clipping; this is expected. Full highlight
preservation does not guarantee fine-detail protection. If the result is too dark,
reduce Amount, raise Preserve highlights, add explicit Protect shapes or reset fade.
A pointer failure may leave a complete orphan revision; inspect actual working and
accepted pointers and use existing explicit restore/retry. Do not delete dependencies
or strip new effect records for use in an older binary.

## Background appearance recovery

For fixed-size delivery problems, see [series recovery](#series-framing-recovery).

If controls differ from the image, they are unsaved: **Apply background** and wait
for the new saved revision, or **Reload saved inputs** to discard the control draft.
Load the current working revision first. Background requires an accepted base or
explicit candidate comparison, and cannot consume pending matting guidance.
Changed background in an edited recipe blocks unrelated processing until an
explicit background operation or restore resolves it. Saved foreground-effect
staleness still requires each effect's own rebuild/disable; a background change
cannot clear it. Pure black with nonzero variation is expected and exact.

Missing, corrupt, unbound or mismatched saved background files stop reading;
restore from an intact backup rather than regenerating or rewriting accepted
assets. If state publication was interrupted, a complete saved orphan remains
non-authoritative. Explicit restore with draft replacement preserves current drafts
in recovery storage and selects that revision's background; acceptance is unchanged.
Export collisions preserve the existing delivery. Do not delete original projects,
accepted dependencies, failed stages or recovery material automatically.

## Series framing recovery

- **Malformed or oversized portable file:** retain the original file. Use UTF-8 JSON
  matching the [exact portable contract](file-contract.md#fixed-size-series-settings-and-deliveries),
  including strict integers, unique fields and at most 16384 bytes. Load changes no
  form values until validation succeeds. CLI preset paths must be regular files
  without symlink aliases; the viewer accepts file contents, never server paths.
- **Foreign, malformed or symlinked `series-framing.json`:** preserve it for explicit
  recovery. It belongs to one source identity/dimensions; do not transplant that
  project envelope to another photograph. Reuse a portable preset instead. The
  invalid file disables affected save/reload behavior while explicit valid series
  preview/export and native operations remain independent.
- **Empty mask, stray alpha or source-edge warning:** an empty mask cannot be framed.
  Every positive alpha value participates, so faint outliers can change the fit.
  Inspect Show subject bounds and repair the native mask explicitly. A subject
  touching the source edge may already be clipped; framing restores no anatomy.
- **Wider side margins than requested:** height limits the uniform fit. Change the
  output aspect ratio or margin settings if appropriate; the application will not
  stretch or crop the subject. Enlargement adds no captured detail; very small
  features can disappear on reduction. Inspect final TIFF pixels, not only preview.
- **Changed appearance under partial edges:** Match series regenerates the saved
  background recipe at the output size. Review that choice beneath transparency;
  Add margins has different exact-copy/edge-extension semantics. Unsupported or
  damaged saved backdrop records require an intact backup, not silent regeneration
  of native accepted assets.
- **Stale selection, manifest, source, effect or acceptance:** reload current state,
  select the intended complete saved revision and preview again. Accepted export
  requires that exact selection still be accepted. Draft remains DRAFT. Rebuild or
  explicitly disable each stale enabled effect; no BASE fallback is exported.
- **Busy preview or writer:** wait for the current operation. Preview modes share a
  nonblocking render guard and writers share the project lock. Do not remove lock
  files or start a second queue. A stale delayed response cannot replace newer fields.
- **Stale save or durability uncertainty:** retain unsaved values, choose Reload saved
  series settings to inspect actual visible settings/digest, reapply desired changes
  and save explicitly. Another tab's raw-byte change invalidates CAS even if settings
  look equal. No rollback or automatic overwrite is promised.
- **Low resources, coefficient/phase error or failed allocation:** keep the project
  and existing deliveries. Inspect the reported estimate/free space and choose an
  appropriate smaller requested delivery if desired. The 10 GiB reserve remains;
  a disk check does not guarantee RAM. No automatic cleanup, downsizing or precision
  reduction occurs. Report a sampling-phase error with the requested geometry.
- **Collision, unconfirmed publication or partial duplicate cleanup:** retain the
  destination and stages. An identical retry validates complete bytes and confirms
  publication sync. A successful-publication/cleanup error can leave a partially
  removed duplicate stage; it does not imply the delivered result failed. Earlier
  failed stages and accepted work are not swept. See
  [shared framed export recovery](#framed-export-recovery).
