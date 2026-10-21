# Verification

## Fixed-size series framing

Current local implementation evidence is synthetic and bound to frozen application
inputs recorded with candidate `5ffcc99254b3d6b884844bfbb472f303478dd77ba8be755d3557e927c3b8de41`.
The independent review, representative resource measurement, package inspection and
observed synthetic browser journey are complete. Root's full suite passed 746 tests
with three optional cache skips. Final lint/type/format checks passed after one
AST-equivalent test-formatting correction and a passing affected application test.
No human photographic or full accessibility acceptance is claimed.

- Checkpoint 1: 170 series/framing/CLI/background tests passed, exit 0, with
  unchanged captured inputs (`local/series-framing/1792596003246821000-checkpoint1`).
- Checkpoint 2: three persistence/reuse tests passed, exit 0, with 33 deselected;
  two real processes contend over one raw digest, and pre/post-replace failures
  preserve settings or expose the actual visible digest/reload requirement
  (`1792596226316476000-checkpoint2`).
- Sampling oracles compare independent float64 ideal coordinates separately from
  effective Pillow float32 boxes. Six reduction/enlargement/singleton/strip-order
  fixtures measured contribution error <=0.001166732 RGB16 units against the
  declared 0.125 target, alpha error <=2.918983e-8 against 2e-6, and centre phase
  <=1.760276e-6 output pixels against 1/64. The independent coefficient-difference
  bound also passed. These are observed fixtures, not universal error guarantees
  (`1792595713935647000-task2-oracles-green`).
- Full-grid sampled backdrop comparisons, genuine negative filter lobes, hidden
  zero-alpha colours, bounded alpha quantization scratch, TIFF/PNG readbacks,
  selected/working/accepted separation, immutable reuse/failure preservation and
  fresh-process saved-only CLI replay are exercised by the retained application tests.
- Shipped-handler tests passed all four new series scenarios. Subsequent combined
  viewer/series/page regression passed 144 tests, exit 0, with unchanged inputs
  (`1792596908826041000-viewer-series-handler-regression`). Node DOM tests exercise
  shipped functions and controlled browser boundaries; they do not establish
  actual browser rendering, keyboard usability or file-picker behavior.
- A subsequent source-record identity regression failed before adding the exact
  source byte hash, then all ten selected series export/CLI tests passed
  (`1792597060481583000-series-source-record-green`). Add margins identities are
  unchanged by this series-only field.

All stems above refer to ignored local raw `.log`/`.json` pairs with exact commands,
exit status, timing and input hashes. They are local evaluation evidence, excluded
from distributions and Git. Inherited framing evidence below remains separately
labelled; its historical 699 passes/three optional cache skips are not new series proof.

### Independent review and actual browser observations

The fresh, read-only independent reviewer reported **No material improvements
recommended** on the unchanged 20-file candidate and 46 runtime/test/config inputs.
Their 48 additional numerical cases exited 0; maximum alpha error was
1.2200124044348115e-7 and contribution error 0.005682509865437169 RGB16 units.
This native review report adds source/numerical evidence; it supplies neither
photographic acceptance nor a universal numerical bound.

Root exercised the real Brave UI under production CSP with synthetic saved data:
selected `rev-004`, working `rev-005` and accepted `rev-003` remained distinct.
The selected unaccepted revision disabled the accepted-export button. Preview
showed 400×500 dimensions, bounds, 60-pixel side margins, approximately
216.02-pixel top/bottom clearance and 2.72× enlargement. Keyboard numeric/slider
linkage and literal Unicode/HTML-like names worked. Saving/reopening in a second
tab preserved the exact name and settings; a real file picker loaded a portable
preset into the unsaved form while retaining the saved photo snapshot.

The draft export used selected `rev-004` and 15% margins, including transparency.
The accepted export used selected `rev-003` and visible unsaved 15.1% margins.
Root read back both 400×500 deliveries: uint16 TIFF with non-257 samples, profiles,
PNG modes/partial alpha/zero RGB at zero alpha, member hashes and privacy checks
passed (exit 0). Their saved backgrounds were respectively `#16304B` and
`#203040`, rather than the working revision's `#291A35`. Acceptance did not change.
A competing tab save made the first tab's save visibly stale while retaining its
fields; explicit Reload recovered the actual second-tab snapshot. Dirty native
Add margins Left=7 survived mode/file/series actions and reload.

