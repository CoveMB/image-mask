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
  authorized cleanup. Resume/revision recovery arrives later.
- **Failed approval:** reopen the project and inspect its actual state. Before
  atomic replacement, failure preserves old state. After replacement, the update
  may be visible even if a later directory sync fails; never infer success/failure
  solely from the CLI exit. Reopen validates assets and actual acceptance state.
- **Stale identity/corrupt master/malformed draft:** do not bypass validation.
  Restore an independently retained correct copy or create a fresh project from
  the unchanged capture; human acceptance never follows from restore. No general
  repair command is implemented.
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
  retry with current identities. Resume/restore/automatic cleanup are unavailable.
  A failed pointer write may leave effective root guides updated; inspect them.
- **MPS failure:** retry explicitly with recipe device `cpu`, preserving geometry.
  Auto remains CPU; upstream implicit MPS fallback must be disabled. One synthetic
  successful MPS smoke is not photographic or regular-use acceptance.
- **Prepared revision rejected by accept:** expected. Human trimap review comes
  before later native matting; preparation never substitutes for a final result.
