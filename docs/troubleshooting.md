# I01 recovery

- **Missing profile:** explicitly assume sRGB only when correct, or supply a trusted
  sRGB TIFF. An assumption never overrides an incompatible embedded high-depth ICC.
- **Unsupported profile/compression/RGB16 PNG:** export a single-page contiguous
  uncompressed RGB16 sRGB TIFF through a trusted full-precision application. I01
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
  authorized cleanup. Resume/revision recovery arrives later.
- **Failed approval:** reopen the project and inspect its actual state. Before
  atomic replacement, failure preserves old state. After replacement, the update
  may be visible even if a later directory sync fails; never infer success/failure
  solely from the CLI exit. Reopen validates assets and actual acceptance state.
- **Stale identity/corrupt master/malformed draft:** do not bypass validation.
  Restore an independently retained correct copy or create a fresh project from
  the unchanged capture; human acceptance never follows from restore. No general
  repair command is implemented in I01.
- **Moved capture:** reopen uses retained master; locate the original by SHA-256
  before future source-dependent recomputation. Same filename is insufficient.

No model/MPS/viewer/assistant service is used by I01; their recovery procedures
will ship with those supported behaviors. All I01 commands work offline after
package setup. Preserve independent backups; ignored local data is not Git backup.

A publication collision means another tool/editor created a project asset while ingestion ran. Its bytes are preserved. Keep the incomplete project for inspection and choose a new empty destination. Do not delete an arriving file to force publication.