An apparent accessibility-tree slider value after file load was an inspection
cache artifact: actual keyboard movement proved the correct underlying value;
no behavior change was made. Changing settings during a large preview kept the
old response invalidated, but no artificially delayed real-network response was
forced. The original server process ended during interruption; restarting
preserved all 638 existing synthetic project/export file hashes. A browser
blocked-page warning was respected, and the user later opened the local round
fixture manually. Root then completed the remaining synthetic journey in Brave Private: a real
round-project file picker reused the shared preset (400×500, 15%) into an unsaved
form, preview/bounds showed 60/60/110/110-pixel margins and 4.75× enlargement, and
Save was explicit. Direct state inspection confirmed different masters and
independent saved snapshots: the long project retained `Second tab saved` at
16.3%, while round saved `Synthetic shared series` at 15%. Tall preview reported
135.34/135.34/25/25-pixel clearances, 5.17× enlargement and the height-limited
exception. Source-edge preview reported 60/60/66.25/66.25, 5.83× enlargement and
the captured-edge warning. Screenshots were visually inspected; the actual file
picker Cancel preserved the edge form and preview. The private browser console
showed only a pre-existing favicon HTTP 403, with no application JavaScript or CSP
errors visible. No security settings were changed.

This completes the observed synthetic browser journey with bounded claims:
there was no complete network trace, forced live out-of-order response injection,
actual download-to-disk assertion, full accessibility audit or human photographic
acceptance. Controlled handler tests cover forced response ordering, malformed
file cases and download bytes separately.

### Representative resource measurement

One synthetic 3000×2000 source was prepared through normal project, recorded-guide,
stub-matte, saved-background and series-save controls. No model download or real
inference ran. Separate fresh Python processes measured exactly one default
4000×5000 export (with RGBA8 variant) and its 1280×1600 reduced preview.

| Measurement | Export | Reduced preview |
| --- | ---: | ---: |
| Operation latency | 4.6506 seconds | 1.1047 seconds |
| Process peak RSS, macOS bytes | 750,387,200 | 638,976,000 |
| Canonical sampling estimate, bytes | 302,949,184 | 108,559,856 |
| Retained native foreground/alpha, bytes | 48,000,000 | 48,000,000 |
| RGB16 output buffer, bytes | 120,000,000 | 12,288,000 |
| Filtered alpha, bytes | 20,037,888 | 2,078,208 |
| Scalar intermediate, bytes | 16,960,320 | 5,448,080 |
| Strip transfer/native scratch, bytes | 13,750,016 | 12,300,032 |
| Coefficients, bytes | 183,808 | 133,984 |
| Row/allocator allowance, bytes | 84,017,152 | 28,311,552 |

The later RGBA8 variant is 80,000,000 bytes and is processed sequentially after
RGB16 release/readback; it is not added to the simultaneous RGB16 estimate.
Preview server initialization took another 0.1643 seconds. The estimate accounts
for sampling buffers and retained inputs; **it does not bound whole-process RAM**.
Measured process peaks include the surrounding validation/encoding/readback and
allocator lifetime. These one-run measurements do not cover supported extreme
sizes, guarantee available RAM or establish photographic quality.

Actual export admission observed 34,672,177,152 free bytes against the unchanged
10,737,418,240-byte reserve plus 1,114,097,152 pending bytes. The complete stage
immediately before publication and published five-member delivery each contained
120,674,213 logical bytes (120,692,736 allocated). No stage remained afterward;
all native project input hashes were unchanged. TIFF was 5000×4000×3 uint16 with
a 588-byte ICC profile. The reduced preview PNG was 125,455 bytes.

Raw export/preview log+input-hash JSON stems:
`1792603481515345000-representative-export-measurement-corrected-invocation` and
`1792603509379832000-representative-preview-measurement`; both exited 0 with
unchanged inputs. Detailed records are beneath ignored
`local/series-framing/1792603392951081000-resource-fixture/`.
The initial measurement harness invocation exited 1 before calling export because
it used an incorrect keyword; correcting it to the implemented
`framed_transparent` argument produced the sole completed export above.

