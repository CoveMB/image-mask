# Single-photo black-background workflow — incremental plan

Status: independently reviewed; ready for I01 executor preparation only. Created: 2026-10-16; updated: 2026-10-16.

<!-- substantive:start -->
## Purpose and context

Deliver beautiful black-background photographs using photographed detail, editable masks and targeted corrections, with optional reversible color cleanup and shading. One local processing path, one photo project and one small localhost viewer must remain useful without Codex, credits or internet after setup. Quality and real detail take priority over recurring effort; simplicity applies throughout.

**Primary authority:** [Single Photo Black Background Workflow Implementation Plan, version 4](../../../single-photo-black-background-implementation-plan-v4-2026-10-11.txt), dated 2026-10-11, inspected 2026-10-16; SHA-256 `2b41bad662f2ab364e0be8e4c834e554059d10acf668314c288a0c60cef81b76`. Sections 1–8 define the consolidated specification; sections 9–11 preserve acceptance, documentation and release obligations. Section 13 reports historical design reviews, not approval of this incremental candidate or new implementation authority. Source line locators below refer to these unchanged bytes.

**Supporting context:** the extracted `Photo-workflow-reference/` contains experimental scripts, metadata and limited fixtures. Its older contract clarifies provenance; it does not override v4. Read in full: README.txt, INPUT_OUTPUT_CONTRACT.txt, TECHNICAL_REFERENCE.txt, PORTING_CHECKLIST.txt, MODEL_REFERENCE.json and PACKAGE_AUDIT.json. Read-only inspection of `guided_mask_test/run_guided.py` and `guided_mask_test/spider_repair_v3/finalize_repair.py` confirms RGB8 processing, photo-specific repair geometry and fixed-output behavior. Do not execute those scripts unchanged. The separate older DOCX and original brief are historical, not competing specifications selected for this conversion.

Supporting SHA-256 identities, relative to `Photo-workflow-reference/`:

| File | SHA-256 |
| --- | --- |
| README.txt | `d4a8becba0b295944f61b0f5f035c8cd73bf0b3321303bfb159bb99b60f04454` |
| INPUT_OUTPUT_CONTRACT.txt | `d0c4160fe087c98ba56715a0cc9b1787bdb89d55122c83235cf6a59a43c64bcb` |
| TECHNICAL_REFERENCE.txt | `9748c058d36c4b02958731ab91572b18bf3748459d5b0df1e8a3add989ea9b6b` |
| PORTING_CHECKLIST.txt | `566e270d0284fa624396f703c90279aba105a213ab114f015d47413e7376c281` |
| MODEL_REFERENCE.json | `4b0ba958d92429ea22c8eb21ed61c9290cea7191225e976b9748784537355fb8` |
| PACKAGE_AUDIT.json | `1efa69874f0f76781e461584a0953dcaa42ba332fd53ae88b0da29565a5d922b` |

**Baseline:** selected root is `~/Code/CoveMB/image-mask` (the requested `CoveMb` spelling resolves to it on this host). On 2026-10-16 it contains the v4 TXT, an older DOCX, extracted reference material and Finder metadata. It has no application package, target AGENTS.md or Git repository; branch, base revision, staged and committed comparisons are therefore not applicable. Do not initialize Git as a planning step. Preserve all existing files. Hardware/OS/free-space figures in v4 are source-reported and require a live setup preflight; none was remeasured here.

No product code, installation, model download, inference, application test, live assisted evaluation or photo processing has been performed for this conversion. Every acceptance check below is proposed unless a planning-review record explicitly says otherwise.

## Global obligations

- **G1 — truthful photographic result:** preserve capture bytes, real geometry and source detail. No synthesis, inpainting, sharpening, invented hairs/web/anatomy or reconstruction of absent detail. Keep object membership separate from opacity. Mask-only RGB is the approved developed master; alpha changes its displayed composite.
- **G2 — small local product:** native ARM64 Python 3.12, one processing implementation shared by CLI/viewer/Codex, standard-library CLI/TOML reading/JSON/hashing/locking/localhost serving, plain local HTML/JavaScript. Use the source dependency set; no database, queue, scheduler, React/Electron, Docker, MCP server, cloud API integration, separate language/vision assistant, training frameworks or mandatory assistant access. Process pilot photos separately.
- **G3 — immutable authority:** one OS project lock serializes all writers from their introduction, including draft writes, processing, publication, accept and restore. Validate working revision/master/draft digest and snapshot referenced inputs; recheck hashes before publication. Reject stale/conflicting inputs without advancing state or overwriting guidance. `state.json` alone owns working/accepted revision pointers; development approval is separate. Temporary output, validated publication and atomic state updates must protect prior accepted work from the first candidate onward.
- **G4 — human gates:** every increment requires executor preparation, Gate 2 approval of its concrete plan and Gate 3 approval of its verified result. No bypass has been granted. These developer gates are separate from product development approval, trimap review and human visual acceptance of each photo. AI advice never accepts a photo. Obtain all three independent implementation review scopes and the architecture-owned simplicity substitute; Ponytail is not authorized.
- **G5 — authority and recovery:** this request authorizes planning artifacts only. Installation/downloads, implementation, live assisted evaluation, Git writes, external mutations and private-source transfer require their applicable separate direct authority. V4's cloud-photo permission is retained as source context, not treated as a new transfer command. Never automatically delete originals, accepted revisions or their dependencies. Recovery may retain failed candidates or verified cache; rollback, deletion and Git operations are not implicitly authorized.
- **G6 — verification and documentation:** material invariant tests precede corresponding behavior; use focused deterministic checks while changing and the full relevant suite once on the settled candidate. Keep tests, docs and safeguards with their owning behavior. Register integration markers when introduced. Distinguish stub orchestration tests, real inference/backend tests, manual viewer/photographic checks, live assistance and source-derived history. Static or arithmetic evidence cannot prove photographic, anatomical or artistic quality.
- **G7 — bounded storage and failure:** one environment/model cache, measured write estimates and the source's proposed 10 GiB reserve; recheck real free space before writes. Fail safely on corrupt/missing models, malformed input, low disk and non-finite/OOM/unsupported inference. Cache is rebuildable, never the sole accepted dependency. Statuses are needs_input, ready, running, review_needed, accepted and failed; a calculation normally ends review_needed.
- **G8 — exclusions and completion:** retain all v4 §11 exclusions: batch/video, training, general assistant/RAW editor, arbitrary high-bit-depth color conversion, generative editing, PSD/plugin exports, hosting/mobile, calibrated print production and guaranteed unseen-detail recovery. Optional appearance means optional use, not omission of the specified feature implementation. Regular-use readiness requires all increments plus real RAW, CPU/MPS disposition, photographic and assisted/offline/recovery gates. Stop after material findings and one focused correction check; no open-ended polish.

