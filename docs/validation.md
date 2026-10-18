# Verification

## Retained trusted-master evidence

Observed on 2026-10-18 with native ARM64 Python 3.12.14, macOS 26.5.2 and
LibRaw 0.22.1. The results below describe the trusted-master implementation and
its stated evidence limits.

```sh
.venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/ruff check src tests --no-cache
.venv/bin/ruff format --check src tests --no-cache
.venv/bin/mypy src
```

Recorded result: **50 passed** (exit 0); lint, format and type checks exited
0. Hash-locked binary-only installation and dependency checks passed. Built-wheel
inspection found only six application modules and package metadata, with no
photographs, private planning, personal paths or VCS data. CLI create/reopen,
explicit development approval and download-free doctor are exercised in fresh
processes. Dependency/native evidence is summarized in [provenance](model-provenance.md).

Independent source-fidelity, architecture/simplicity and verification scopes were
completed, with focused rechecks after material corrections. Corrections covered
initial publication collisions, non-finite rejected camera WB metadata, meaningful
ICC conversion regression sensitivity and TIFF-container RAW routing. All findings
closed within their scopes.
These reports and passing tests do not replace human development or photographic
acceptance.

Synthetic ingest checks exercise exact non-257 RGB16 TIFF file reload, all eight
asymmetric orientations, big-endian TIFF, misnamed signatures, JPEG/PNG8 sample
expansion, actual LittleCMS RGB8 transform, original-profile/dimension metadata,
RGB16 PNG rejection before Pillow, alpha/compression/profile/development errors.
RAW boundary stubs assert explicit AHD/full-size/gamma/WB/brightness parameters and
invalid camera-coefficient response; they cannot establish real RAW correctness.

Project tests exercise unchanged capture hashes, separate identity for development
changes, alias/symlink refusal, existing-project preservation, corrupt master and
draft rejection, reserve failures, state publication/approval faults, actual
competing-process busy/read behavior and an actually killed initial writer.
No accepted pointer ever references an incomplete candidate in these checks.
Fresh CLI processes create/reopen/approve development and run the download-free
native preflight. Synthetic approval calls model a human decision for fixtures;
no real photograph has been approved by an agent.

Native environment observed: macOS 26.5.2 ARM64, Python 3.12.14, LibRaw 0.22.1.
Package metadata, wheel hashes, licences and advisory disposition are in provenance.
Passing deterministic tests/type/lint checks are not photographic, usability,
accessibility, production safety or real RAW/backend evidence. No model, private
photo upload, MPS/CPU inference or live assisted run occurred. These trusted-master checks did not exercise a viewer.
User-selected RAW/human WB/clipping/orientation review remains pending; regular-use acceptance and model/viewer/combined-journey checks remain future work.

Regression checks include explicit NaN/Inf daylight project-creation cases, arriving-file collision preservation and a linear-light RGB ICC sentinel. The latter independently expects encoded sRGB [71,137,188] from RGB8 linear samples [16,64,128]; bypassing colour conversion is observably wrong.


TIFF-container RAW regressions distinguish IFD0 RGB8 preview
from the LibRaw-developed full-resolution RGB16 and cover recognized-RAW WB/data
failures, including an unsupported exception raised after opening. Only unsupported
format at opening permits ordinary TIFF fallback; its existing compression/profile
and PNG16 rejections remain exercised. The public upstream Kodak KDC also
passed actual LibRaw ingest/create/reopen/master-reload with exact direct-decoder
pixels and unchanged source. It stayed unapproved. Provenance identifies the public
source/hash; the fixture is not tracked. This is bounded actual RAW evidence, not
human photographic acceptance or comprehensive camera-format coverage.


## Selection and preparation evidence — 2026-10-18

The recorded suite with explicit local model cache passed **108 tests** (exit 0),
including the registered real SAM `integration` test; no skips. Ruff check/format,
mypy (9 source modules) and pip dependency check exited 0. Pip reported its
unwritable user cache warning while the dependency check still completed.

```sh
BLACKMASK_SAM_CACHE=/path/to/model-cache/sam2 .venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/ruff check src tests --no-cache
.venv/bin/ruff format --check src tests --no-cache
.venv/bin/mypy src
.venv/bin/python -m pip check
```

Guidance checks exercise actual native half-open geometry, categorical labels/locks,
unknown corridors, typed roles, zero/inward-feather support, invalid inputs,
FG/BG/lock contradictions and saved partial-alpha protection. Preparation carries
nonempty partial alpha exactly; these downstream-boundary fixtures are synthetic,
not actual matting or final acceptance. Selected membership remains separate from
opacity; actual file round trips validate published assets.

Preparation identity, cache and recovery checks exercise stale master/base/draft/request/external
edit/parent and non-parent lock identities, digest/state binding at capture and final atomic-replacement boundaries, no clobber of changed drafts, corrupt
revision rejection, reserve/publication failure, real competing writer/read
behavior and a killed prepare process followed by safe retry. State alone owns
pointers; retained stages and orphans are not working/accepted data. No resume or
persistent tile cache is claimed.

Pinned real CPU SAM validates explicit image/fast processor classes, hash checks,
actual 1024 overview and native mask geometry, finite output, independently
expected normalization, warm embedding reuse and changed-master invalidation.
A fresh actual CLI journey created a synthetic RGB16 master, simulated development
approval, saved three real SAM candidates/selected membership and explicit FG/BG
trimap, and reopened the prepared revision with accepted state still empty.
Separate MPS synthetic execution passed, with identical binary masks and small
score differences; observed timings/RSS and package/advisory limits are in
[provenance](model-provenance.md). CPU remains auto default. Failure/one-CPU-retry
behavior uses injected failures, distinct from actual MPS success.

No real photograph, human trimap review, final photographic acceptance, ViTMatte
runtime, matte/export/viewer or regular-use acceptance was established by these
selection and preparation checks.
These remain explicit downstream obligations.


### Native morphology proposal verification

The earlier 96-test result and associated reviews did not exercise morphology
proposal generation. Verification including explicit saved native margins and
selected-mask influence passed 108 tests. Hand-derived non-square core/boundary grids cover erosion/dilation, zero
margins, image exterior, holes, fragile-group overlaps, separately confirmed solid
cores, BG/lock/support conflicts, saved-alpha/state preservation, invalid settings
and old-draft compatibility. The proposal is a separate unreviewed categorical
asset; no known values or human review are inferred into authoritative trimaps.
The existing real CPU synthetic project also exercised the changed proposal route;
model/device/package pins and prior independent MPS evidence remain unchanged.