### Settled application verification

Root's complete deterministic suite exited 0: **746 passed, 3 skipped**, with
unchanged captured inputs (195.55 seconds including command overhead; pytest
reported 194.85 seconds). All three skips require explicitly installed pinned
SAM/ViTMatte model caches; no assets were downloaded or real inference implied.
Raw stem: `1792603569077075000-final-full-suite`.

Full Ruff check exited 0 (`1792603764677463000-final-ruff`). Mypy exited 0 with
no issues in 20 source files, 17.20 seconds
(`1792603765088686000-final-mypy`). The first formatting check exited 1 for
one long raw-source-hash assertion in `tests/test_series_framing.py`; the other
41 files were formatted (`1792603764949617000-final-format`). Ruff changed only
that assertion's line wrapping; exact AST equivalence and the bounded diff are
recorded in `1792603842905889000-targeted-format-ast-proof` (exit 0; this intentional
format operation correctly records changed test bytes). Production source is
unchanged from the independently reviewed and fully tested candidate.

After formatting, the affected real export round-trip test passed (1 test,
exit 0), that file's Ruff check passed, and the complete format check passed
(42 files already formatted). Raw stems are
`1792603851042334000-formatted-source-record-roundtrip`,
`1792603851041054000-formatted-series-test-ruff` and
`1792603851041732000-final-format-after-bounded-fix`. Their input hashes remained
unchanged. The full suite/mypy were not repeated for an AST-equivalent test-only
format change; the record distinguishes their tested bytes from this final
formatting proof.

### Portable bytes and delivered-package privacy

The shipped download handler generated exactly 224 canonical UTF-8 bytes for a
Unicode/HTML-like preset name; the canonical Python parser accepted those bytes.
The Blob type, filename, URL release and absence of project-save posts passed.
This controlled DOM/transport check initiated no actual browser download and does
not claim a file landed on disk. Raw stem:
`1792603573783174000-shipped-download-bytes-canonical-parser` (exit 0).

An offline, dependency-free wheel build used the already installed build backend.
Its 27 actual members include the new renderer and UI, exclude plans/tests/local
evidence/VCS, contain no personal-path/local-evidence markers and retain exactly
the ten declared pinned dependencies. Wheel SHA-256:
`2f724cff0d49ca4985bfa4dc6917cc763fce0d113e11b370f496760913076814`.
Build/inspection exited 0; pip disclosed an unwritable user cache and disabled it.
Raw stem: `1792603610067323000-offline-wheel-inspection`. No installation or
download occurred. The actual representative delivery also passed five-member,
metadata/profile, path/privacy and file-hash inspection (exit 0), raw stem
`1792603639586263000-representative-delivery-privacy-inspection`.

## Framed export reuse cleanup — 2026-10-20

Identical framed exports now remove only the current attempt's byte-verified
duplicate stage after publication validation and successful parent-directory sync.
Published delivery bytes and identity remain unchanged. Failed validation or reuse
sync retains the duplicate; a cleanup failure separately reports successful
publication and the stage path, without implying that partially removed staging
files are intact. Earlier failed stages are preserved.

Five focused synthetic regressions cover repeat export with and without RGBA,
unchanged project/delivery bytes, preservation of earlier stages, a same-size
delivery mismatch, reuse parent-sync failure and partial cleanup failure. Against
the original writer they produced three expected failures and two passes;
after the repair all five passed. The complete default pytest suite then passed
699 tests with three optional real-model tests skipped because their explicitly
installed cache variables were unset. No tests were deselected from that full run.
Ruff lint, formatting and mypy checks passed. Captured source/test/configuration
hashes were unchanged during each verification command.

These checks used the selected source tree, synthetic saved projects and offline
settings. They establish the bounded filesystem lifecycle behavior; the historical
browser and image-readback evidence below remains applicable to unchanged UI and
raster behavior. No new real-model or human photographic acceptance is claimed.

## Actual browser journey and export readback — 2026-10-20