## Current documentation check

Official documentation was opened on 2026-10-16 using generic public URLs only. The check supports retaining the selected architecture; it does not select a working environment or prove Mac compatibility.

| Official source | Planning implication |
| --- | --- |
| [SAM2, Transformers 4.57.3](https://huggingface.co/docs/transformers/v4.57.3/en/model_doc/sam2) | Direct Sam2Model/Sam2Processor point/box inference remains documented. Use pinned image processors/configs; do not copy unrelated automatic/video examples. |
| [ViTMatte, Transformers 4.57.2](https://huggingface.co/docs/transformers/v4.57.2/en/model_doc/vitmatte) | Explicit model/image-processor route and padding settings remain documented. Record actual tensors and remove padding; documentation is not geometry test evidence. |
| [rawpy Params](https://letmaik.github.io/rawpy/api/rawpy.Params.html) | Gamma, bit depth and WB settings need explicit values; defaults do not reproduce the source's sRGB development recipe. |
| [Pillow concepts](https://pillow.readthedocs.io/en/stable/handbook/concepts.html) | RGB/RGBA modes do not provide a multichannel RGB16 precision route. Preserve TIFF color masters and grayscale16 masks; reject RGB16 PNG before lossy conversion. |
| [PyTorch MPS](https://docs.pytorch.org/docs/2.14/notes/mps.html) | Availability checks precede backend use. This documentation version does not mandate Torch 2.14 or prove either model works on MPS. |
| [Python 3.12 fcntl](https://docs.python.org/3.12/library/fcntl.html) | A nonblocking native file lock fits the source's single-project writer policy; test CLI/viewer contention and busy responses. |

At each increment's preparation, verify current official metadata/advisories for packages actually installed/configured, record versions/date/applicability, and reuse unchanged relevant evidence. Begin from Transformers 4.57.6/rawpy 0.27.1; resolve a matching native Torch/torchvision pair rather than inheriting Linux `+cpu` pins or upgrading just for novelty. Source-selected checkpoint revisions and hashes remain authoritative; an unsupported route returns for a material decision.

## Parts and increments

Parts organize reading; dependencies determine eligibility. Each card owns one feature contribution with its tests/docs. Exact future files/interfaces are source proposals until the executor checks the current target.

| Part / topic | Purpose | Ordered increments |
| --- | --- | --- |
| 1 — Trusted photo project | Establish a safe developed source | I01 — Trusted RGB16 master |
| 2 — Editable masking | Prepare, matte, repair and resume one photo | I02 — Reviewed selection and guides; I03 — Native mask and precise base exports; I04 — Replayable scoped repair; I05 — Interrupted-work recovery |
| 3 — Human and assisted review | Make the same engine usable manually and with Codex | I06 — Offline local review window; I07 — Bounded assisted defect loop |
| 4 — Reversible appearance | Add independent, optional appearance choices | I08 — Source-guided color cleanup; I09 — Protected inward shading |
| 5 — Regular-use evidence | Demonstrate the complete specified workflow | I10 — Representative acceptance pilot |

**Regrouping from source Tasks 1–6:** Task 1's image contract becomes I01; model-specific setup/smokes move beside first use in I02/I03. Task 2 becomes guide preparation and a complete matte result in I02/I03. Task 3's nonblocking project lock and safe initial master/draft/development-state writes start in I01; I02 extends those helpers to operation snapshots and revision publication. Its repair, resume and viewer contributions become I04–I06. Task 4 is I07. Task 5's base precision export is brought forward into I03, with cleanup and shading separately in I08/I09. Task 6 is I10, while behavior-specific docs/tests remain in every earlier card. This avoids a broad viewer/repair/recovery bundle and avoids leaving early masks without safe storage, real tests or usable exports.

The baseline route is I01 → I02 → I03 → I04 → I05 → I06 → I07 → I08 → I09 → I10. Dependencies below retain what is actually required; ordered delivery reduces simultaneous review load without claiming unrelated features are technically coupled.

## Source coverage

| Source locator (v4 lines) | Obligation | Owner | Disposition |
| --- | --- | --- | --- |
| Goal/architecture/stack, 7–15; globals, 17–29; §1, 41–58 | Quality-first one-photo local tool, recipe/guides/viewer, optional cloud and full offline use | G1/G2/G4/G5; I01–I10 | Preserved; historical approvals are not new execution authority |
| Review focus, 31–39 | Format/registration, stale requests, partial locks/core conflicts, native precision, failures/recovery | I01–I06; I10 | Explicit failure evidence with each owner |
| §2, 60–83; §12–13, 584–639 | Experimental provenance and missing originals; prior review limits | Global context; I02/I03/I04/I10 | Historical results not rerun or certified here |
| §3.1, 85–93 | Shared operations, small loopback viewer and single nonblocking writer | G2/G3; I01/I02/I06 | I01 protects first project/development writes; I02 extends operation transactions |
| §3.2, 95–113 | Exact two checkpoint pins/configs/hashes, safe local-only loading, coherent ARM64 packages | I01/I02/I03; I10 | No standalone research frameworks; BiRefNet conditional, not installed by default |
| §3.3, 115–121 | CPU float32; per-model MPS tests, same-geometry one-time auto fallback, explicit-MPS errors and cache invalidation | I02/I03/I05/I10 | No mixed-device matte or silent resolution reduction |
| §4.1, 123–144 | Signature, orientation, RGB16 TIFF/profile, RAW recipe/WB/crop, profile failure and master identity | I01; G1 | Real RAW proof remains I10 release gate |
| §4.2, 146–156 | Separate RGB8 model view; native top-left points/half-open boxes, saved crop/preview transforms | I01/I02/I03/I06/I07 | Transform checks follow each new input route |
| §4.3, 158–166 | Keep/opacity separation, selected SAM candidates, all typed guide roles and shared rasterizer | I02/I06/I07 | Viewer and assistant both generate assets without custom scripts |
| §4.3, 168–174 | Reviewed conservative cores, fragile unknowns/corridors, categorical labels and conflicts | I02/I03/I04 | Whole-image unknown is a slower fallback, not a quality claim |
| §4.3, 174–178 | Persistent same-master saved-value locks; native tiling/weights, finite alpha/quantization and known cores | I02/I03/I04 | All later operations inherit protection |
| §4.4, 180–188 | Context versus support, exact partial-alpha/RGB preservation, three ordered merge policies and saved-operand replay | I04 | Core/support and lock assertions precede publication |
| §4.4, 190–192 | Change-required cores at full support; stale effects, labelled base comparisons and bounded rebuild | I04/I08/I09 | Effect-dependent enforcement begins with each effect feature |
| §4.5, 194–202 | Optional source-based high-precision correction; separate assets, bounded heuristic, no repeated application | I08 | Off by default; 0.35 is a historical starting point |
| §4.6, 204–221 | Optional W16/p shading, explicit thin/highlight protection and exact single-alpha encoded-sRGB exports | I03/I09 | No second compositing mode; all viewing precision/baked effects labelled |
| §5.1, 223–239 | Source-based defect classification, same crops, two attempts total, early stops and human acceptance | I07; G1/G4 | No score/confidence optimization as proof of quality |
| §5.2, 241–261 | Entire planned command surface, four processing kinds and typed request identities | I01–I09 as introduced | No unsupported command may appear ready before its owning card |
| §5.2, 263–280 | Prepare returns paths/digest; repair consumes edits once; store request/result; reject invalid data | I02/I04/I07 | Example IDs/coordinates are illustrative only |
| §5.3, 282–286 | Full same-project offline operation and restart without conversation memory | I06/I07/I10 | Offline includes authoring and processing, not viewing alone |
| §6.1, 288–354 | Exact recipe/state/revision roles, immutable snapshots/master sharing, input recheck and provenance | I01/I02/I03; extended by I04/I08/I09 | Source path contract retained; no custom planner state system |
| §6.2, 356–368 | Minimal useful caches; complete keys/invalidation; saved reconstruction exact, inference not cross-device identical | I02/I03/I04/I05/I08/I09 | Unknown dependency is a miss |
| §6.3, 370–378 | Temporary publication, atomic accepted state, verified resume, clear statuses, disk reserve and preservation | G3/G7; I01–I06 | I01 safely writes initial master/draft/development state; I02 adds candidate publication; I05 adds resumable progress |
| Task 1, 384–397 | Source/precision/development tests, native preflight and per-model CPU/MPS smokes | I01/I02/I03 | Runtime after separate setup authority |
| Task 2, 399–413 | Guide/rasterizer/geometry/core tests plus spider/dragonfly model evidence | I02/I03 | Multi-pass reference finals are comparisons, not one-pass equivalence |
| Task 3, 415–431 | Partial locks, replay, stale/concurrent writes, viewer transforms/security, interrupted processing | I02–I06 | Controls/tests delivered with behavior |
| Task 4, 433–446 | Operating contract, reusable review exports, invalid AI proposals, live repair and fallback | I07 | Live assisted evaluation has separate authority/evidence |
| Task 5, 448–462 | Effect identity, stale combined effects, exact precision, labelled 0/12/24 comparison and optional GIF | I03/I08/I09 | GIF only on request; no precision claim |
| Task 6, 464–477 | Synthetic/real E2E, real RAW, performance, fresh-session docs and final material review | I10; G6 | Final review assesses the full implemented workflow once |
| §8, 479–501 | Complete spider sequence, offline new guides/lock, recovery and model-free replay/export | I01–I10; I10 owns integrated proof | Do not manufacture a photographic defect; correctly bind archived before-mask if needed |
| §9 matrix, 503–527 | All 21 end-to-end acceptance rows | Table below | Every row has evidence owner; none declared passed |
| §9 pilot, 529–536 | Three separate subjects plus tiny synthetic fixtures and an actual local RAW | I03/I09/I10 | Missing dahlia source cannot count as a fresh full-source run |
| §10, 538–551 | Actionable synchronized setup/workflow/assistant/contract/validation/troubleshooting/provenance/notices and per-photo docs | Each behavior; I10 integrated walkthrough | No documentation platform or prose-matching tests |
| §11, 553–582 | Estimates versus measurements, resource limits, release conditions/exclusions and bounded review | G7/G8; I05/I10 | 4–8 core + 1–3 appearance days and 5–10 GB are source allowances, not measured commitments |

### End-to-end evidence ownership

These are v4 §9's acceptance rows, grouped only for navigation. I10 reconciles actual evidence from every owner and repeats integration only where necessary.

| Acceptance row | Owning card(s) |
| --- | --- |
| Source integrity; RGB precision; input/orientation; WB/profile failure | I01 (RGB mask-only/export extension I03) |
| Real model geometry; opaque/background cores; transparency/web; tile boundaries | I02/I03, with native photographic sign-off I10 |
| Conflicting guidance; local repair and full rerun; repair replay | I02/I03/I04 |
| Stale/concurrent input | I01 initial-writer protection; I02 operation snapshots plus every new writer I04/I05/I06 |
| Bounded AI loop; AI defect pilot | I07 |
| Optional effects; alpha/opacity arithmetic; export precision | I03/I08/I09; combined-effects repair I09 |
| Cache use | I02/I03/I04/I05/I08/I09 |
| Interrupted/low-disk run | I01 initial-write safety; I02/I03 processing fail safety; I05 resumability; I06 viewer contention |
| No-credit/offline flow; documentation walkthrough | I06/I07; fresh complete walkthrough I10 |

## Increment cards

### I01 — Trusted RGB16 master

- **Outcome and scope:** a single-photo project can safely ingest an input, preserve capture bytes and create/reopen an identity-bound RGB16 sRGB TIFF master for explicit development review. Include typed recipe defaults, shared-master storage, source metadata and the nonblocking project lock protecting all initial project/master/draft/development-approval writes. Add Python/package preflight and a download-free `doctor`; document explicit setup separately.
- **Exclusions:** no model download/inference, segmentation, viewer, effects or final-photo acceptance. Do not claim full RAW support from synthetic or developed fixtures.
- **Prerequisites / predecessor:** none implemented. Before setup choose source/project folders and the actual local RAW pilot with the user; obtain setup authority. Confirm hardware, OS, native Python, free disk and coherent dependency metadata. Preserve reference files.
- **Owning areas / interfaces:** source Task 1's pyproject.toml, requirements-macos-arm64.lock, ingest.py, project.py and create_project/load_master contracts; CLI open/doctor/development acceptance as locally available. I01 owns shared locking and safe initial master/draft/development-state writes, including atomic approval-state updates; I02 extends these helpers rather than introducing a second writer path. Exact package layout is provisional. Update README setup and supported-input sections, file contract, provenance/notices and per-photo README with this behavior.
- **Human review focus:** every authoritative RGB sample, orientation and identity can be traced to the approved development; no output targets the capture path. Distinguish RGB8-derived TIFF from captured 16-bit information.
- **Safe intermediate state / compatibility:** inspect/reopen a master without masking. Invalid development remains needs_input. Apply orientation once. Master changes invalidate aligned guides/masks; equal dimensions never establish registration. Initial immutable master writes, atomic draft/development-state updates and disk checks preserve existing material; every writer acquires the same nonblocking project lock, and a second writer receives busy. No incomplete master is recorded as approved.
- **Acceptance / verification:** source-byte hashes before/after; signature/extension mismatch and rotated non-square input; JPEG/PNG8, RAW/DNG and uncompressed supported sRGB RGB16 TIFF paths; reject RGB16 PNG before conversion, unsupported compression/profiles and malformed recipes/unknown keys. A non-257-step ramp survives lossless TIFF reload. Test two processes competing to create/update the same project and approve development: only the lock holder writes, the loser reports busy, and interruption/low disk during initial writes cannot publish incomplete masters or approval state. Missing profiles require a recorded assumption/corrected input. Invalid camera WB stops for daylight preview or trusted developed TIFF and human review. RAW uses explicit full-size AHD/WB/brightness/gamma=(2.4,12.92), no extra sharpening/noise reduction; retain historical daylight/crop and spider recipes as provenance, not universal settings. Proposed source check: `pytest tests/test_ingest.py tests/test_project.py`; real local RAW remains a required I10 gate.
- **Recovery:** keep original/master identities and diagnostics; correct the input/development in a new master, without replacing prior masters or inferring downstream registration.
- **Gates / review scope:** G4, plus setup permission and product development approval before any masking; all three reviews inspect ingest/precision/preservation and failure evidence.
- **Future impact:** I02/I03 depend on approved master identity, RGB8 proxy and native coordinate metadata. Any changed development contract returns for reconciliation before dependent work.

### I02 — Reviewed selection and guides

- **Outcome and scope:** `prepare` turns one approved master plus typed groups/guides into saved SAM candidates, a selected subject definition and a reviewable categorical trimap/support/protection set. Author all source guide roles through one shared rectangle/stroke rasterizer; return actual generated paths, revision/master and draft digest.
- **Exclusions:** no matte, final acceptance, viewer or prose execution. Preparation of repair guides carries existing alpha forward exactly and cannot become an accepted final result.
- **Prerequisites / predecessor:** accepted I01 result and photo development approval. Explicitly authorized setup/download of pinned SAM2.1 and configs; verify SHA-256 against v4 §3.2 and MODEL_REFERENCE.json before first session use. The planned two-model environment must be coherent; confirm ViTMatte compatibility metadata without claiming its runtime validation yet.
- **Owning areas / interfaces:** models.py/guidance.py select_candidates/rasterize_regions/build_trimap, shared `apply_operation`, `blackmask run --request`, typed recipe/guides and project transaction helpers. Extend I01's shared lock and safe state writes to G3 operation snapshots, input recheck, immutable parent revisions, safe atomic publication and authoritative working/accepted pointers. This extension protects the first prepared candidate. Update request/file-contract and guide docs alongside behavior.
- **Human review focus:** selected membership never forces translucency opaque; negative SAM hints are not certified background. Categorical 0/128/255 guides, native points/half-open boxes, widths/radii, stable IDs and full-master support/locks are inspectable and source-backed. Unknown corridors locate evidence; they do not paint strands.
- **Safe intermediate state / compatibility:** saved preparation can be reviewed/revised without changing parent alpha or accepted work. Same-master locks bind saved alpha/applicable RGB and persist until an explicit recorded removal; acceptance does not lock the whole photo. Reject core/lock contradictions before model processing/publication.
- **Acceptance / verification:** role-specific rectangle/stroke rasterization; categorical labels without antialiasing, correct dimensions and scope clipping, full-strength support interior/optional inward feather including zero. Test nonempty cores, fragile unknowns, whole-image-unknown fallback and contradictory assertions. Test old revision/master/digest, referenced-file snapshots, mid-run text edits and competing writers; preparation stays nonaccepting. CPU float32 SAM smoke records actual processor tensors, normalization, device/attention and pins; test MPS separately before defaults. Auto retries one failed stage on CPU with unchanged geometry; explicit MPS fails visibly. Missing/corrupt model has no hidden download. Proposed check: relevant `tests/test_guidance.py` plus project/operation invariants introduced here and real SAM smoke; stub tests are labelled.
- **Recovery:** retain previous working/accepted state on validation or inference failure; revise typed guides and submit against newly returned current identities. Never shrink locks or widen scope silently.
- **Gates / review scope:** G4; authorized model setup and human trimap review before I03. Three reviews cover source roles, one shared rasterizer, writer safety and preparation-only status.
- **Future impact:** I03/I04 consume these exact assets; I06/I07 must call this owner rather than implement a second guide interpretation. Changes to identities/rasterization reopen affected contracts and reviews.

### I03 — Native mask and precise base exports

- **Outcome and scope:** a reviewed preparation produces an editable native-pixel alpha16 and complete mask-only result: saved layers, basic same-crop review assets, human acceptance and exact RGB16 black/labelled PNG8 exports through the CLI. Include protection on full reruns from first delivery.
- **Exclusions:** no local repair, viewer, color cleanup or shading. Effects remain disabled; do not claim RGB8 model inputs are RGB16 inference or final-sized SAM output is native inference.
- **Prerequisites / predecessor:** accepted I02; approved master and reviewed trimap. Authorize/download verified pinned ViTMatte/configs and complete the coherent ARM64 environment lock, transitive versions and installed LibRaw record. No separate research frameworks.
- **Owning areas / interfaces:** models.py/matte.py infer_matte, `matte` kind; basic review.py/export.py and revision manifests; accept-revision/export CLI. Introducing minimal exact base rendering here makes this a usable masking outcome. Update file/precision/CLI docs and model provenance now.
- **Human review focus:** RGB16 master is foreground; RGB8 proxy only feeds models/review. Initial tiles are native 1024, nominal overlap 256/stride 768 with appended boundary origin, recorded processor padding and sine-squared weights. Saved-value protection overrides permitted predictions without concealing contradictory cores.
- **Safe intermediate state / compatibility:** immutable review_needed candidate with previous accepted result intact; no prepared-only/incomplete result may be accepted. Known cores are exact, locks preserve partial alpha and applicable RGB on every full rerun. Export defaults to accepted revision; explicit draft export is labelled and never replaces an earlier export. Reuse identical files; reject collisions with different content.
- **Acceptance / verification:** tile coverage on sub-tile/exact/odd/boundary dimensions; padding rather than hidden resize; positive accumulated weights; no-unknown-tile bypass; malformed trimap/non-finite/OOM failures, exact nonempty cores, mixed alpha and one quantization to PNG16. CPU float32 ViTMatte smoke plus per-model MPS comparison; one same-geometry auto fallback discards mixed-device matte tile cache, explicit MPS reports failure. Cache keys include master/crop/trimap/model/config/packages/backend/dtype/geometry/preprocessing; unknown dependencies miss. Saved-base RGB16 black output equals ties-to-even float64 `round(F * (alpha16/65535))`; alpha applied once; no mask gamma/ICC conversion; PNG8/RGBA8 convenience precision and straight RGB labelled. Test atomic failure/low disk and source/pixel preservation using real reloads. Proposed source checks: `tests/test_matte.py`, relevant `tests/test_export.py` and guidance/project tests; real spider/dragonfly inference and sensitive native crops must be recorded separately. A single pass need not equal historical multi-pass finals.
- **Recovery:** leave accepted files usable on failure; retain verified work without publishing incomplete output. Reopen the preserved accepted revision; resumable interruption is added in I05.
- **Gates / review scope:** G4, real-model/backend evidence and human native photographic inspection on black/gray/white/checkerboard as appropriate before product acceptance. Scores/disagreement are diagnostics, not calibrated confidence or seam proof.
- **Future impact:** I04 needs immutable parent alpha and canonical master; I08/I09 extend this one renderer, never use flattened output as foreground. Review crop mapping must remain the same contract used by I06/I07.

### I04 — Replayable scoped repair

- **Outcome and scope:** a `repair` operation improves one source-supported region while proving exact preservation elsewhere, and can replay that merge without a model/cache. Add restore of an existing revision and its draft without changing final acceptance.
- **Exclusions:** no effects, viewer or autonomous defect detection; no implicit broad scope, destructive restoration or acceptance. Do not execute reference repair scripts.
- **Prerequisites / predecessor:** accepted I03; a current same-master parent, explicit requested defect/context/write scope, reviewed cores and revision-bound locks. Use I02 `prepare` for edited guides; repair consumes returned identities/support once, omitting already-applied guide_edits_file.
- **Owning areas / interfaces:** repair.py/apply_operation, immutable repair operands and restore command through existing lock/transaction helpers; tests/test_repair.py and recovery/operation contracts; repair/replay/file-contract docs.
- **Human review focus:** distinguish read context from write support. Reload immutable local candidate alpha16 and support16. For P parent and C candidate, D is C/max(P,C)/min(P,C) for replace/increase-only/decrease-only; calculate ties-to-even float64 `round(P*(1-w)+D*w)`, w=support16/65535, then copy protected samples exactly. Store parent, crop mapping, ordered operations and explicit directional rationale.
- **Safe intermediate state / compatibility:** outside support and inside persistent locks, all alpha and applicable foreground RGB remain bit-exact, including soft wings/web. Replace is default. Reject contradictory guides, needed core changes where support is not 65535 and direction policies incompatible with erasure/increase; do not apply one layer last to hide conflict. Validate all cores after merge. Accepted pointer remains untouched by processing/restore.
- **Acceptance / verification:** nonempty soft-alpha/protected/opaque test sets; zero/full/feather support, all three policies, contradictory cores and narrow write scope with larger context. Real file reload/crop mapping round trips and exact model-free/cache-free replay from saved operands; full rerun after repair retains locks. Stale guide/crop/master/digest, attempted lock shrink and mid-run edit fail safely; restore loads exact saved draft/head while preserving accepted_revision. Proposed checks: `pytest tests/test_repair.py tests/test_recovery.py tests/test_coordinates.py` as applicable to delivered behavior; replay tests must assert zero model calls. Photographic gap comparisons use correctly bound source/before-mask, never fabricated defects.
- **Recovery:** retain valid parent and candidate operands; explicitly select a prior working revision. Restoring accepted state itself requires explicit human acceptance, not restore alone.
- **Gates / review scope:** G4 plus source-supported scope/trimap decisions and human photo acceptance. All three reviews examine arithmetic, nonvacuous partial-value preservation and replay applicability.
- **Future impact:** I08/I09 must mark dependent effects stale after alpha repair and scope their rebuilds. No enabled effect exists in this intermediate release; introducing each effect carries that safeguard with it.

### I05 — Interrupted-work recovery

- **Outcome and scope:** `resume` safely continues a saved interrupted single-photo operation from verified completed stages/tiles, avoiding needless repeated full inference while leaving accepted work available.
- **Exclusions:** no queue, scheduler, worker service, automatic accepted-data cleanup or new processing path. Earlier fail-safe publication is retained, not postponed here.
- **Prerequisites / predecessor:** accepted I03/I04; their lock, immutable snapshots, complete cache keys and fail-safe temporary publication already work. No incomplete accepted state is tolerated before this card.
- **Owning areas / interfaces:** existing project/model/matte/repair transaction and cache owners; resume CLI, tests/test_recovery.py and troubleshooting/storage docs. Inspect exact owners before choosing files.
- **Human review focus:** resume only the saved input snapshot if current identity/digest still corresponds. Completed files/stages/tiles need hashes and validation; unknown, incomplete or invalidated data is not reusable. Device changes invalidate the whole fresh matte's tile cache.
- **Safe intermediate state / compatibility:** failure remains visible and previous acceptance/export stays unchanged. Project lock rejects a second writer with busy while reads remain possible. Missing models, moved source path and low disk produce actionable recovery; locate moved captures by recorded hash rather than filename alone.
- **Acceptance / verification:** inject interruption between output writes, publication/state updates and tile completion; restart in a fresh process and resume only valid work. Edit recipe/guides/referenced support while paused and during execution; reject stale publication/resume without clobbering edits. Measure call counts proving reuse of unrelated verified tiles, complete invalidation on master/backend changes and no mixed-device matte. Test reserve plus estimated pending writes before work, not only a fixed byte threshold. Cache cleanup in disposable tests cannot remove accepted dependencies. Proposed source check: `pytest tests/test_recovery.py` with project/operation integration and a recorded manual interrupted real-model run.
- **Recovery:** ignore incomplete temporary files or retain diagnostics; user can restart from preserved state when resume is invalid. Deleting originals/revisions and broad cleanup remain outside authority.
- **Gates / review scope:** G4; fault-injection/static tests are distinct from actual interrupted real-model/resume evidence.
- **Future impact:** I06 must expose these statuses/resume semantics without blocking reading. I10 measures saved work, disk growth and practical recovery on this Mac.

### I06 — Offline local review window

- **Outcome and scope:** one loopback page lets a person perform the complete current mask/repair/recovery workflow without Codex, credits, prebuilt support files, external editing or custom scripts.
- **Exclusions:** no natural-language understanding, accounts, hosted frontend, extra framework or second engine. Effect controls arrive with their behavior in I08/I09; do not expose working-looking placeholders.
- **Prerequisites / predecessor:** accepted I02–I05, including review assets and shared operations; I01 development approval remains separate from final-photo acceptance.
- **Owning areas / interfaces:** source viewer.py, ui/review.html, cli.py, shared review/transaction/guidance owners and tests/test_coordinates.py. Add open/reopen integration and short manual workflow docs.
- **Human review focus:** native source/result toggle, pan/zoom, black/gray/white backgrounds; group points/boxes/coarse strokes and every role selector; trimap/support/lock previews, revision-bound create/remove locks, context/write scope, run/resume/accept/restore. Invert pan/zoom/letterboxing before saving points/half-open boxes. Display actual revision, settings, status and development approval clearly.
- **Safe intermediate state / compatibility:** all writes call existing validators and one lock. Read views remain responsive during one active operation. Loopback binding, validated paths/origin and current-project-only assets prevent exposing unrelated local files; no network fetch is needed to render controls/assets after setup.
- **Acceptance / verification:** non-square images, zoom/pan, resized/letterboxed windows and invalid/out-of-image coordinates; source/result native registration and round-tripped crop transforms. Reject traversal/out-of-project paths, unexpected origin and competing CLI/viewer writes including accept/restore; verify readable viewer while busy. Disconnect network/close Codex; create a new confirmed-background core, support16 and partial-alpha lock entirely in the viewer, prepare→repair→compare→accept, then restore/resume. Verify preparation cannot be accepted as a final photo. Proposed source checks: `pytest tests/test_recovery.py tests/test_coordinates.py` plus real manual viewer walkthrough; tests alone do not prove usability or visual quality.
- **Recovery:** reopen saved project state; CLI remains the same validated route. Failures preserve current guides and accepted result, with actionable displayed diagnostics.
- **Gates / review scope:** G4; manual visual/usability and current-project exposure review are required alongside independent contracts/verification reviews.
- **Future impact:** I07 consumes this same review/coordinate contract; I08/I09 add small controls through the shared effects request kind. Preserve guide asset authoring as the v4 gap correction.

### I07 — Bounded assisted defect loop

- **Outcome and scope:** Codex can inspect source/current result, identify a real defect and submit a validated bounded local correction through the existing engine, then hand the result to the human. Save requests/results and the two-attempt review cycle disposition in project evidence.
- **Exclusions:** no API-key integration, SDK, background agent, arbitrary prose execution, hidden upload or automatic human acceptance. Do not add a new durable counter service; existing request/results document bounded cycles.
- **Prerequisites / predecessor:** accepted I06 and existing local processing. Live assisted evaluation/photo inspection needs separate direct authority at that time; quoted cloud authorization in v4 is not a new action instruction.
- **Owning areas / interfaces:** source AGENTS.md, docs/assistant-workflow.md, review.py, tests/test_operations.py and examples/requests/. Review manifest includes revision/master, draft digest, exact crop mappings, source/result/alpha paths, QA and settings; each extension is synchronized with viewer display.
- **Human review focus:** identify location, visible evidence, likely cause and uncertainty; classify guidance/alpha, color, shading or user decision. Inspect native sensitive anatomy/web/wings/gaps/seams and compare identical crops/effect state. Vague or artistically unresolved requests stop for the user. Fine detail absent from source cannot be repaired into existence.
- **Safe intermediate state / compatibility:** existing validators reject unknown operations, stale parent/master/digest/crop transforms, off-image coordinates, unresolved prose and lock conflicts. Prepare returns assets/current identities; repair does not apply guide edits twice. Future effects are described as unavailable until delivered.
- **Acceptance / verification:** recorded synthetic proposal validation exercises real public operations. Demonstrate at most two automatic repair attempts total per requested cycle; stop earlier on ambiguity, no progress or regression, preserving the best valid candidate as review_needed. Store before/after evidence without confidence-as-probability claims. Run one explicitly authorized live assisted source-supported defect/repair/human comparison, then close Codex and continue with new local guides and repair. If no genuine defect exists, do not manufacture one; use the correctly bound archived before-mask for deterministic validation, and keep the live-defect requirement pending until demonstrated. Proposed check: `pytest tests/test_operations.py` plus separate live assisted/offline record.
- **Recovery:** local viewer/CLI continues from saved files with no assistant session or conversation memory. Retain unresolved decisions and validated candidates; no-progress does not mean acceptance.
- **Gates / review scope:** G4 and separate live/privacy authority; human visual acceptance after advisory AI review. Independent reviews inspect boundary enforcement and actual versus proposed live evidence.
- **Future impact:** I08/I09 extend defect classification/settings only after their contracts exist. I10 reconciles assisted and manual evidence rather than inferring one from the other.

### I08 — Source-guided color cleanup

- **Outcome and scope:** optional bounded high-precision color decontamination changes a separate foreground RGB asset while preserving alpha/master and keeping edits reversible. Deliver controls, renderer integration and stale/rebuild handling together.
- **Exclusions:** no physical recovery of missing color, new detail or global color editor. Off by default; no automatic interpretation of every fringe as an alpha defect.
- **Prerequisites / predecessor:** accepted I04/I06/I07 and base mask human acceptance, or an explicit candidate-comparison request. Confirm permitted source-supported support and locks.
- **Owning areas / interfaces:** effects.py make_corrected_rgb, shared `effects` request, export.py, viewer controls and tests/test_effects.py/test_export.py. Update file/assistant/workflow docs and declared per-effect supports.
- **Human review focus:** estimate background from authoritative source/known empty pixels, not previously corrected output. Source heuristic uses amount=0.35*(1-alpha)*support and corrected=(source-amount*estimated_background)/(1-amount), clipped; 0.35 is a historical starting strength. Restrict changes to permitted partial-alpha pixels and retain other RGB exactly. Save support/settings and corrected RGB16; renders never compound correction.
- **Safe intermediate state / compatibility:** disabled/zero effect selects unchanged developed RGB. Alpha changes mark dependent cleanup stale; show labelled base-to-base views with cleanup disabled on both sides, retain complete accepted result, and block final appearance acceptance/export until rebuilt within declared support or explicitly disabled. Preserve prior corrected RGB outside rebuild support and protected values inside it; wider work needs an explicitly wider operation.
- **Acceptance / verification:** mask-only/disabled/zero identity, unchanged alpha, nonempty opaque/protected/outside-support RGB equality, partial-pixel bounds and no cumulative correction on repeated render/reload. Enable cleanup, perform local alpha repair, verify stale labels/accept-export block and scoped rebuild preservation. Shading is still unavailable. Same-alpha untouched/corrected native comparisons establish the appearance tradeoff; arithmetic does not prove preferable color. Proposed checks: `pytest tests/test_effects.py tests/test_export.py` and native visual review.
- **Recovery:** explicitly disable cleanup/use saved master foreground or restore an earlier complete revision without overwriting either asset; acceptance remains human.
- **Gates / review scope:** G4 plus requested effect/support and human appearance choice; reviews cover precision, privacy/preservation and stale dependencies.
- **Future impact:** I09 must combine effects in one renderer and verify the case where both are stale after alpha repair. Keep per-effect write supports distinct.

### I09 — Protected inward shading

- **Outcome and scope:** optional, adjustable inward shading uses separate unbaked W16 and scalar p, preserving alpha and protected details. One exact renderer supports master/corrected foreground, editable layers and labelled convenience exports.
- **Exclusions:** no global 24%/48px/88px default, second compositing mode or shading used to conceal mask defects. GIF only on explicit request and never precision evidence.
- **Prerequisites / predecessor:** accepted I08 and source mask acceptance, or explicit candidate comparison. Set saved width/direction/protection against the photo's scale; preserve per-photo artistic choice.
- **Owning areas / interfaces:** effects.py make_shadow_weight, renderer/export.py, shared effects requests, viewer toggle/settings, tests/test_effects.py/test_export.py and layer/editor-handoff docs.
- **Human review focus:** W includes inward falloff/direction/protection but excludes p. Reference thin-feature/highlight heuristics cannot replace explicit W=0 protection for antennae, hairs, web, petal tips, highlights/bee. Source equation: float64 ties-to-even `round(F * (alpha16/65535) * (1-p*(W16/65535)))` in encoded sRGB; select saved master or corrected RGB, apply alpha once, never recycle flattened black foreground.
- **Safe intermediate state / compatibility:** p=0/disabled is identity; alpha never changes with effects. Any alpha repair marks enabled cleanup/shading stale; base-to-base comparison disables both, while final appearance acceptance/export waits for bounded per-effect rebuilds or explicit disabling. Preserve old corrected RGB/W outside each support and all protected values inside. Global opacity change is a separately declared global appearance operation and invokes no model.
- **Acceptance / verification:** nonempty band/inside/outside/protection fixtures; W=0 in protected/outside-band pixels, unchanged alpha and exact saved-file composite. Test double alpha/double p mistakes, unbaked W, RGB16 black export and labelled straight RGBA8 with baked shading but unmultiplied RGB. Start with both effects enabled, repair alpha, verify stale labels/blocks, then scoped rebuild with exact outside-support/protected prior assets. Compare 0/12/24% on identical reference crops with true scale/width/encoding/cleanup labels; 48/88px are only grasshopper/dahlia reference settings. Included dahlia masks/previews cannot prove a fresh run without the full source. Viewer toggle comes first. Proposed checks: `pytest tests/test_effects.py tests/test_export.py` plus native visual inspection and zero-model-call assertions for opacity-only changes.
- **Recovery:** disable an effect or select preserved earlier assets/revision, with explicit human acceptance of the resulting appearance; never alter base alpha to undo shading.
- **Gates / review scope:** G4, per-photo effect/protection choice and human native appearance review; independent reviews inspect single-alpha arithmetic, stale combined effects and export labels.
- **Future impact:** I10 owns full-source shading evidence and complete saved-layer reproduction. Changed rendering encoding or expanded appearance behavior requires a material design decision.

### I10 — Representative acceptance pilot

- **Outcome and scope:** demonstrate the complete specified single-photo workflow and its practical costs on this Mac, with every original obligation reconciled against actual evidence. Close gaps in behavior/docs within approved scope; return material growth for a decision.
- **Exclusions:** no new feature family or speculative optimization, fabricated live success, batch processing or calibrated print certification. Accepted increments alone do not prove regular-use readiness.
- **Prerequisites / predecessor:** accepted I01–I09 with applicable reports/results, separately authorized real-model/live checks and user-selected third photographic case plus actual local RAW/DNG. Missing sources, permissions or backend evidence remain explicit blockers to the affected release claim.
- **Owning areas / interfaces:** source tests/test_end_to_end.py, tests/fixtures/, docs/workflow.md, file-contract.md, validation.md, troubleshooting.md, model-provenance.md and THIRD_PARTY_NOTICES.md; update existing docs, not a second platform.
- **Human review focus:** separate pixel invariants from photographic judgment and local test results from historical reference claims. Reconcile v4 §9's 21 rows through their actual owning evidence, with current candidate/package/model/backend identities. Required photos are spider/prey/web, dragonfly and user-local bee/flower or grasshopper, processed separately; tiny synthetic fixtures are not photographic deliverables.
- **Safe intermediate state / compatibility:** last accepted work remains available while a failing/blocked pilot is reported. No regular-use claim until Tasks 1–6, real RAW and photographic gates are met or the user explicitly amends scope. MPS is enabled only where tested; an evidenced CPU-only disposition is honest, not GPU success.
- **Acceptance / verification:** deterministic E2E uses recorded guides/repair requests and real reloads; stub predictions only in labelled fast orchestration tests. Real models separately prove geometry/source preservation/backend disposition and native seams/web/transparency. Validate actual local RAW WB/profile/precision; do not count the RGB8 spider fixture as RAW. Fresh session follows v4 §8 through new guide/support/partial lock creation offline, assisted restart, acceptance, restore, interrupted resume and cache-free/model-free repair plus export reproduction. Record cold model load, warm SAM, full matte, local repair, export, peak memory pressure and disk growth; no invented seconds/photo. Run source-planned `pytest -m "not integration"` and `pytest -m integration` separately once relevant to the settled candidate, then the documented human visual checklist. Reuse applicable owner evidence; repeat only changed/unproven integration. Complete one bounded final independent material review, reconcile findings and focused corrections, then stop.
- **Recovery:** retain acceptance/source files and report the exact failed obligation, evidence and next bounded repair/decision. Reopen affected completeness without erasing historical acceptance.
- **Gates / review scope:** G4 plus actual RAW, real-model, CPU/MPS disposition, human photographic, assisted/offline/recovery and fresh-session documentation evidence. Any outstanding mandatory obligation blocks completion absent an explicit amendment. Physical print proof, if desired, remains separate.
- **Future impact:** at closure use an owner/evidence table for every original/amended requirement, exclusion and gate; distinguish achieved behavior, approved deferral and unresolved condition. Do not infer completion from the last card's tests.

## Decisions and remaining obligations

- The direct 2026-10-16 request authorizes this conversion and quality-review passes. It supplies no implementation approval, setup/download permission, photo transfer command or Gate 2/Gate 3 bypass.
- No material source change is proposed. The v4 hierarchy resolves older reference differences; the current output does not reopen its artistic specification. Source/project folder selection, actual RAW pilot and per-photo development/subjects/effect choices remain intentional setup/photo decisions, to be obtained before their affected work.
- Environment/package pairing, real CPU/MPS behavior, RAW handling, photographic quality, resource use and live assisted/manual/recovery behavior remain unverified implementation obligations. They are not defects that a planning review can mark tested.
- The no-Git baseline is valid. A future executor records its actual comparison and identifiable accepted predecessor, even if uncommitted; no forced commit, fetch or branch naming is required by this plan.
- Before Gate 2, if preparation changes future cards/interfaces/dependencies or exposes an unsafe/oversized boundary, return the detailed candidate, baseline, affected cards, rationale, alternatives and material questions to the planner. After authorized reconciliation and affected reviews, resume the same increment for current-context confirmation and Gate 2; do not advance from a preparation proposal.
- After each accepted verified result, separately assess what actually shipped against remaining interfaces, caches, acceptance, recovery and source obligations. Only dependency-eligible work advances. Approval, review findings and historical status cannot substitute for missing evidence.

Next action after independent planning reviews are reconciled: executor preparation for I01 only, using [handoff.md](handoff.md). Preparation is not implementation approval.
<!-- substantive:end -->

## Progress and review readiness

All ten increments are proposed, not implemented. No Gate 2/Gate 3 decision or bypass exists. I01 has no implementation predecessor; I02–I10 are waiting for their stated accepted prerequisite results. Product/hardware/model/runtime evidence is absent.

| Scope | Reviewer / report | Candidate inspected | Disposition |
| --- | --- | --- | --- |
| Requirements/source fidelity | `/root/source_review`; [report and focused recheck](reviews.md#requirements-and-source-fidelity) | Corrected substantive candidate recorded in reviews.md | First-writer ownership finding closed; no material improvements recommended |
| Architecture/reviewability/simplicity | `/root/architecture_review`; [report and focused recheck](reviews.md#architecture-human-reviewability-and-simplicity) | Same corrected candidate | Duplicate ownership finding closed; substitute simplicity review; Ponytail not run because not explicitly authorized |
| Verification quality | `/root/verification_review`; [report and focused recheck](reviews.md#verification-quality) | Same corrected candidate | Proposed checks adequate, including new I01 writer checks; no material improvements recommended; product evidence unrun |

Substantive candidate identity is the SHA-256 of the bytes between `<!-- substantive:start -->` and `<!-- substantive:end -->` in each artifact. Review reports record those hashes and the whole-file draft hashes. Later review/status notes outside those markers are administrative; any changed substantive byte requires affected review reconciliation.

All three independent planning-review scopes are reconciled; the sole duplicated material finding was corrected and its affected scopes rechecked. No unresolved planning decision blocks I01 preparation. See [review identities, findings and dispositions](reviews.md). These administrative readiness notes do not change the reviewed substantive scope or approve implementation.

Artifact checks confirmed ten unique increment cards with all required fields, resolving local links and all 95 pre-existing files unchanged. These are document-integrity checks, not application/runtime/photographic evidence.

Current handoff: [handoff.md](handoff.md). Next action: prepare I01, then retain Gate 2 and Gate 3.
