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

In the 2026-10-18 assisted-review run, synthetic public-operation contract checks
covered finite proposals, native review identity/crop integrity, a two-attempt shared
cycle budget, mandatory source comparison, early stops, unchanged-alpha no-progress, partial-lock/outside-support
preservation, immutable request/result/history reopen, interrupted reservation/resume
and real-process CLI writer contention. Model predictions in these assisted-review
tests were explicitly stubbed; this is not live assistant compliance or photographic
quality evidence. The full deterministic run also covered existing manual requests
and recovery contracts.

The full deterministic run for this assisted-review feature passed 263 tests, with
three unchanged model integration tests deselected. After the final narrow integrity
repair, all 32 affected assisted-review tests passed, along with lint, formatting and
source type checks. That final affected run was not a new full-suite run.

A live source-visible photographic defect/repair/human comparison and same-project
closed-assistant/disconnected-network manual correction remain pending. These
assisted-review runs did not include appearance effects. See
[the assisted procedure](assistant-workflow.md).

## Source-guided color-cleanup evidence — 2026-10-18

The full deterministic suite passed 283 tests with 3 unchanged real-model integrations
deselected, exit 0. It was followed by an actual-browser recovery correction: explicit
disable/zero no longer requires nonempty correction support. The affected effects/page
suite then passed 25 tests; this is affected renewal, not a fresh 284-test full run.
Additional regression checks covered selected-foreground identity in review manifests.
Ruff lint/format and source mypy passed after the recovery fix. These early checks do
not establish later correction or delivered-package results.

Application tests use real profiled RGB16 TIFF, alpha16 and support16 PNG reloads,
independent inverse-mixture sentinels, nonempty changed/opaque/protected/outside sets,
off/zero/no-compounding, exact saved partial RGB locks, stale alpha dependencies,
blocked acceptance/draft export, retained accepted exports, scoped rebuild and explicit
disable. CLI processes exercise effects and writer contention. Injected interrupted
state publication retains the complete effect revision for explicit restore. Source-only
cleanup calls no model; synthetic matte boundary stubs are not real-model evidence.

An actual in-app browser on a 6×4 synthetic source observed labelled default-OFF
controls, keyboard enable, source/result and same-alpha base selection, visible saved
revision/status changes, and keyboard disable after reopening the project with the
recovery fix. Empty support failed visibly instead of expanding scope. The accepted
base revision stayed separate. These observations do not establish human photographic
preference, accessibility conformance, closed-assistant operation or physically
network-disconnected usability. No private photograph or new model was accessed.


After RGB-lock and recipe-identity corrections, a fresh full deterministic suite
passed: **293 passed,
3 unchanged real-model integrations deselected**, exit 0. Ruff lint/format, source
mypy and pip dependency checks exited 0. Five review regressions first failed on
recipe review/accept/restore, same-alpha locks on full matte and scoped repair,
first/re-enabled outside-support locks and no-op before/after panels; an additional
prepared-lock compatibility regression also failed before its bounded repair.
Exact saved RGB/black exports now preserve the independently expected partial-lock
RGB [23559,33559,43559] and black [5890,8390,10890] at alpha16384. Changed guides,
matting settings and groups remain rejected until prepared and completed, while
recipe-only cleanup settings can be accepted/restored with exact consumed bytes.
Independent source-fidelity, architecture/simplicity and verification reviews covered
the corrections. No unchanged real-model or browser execution was repeated.


Independent verification identified a connected guard defect: a new RGB
lock matching the current selected corrected appearance was wrongly rejected outside
narrow alpha support because it was compared with base master RGB. Two actual repair
regressions failed first (unchanged and changed alpha), while a different historical
lock remained correctly rejected. The bounded shared guard correction passed **113
affected effects/repair/matte/recovery tests**, exit 0, plus Ruff lint/format
and source mypy exit 0. The earlier full 293-test result with 3 integrations
deselected remains earlier evidence;
this is affected renewal, not a fresh 296-test full run. Saved selected/corrected RGB and
alpha outside support, independent locked black exports, model-free repair replay,
source/master bytes and prior accepted exports are preserved. Stale base-to-base panels
are labelled and match their actual saved base layers; no differing historical RGB lock
can expand repair scope. No unchanged model or browser check was repeated.


## Protected inward shading validation — 2026-10-18

The settled deterministic suite passed **311 tests**, with three unchanged real-model
integrations deselected. Ruff lint/format, source mypy and installed dependency
checks passed. Earlier focused 78 tests passed before final added invalid-input,
mutable-protection and interrupted-shading cases; it is not substituted for the
settled full run. No unchanged model inference was rerun.

