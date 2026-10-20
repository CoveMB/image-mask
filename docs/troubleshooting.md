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
- **Invalid camera WB:** explicitly request a daylight preview or supply developed
  TIFF; inspect WB/clipping before development acceptance. No generic
  AsShotWhiteXY conversion is available. Actual camera coverage is unverified.
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
- **Stale request:** run `blackmask open --headless --project /path/to/project`
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
- **Prepared revision rejected by accept:** expected. Human trimap review comes
  before native matting; preparation never substitutes for a final result.


## Native matte and export recovery

- **Trimap approval missing/stale:** inspect authoritative prepared trimap against
  source, finish typed edits, prepare again and explicitly confirm returned identities.
  A morphology proposal never counts as confirmed guide values.
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
- **Export collision:** keep prior delivery; identical output reuses it. Different
  bytes or an incomplete directory fail without overwrite. A newer candidate has a
  different revision; explicit unaccepted output must use `--revision ... --draft`.


## Repair and restore recovery

- Repair support must be the current prepared revision's returned support asset.
  Use its exact returned absolute path or project-relative equivalent. Prepare
  edited guidance first, approve its trimap, then submit repair without repeated
  guide edits. An unrelated or symlinked support file is rejected.
- Feathered support cannot change a confirmed core. Revise support explicitly
  inside the authorized scope, or correct a genuinely erroneous core through
  typed guide edits and new trimap review. Never expand scope or remove locks
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

`status` returns saved working/accepted pointers, `writer_busy`, and retained
operation IDs with progress/errors. It does not wait for the writer. A saved
`running` operation without a writer is reported `failed` with interruption
recovery guidance. `stale` means saved inputs/dependencies no longer match;
finish current edits, prepare/review them and start a new request. Resume never
replaces edited drafts or infers acceptance. Older completed operations become
stale after their working parent changes; this is retained history, not damage.

Resume verifies original request, source/master records, draft snapshots,
trimap approval and all consumed immutable support/lock/parent dependencies.
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
`blackmask restore /path/to/project --revision rev-NNN --replace-drafts`.
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