The orchestrator completed the synthetic journey in the user's already-loaded
private Brave window through native computer use. The browser extension had been
showing a different blocked normal-window tab; no browser security setting, Host,
Origin or capability guard, or CSP was changed. Observed client hints identify
Brave/Chromium 154 on macOS, not the exact installed build. The actual production
CSP matched the unchanged page script, and PNG framing previews decoded and drew
successfully. Two retained unmodified JPEG screenshots show the native canvas,
margin controls and framing preview within its sidebar fieldset.

Actual UI observations cover whole-pixel rejection/recovery, Set all sides,
Centre image, manual margins, native zoom and window resizing, stale revision/field
invalidation, and an older delayed preview arriving after the newer displayed
preview. Framing reset/reload/save/export preserved independent unsaved exposure,
fade, cleanup, shading and native-guide drafts before deliberate page reload.
A second tab's stale null-digest save was rejected with its fields retained;
Reload recovered the saved preset. The declared post-replacement directory-sync
fault left Left 17 visible, reported durability uncertainty, disabled Save and
required Reload. No successful fsync or rollback is claimed for that failed save.

A subsequent keyboard-only observation verified Tab/Shift-Tab traversal through
the labelled numeric fields, numeric editing, Space activation of Set all sides
and Reset, and Return activation of Centre image. These edits remained local to
the browser; saved data and code were unchanged.

After free disk exceeded the unchanged 10 GiB reserve, the browser exported
accepted rev-005 twice to the same destination and draft rev-006 separately, using
unsaved margins 9,7,4,5. Each resulting delivery has exactly five files and the
correct accepted/DRAFT label. Prepared readback of these actual browser-created
files passed (exit 0), followed by supplemental literal contract assertions
(exit 0). They verified both complete native RGB16 crops against independent
scalar fixture expectations, every outer backdrop pixel, native RGBA8 samples
and zero outer RGBA, full RGB8 quantization, exact geometry/member/hash sets,
master/revision/native-asset hashes, and 621 partial alpha samples per revision
including protected alpha16 value 26214. Export reuse was observed in the browser;
readback verifies one exact accepted delivery identity without re-exporting.

All ten export files and the raw saved 17,7,4,5 preset remained unchanged through
page reload and restore. Original capture absence and retained synthetic capture
identity were checked. Restore produced working/accepted rev-005, preserved the
four original state/source/recipe/guide files in recovery, and restored the saved
draft digest. The final native point at (17,23) remained an unsaved browser edit.
The readback left all 226 project files unchanged. Production and test bytes remain
identical to the canvas-selector candidate; only this evidence account changed.
No backend/model/full-suite check was repeated.

Current native rev-005/rev-006 image requests returned 200. The earlier generic
404 header was retained error text; its exact historical failing request remains
unknown. The bounded post-reload console observation showed favicon.ico 403 and
no CSP violation; it is not a complete browser-history or security audit. Keyboard
and UI observations are not full accessibility certification, real-model evidence,
maximum-size performance proof or human photographic acceptance. The actual J1
sequence and owner readback are recorded. All three independent result scopes,
affected renewals and final gate reconciliation are complete. The final verification
review concluded: “No material improvements recommended.” The synthetic Q9/J1
verification gap is closed.

## Native canvas layout repair — 2026-10-20

A user-provided screenshot and DOM inspection identified the initial framing
canvas covering the page with a dark layer. The existing global `canvas` rule
positioned it absolutely at the page origin, with full width and its initial 1:1
aspect ratio. That rule was originally written for the single native authoring
canvas inside the positioned viewport.

The correction scopes that unchanged positioning rule to `#canvas`. The framing
canvas now uses its existing normal-flow sizing; the shared canvas focus style
remains. No JavaScript, request/security behavior, bitmap ownership, native-coordinate
logic or persisted data changed. Exact byte correspondence and the frozen narrow
delta record the one-selector production change; static checks do not establish
browser rendering.

The actual browser observations above establish visible initial/preview layout,
working controls after resizing and native-coordinate authoring on this repair.
Node tests use stubbed geometry and cannot prove browser layout. Backend/model/full-suite
checks were not repeated; their results remain historical evidence for unchanged
behavior. The affected independent verification review is complete with no material
improvements recommended.

