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
accessibility, production safety or real RAW/backend evidence. These trusted-master
checks included no model, private photo upload, MPS/CPU inference, live assisted run or viewer exercise.
User-selected RAW/human WB/clipping/orientation review and regular-use acceptance
remain pending. Model, viewer and combined-journey evidence from that stage was
not established; later evidence is recorded separately below.

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


## Native matting and base-export evidence

Native matting and precision export checks exercised saved-file tests, independent
arithmetic sentinels, native tile origins/positive weights and nonempty known/partial
lock regions. A recorded-guide synthetic workflow exercised distinct development/trimap/final
controls through CLI and engine; programmatic fixture confirmations are not human
photographic acceptance. Real local CPU and diagnostic MPS ViTMatte inference
verify actual pad/unpad/normalization/device/attention. Native1024 evidence and
resource observations are in [provenance](model-provenance.md). Interruption,
stale inputs, corruption, conflicts, low space and non-clobber exports preserve
accepted state in covered paths. These native matting and base-export checks did
not certify hostile-writer exclusion, resumability, a viewer, local repair or
appearance effects; later evidence is recorded separately below.

Pending human evidence: selected private RAW orientation/WB/clipping; source-backed
trimap cores/corridors; spider/dragonfly wing/web/detail and native seams on black/
gray/white; explicit final photographic acceptance and regular-use pilot. No
private pixels were uploaded or inspected by an assistant during these checks.


## Scoped repair and working restore

Recorded deterministic verification: 179 tests passed, with three unchanged
model/setup integration tests deselected. Ruff/format and mypy passed. New checks
cover all merge policies, independent 1667/directional sentinels, saved feathered
operands, nonempty changed/outside/partial lock sets, exact RGB preservation, fresh-process replay with zero observed model
calls and an empty isolated cache, later full-rerun locks, restore without new
acceptance, unsaved-text recovery, stale/invalid inputs, low disk and publication
faults. Real CLI processes contend on the same OS lock while reads remain available;
a killed synthetic repair writer preserved source/acceptance and released its lock.
These fixture approvals are not human photographic acceptance. A moved-crop cache
mutation is rejected by its test (one model call instead of the required two).

Actual installed CPU float32 ViTMatte processed a 69×41 native crop at origin (7,5)
from a 97×65 synthetic source, with narrower feathered support and a partial lock.
The processor padded to 96×64 and returned registered native pixels. The measured
operation including loading/validation took about 4.21 seconds; process peak RSS
was 514,703,360 bytes. Exact source/accepted-state/partial-lock preservation and
saved replay passed. This small synthetic measurement is not a full-photo timing
or photographic-quality claim. Existing unchanged native matting CPU/MPS/backend
evidence remains separate; no new backend or dependency was introduced.

Human source-backed defect/scope/trimap, private RAW development, spider/dragonfly
detail/seam comparisons, final photographic acceptance and regular-use observations
remain pending. These scoped-repair checks did not establish a viewer, effects,
resumability or autonomous defect detection. Restore retains recovery bytes and
accepted state; interrupted draft replacement can require explicit text recovery.

Independent review and separate reproduction found four bounded issues in the
initial scoped-repair candidate: malformed current drafts blocked explicit recovery,
normalized saved guides could disagree with their draft digest, a default restore
could capture an intervening text edit without rejecting it, and default review lost
the saved repair crop. Eight failing regressions reproduced these defects;
eleven focused cases now pass, including invalid immutable-asset controls.
Restore uses validated exact input snapshots where needed, preserves malformed
text during explicit replacement, binds default checks to captured bytes and
retains saved crop geometry. The repaired full suite and static checks passed.


## Interrupted-work recovery evidence

Interrupted matte/repair now has durable request/snapshot validation and explicit
`status`/`resume`. Deterministic recovery tests cover paused and mid-run edits,
invalid/incomplete cache dependencies, complete-stage and pointer recovery,
whole-backend generation changes, conservative space rejection and fresh CLI
resume under actual OS writer contention. Fixture approvals are test controls.

A separate actual pinned ViTMatte CPU float32 run on synthetic RGB16 69×41 was
SIGKILLed after one verified native tile, during review-output construction
(child exit −9). Fresh-process `status` and `resume` both exited 0. Resume recorded
one reused tile and zero inferred tiles; accepted revision and all six prior
export file hashes stayed identical. Measured interrupted child peak RSS was
508,329,984 bytes; this small input does not predict full-size memory use. This
is actual backend recovery evidence, distinct from deterministic fault injection
and from pending human photographic/RAW/regular-use acceptance. Existing model
pins, loader, native geometry, quantization and inference APIs are unchanged.