Independent arithmetic sentinels exercise partial A/W, ties-to-even and a
premature-shaded-foreground-rounding counterexample. Synthetic weight checks
cover nonempty bands, thin structures, partial alpha, explicit protection,
empty background and interior/outside support, with W independent of opacity.
Public operation tests cover separate saved RGB16/A16/W16 round trips, cleanup
independence, global opacity without weight rebuild/model calls and exact
lossless black output. Both effects enabled, local alpha repair, labelled
base comparisons, independent stale acceptance/export gates, bounded per-effect
rebuild and a fresh-process export pass together. Prior accepted export bytes
and source/master remain exact; protected W and outside-support W/RGB survive.

Existing manual viewer/server and shipped JavaScript handler tests exercise
0/12/24 identical native crops, explicit width/direction/protection inputs,
independent disable and dirty-authoring protection. Controlled DOM checks and
server pixels are not actual browser, keyboard usability or accessibility
acceptance. Invalid numeric/settings requests, mutable protection and interrupted
publication preserve current state; explicit restore retains accepted work.

Official metadata for the four unchanged NumPy/SciPy/Pillow/tifffile pins lists
no advisories at this bounded check; this does not clear unrelated dependencies.
No package, model, backend or licence change was introduced. Current APIs follow
[NumPy ties-to-even rounding](https://numpy.org/doc/stable/reference/generated/numpy.rint.html)
and [SciPy Euclidean distance](https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.distance_transform_edt.html).

Human same-crop photographic appearance/protection choices remain pending.
Reference-specific widths are not new-photo defaults. No private photographs
were inspected/uploaded and no fresh full-source dahlia outcome is claimed.
User RAW/third input, live assisted, closed-assistant manual, physical offline,
accessibility and regular-use acceptance obligations remain open.


Follow-up fixes passed **110 affected effects/viewer/page/review/repair tests**,
with lint/format/source typing also passing. The earlier full 311-test run remains
earlier evidence; this is not a new full 314-test run. Three new regressions and
the strengthened both-effects repair-and-rebuild journey cover first shading
enablement directly from locally authored saved-value guide protection, effective
historical/BASE/stale/loading labels bound to matching images, and nonempty
partial RGB locks inside/outside
repair support with independently derived decoded BASE pixels on both sides,
exact alpha and replay. The original first-use and page cases failed before
repair; the stronger both-effects journey passed the existing correct processing
behavior.
Categorical8 authored protection normalizes losslessly to separately saved
categorical16 without changing the scalar16 precision contract. No unchanged
model/dependency/full-suite rerun was needed. Human acceptance limits above remain.


## Combined workflow validation

The combined local workflow covers ingestion, selection, native matting, scoped
repair, recovery, assisted review and optional effects. **Representative photographic
and regular-use acceptance remain pending**. These recorded checks use the same
processing, dependency and model inputs as the protected-shading evidence above;
documentation corrections add no processing path.

On native ARM64 Python 3.12.14/macOS 26.5.2, with the pinned local caches and packages
in [provenance](model-provenance.md), the complete registered groups ran separately:

```sh
BLACKMASK_SAM_CACHE=/path/to/installed-sam BLACKMASK_VITMATTE_CACHE=/path/to/installed-vitmatte .venv/bin/python -m pytest -q -p no:cacheprovider -m "not integration"
BLACKMASK_SAM_CACHE=/path/to/installed-sam BLACKMASK_VITMATTE_CACHE=/path/to/installed-vitmatte .venv/bin/python -m pytest -q -p no:cacheprovider -m integration
```

The deterministic group passed **314 tests, 3 deselected**; the real CPU integration
group passed **3 tests, 314 deselected**, no skips, both exit 0. These establish
combined test correspondence after the earlier affected renewals, not photographic
quality. The integrations exercise SAM geometry/normalization/warm embedding reuse,
ViTMatte native pad/unpad and existing pinned setup without network access.
Earlier bounded-assisted-review evidence comprised a full 263-test run followed by
32 affected tests; color-cleanup evidence comprised a full 293-test run followed by
113 affected tests; protected-shading evidence comprised a full 311-test run followed
by 110 affected tests. These remain historical full/affected observations.
Prior lint/format/source typing and dependency evidence remains applicable because
its inputs are unchanged. The earlier MPS/native 1024 runs remain prior evidence;
they were not repeated for combined validation.

A separate fresh-process walkthrough copied the combined synthetic both-effects
repair/rebuild project without inference cache or exports. Both model constructors, network loading and
original-capture reads were blocked. Actual headless reopen, status, repair replay,
review, export and restore exited 0. Empty model caches stayed empty. Independently
decoded 6×4 RGB16/A16/W16 and opacity .12 reconstructed black pixels exactly; all
13 accepted export files matched the original fixture bytes. There were 16 partial
alpha samples and 8 nonzero W samples. Restore retained its synthetic accepted
pointer. Fixture approvals are test controls, never human photographic approval.
Installed help for all 11 documented commands exited 0. Review found that the manual
launch examples required an undocumented shell activation; they now use the explicit
`.venv/bin/blackmask` executable from the repository root. Actual open-help and
headless reopen passed in a fresh process with only system PATH and no VIRTUAL_ENV.
This CLI walkthrough does not establish a human keyboard/browser walkthrough or
physically offline use.

The following rows identify current computational coverage and remaining source
obligations. Test names refer to the shipped `tests/` suite. “Pending” cannot be
closed by a numerical pass or approval of source development.

| Acceptance check | Applicable evidence | Remaining obligation / owner |
| --- | --- | --- |
| Source integrity | `test_ingest.py`, `test_project.py`; operation/export preservation checks and saved-only reconstruction | Capture integrity checked on fixtures; human selects and retains pilot originals |
| RGB precision | RGB16 ramp, unsupported PNG16 rejection, real saved TIFF/mask reloads and independent export arithmetic | Human reviews selected RAW development; RGB8 inputs gain no captured precision |
| Input/orientation | Misnamed/rotated non-square tests; unchanged canonical ingest; bounded actual Kodak LibRaw receipt | User-selected RAW orientation and source/guide registration review |
| WB/profile | Invalid WB/profile tests, explicit assumptions and separate development gate; Kodak remains unapproved | Human WB/clipping/profile/development decision on local RAW |
| Model geometry | Current 3 integrations; prior actual separate CPU/MPS records and native 1024 geometry | Human photographic CPU/MPS quality/responsiveness; auto stays CPU |
| Known cores | Nonempty exact FG/BG assertions in guidance/matte/repair tests | Human verifies actual source-supported cores |
| Transparency/web | Unknown corridors, mixed-alpha and partial-lock tests | Native spider/web and dragonfly wing/detail review by human |
| Conflicts | Shared rasterizer, feather/core, directional and lock-contradiction rejection tests | Human resolves ambiguous source guidance; no automatic expansion |
| Tile boundaries | Hand-derived origins, positive coverage, pad/unpad; retained two actual 1024 tiles | Human native photographic seam inspection; statistic is insufficient |
| Repair/full rerun | Scoped-repair and both-effects journeys with nonempty outside/partial alpha/RGB locks, decoded exports and full-rerun preservation | Human approves defect/scope and resulting fragile detail |
| Repair replay | All three policies in the scoped-repair/restore/replay journey; fresh guarded saved-only combined repair replay | Computationally covered for fixtures; retain all pilot operands/dependencies |
| Stale/concurrent | Wrong identities, mutable inputs and real OS writer contention in operation/viewer/restore tests | Human follows visible busy/stale recovery in pilot |
| Bounded AI loop | `test_assisted_review.py` validates shared two-attempt cycle, early stops and immutable history | Actual assistant behavior and human comparison remain pending |
| Live AI defect | Public operation/proposal tests only | Human authorizes live image access, then confirms source-supported repair; no upload implied |
| Optional effects | Complete both-effects journey, independent scoped stale/rebuild gates, partial RGB locks and BASE pixels | Human same-alpha color/shading preference and explicit protection review |
| Alpha/opacity | Independent single-round sentinels and saved-only RGB16/A16/W16/p reconstruction | Exact arithmetic covered; photographic appearance remains human |
| Exports | Lossless reload/collision tests; all 13 saved-only export files match, straight viewing copies labelled | Human inspects editable handoff/native appearance; PNG8 is a convenience |
| Cache use | Current warm SAM integration, invalidation/device-generation/opacity zero-model tests | Representative cold/warm photo measurements pending; cache is not accepted-data storage |
| Interruption/disk | Deterministic reserve/publication faults; retained actual native-model post-tile SIGKILL/resume | Human pilot recovery; review-window interruption phase remains unverified, never relabelled post-tile |
| No-credit/offline | Local HTTP/page tests, prior real synthetic browser controls and guarded saved-only CLI | Human closes assistant, physically disconnects network and authors NEW guides/support/partial lock |
| Documentation | Actual installed help and fresh guarded CLI walkthrough; corrected current workflow/recovery docs | Fresh human source-to-export keyboard/status/recovery walkthrough without hidden context |

| Journey | Combined evidence | Remaining human evidence |
| --- | --- | --- |
| Ingest to export | `test_recorded_guides_matte_acceptance_and_saved_exports`; current integration geometry | Three separate photographic cases plus selected RAW; development/trimap/final choices |
| Repair/full rerun/restore/replay | `test_repair_roundtrip_replay_full_rerun_locks_and_restore`, all policies; fresh CLI replay | Source-backed defect/scope and human fragile-detail acceptance |
| Interrupt/resume/export | `test_resume.py`; actual native-model verified-tile SIGKILL -9, fresh reuse 1/infer 0 with accepted exports intact | Representative pilot recovery; no new combined-validation kill or inferred review-window phase |
| Offline authoring | Current viewer/page tests and prior real synthetic browser authoring | Same-project closed-assistant/physically offline NEW core/support/partial-lock correction and keyboard use |
| Live assisted to manual | Recorded synthetic bounded-cycle and continuation contracts | Authorized live source-visible repair/human compare followed by closed-assistant manual correction |
| Both effects/repair/rebuild/export | `test_both_effects_repair_independent_stale_rebuild_and_fresh_export`; guarded saved-only reproduction | Human appearance/protection on complete photographic sources; full-source dahlia unavailable |

### Resource and retention limits

The observed Mac is MacBookPro18,2, 10 physical CPU cores and 64 GiB memory. Free
space at combined-workflow preflight was 28,139,569,152 bytes; estimated bounded
pending writes were 250 MiB, checked in addition to the 10 GiB reserve. Measured logical file sizes
excluding symlinks were 1,065,483,744 bytes for the environment and 575,214,708 bytes
for the existing model-cache root. Logical bytes are not physical allocated disk.
No environment, source, accepted asset, model, cache, failed stage or evidence was deleted.

Earlier observed conditions remain separate: SAM synthetic 65×97 recorded .035s load,
.732s first stage and .025s warm embedding stage, peak RSS about 1.93GB including
separate MPS work. Native 1024 matting used two 1024×1024 tiles over 1025×1024, 3.49s
operation and 7,856,570,368-byte process peak RSS. CPU 69×41 repair in a 97×65
synthetic source took 4.21s including loading/validation, peak 514,703,360 bytes.
Native-model post-tile recovery observed peak 508,329,984 bytes. These are distinct
prior synthetic measurements, not full-photo throughput or current memory-pressure data.
The fresh 6×4 saved-only export CLI took .375s including process startup. The two
current pytest groups took 67.25s and 8.02s respectively; suite duration is not
seconds per photograph. Representative cold/warm full matte/repair/export timing,
OS memory pressure and photo-project disk growth remain unmeasured human-pilot work.

Retain durable source/contracts/reviews and exact computational proof; hold active
pilot inputs, earlier environments, failed/successful packages, caches/stages and
accepted dependencies until their consumers and independent backups are verified.
Uncertain external ownership/storage remains unknown. Retention review grants no
deletion permission and does not make ignored data a Git backup.

### Pending representative pilot

Use the [complete manual workflow](workflow.md), [bounded assisted procedure](assistant-workflow.md)
and [recovery instructions](troubleshooting.md), processing each photograph separately.
The human owns input selection, development/trimap/photographic decisions and the
regular-use decision. The existing Kodak test is bounded LibRaw evidence with
unresolved redistribution rights; it is neither the selected RAW pilot nor a
redistributable fixture. No private pixels were uploaded for this reconciliation.

1. Select local spider/prey/web, dragonfly and bee/flower or grasshopper originals,
   including a real RAW/DNG; record hashes and choose separate empty project roots.
   Preserve originals and existing accepted results. Choose CPU and verify existing
   model caches with `doctor`; check reserve plus actual estimated pending writes.
2. In a fresh session follow source development, named groups/unknown corridors,
   explicit trimap review, native matte and black/gray/white same-crop detail/seam
   review. Inspect the saved RGB16 master in a trusted full-precision viewer.
3. Record a concrete source-visible defect, permitted support/context and partial
   locks. Live assistant image access needs separate authority. Stop ambiguous or
   unimproved cycles, never degrade a good result to manufacture a defect. Human
   confirms matching before/after and base photographic acceptance.
4. If desired compare same-alpha cleanup and 0/12/24% shading on identical native
   crops with explicit per-photo width/protection. Exercise both-effect stale gates
   and bounded rebuild; human decides appearance. Missing full-source dahlia stays pending.
5. Close the assistant and physically disconnect application network after setup.
   In this same project author a NEW source-supported background core, support and
   saved partial-alpha/RGB lock through the viewer, without prebuilt masks/editor/
   scripts. Prepare, approve, repair, compare, explicitly accept, restore and resume.
   Record keyboard/status/errors and retained acceptance; automated local use does
   not establish this observation.
6. In a separately retained candidate observe actual interruption stage and fresh
   resume while prior accepted exports stay intact. Use a copied disposable project
   with cache absent and models unavailable to replay saved operands and reconstruct
   exact RGB16/A16/W16/p output; preserve the original project and caches.
7. Record actual dimensions, inferred/reused tiles, cold/warm conditions, stage
   times, process peak RSS, OS memory pressure and disk growth. Enable default GPU
   only after separate actual quality/responsiveness decisions. No invented threshold
   or CPU result substitutes for MPS quality acceptance.
8. Record unresolved observations and each human decision. Source-development
   approval, test passes and independent review cannot supply regular-use acceptance.