## Reduced framing-preview verification repair — 2026-10-20

Independent verification review found a test gap: the prior literal pixel oracle
used 1:1 output, while the reduced-preview checks asserted dimensions and allocation
bounds. No production sampling defect was observed. A new nonsquare asymmetric
case reduces a 6×5 virtual canvas to 4×3 and lists every expected RGB8 sample
independently, including two native-image pixels and ten saved-backdrop pixels.

Two isolated test-owned copies of the renderer change only the x or y sampling
offset from pixel centres to pixel edges. Each produced the intended pixel-assertion
failure (exit 1). The unchanged production renderer passed the new oracle and the
existing bounded-preview check (2 passes, exit 0). Production files were never
rewritten for the RED witnesses. Changed-input lint/format checks passed.

The 693-pass full run below remains the actual historical full-suite result; the
augmented suite was not rerun and no aggregate count is claimed. Exact source
hashes and AST correspondence establish that production and all pre-existing test
bodies are unchanged. Only the new reduced-preview oracle and this evidence account
were added. Unchanged Pillow, resource and model evidence was not rerun. The affected
verification reviewer subsequently closed this test gap. Later actual-browser Q9/J1
evidence above has also completed its affected verification review.

## Saved framing controls candidate — 2026-10-20

The renewed coherent deterministic suite passed **693 tests**, with three explicit
missing-model-cache skips, in 175.11 seconds (exit 0). All source/test/dependency
inputs stayed unchanged during that run. Final Ruff lint and format checks passed
(51 files); mypy passed for 19 source files. After the suite, one blank import
separator in a test was corrected for Ruff; its Python AST is identical and the
tested body plus both hashes are retained. Application code stayed unchanged until
the later CSS-only native canvas layout repair described above.

New behavior checks cover optional source-bound preset absence and validation,
foreign/corrupt/symlink preservation, two actual processes exercising the canonical
writer lock and raw-byte CAS, and failures at temporary creation, file sync,
replacement and directory sync. Real HTTP tests obtain the preview identity from
actual snapshot entries and exercise PNG transport, authentication/origin/body
bounds, stale enabled effects, raw-manifest changes, nonblocking render contention,
disconnect release and recovery. Shipped-page Node scenarios cover independent
forms, local reset/reload, explicit exports, uncertainty recovery, native guide
coordinates, out-of-order responses, pending bitmap decoding and bitmap closure.

The first full run exposed four ordinary-polling regressions: an added snapshot
state-byte check rejected legitimate operation completion. The repair preserves
the existing action-first snapshot ordering and permits pointer progress while
retaining source and exact consumed-manifest checks. All 37 affected tests passed,
including deterministic completion ordering and source/manifest replacement
counter-tests, before the renewed full suite. Assertions were not weakened.

A real HTTP preview of a virtual 10000×10000 canvas from a saved 96×72 synthetic
source returned a 1600×1600 RGB8 PNG in 0.091 seconds. Process peak RSS was
85,917,696 bytes, compared with a pre-request high-water mark of 66,879,488 bytes;
the PNG was 11,821 bytes and every project file hash remained unchanged. Allocation
instrumentation separately checks that preview sampling does not allocate the
expanded full canvas. This is one bounded observation, not maximum native-image
performance proof. This resource observation predates the snapshot-polling
compatibility repair; the measured preview-rendering path was unchanged. It is
not a new whole-process measurement of the repaired snapshot or a maximum-size claim.

The combined synthetic browser fixture includes boundary-reaching legs, 621
partial samples, a protected alpha16 sample of 26214 and saved nonuniform
backdrops. Its original synthetic capture is retained away from its original path;
saved-only reopening succeeds. A separate copy completed nine real HTTP journey
events: snapshot-derived preview, save, stale CAS rejection, post-replacement sync
uncertainty, accepted export and identical reuse, explicit draft export, restore
and fresh-server preview. Independent decoded readback compared both deliveries'
entire native RGB16 crops to scalar composition, every outer pixel to saved backdrop
edges, native RGBA8 samples and zero outer RGBA, exact member/hash sets and raw
revision identities. Source preset and accepted pointer survived restore, saved
native assets and prior deliveries stayed unchanged, and the pending browser
fixture's hashes remained unchanged.