Recorded recovery verification: **213 passed**, three unchanged integration tests
deselected; Ruff lint/format and mypy passed (all exit 0). At that verification,
the inspected wheel (18 entries) and source archive (55 entries) matched the
then-current modules; source tests and public docs also matched. No private asset
or personal-path content was found.

Review repairs bind recovery to the original request bytes. Matte and repair
race regressions rejected stale completed-stage publication before the fix and
now pass. Cache invalidation checks include warm reuse with complete identities;
in-memory omissions of model hashes, packages and the operation’s native context
each caused the intended assertion failure. The recorded archive inspection
followed the completed documentation.


## Local review boundary

Local review verification covers HTTP origin/host/capability and exact asset-identity
checks, executable native JavaScript transform checks, shared-lock CLI/viewer contention, draft concurrency,
malformed-draft restore and an actual HTTP synthetic guide/support/partial-lock
repair/accept/restore/resume journey. That deterministic journey stubs the expensive
model boundary; it exercises real rasterization, files, publication and rendering.
Node.js executes the shipped coordinate helper across cropped/non-square,
zoomed/panned/letterboxed/resized views, including CSS/canvas scale differences.

A separate actual browser walkthrough used a rotated RGB16 synthetic gradient
with real pinned CPU SAM and ViTMatte. New background, feathered support and 25
partially transparent locked pixels were authored through page controls. A native
point under zoom/pan saved the expected coordinates. The repair changed 875 samples;
5,405 outside-support samples and all 25 partial locks stayed exact, and the new
background core was exactly zero. Accepted export hashes were retained for comparison.
These are bounded synthetic computational/browser observations, not photographic
quality or calibrated color evidence. The environment used local packaged resources
and existing model assets; physically disconnected network and a closed assistant
were not observed. Human keyboard/usability/accessibility, user-selected RAW,
photographic review and regular-use offline acceptance remain pending.

A real viewer process was also interrupted while a full native rerun was active,
then reopened in a fresh process. The readiness marker was not observed, so the
precise interruption phase is unverified. Fresh UI status reported the interrupted
writer and Resume completed from validated saved inputs, preserving all 25 partial
locks and the accepted pointer/export hashes. Its actual tile counts are recorded
separately from the earlier successful cropped repair; no post-tile kill is claimed.

The settled full deterministic run passed 227 tests (three unchanged model integration
tests deselected). Ruff, formatting, mypy and UI formatting passed after two test-only
import-order corrections; the affected two tests passed after those corrections.
An initial partial run was interrupted because a legacy JSON-only CLI test did not select the new
`--headless` option; that compatibility check was corrected before the full pass.


The bounded UI review repairs add six behavioral regressions that execute the shipped
page and coordinate functions with controlled DOM/transport boundaries. All six
failed for the original defects, then passed: export preserves unsaved authoring;
processing and crossing gestures cannot create guides; pending/failed crop loads
cannot remap old pixels; reload clears review confirmations and selects current
revision; resume requires saved authoring. Matching image/overlay publication is
atomic from the page’s perspective. These checks are distinct from native browser
rendering and human usability observations.

The repaired full deterministic suite passed 233 tests (three unchanged integrations
deselected). Changed page/test formatting and lint passed; the six affected tests
passed after a test-only import-spacing correction. Python source/type inputs
are byte-identical to the successful mypy run. Actual browser export retained
a new unsaved guide; a real CLI restore followed by page reload cleared both review
checkboxes, selected the current revision and rejected acceptance without a new
confirmation. Long recovery controls fit 1,000- and 800-pixel desktop widths;
accepted export hashes stayed exact. No model inference was repeated for these frontend repairs. Human acceptance obligations remain pending.

## Bounded assisted review evidence

Synthetic public-operation contract checks cover finite proposals, native review
identity/crop integrity, a two-attempt shared cycle budget, mandatory source
comparison, early stops, unchanged-alpha no-progress, partial-lock/outside-support
preservation, immutable request/result/history reopen, interrupted reservation/resume
and real-process CLI writer contention. Model predictions in these assisted-review
tests are explicitly stubbed; this is not live assistant compliance or photographic
quality evidence. Existing manual request and recovery contracts remain covered.

The full deterministic run for this assisted-review feature passed 263 tests, with
three unchanged model integration tests deselected. After the final narrow integrity
repair, all 32 affected assisted-review tests passed, along with lint, formatting and
source type checks. That final affected run was not a new full-suite run.

A live source-visible photographic defect/repair/human comparison and same-project
closed-assistant/disconnected-network manual correction remain pending. These
assisted-review runs did not include appearance effects. See
[the assisted procedure](assistant-workflow.md).
