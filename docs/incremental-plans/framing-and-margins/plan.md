# Framing and margins incremental plan

Status: I01 and I02 are complete under the recorded Gate 2/3 pause bypass. The bounded export-reuse repair is committed and pushed to public MR #16 at `2a6029dfeda8f2aa4fe03f2bb3b9e730cab86404`; current full-suite evidence is 699 passes / three optional model-cache skips. All three affected independent reviews are reconciled. Earlier actual synthetic Q9/J1 and keyboard evidence remain applicable to unchanged UI/raster behavior. CodeRabbit marked its original thread resolved, but its new-head review was rate-limited. Photographic acceptance remains separate. Created: 2026-10-20.

## Purpose and authority

Add room around a complete photographed insect or flower, allow manual placement within the larger canvas, and export that composition without changing native image pixels or editing coordinates. This is one feature, delivered in **one part and two increments**.

The original conversion request authorized these coordinated planning artifacts. Supplementary QA design is **on**: [qa-plan.md](qa-plan.md) is coordinated with this document and [handoff.md](handoff.md). The subsequent direct 2026-10-20 request launches orchestration: resolve the reviewer-policy conflict, complete authorized planning reviews, then prepare I01 in a verified application checkout, with one persistent owner and sequential writers. That initial request authorized planning reconciliation and preparation; the subsequent direct preapproval below permits eligible local implementation without another routine Gate 2 pause. Git/publication and external actions retain separate authority. The original plan and design remain unchanged. Proposed interfaces and commands below require executor preparation against the selected implementation checkout.

**Current authority — direct user amendment, 2026-10-20:** in chat `01a159dc-236c-7a81-a328-0c3cfa514bc1`, the user wrote “I preaprove all and any gate 2 and gate 3 approvals only material design decision would need a new approval”. This bypasses routine Gate 2 and Gate 3 pauses for the framing program (I01 and I02), retaining approval for material design decisions. It supersedes earlier preparation-only/manual-pause instructions within that scope. Gate 1, concrete packets, verification, independent reviews, preservation and predecessor correspondence remain mandatory. Record actual bypass eligibility with candidate/evidence; never label an unseen result human-accepted. This is a scoped gate bypass, not the publication-bearing “Preapproved orchestration” mode: Git/publication, installations/downloads, private-data and external actions retain their separate boundaries. I01 now has applicable completed result evidence for I02 preparation, as recorded in the current handoff.

The user's subsequent direct **“approved”** reply resolves D1–D3 and authorizes the concrete bounded Pillow prerequisite/setup described in handoff.md. It permits only the specified official wheel download and isolated cached-dependency environment, exact compatibility checks and conditional five-file maintenance change. This adds no migration, other download, Git/publication or human photographic acceptance. The same I01 owner proceeds to the prepared framing implementation only if compatibility is preserved.

**Resolved review policy:** The user replied **“approved”** on 2026-10-20 in chat `01a159dc-236c-7a81-a328-0c3cfa514bc1` to the recommendation for three sequential fresh-context reviewers. This is a scoped amendment of the one-final-reviewer cap for this coordinated planning candidate and each framing increment result: requirements/source fidelity, architecture/reviewability/simplicity, and verification quality/test evidence. That reviewer-policy decision left Gates 2/3 manual and did not approve D1–D3 or separate actions; the later direct Gate 2/3 preapproval below supersedes only those routine pauses. The earlier source-plan review remains historical input, not review of this coordinated candidate.

## Sources and inspected baseline

Paths in this document are relative to the planning repository unless stated otherwise.

| Role | Source and exact identity |
| --- | --- |
| Primary source, referred to as **P** | [Framing and Margins Implementation Plan](../../superpowers/plans/2026-10-19-framing-and-margins.md), SHA-256 `0740e99606555b814e4f1249c25ed75ee8cc8666d9d4d271dfd6c9028ec08dc7` |
| Product design, referred to as **D** | [Framing and margins design](../../superpowers/specs/2026-10-19-framing-and-margins-design.md), SHA-256 `966ce48c58cfd56ea2469be6fe458e745df766091e2db3df50597a0e8a2ec55b` |
| Source review, referred to as **R** | [Independent source-plan review](../../superpowers/plans/2026-10-19-framing-and-margins-review.md), SHA-256 `70537809dffa711b147922f561ed3a265a37664cf09f3f22d51fb3cbb2d745e9` |
| Private source inspection record | `local/plans/framing-and-margins/source-baseline.json`, SHA-256 `8dd3bdba59c83364f5c9adcdd37926dda76a878829f1b79412988faef1272e72`; contains local paths and file identities, retain locally |
| Repository instructions | Root `AGENTS.md`, SHA-256 `1cd45850d46e618b0d24e258f8b7d6321191b3fd05e04839d4ed6ba7da16ae08`, plus the user's directly supplied repository instructions, including the reviewer cap |