Initial browser navigation was blocked by Brave (`ERR_BLOCKED_BY_CLIENT`); the
in-app browser was unavailable. The local HTTP page returned 200 with the expected
CSP, but no application UI action or security change occurred. This establishes
neither browser rendering under CSP nor keyboard/canvas behavior. The later actual
browser journey above supplies those observations separately. Node/HTTP checks do
not substitute for browser evidence, independent result review, human photographic
acceptance or real model inference.

## Framed presentation candidate — 2026-10-20

The settled deterministic suite passed **663 tests**, with three explicit
missing-model-cache skips, in 157.05 seconds (exit 0). Ruff lint and format checks
passed for 40 files; mypy passed for 19 source files. The isolated environment's
dependency check passed. Tests selected this checkout's `src`, removed the two
explicit model-cache environment variables and set Hugging Face/Transformers
offline flags. All 44 recorded source/test/dependency input hashes remained
unchanged during the full run.

New application checks cover literal asymmetric geometry; strict integer, shape
and output limits; non-257 RGB16 samples; an independent scalar composition oracle;
nonempty protected partial/opaque pixels; saved cleanup/exposure/fade/shading once;
TIFF/PNG/profile readback; zero RGBA margins; native export compatibility and
explicit draft labels. Actual CLI processes exercise saved-only replay after the
original capture is moved away, busy locks and invalid requests. Fault checks
cover initial semantic/raw-byte correspondence, changes during rendering, stale
enabled effects, low disk, corrupt raster readback, unexpected delivery members,
symlinks, and failures before rename or during parent sync. Prior work is preserved.
The initial framing tests failed for the absent module/API before implementation.

Independent review identified a retained RGBA render buffer. Two added regressions
failed before the repair, then passed: the real NumPy buffer is released before PNG
readback, and a save failure closes the real Pillow image while preserving prior
exports and accepted state. The transparent image now closes explicitly in
`finally`, including on save failure. The focused framing/CLI suite passed 69 tests.

A synthetic 6×4 source with 1024-pixel margins produced a 2054×2052 canvas
(4,214,808 pixels), including the transparent variant. The warmed repair probe
took 0.230 seconds and wrote 25,327,364 bytes. Process peak RSS was 107,167,744
bytes, a 42,385,408-byte high-water increase. Row-based PNG readback replaced
expanded NumPy readback copies after an earlier probe measured a larger peak.
The renewed peak matches the probe before explicit RGBA closure; the lifetime
regression establishes release at the readback boundary without claiming a lower peak.
The disk-admission estimate for this case was 69,537,248 bytes; it is distinct
from RAM use. These observations do not establish maximum-size performance or
isolate every allocator.

This is synthetic/local implementation evidence. Independent result reviews,
human framing/photographic acceptance, browser framing controls and real model
inference are not established by these checks.

## Pillow compatibility prerequisite — 2026-10-20

Pillow 12.3.0 created two tiny synthetic saved projects, one with the legacy black
background and one with a saved backdrop. A fresh process using the isolated
Pillow 13.0.0 environment reopened those projects and reproduced their exact saved
native pixels, PNG samples, default export member bytes and identical-delivery
reuse. Both comparison commands exited 0. The normalized sRGB profile stayed
588 bytes with SHA-256
`6f6fe5cc53cd24ceeb7997fb24ce2889fdfb88d88ce4fdc5f8e25e0481294953`.
All application imports explicitly selected this checkout's `src`.

