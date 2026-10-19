# Photo project recovery

- **Missing profile:** explicitly assume sRGB only when correct, or supply a trusted
  sRGB TIFF. An assumption never overrides an incompatible embedded high-depth ICC.
- **Unsupported profile/compression/RGB16 PNG:** export a single-page contiguous
  uncompressed RGB16 sRGB TIFF through a trusted full-precision application. The importer
  recognizes a conservative canonical ICC representation; an sRGB name alone is
  insufficient. Do not convert high-depth data through Pillow RGB8.
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
  authorized cleanup. Resume remains future work; saved working revisions can be restored.
- **Failed approval:** reopen the project and inspect its actual state. Before
  atomic replacement, failure preserves old state. After replacement, the update
  may be visible even if a later directory sync fails; never infer success/failure
  solely from the CLI exit. Reopen validates assets and actual acceptance state.
- **Stale identity/corrupt master:** do not bypass validation.
  Restore an independently retained correct copy or create a fresh project from
  the unchanged capture; human acceptance never follows from restore. Scoped alpha repair does not repair corrupt master/project data.
- **Moved capture:** reopen uses retained master; locate the original by SHA-256
  before future source-dependent recomputation. Same filename is insufficient.

The viewer and assistant service are not implemented. Processing works offline
after explicit package/model setup. Preserve independent backups; ignored local data is not Git backup.

A publication collision means another tool/editor created a project asset while ingestion ran. Its bytes are preserved. Keep the incomplete project for inspection and choose a new empty destination. Do not delete an arriving file to force publication.


## Preparation recovery

- **Missing/corrupt SAM:** inference never downloads. Inspect the explicit cache;
  retain mismatched files for diagnosis and select a new empty cache for a separately
  authorized setup. Do not replace weights/configs with same-name alternatives.
- **Stale request:** reopen to obtain actual master/base/draft digest. Finish external
  edits, inspect source/trimap intent, and submit a fresh request. Newer text remains
  untouched. Typed edits already published need not be submitted again.
- **FG/BG/lock/core-support conflict:** resolve the typed assertions from the source.
  No last-layer overwrite or automatic shrinking of protection occurs. Remove a
  lock explicitly before changing its binding. A new prepare-only project has no
  saved alpha to lock.
- **Interrupted/failed prepare:** reopen actual state. The prior working revision
  remains authoritative until state advances. `.prepare-*` or a complete orphan is
  not accepted/working solely because it exists. Inspect retained diagnostics;
  retry with current identities. Resume and automatic cleanup are unavailable;
  saved working revisions can be restored explicitly.
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
  `.matte-*` and complete orphans are not pointer authority. Submit a fresh current
  request; verified cache can help, but resumability is not yet supported.
  Saved working revisions can be restored explicitly.
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
  cache work are retained; there is no automatic cleanup or resume command.
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