Inspection date: 2026-10-20. Planning root is `/Users/CoveMB/Code/CoveMB/image-mask`, branch `main`, HEAD `b84cfdca1b4a8b5e1665e5535fbf1e0f8a11b813`. It has no application source. Existing modified `.DS_Store` files and untracked configuration, instructions, README, prior QA and Superpowers documents are preserved; this conversion owns only this new directory's four Markdown documents.

The inspected application checkout is `/private/tmp/image-mask-background-appearance`, branch `background-appearance`, HEAD `037e8fb4f62774fc85e4fe63e5029bcca832d877`. All 23 recorded application baseline file hashes still match the source inspection record. Four existing modified documentation files remain user-owned. No fetch, checkout, merge, test or application execution occurred.

**New baseline evidence:** the locally available `origin/background-appearance` is now `0443b15bee5fec4a0b2080f57163a34f9ad17c70`, 29 commits ahead of that checkout. Its inspected diff changes review metadata, viewer action error reporting, and preservation/staleness of exposure and Shadow fade controls, with corresponding tests/docs. Thus D's historical “differs only in troubleshooting documentation” observation is no longer current. Do not use it as an execution assumption. Gate 1 must select the actual authorized baseline and reconcile these changes, especially I02's independent form state. Remote freshness was not checked.

I01 preparation selected the clean existing application checkout `/private/tmp/image-mask-shading-doc-review-integration` at detached HEAD `0443b15bee5fec4a0b2080f57163a34f9ad17c70`. The photo-library migration has not landed there; use existing `master_id`, `masters/` and revision-relative asset resolution. Recheck on resumption. If storage changes later, use its canonical identity/resolvers without adding a parallel scheme or requiring an unrelated proposal to land.