The regression suite retains that profile identity and exercises harmless 8×6
animated PNG rejection with each disposal method. No hostile allocation probe,
private capture, model inference or human photographic acceptance is claimed.
Dependency and upstream-fix provenance is recorded in
[model-provenance.md](model-provenance.md#pillow-maintenance-update--2026-10-20).

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
verify actual pad/unpad/normalization/device/attention. Native 1024 evidence and
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

An earlier full deterministic run passed 227 tests (three unchanged model integration
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

An intermediate repaired full deterministic suite passed 233 tests (three unchanged integrations
deselected). Changed page/test formatting and lint passed; the six affected tests
passed after a test-only import-spacing correction. Python source/type inputs
are byte-identical to the successful mypy run. Actual browser export retained
a new unsaved guide; a real CLI restore followed by page reload cleared both review
checkboxes, selected the current revision and rejected acceptance without a new
confirmation. Long recovery controls fit 1,000- and 800-pixel desktop widths;
accepted export hashes stayed exact. No model inference was repeated for these frontend repairs. Human acceptance obligations remain pending.

The final review-window candidate added two dispatch-guard regressions, bringing
that page-test set to eight. A delayed save POST blocks guide/group authoring even
when an idle state poll arrives; a rejected POST releases controls while preserving
unsaved edits and allowing subsequent authoring. Both failed before their repair.
That final candidate passed **235 deterministic tests**, with three unchanged model
integration tests deselected; lint, formatting and type evidence passed as recorded
above. The earlier 227- and 233-test runs remain historical evidence, rather than
counts for the same final candidate. The subsequent review fixes below have their
own verification counts.


### Review-window recovery and polling corrections

The subsequent deterministic suite passed **247 tests**, with three unchanged
model integration tests deselected. Twelve added cases cover damaged/missing
pending-authoring records and explicit recovery, request-local validation reuse,
changed-asset rejection, serialized polling and recovery after a failed poll.
Nine cases failed before the fixes; the three corruption-rejection controls already
passed and protect integrity while introducing reuse. The page suite now has ten
behavioral tests. One lint-only conditional simplification and a timer guard that
skips pending reads were then checked with the affected page and validation tests;
final lint, Python/UI formatting and type checks passed. No inference or browser
walkthrough was repeated for these fixes.

A warm-cache snapshot of one synthetic 6,000×4,000 RGB16 project took about 0.50 s
and decoded the master three times before the change; one subsequent snapshot
took about 0.17 s and decoded it once. These single local observations are not
full-photo processing benchmarks. Immutable validation is reused only within one
read request, checking file identity, size, modification/change times, metadata
and manifests. The next request revalidates bytes; mutable drafts and write/approval
paths retain their checks. Memory retains at most one master and 128 revision
validation entries per request, and is released at its end. No persistent pixel
cache or weaker accepted-data contract was introduced.

Damaged pending authoring is reported in a readable page; explicit draft-replacing
restore preserves the raw pointer in recovery and retires unreadable authoring.
It does not silently approve, reconstruct or delete missing data. Historical real
backend, geometry and human acceptance limits above remain unchanged. The
[numbered offline use check](workflow.md#numbered-offline-use-check) is an instruction
for the user, not an observed human acceptance result.

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


## Shadow fade verification

The settled deterministic suite passed **511 tests**, with **3 optional real-model
checks skipped**; Ruff lint/format and mypy passed. New tests cover the independent
scalar gain oracle, exact excluded/partial-alpha behavior, default-OFF optional
recipe combinations, present-null rejection, immutable/warm validation, replaced-area scope, upstream
recomputation, partial RGB locks through prepare/matte/repair, stale blocking,
writer/input races, low space and orphan recovery. A fresh process with the original
locator unavailable and network/inference boundaries forbidden reproduced saved
selected RGB and export. Exposure clipping stayed 1/1 on a full-white +2 EV pixel
under full fade. The preexisting encoded shading/alpha equation remains unchanged.
These checks do not exercise real model inference or establish photo quality.

A 1024×768 arithmetic RGB16 project using an explicit matting test double exercised
real fade save/export. The measured process peak RSS was **372,326,400 bytes**;
project files totaled **53,011,122 bytes** after its first export. The setup,
stub-matte, exposure, fade and export sequence took **2.50 seconds** on the test
host. These are one synthetic run's values, not full-photo throughput targets or
OS memory-pressure evidence. The existing reserve plus conservative pending-write
estimate remains required.

In the actual loopback browser, numeric and pointer rectangle authoring, native
softness, explicit partial-alpha protection, saved area replacement, amount/highlight
changes with a dirty area, exclusive fade-OFF/exposure-OFF, reset, reload, labelled
draft export and keyboard focus were observed. Dirty geometry survived amount/reset
and export; reload loaded saved geometry. A real second process holding the project
lock displayed busy state. An old viewed revision rejected adjustment; reload
recovered the working view. A candidate authorization rejection was resolved by
explicitly enabling candidate comparison. Automated page checks separately cover
brush coordinates, transition guards and saved/prepared state.

This is synthetic computational and browser evidence. It does not establish WCAG
conformance, disconnected-network human operation, a representative flower result,
human photographic preference or regular-use acceptance. Those remain separate
manual observations and decisions. No new model, dependency or download was needed.

## Background appearance verification

The complete deterministic suite passed **554 tests**, with **3 optional real-model
checks skipped** because explicitly installed model-cache selections were absent.
The 43 background checks cover independent scalar native-field/composition
expectations, legacy absence/defaults, exact inheritance, saved-file corruption
including warm caches, combined foreground effects, alpha repair/stale gates,
writer exclusion, low space, pointer interruption, newer-draft races, native crops,
Result/black/transparent export roles, collision refusal and fresh-process saved-only
reconstruction. Ruff, formatting and mypy passed. These are computational and
stub-matte checks, not new inference or photographic evidence. One independent
review found pending cleanup/shading controls were reset by background completion;
a shipped-page regression reproduced the loss, then passed after extending the
existing preservation snapshot. The full suite above passed after that correction.

A synthetic 2048×1536 native background took 0.443 seconds to generate, produced
18,874,368 pixel bytes (18,875,184 bytes in its TIFF) and reached process peak RSS
108,724,224 bytes, including imports. This measures generation/write only; it does
not establish full-photograph workflow timing or memory requirements.

Direct local browser observations on a generated 360×240 synthetic project
covered the explicit warm default, uniform tone save, warm variation save, pure
black save at unchanged 55%, new saved revision feedback, preservation of an
unsaved fade rectangle plus exposure/fade values, and mutually exclusive comparison
controls. After explicit authorization, the retained generated project also passed
native browser warm-background save, keyboard slider/numeric synchronization,
stale-view refusal, real competing-writer busy/recovery, explicit reload, saved
revision restore and labelled draft export checks. Pending cleanup/shading support,
protection, geometry and opacity values also survived background completion. Restore
recovered the saved uniform tone/zero variation; reload discarded an unsaved black
choice and restored the saved warm settings. Both actual draft exports reconstructed
from saved layers, with the accepted pointer unchanged. Fit/native zoom and crop/full
image transitions were observed. No new code defect or model call was needed.
These direct observations complement the automated HTTP/transaction checks.
Accessibility certification, real photographic appearance/banding, the representative
offline-use pilot and human acceptance remain separate and pending.

## Optional source-development review

Source-development approval is no longer a prerequisite for preparation, trimap
review, matting/repair, explicit effects or final-photo acceptance. The saved
Boolean and optional legacy CLI/API remain compatible. New projects start ready;
older empty projects marked review-needed reopen without a state rewrite. The
[source-appearance workflow](workflow.md#source-appearance) preserves saved lighting
and colours and permits appearance changes only when explicitly requested.

The complete deterministic suite passed **752 tests**, with **3 optional real-model
checks skipped** because model caches were not selected for those checks. Ruff lint
and formatting passed (42 Python files); mypy passed (20 source files). Regression
checks exercise both new and legacy initial state through preparation, explicit
trimap review, actual known-core matting, requested background effects and explicit
final acceptance while development approval remains false. They verify exact
source/master preservation, unchanged foreground RGB and alpha under the requested
background effect, refusal before trimap confirmation, and no automatic final
acceptance. Invalid initial statuses fail without rewriting state. Shipped-page
JavaScript checks exercise preparation without the removed development control
and preserve unrelated appearance values without submitting an effects operation.
All 73 local documentation links in the changed maintained guidance resolved.

One independent read-only review covered the connected processing gates, saved
state, CLI/API, UI and regression protection; no material improvements were
recommended. This is deterministic and source-review evidence, not new model
inference, direct browser observation or photographic acceptance. An already
running local server must be reopened to load the changed Python workflow; retain
pending edits before closing its page.