Public documentation checked live on 2026-10-20: [NumPy 2.3 edge padding](https://numpy.org/doc/2.3/reference/generated/numpy.pad.html) supports nearest-edge semantics; [Python 3.12 replacement](https://docs.python.org/3.12/library/os.html#os.replace) distinguishes successful replacement from the application's subsequent directory-sync outcome; [WCAG dragging alternatives](https://www.w3.org/WAI/WCAG22/Understanding/dragging-movements) supports numeric/button operation without required dragging. These checks do not establish an installed environment, complete dependency/security revalidation, visual quality or runtime correctness. Gate 1 revalidates the consumed stack and official sources before Gate 2.

## Shared contract and remaining decisions

- Native developed source, RGB16 sRGB interpretation, masks, protected partial values, guides, effects, recipe/guidance digests, caches, and accepted/working revision pointers remain unchanged. Framing is presentation metadata and output only.
- Exactly four nonnegative integer pixel margins define the layout. Reject booleans, fractional/nonfinite/string values, unknown keys, invalid array shapes/dtypes and oversized output before allocation/staging. Source rectangle is half-open `[left, top, left + W, top + H]`; output is `(W + left + right, H + top + bottom)`.
- Render the existing native result once through its canonical renderer, then copy it exactly at `(left, top)`. Extend only the **saved native backdrop's** nearest edges/corners, or black when absent. Never pad subject pixels, recomposite the finished result, regenerate/resize/reflect/tile the backdrop or reconstruct cut-off anatomy.
- Proposed first-version bounds are 32,768 per axis and 100,000,000 output pixels. Preview is at most 1600 pixels on its long edge with no upscaling. Use one RGB16 destination at a time and bounded row scratch; no enlarged float64 F/A/W arrays. Existing disk reserve remains, with current native budget plus `16 * output_pixels + 2 * 1024**2` in the verified I01 implementation (the source proposed 1 MiB overhead); measurement can require a higher budget, never silent loss of precision.
- No new dependency families, models, services, uploads, background queues, geometry migration, subject detector, crop/rotation/scale/aspect-ratio tool or percentage units. The separately approved Pillow security prerequisite permits its exact wheel download and isolated setup; other downloads remain outside scope. No change to native image routes, authoring coordinates or assistant inspection semantics.
- **D1 — approved design choice:** manual placement plus Centre image, rather than automatic subject centring. Centre image balances current total padding, assigning odd extra pixels to Right/Bottom; it centres the image rectangle.
- **D2 — approved design choice:** accept saved-backdrop edge extension and its possible visible bands on varied backgrounds.
- **D3 — approved design choice:** accept the proposed output bounds. They are conservative limits, not measured performance promises.
- D1–D3 were approved together by the subsequent direct “approved” reply in this chat on 2026-10-20; do not ask for them again. Ordinary additive interface details within the prepared contract require no renewed Gate 2 permission; any consequential compatibility or product-contract change still needs a material decision.
- Use domain/behavior names for every authored/generated filename, API, schema, CLI label, test, fixture, comment, diagnostic, UI string and document. Increment IDs belong only in work tracking and factual provenance. Preserve existing public names, legitimate domain/version names and source/history. Select concrete names before Gate 2; architecture review checks actual artifacts. No unrelated renaming.

## Part and source coverage

| Part | Contribution | Ordered increments |
| --- | --- | --- |
| Framing and margins | Exact presentation exports, followed by a complete saved control and preview workflow | **I01 — Precise framed exports** → **I02 — Saved framing controls and preview** |

P's helper-only Task 1 is combined with the export/CLI portion of Task 2 so I01 is immediately usable. Preset persistence moves with its UI consumer into I02; the bounded preview helper moves there too. This avoids shipping unused interfaces while keeping each increment's meaningful tests, documentation and safeguards with its behavior. Parts introduce no gate.

| Source locator | Material obligation | Owner / QA correspondence | Disposition |
| --- | --- | --- | --- |
| P Goal, Global Constraints; D Intent and success, Alternatives | More room and manual positioning; source detail/native editing preserved; offline use; no generative completion | Global; I01 exact export, I02 control; Q1, Q2, Q7, J1 | Both complete; synthetic Q9/J1 and readback verified |
| P Task 1; D Geometry, precision and backdrop | Strict geometry; RGB16 interior exact; saved-backdrop border only; optional transparent outer zeros; zero/singleton/odd/edge cases | I01; Q1–Q3 | Complete in closed I01 |
| P Task 2 Produces/export/budget/collision; D Export and preview contract | Explicit compact framed bundle; legacy default unchanged; exact identity, manifest, labels, immutable reuse/collision and saved-only replay | I01; Q2–Q4 | Complete in closed I01; consumed unchanged by I02 |
| P Task 1 preview interface; Task 3 preview; D Resource limits | Direct bounded preview, no full expanded canvas; per-server nonblocking render guard; stale response rejection | I02; Q6, Q8 | Implemented; Q6/Q8 deterministic and resource evidence retained |
| P Task 2 preset and two-process failure checks; D Saved preset and compatibility | Source-bound optional schema; no read writes; independent error; lock/CAS; pre/post-replace distinction; restore retention | I02; Q5, Q7 | Implemented; Q5 real-process/write-phase evidence retained |
| P Task 3 snapshot/API; R producer-identity finding | Exact validated manifest bytes produce snapshot revision digest consumed by preview; draft digest is different | I02; Q6 | Implemented; exact producer/consumer HTTP identity tests pass |
| P Task 3 bitmap/browser checks; R CSP finding | Base64 bytes → Blob → createImageBitmap under unchanged CSP; close replaced/stale bitmaps; actual browser proof | I02; Q6, Q9 | Complete; Node/HTTP and actual production-CSP browser Q9/J1 evidence retained |
| P Task 3 form/lifecycle/docs; D User controls | Four fields, equal/centre/reset/reload, explicit preview/save/export; unsaved visible fields used; preserve unrelated dirty forms and native coordinates | I02; Q7, Q9, J1 | Complete; Q7 behavioral tests and actual controls/draft/native-coordinate journey verified |
| P Global Constraints, execution preflight; D integration boundary | Current owners, no source-free implementation, landed storage compatibility, no model/download/publication implication | Global preparation; both cards | Exact predecessor/baseline and prerequisites verified; no storage migration |
| P settled-batch verification; D Acceptance and review | Full relevant deterministic suite and static checks; measured resources; synthetic edge cases; actual browser/keyboard checks; separate human photographic acceptance | Each card's tests; I02 J1; global Q10 | 693 historical passes/3 model-cache skips, separate two focused preview passes, static/resource and actual browser proof; human limits explicit |
| P Review Focus, Planning disposition, settled-batch review; user reviewer cap | Independent bounded review without repeated unchanged passes | Global; three sequential fresh-context scopes | Three planning and both result scopes complete; affected repairs and verification renewals closed |
| D Resource/failure; root instructions | Locks, low disk, interruption and stale inputs preserve accepted work; privacy and recovery, no automatic cleanup | I01 Q4; I02 Q5/Q6; global retention | Implemented deterministic preservation checks; retained evidence and no cleanup |
Detailed QA cases and independent expected outcomes are in [qa-plan.md](qa-plan.md). No additional certification feature or mandatory third-party/model evaluation is justified by this local presentation change; existing runtime and human acceptance duties remain.

## I01 — Precise framed exports

**Outcome:** an offline CLI user can add exact asymmetric/equal pixel margins to an accepted result or explicitly selected draft and obtain a separate reproducible presentation bundle.

**Scope and owners:** proposed `src/blackmask/framing.py` owns strict geometry and exact RGB16/RGBA8 placement. `export.py` retains native rendering and safe publication ownership; `cli.py` exposes `export PROJECT --margins LEFT RIGHT TOP BOTTOM [--framed-transparent]` alongside existing revision/draft selection. Proposed `tests/test_framing.py`, relevant export/background/CLI tests, and canonical file-contract/workflow/troubleshooting docs accompany this behavior. Reuse project/path/lock/check-space, saved-layer/backdrop and publication helpers. The exact eight-file proposal, signatures and compatibility/failure guarantees are in [the concrete preparation packet](handoff.md#concrete-i01-preparation-packet--2026-10-20).

**Exclusions:** no preset API/file, preview helper/route or UI controls yet. No native-layer duplication, processing changes, new dependency or speculative compatibility layer.

**Prerequisites:** authorized application checkout and current contract correspondence established; D2/D3 and concrete new export interface resolved before implementation; applicable review policy resolved. No predecessor increment exists.

**Behavior:** omitted framing preserves existing export behavior, file set and destination exactly. Explicit framing creates only RGB16 result TIFF, RGB8 viewing PNG, compact manifest and README, plus optional RGBA8 viewing PNG. Transparent margins are zero RGBA with native straight RGB/alpha bytes unchanged. The manifest records source/revision and validated revision-manifest digest, selected effect/backdrop identities, canonical margins, output/source geometry, algorithm/encoding and hashes. Destination identity binds those inputs and variants; reuse only a validated complete matching delivery, never overwrite a corrupt/colliding delivery. All-zero explicit layout may use the separate compact bundle with identical decoded native pixels.

Label accepted input precisely: **“Framed presentation of accepted revision; framing has not been separately accepted”**. Unaccepted input is clearly DRAFT. Saving/exporting is not photographic or composition acceptance.

**QA ownership:** Q1–Q4 and applicable Q10. Exercise the actual CLI → saved layers → canonical native renderer → framing → publication → TIFF/PNG readback path. Use independent literal border/corner values, non-257 uint16 samples and protected partial alpha; assert exact insertion and unchanged inputs. Fresh-process saved-only replay uses synthetic saved project assets with original capture/model availability removed only within test-owned storage. Check legacy export reuse/file set, transparent option, changed-layout destinations, corrupt/extra/missing/symlinked delivery members, low disk, busy writer, stale source/revision and interruption before/during publication. Reject out-of-bound dimensions before destination allocation/staging; measure representative peak memory/time and inspect the space estimate.

**Human review focus and safe intermediate state:** one precise export path with unchanged native workflow. The CLI is useful immediately; existing UI stays usable. There is no unused preset or preview endpoint awaiting later repair. Updated docs distinguish presentation output from editable native layers and explain visible edge bands.

**Recovery:** failures preserve source, accepted pointers and prior deliveries. Keep incomplete staging under current repository policy with actionable diagnostics; do not add automatic deletion or claim full rollback after visibility/durability boundaries. Retry only after validating input identity and collision state. Previously created exports remain usable regardless of later UI/preset work.

**Gates/reviews:** retain the concrete Gate 2 packet and complete result evidence/review at Gate 3; both routine pauses are bypassed by the direct grant above. Resolve material design choices before affected implementation. Three distinct fresh-context scopes are authorized by the scoped review-policy amendment. Use ordinary scoped reviews; the completed architecture assignments report **“Substitute simplicity review; Ponytail not run”** under the instructions then applicable. The latest direct replacement AGENTS Section 9 restores Ponytail explicit-only. It was not invoked; satisfied unchanged coverage does not need an additional pass. No optional external/heavier review is needed for this plan. Freeze candidate/comparison; renew only scopes affected by material repairs. Any future Ponytail invocation needs applicable authority. Under the replacement AGENTS.md review policy, the implementation owner handles verified, material, in-scope findings unless the review was explicitly read-only/report-only; material design decisions and separate actions still need authority.

**Future impact:** return the actual export arguments, identities/geometry schema, error outcomes and verified native compatibility for I02 consumption. A material preparation change returns to the same increment after plan reconciliation; an unimplemented proposal never advances I02.

## I02 — Saved framing controls and preview

**Outcome:** a user can set margins, centre the image, preview, save/reload, and export the visible layout entirely through the existing local UI without disturbing native editing.

**Prerequisites:** I01's actual candidate, checks, reviews and recorded Gate 3 bypass eligibility apply to the selected checkout; compare the real I01 producer contract with viewer/CLI consumer needs. D1 and preset/UI/API compatibility decisions are resolved before implementation. Reconcile the newer exposure/fade form preservation changes and any landed storage work first.

**Scope and owners:** extend framing's domain owner with bounded preview and optional preset validation/read/save; `project.py` remains path/lock/atomic-write owner. `viewer.py` snapshot/action/HTTP handling and `ui/review.html` consume these APIs together. Add behavioral tests to framing/viewer/page suites; retain native coordinate tests. Update README and canonical user/assistant workflow, file-contract and troubleshooting docs in this increment.

**Preset:** optional schema version 1 binds current developed source identity, oriented native dimensions and four margins. Absence yields in-memory zeros without a write. Invalid/foreign/symlinked presets report an independent framing error while native work/export remains usable; do not silently overwrite or migrate them. Save under the existing lock with source validation and compare-and-swap expected raw-byte digest, null meaning absent. A stale second client reloads. Reads/saves do not change native recipe/guidance digests, inference caches or revision pointers; revision restore retains the source-bound preset.

Before replacement, failure retains old preset bytes. After replacement but failed directory sync, new bytes may already be visible with durability uncertain: reread actual bytes/digest, retain form edits, report uncertainty and require reload before another CAS save. Do not assert rollback or auto-restore/delete. Use real two-process lock/CAS tests plus phase-specific write failures.

**Producer/consumer contract:** each relevant snapshot revision entry supplies `revision_manifest_sha256` from the same exact validated persisted bytes, distinct from `draft_digest`. Snapshot also supplies framing values/digest/error, preserving native dimensions. Save uses the existing identity envelope; clients supply no arbitrary paths. Framed exports consume the explicit current form and I01's same validated export API, including unsaved margins with visible status.

The authenticated same-origin read-only preview POST binds source, selected revision, its manifest digest and canonical margins. JSON returns base64 PNG8 bytes and matching identities/geometry. Decode to local bytes and PNG Blob, then `createImageBitmap`, keeping CSP unchanged and closing stale/replaced bitmaps. Bound output sampling directly from native result/saved backdrop, not an expanded full canvas. One nonblocking per-server render guard rejects competing work before allocation and releases on success, errors and disconnects; no queue. Revalidate inputs before response and reject stale enabled effects instead of showing an unrequested BASE result.

**Control behavior:** labelled whole-pixel Left/Right/Top/Bottom plus Equal margins/Set all sides, Centre image, Reset margins, Reload saved margins, explicit Preview framing, Save margins, and separate framed accepted/draft exports. Reset changes the local four fields only. Reload changes only framing form state. Polls preserve unsaved framing and unrelated effect/guidance drafts; old preview is visibly stale. Response sequence, current margins and source/revision identities must all match before display. Source changes invalidate preset applicability and preview. No preview authoring or native guide transformation. Show output/native dimensions, pixel units, RGB8/reduced-detail label, unsaved status and cut-off-subject limitation.

**QA ownership:** Q5–Q10 and **J1**, the final combined journey across both increments. Test actual snapshot → preview HTTP request → response, not a manufactured digest. Test malformed fields, Host/Origin/token/body-size checks, source/revision races, busy preview guard and release on transport failures; use actual server tests plus behavioral Node tests. Verify actual browser display under production CSP, keyboard-only controls/error recovery, out-of-order responses, polling and independent draft preservation. Reopen the native view and author a known guide at its unchanged coordinate. Inspect synthetic edge/corner/varied-background outputs and record human visual observations separately. User photo acceptance requires user-selected local source authorization.

**Human review focus and safe intermediate state:** preset, producer digest, form state and preview consumer ship together. There is no half-working UI or undocumented persistence. Corrupt framing metadata cannot disable native editing/export. A browser request failing or an optional preset not applying leaves the native workflow and prior exports intact.

**Recovery:** preserve local fields and unrelated dirty forms on busy/stale/invalid failures; use explicit reload for preset reconciliation. Stop stale preview replacement, release render guards and close disposable bitmap resources. Never repair an invalid preset by silently overwriting it. Retain immutable exports and all accepted source work.

**Gates/reviews:** concrete Gate 2 packet, verification and independent review, then recorded Gate 3 bypass eligibility. The routine pauses are preapproved; material decisions remain with the user. Three distinct scopes are authorized by the scoped review-policy amendment; same architecture substitute and freeze/renew rules as I01. Human photographic acceptance remains separate from automated or code-review results. No claim of comprehensive accessibility from a keyboard walkthrough alone.

**Future impact:** return whole-feature J1 evidence and any residual human/local-photo limitation. No future increment is required to make this result coherent; close by reconciling all source obligations and retention.

## Shared verification and evidence

Commands below are historical source-discovered templates. The selected checkout now has the approved isolated `.venv`; I01's actual interpreter, explicit candidate `PYTHONPATH`, offline environment, executed commands/results and limits are maintained in [handoff.md](handoff.md#environment-and-executable-command-preparation). Use that recorded evidence rather than treating the historical templates as execution proof. Revalidate I02's environment during its own preparation.

```bash
rtk proxy .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_framing.py tests/test_background.py tests/test_cli.py
rtk proxy .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_framing.py tests/test_viewer.py tests/test_viewer_page.py tests/test_viewer_coordinates.py
rtk proxy .venv/bin/python -m pytest -q -p no:cacheprovider -m 'not integration'
rtk proxy .venv/bin/ruff check src tests --no-cache
rtk proxy .venv/bin/ruff format --check src tests --no-cache
rtk proxy .venv/bin/mypy src
```

First focused command belongs to I01, second to I02. Run relevant focused checks during edits and the full relevant deterministic/static set once on each settled candidate; reuse passes on unchanged relevant inputs, renew after changed behavior/inputs or justified new evidence. Establish meaningful failing behavior before implementation when appropriate. Real model inference is not warranted solely for framing.

Reuse source identities, actual diffs, small synthetic fixtures, check outcomes and bounded failure logs. Necessary uncommitted evidence includes relevant new-file bodies/deletions and its available base, not hashes alone. Proposed executor evidence root is its ignored `local/plans/framing-and-margins/`; select exact contents and canonical parents before capture, preserve existing contents, and use no duplicate root archive. Current planning evidence is four small Markdown files plus existing references. Future resource/browser evidence size is unknown until the executor selects fixtures; estimate before large copies. No target size-warning threshold was found, so do not invent one.

Keep private photos, private baseline paths/configuration and model assets out of commits, public packets and web queries. Prefer synthetic fixtures. Preserve unique/offline-only dependencies, failed environments, human edits, accepted data and evidence with active consumers regardless of cache/ignored naming. Record exceptions with size or honest unknown, owner, consumer and review event. Planning creates no copies of application roots and authorizes no cleanup.

## Progress, reviews and decisions

| Increment | Factual status | Candidate/evidence | Approval | Next action |
| --- | --- | --- | --- | --- |
| I01 | Complete under Gate 3 pause bypass | Closed 13-file candidate manifest `c16fd6bbcf2e0c4ad5074346036c40e74e94d672aa0c2e61df7cec8eca8e8d4d`; 663 passes/3 explicit model-cache skips; three result scopes and affected repair renewals complete | Candidate-specific eligibility recorded in handoff; photographic acceptance remains separate | Preserve result/evidence; consume exact uncommitted predecessor in I02 |
| I02 | Complete locally under Gate 3 pause bypass | Persistent owner `/root/i02_saved_framing_controls`; final 19-file manifest `b920e3fc3349584a75229e8c00ad3d2bd9f132ba97badd5ce06d8ee75385e871`, exact I01 predecessor, browser/readback and keyboard supplement verified | Candidate-specific eligibility recorded after original verification renewal; photographic acceptance separate | Preserve candidate/evidence; no further eligible increment or Git/publication action |

| Independent planning scope | Report | Candidate | Current disposition |
| --- | --- | --- | --- |
| Requirements/source fidelity | `/root/framing_source_review` | Frozen coordinated candidate in reviews.md | No material improvements recommended |
| Architecture/reviewability/simplicity | `/root/framing_architecture_review` | Same frozen candidate | No material improvements recommended; substitute simplicity review; Ponytail not run |
| Verification quality | `/root/framing_verification_review` | Same frozen candidate | No material improvements recommended |

Actual assignments, content identities, reports, limitations and reconciled findings belong in [reviews.md](reviews.md). Author coverage/link checks do not count as independent review. Administrative status/report updates are distinguished there from substantive revisions.

Current decision record: the original conversion selected supplementary QA; the subsequent direct orchestration request authorized this launch. The user replied **“approved”** on 2026-10-20 in chat `01a159dc-236c-7a81-a328-0c3cfa514bc1` to the recommendation for three sequential fresh-context reviewers. This is a scoped amendment of the one-final-reviewer cap for this coordinated planning candidate and each framing increment result: requirements/source fidelity, architecture/reviewability/simplicity, and verification quality/test evidence. That reviewer-policy decision left Gates 2/3 manual and did not approve D1–D3 or separate actions; the later direct Gate 2/3 preapproval supersedes only those routine pauses. The sole orchestrator is this chat, titled `Framing · 2/2 · MR #16`; the persistent I01 owner is `/root/framing_architecture_review`, reassigned after its completed independent planning review as documented in handoff.md. I02's fresh persistent owner is `/root/i02_saved_framing_controls`. Configured model defaults apply. The earlier unanswered-policy checkpoint is historical; this direct approval resolves it. No inaccessible historical grant is imported.

Initial resumption inspection on 2026-10-20 confirmed all three original source hashes, initial candidate hashes, root instructions and all 23 historical application baseline hashes. Planning HEAD remains `b84cfdca1b4a8b5e1665e5535fbf1e0f8a11b813`. The historical `037e8fb4f62774fc85e4fe63e5029bcca832d877` checkout and its four modified docs remain preserved; its local tracking ref is 29 commits ahead. Preparation then selected the clean newer checkout recorded above and inspected declared/resolved/observed stack correspondence. No refs were fetched. No application test, import or execution occurred; runtime/version and standard-library metadata checks are separately qualified in the packet.

## Current scope reconciliation

Final reconciliation on 2026-10-20 closes both local increments. Controlling P/D/R and source-baseline hashes still match. The final I02 candidate, observed browser code, selected retained content and original independent reports correspond. Administrative status/review updates do not change product requirements or create a new implementation candidate.

| Obligation group | Owner | Actual closure evidence | Status and limits |
| --- | --- | --- | --- |
| Exact framed exports, compatibility, failure/resource integrity | I01 | Closed c16fd6 candidate; exact pixel/file/CLI/replay/failure checks, three scopes and affected repairs | Complete; no maximum-size execution or photographic acceptance claim |
| Preset/control/preview, state/security/coordinate preservation | I02 | Final b920e3 candidate; deterministic checks, actual production-CSP browser journey, two-client CAS/fault recovery, unsaved-layout exports, saved-only reopening/restore, keyboard supplement and readback | Complete; reduced-preview P2 and canvas integration defect closed; all affected reviews renewed |
| Complete manual/offline framing outcome | I02 | Real synthetic browser plus independent full-delivery pixel/identity/preservation readback; native guide (17,23); no original capture or model execution needed | Synthetic Q9/J1 complete; human photographic judgment and full accessibility certification remain unclaimed |
| Scope/exclusions, privacy, baseline and decisions | Both owners/orchestrator | Exact I01 predecessor; 19 live/frozen I02 bodies, 37 result/log pairs, 249 evidence hashes, approved D1–D3 and Pillow compatibility | No generative completion, native-coordinate migration, new model use or publication; current security qualification retained |

The subsequent explicit MR request authorized publication. The application is committed at `90829e007f8af677a8ef29694a3f81494b1f07f2` on `framing-and-margins` in `/private/tmp/image-mask-shading-doc-review-integration`, with [MR #16](https://github.com/CoveMB/image-mask/pull/16) open against refreshed public main. That main tree equals the reviewed baseline. The sole publication-only difference from the frozen candidate is completed-review metadata and already-reviewed keyboard evidence in docs/validation.md; all production/test bytes still correspond. The primary planning checkout, private photo/evidence and user work remain preserved. See handoff.md for exact publication identity and pending automatic provider status; no merge or formal photographic acceptance occurred.

### Evidence retention and cleanup review

**Final evidence-retention reconciliation is complete.** Required reviews and browser consumers have finished. Surviving originals, selected retained proof and recovery material remain held for reproducibility and any late finding; this review adds no gate, increment or deletion authority.

| Disposition | Surviving content and consumer |
| --- | --- |
| Keep | Four coordinated Markdown files and unchanged P/D/R; source, decision, review and gate correspondence |
| Keep | Exact reviewed planning capture, 71,517 logical bytes; source baseline, 3,228 bytes; prior baseline evidence, 84,472,665 logical bytes reused by reference (historical measured size) |
| Keep | `local/plans/framing-and-margins/retained-i01/`: 496 files, 31,140,967 logical / 32,825,344 allocated bytes; candidates, full command evidence, compatibility fixtures, approved wheel and resource fixture |
| Keep | `retained-i02-browser-pending/`: 549 files, 4,004,649 logical / 5,672,960 allocated bytes; original candidate/predecessor, complete selected logs/scripts and fixtures |
| Keep | `retained-i02-reduced-preview-repair/`: 54 files, 1,193,340 logical / 1,294,336 allocated bytes; repaired candidate, independent literal oracle, intended RED/GREEN and raw logs |
| Keep | `retained-i02-browser-diagnostics/`: two files, 12,049 logical / 16,384 allocated bytes; bounded guard-preserving diagnosis with declared redaction |
| Keep | `retained-i02-native-canvas-layout/`: 47 files, 1,257,535 logical / 1,339,392 allocated bytes; exact selector repair, original/prior bodies and checks |
| Keep | `retained-i02-browser-progress/`: three files, 576,146 logical / 581,632 allocated bytes; immutable partial observations, safe screenshot and event checkpoint |
| Keep | `retained-i02-browser-completed/`: 81 files, 2,695,570 logical / 2,867,200 allocated bytes; final candidate, complete selected command logs/readback/fixtures, final safe screenshot, observations and retention selection. The selection also verifies 283 existing retained-file bindings |
| Keep | Root `browser-keyboard-verification.json`: 8,249 logical / 12,288 allocated bytes; explicit actual keyboard observation and post-observation hash correspondence, outside the copy totals below |
| Hold | Original synthetic fixture, recovery inputs, application checkout, server/private connection and isolated environment; useful for late findings and authorized local use. Runtime capability excluded from retained copies and public docs |
| Hold | Historical dirty checkout, old environment, accepted/user/private work and offline-only dependencies; no new broad size inventory or disposal authority |
| Cleanup candidate | Redundant completed temporary test trees only after exact owner/consumer revalidation and separate deletion authority; nothing deleted or archived wholesale |

The seven retained-copy roots total **1,232 files / 40,880,256 logical bytes / 44,597,248 allocated bytes**. Root verified each new copy and all 283 reused bindings against selected source hashes; all 19 candidate bodies and 249 evidence hashes still matched after keyboard observations. The 81-file final copy includes its 115,325-byte selection record and excludes the runtime capability. Earlier partial events remain unchanged; final events are retained separately. Free space at copy time was 20,390,211,584 bytes, above the unchanged 10 GiB reserve; this is an observation, not a future guarantee.

Root owns planning records and retained copies; each persistent owner owns original implementation evidence. Revisit held material only for a new material finding, explicitly requested shutdown or separately authorized cleanup. Full model inference, maximum-size performance, full accessibility certification and human photographic acceptance remain outside the achieved evidence. The earlier native 404 cause and exact full Brave build remain unknown; actual reduced browser identity and successful current image responses are recorded. No mandatory synthetic QA gap remains.
