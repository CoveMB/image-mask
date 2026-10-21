# Framing and Margins Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task after explicit implementation approval. Steps use checkbox (`- [ ]`) syntax for tracking. Recommended execution: one sequential writer, one bounded independent final reviewer. No per-task agent fan-out or Git writes without separate authority.

**Goal:** Add reversible margins and manual centring around a photographed insect/flower, with saved layout, preview and precise framed exports.

**Architecture:** Keep all native editing assets and coordinates unchanged. A small presentation module validates integer margins and places the existing rendered result over an extension of its saved backdrop. Existing project transactions, rendering, publication and local HTTP security remain canonical owners.

**Tech Stack:** Existing Python >=3.12,<3.13, NumPy 2.3.5, Pillow 12.3.0, tifffile 2026.10.15, vanilla HTML/JavaScript and pytest/Node tests. No dependency or model changes.

**Spec:** [Framing and margins design](../specs/2026-10-19-framing-and-margins-design.md). Read it first; this plan implements that candidate, not an approval to execute.

## Global Constraints

- Preserve originals, native RGB16/sRGB, grayscale16 masks, partially transparent/protected pixels and source registration. No resampling, cropping, new photographed detail or model execution.
- Missing framing means exact legacy native export behavior. No recipe schema/mask/guide migration; no rewrite on read.
- Canonical settings are exactly `left_px`, `right_px`, `top_px`, `bottom_px`: nonnegative whole pixels, strict integer types, no booleans/unknown keys.
- Framed canvas maximum is 32,768 pixels per side and 100,000,000 total pixels; reject before allocation/staging. Preview long edge maximum 1600, no upscaling.
- Algorithm identity is `saved-backdrop-edge-padding-v1`. Extend saved background only, never flattened subject edge pixels or regenerated background.
- Four numeric margins, Set all sides, Centre image, Reset margins, Reload saved margins, Preview framing, Save margins, and explicit framed accepted/draft exports. No automatic subject centring unless the user changes the proposal.
- Use existing project lock, managed-path/symlink validation, atomic JSON and exclusive artifact publication. Preserve accepted/working pointers and unrelated drafts.
- Implement only after user approval and baseline reconciliation. Keep Git writes, publication, private-photo use, deletion and human acceptance under their own authority.
- Prefix every shell command with `rtk`; use `rtk proxy` for exact/raw checks. Run tests in the verified implementation checkout, not this planning checkout.

## Review Focus

1. A leg or petal reaches the image boundary: padding must copy background only and must not extend anatomy. T1 border oracle; T3 native visual check.
2. Partial alpha and a varied background: every original rendered pixel must remain exact while new borders can exhibit edge bands. T1 insertion/oracle; T2 round trip; T3 visual evidence.
3. Two clients change margins or the revision changes during preview/export: stale settings/response cannot overwrite newer state or mislabel pixels. T2 CAS/publication and T3 HTTP/response-order tests.
4. Huge, boolean, fractional or tampered dimensions/preset files: fail before canvas allocation or mutation while native editing/export remains available. T1 validation; T2 corrupt-preset isolation; T3 recovery.
5. Another storage/export refactor lands first: use its canonical resolver/selection/identity and retain this feature's geometry/legacy contracts. Mandatory preflight comparison; T2 reconstruction/default-export regression tests.

---

## Execution preflight and file map

- [ ] Confirm implementation authorization, optional centring answer and acceptance of the proposed edge-extension/100 MP limits. This plan is a reviewable proposal, not a claim those design choices were individually approved.
- [ ] Inspect actual branch, worktree, status, source/tests/dependency hashes against `local/plans/framing-and-margins/source-baseline.json`. The inspected application baseline is `037e8fb4f62774fc85e4fe63e5029bcca832d877`; remote refs were not refreshed. Preserve all dirty/untracked work. Select an authorized implementation checkout; do not implement in the source-free planning checkout or invent publication ancestry.
- [ ] Reconcile any landed photo-library-storage work. Current native revision assets are read through `_asset`; a landed shared-asset resolver supersedes that physical-access detail. The design's presentation-only contract remains fixed. Material interface differences return for plan correction, not parallel compatibility scaffolding.
- [ ] Confirm `.venv/bin/python`, `.venv/bin/ruff`, `.venv/bin/mypy` and Node are available without installing anything. Commands below are discovered from application README/validation docs; they have not been run for this plan.

| File | Responsibility / change |
|---|---|
| Create `src/blackmask/framing.py` | Strict layout validation, exact raster placement, bounded preview, preset read/save; one domain owner |
| Modify `src/blackmask/export.py` | Opt-in framed delivery using canonical renderers and safe artifact publication |
| Modify `src/blackmask/cli.py` | `export --margins LEFT RIGHT TOP BOTTOM` and optional `--framed-transparent`; no new command namespace |
| Modify `src/blackmask/viewer.py` | Preset state/error, authenticated save/preview, explicit framed export fields |
| Modify `src/blackmask/ui/review.html` | Independent framing form/preview and explicit export controls; no native authoring coordinate change |
| Create `tests/test_framing.py` | Pure geometry, backdrop/precision, preset/export/CLI integration and failure contracts |
| Modify `tests/test_viewer.py`, `tests/test_viewer_page.py` | Actual HTTP/schema/security flow and Node-based UI behavior |
| Modify `tests/test_background.py` only if fixture reuse needs it | Keep existing legacy/native result coverage; prefer importing its existing test helpers over broad fixture reorganization |
| Modify `docs/file-contract.md`, `docs/workflow.md`, `docs/assistant-workflow.md`, `docs/troubleshooting.md`, `README.md` | Canonical persistence/export and user instructions; mark framed coordinates as unsuitable for native guide authoring |

Do not modify `recipe.py`, processing/repair/model paths or `coordinates.js` just to add presentation framing. Existing tests for those consumers remain regression evidence. A necessary deviation requires a concrete source-backed explanation and plan update.

### Task 1: Exact margin geometry and presentation raster

**Files:** Create `src/blackmask/framing.py`, `tests/test_framing.py`.

**Interfaces:**

- Produce frozen `Margins(left_px: int, right_px: int, top_px: int, bottom_px: int)` with `to_dict() -> dict[str, int]`.
- `validate_margins(value: object, source_size: tuple[int, int]) -> Margins`: width/height order; strict fields/types and output bounds.
- `framed_geometry(source_size: tuple[int, int], margins: Margins) -> tuple[int, int, tuple[int, int, int, int]]`: output width, height, source rectangle. All public raster entry points revalidate, including directly constructed dataclass values.
- `frame_result(native_rgb16: np.ndarray, background_rgb16: np.ndarray | None, margins: Margins) -> np.ndarray`: aligned uint16 RGB inputs; exact native insertion and saved-backdrop edge extension, absent backdrop black.
- `frame_transparent(native_rgba8: np.ndarray, margins: Margins) -> np.ndarray`: zero RGBA outside, exact native bytes inside.
- `framing_preview(native_rgb16: np.ndarray, background_rgb16: np.ndarray | None, margins: Margins, *, max_edge: int = 1600) -> tuple[np.ndarray, dict[str, object]]`: bounded RGB8 display sample and explicit source/output/display geometry. Internal UI always uses 1600; helper validates a positive bound no greater than 1600.

- [ ] **Write failing behavior tests.** Use independent literal border/corner values and varied uint16 values not divisible by 257. The basic insertion contract is:

```python
native = np.array([[[1, 258, 65534], [19, 1001, 32768]]], dtype=np.uint16)
backdrop = np.array([[[11, 12, 13], [21, 22, 23]]], dtype=np.uint16)
margins = validate_margins(dict(left_px=1, right_px=2, top_px=1, bottom_px=0), (2, 1))
result = frame_result(native, backdrop, margins)
assert result.shape == (2, 5, 3)
np.testing.assert_array_equal(result[1:2, 1:3], native)
np.testing.assert_array_equal(result[0], [[11,12,13],[11,12,13],[21,22,23],[21,22,23],[21,22,23]])
np.testing.assert_array_equal(result[1, 0], [11,12,13])
np.testing.assert_array_equal(result[1, 3:], [[21,22,23],[21,22,23]])
```

Add `test_zero_margins_exact_and_inputs_unmodified`, `test_framing_rejects_invalid_types_geometry_and_resource_bounds`, `test_transparent_margin_and_partial_alpha_are_exact`, and `test_preview_samples_without_allocating_full_canvas`. Exercise singleton/odd/non-square images, each zero side, all-zero settings, boundary-valued margins, invalid channel counts/dtypes, boolean/float/string/unknown keys, arithmetic overflow-size requests and every output-limit boundary. Validation spies assert no destination allocation for rejected sizes.
- [ ] **Run red check:** `rtk proxy .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_framing.py`. Expected failure is missing new behavior/module, not unrelated environment failure.
- [ ] **Implement the listed interfaces.** Use direct destination slice copies and constant/edge fills from the saved backdrop; no full padded foreground/alpha/weight arrays, no float64 output canvas. Implement preview by mapping bounded output pixel centres to native result/background samples; convert RGB16 to RGB8 once with existing ties-to-even/257 semantics. Metadata marks preview sampling as reduced detail, not authoritative photographic output.
- [ ] **Add composite-input test.** Build native pixels with the existing `render_background` and independent scalar expectations for alpha values 0, 1, 32768, 65535, nonzero shading, protected opaque/partial samples and visible subject on every image edge. Assert native interior exact, border from backdrop alone, arrays unchanged, and no call to background generation/model inference. Never use the framing implementation to calculate its own expected borders.
- [ ] **Run the Task 1 suite to green** with the same command. Passing means exact assertions, not just image shape. Update design only for verified contract issues; do not weaken assertions.

### Task 2: Source-bound preset and immutable framed exports

**Files:** Modify `framing.py`, `export.py`, `cli.py`, `tests/test_framing.py`, `docs/file-contract.md`, `docs/troubleshooting.md`.

**Consumes:** Task 1 geometry/raster interfaces; existing `_root`, `_asset`, `_atomic_json`, `project_lock`, `check_space`, `read_project`, `read_revision`, `saved_layers`, `saved_shading`, `read_background`, `render_black`, `render_background`, `view_rgba`, `write_master`, `publish_artifacts`.

**Produces:**

- `read_framing_preset(project: Path, source_id: str, source_size: tuple[int, int]) -> tuple[Margins, str | None]`: absent returns zero margins and null digest, no writes. Validate schema/identity/dimensions before returning; digest exact saved bytes.
- `save_framing_preset(project: Path, value: dict[str, object], *, expected_digest: str | None, expected_source_id: str) -> dict[str, object]`: own project lock; derive current dimensions from canonical source; CAS, safe atomic write, return margins/digest. The payload is margin fields only; server builds trusted identity/schema envelope.
- Extend `export_project(project: Path, *, revision: str | None = None, draft: bool = False, framing: dict[str, int] | None = None, framed_transparent: bool = False) -> dict[str, Any]`. Reject transparent flag without explicit framing. No implicit preset lookup in existing exports. Preserve the omitted-framing path exactly.
- CLI flags are proposed new interfaces, not available commands yet: `export PROJECT --margins LEFT RIGHT TOP BOTTOM [--framed-transparent]`, retaining existing `--revision`/`--draft` behavior.

- [ ] **Write failing persistence/export tests.** Names: `test_missing_preset_is_read_only_zero`, `test_preset_cas_and_source_binding`, `test_corrupt_or_symlinked_preset_leaves_native_work_usable`, `test_framed_export_roundtrip_identity_and_variants`, `test_framing_preserves_native_export_files_and_digests`, `test_framed_export_replay_without_models_or_original_capture`, `test_framed_export_low_disk_stale_and_publish_failure`, `test_cli_margin_order_and_explicit_opt_in`. Reuse `tests/test_background.py:legacy_project`, `background_request` and established synthetic helpers; no private photos or inference fixtures.
- [ ] **Run red check** with the Task 1 command, now including the added tests; confirm each new behavior fails for the intended reason.
- [ ] **Implement preset persistence.** Use existing lock/atomic/path helpers; strict schema and SHA-256 CAS under lock including missing-file race. Preserve native state/recipe/guidance/revision hashes before/after save. Reset is explicit save of four zeros, never file deletion. Preset corruption cannot break unrelated state loading/export; expose it independently in Task 3. Do not silently overwrite malformed or foreign presets.
- [ ] **Implement framed export as an opt-in branch of the canonical owner.** Reuse existing source/revision/acceptance/stale-effect validations, render native selected pixels once, frame via Task 1 and write only the compact requested delivery. Canonical identity object includes source/revision manifest digest, margins, selected variants, algorithm and encoding; use its full SHA-256 in `exports/<revision[-DRAFT]>-framed-<digest>`. If migrated export selection exists, integrate this identity there instead of creating a parallel scheme. Construct/revalidate under the project lock; do not re-enter the lock through nested helpers.
- [ ] **Bind exact evidence and replay.** Manifest records all fields in the design, per-file dimensions/precision/hashes, exact native-to-output translation and native asset references/identities. Frame/result reconstruction reads native saved layers plus recorded margins, never a saved preset that may have changed. Native layer exports are explicitly a separate action. Source accepted status and framing acceptance wording remain distinct. All-zero framed delivery retains exact native decoded pixels while omitted framing retains the old file set/manifest bytes/destination.
- [ ] **Implement preflight and collision handling.** Check output bounds before allocation/staging; call `check_space` with current native budget plus `16 * output_pixels + 1024**2`, retaining its reserve. Verify an existing matching complete delivery's manifest/expected file set/hashes before reuse; corrupted/extra/missing/symlinked members fail. Different geometry/variants cannot overwrite prior output. Recheck source/revision state before publication; preserve errors/staging under current policy. Tests interrupt before/during publish and simulate source/revision changes without mutating accepted data.
- [ ] **Add real two-process save/lock test**, using existing project-lock testing patterns. One client holding the writer lock makes the other fail busy; two saves with the same prior digest produce one success and one stale error. Test atomic-write failures both before replacement and after replacement during directory sync. Before replacement, prior preset bytes survive; afterward, re-read actual bytes/digest and report visible state with durability unconfirmed, preserving form edits and requiring reload before another CAS save. Do not claim rollback or automatically restore/delete the visible preset. Photo pointers remain unchanged in both phases. Tests must not rely only on mocked locking.
- [ ] **Wire CLI flags** to the same export interface, validate argument order, and document preset schema, error recovery, separate compact presentation bundle, acceptance label, zero/absent behavior and immutable export identities in canonical docs.
- [ ] **Run Task 2 checks:** `rtk proxy .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_framing.py tests/test_background.py tests/test_cli.py`. Expect all selected deterministic tests to pass; no inference/download. Record actual selected count/failures. Test replay after removing only test-owned cache/source availability; never delete user data.

### Task 3: Accessible manual framing control and honest preview

**Files:** Modify `viewer.py`, `ui/review.html`, `tests/test_viewer.py`, `tests/test_viewer_page.py`, `tests/test_framing.py`, `README.md`, `docs/workflow.md`, `docs/assistant-workflow.md`.

**Consumes:** Task 1/2 APIs; existing local server origin/token guards, action serialization, `snapshot`, `execute`, native renderers and form dirty-state/polling conventions.

**Produces:**

- Snapshot fields `framing` (canonical margins or null on error), `framing_digest` (null for absent), and `framing_error`; keep native `dimensions_wh` unchanged. Every relevant snapshot revision entry also gains `revision_manifest_sha256`, computed from exact validated persisted manifest bytes and distinguished from `draft_digest`. Validate/hash the same bytes and reject a changed snapshot rather than pairing identities from different reads.
- `framing-save` action with margins and expected preset digest plus existing viewer identity envelope, routed to `save_framing_preset`. No direct file paths from client input.
- `POST /api/framing-preview` with exact source identity, selected revision, revision-manifest digest from the snapshot and canonical margins. Return JSON with `png_base64` (PNG8 bytes, no data-URL prefix) plus output/source/display dimensions, source rectangle, selected identities, and canonical layout. Decode base64 locally to a `Uint8Array`, construct a PNG `Blob` and pass it to `createImageBitmap`; do not assign/fetch a data URL or change CSP. Close replaced or stale bitmaps. This read-only route uses the same host/origin/session authorization and request-size validation as existing routes. Reject stale enabled effects; do not silently display a BASE view as the requested final result. Validate that saved inputs remain unchanged before response. Guard rendering with one nonblocking per-server preview lock: a competing request gets busy before allocation; every completion/error/disconnect releases the guard. No queue or new worker subsystem.
- Existing `export` action gains optional explicit framing/transparent fields, validated and passed to Task 2; native payload without these fields stays unchanged.

- [ ] **Write failing HTTP/UI tests.** `test_framing_preview_requires_current_authenticated_identity`, `test_framing_save_is_independent_of_native_authoring`, `test_framing_preview_response_order_and_dirty_polling`, `test_margin_buttons_and_keyboard_export_state`, `test_framing_preview_does_not_accept_source_or_layout`, `test_native_coordinates_unchanged_with_framing`, `test_framing_preview_bounds_concurrent_rendering`. Reuse actual `ReviewServer` HTTP test harness and Node page tests; assert controls/actions and resulting state, not just source strings. Build the preview request from an actual snapshot revision entry; never manufacture the required digest in the test. Assert snapshot → request → response identity, local base64-to-Blob decoding, stale/replaced bitmap closure, and lock release after rendering/transport failures.
- [ ] **Run red checks:** `rtk proxy .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_framing.py tests/test_viewer.py tests/test_viewer_page.py tests/test_viewer_coordinates.py`. Confirm intended new-API failures, preserving existing failures as blockers.
- [ ] **Implement snapshot/actions/preview** through the shared APIs. Never let corrupt preset metadata break native workflows. Retain explicit accepted/draft authorization and exact request schemas. Test unsupported keys, foreign Origin/Host/token, stale revision, malformed bodies, oversized dimensions and symlinked presets. Preview is bounded/read-only and cannot reserve a processing operation or publish a revision.
- [ ] **Implement the spec's form and separate preview.** Keep a dedicated `framingDirty` flag and monotonic request sequence. Polls/revision changes must not replace unsaved fields. Centre image uses `left=floor((left+right)/2)` and remainder Right, analogous Top/Bottom; Set all sides and Reset are local draft actions. Preview responses must match request sequence, selected revision/manifest/source and current margins before display; source changes invalidate preset and preview. No edits/guide transforms attach to the preview.
- [ ] **Handle write lifecycle and user feedback.** Save success updates framing digest/status only. Busy/stale/invalid responses preserve local fields and offer Reload saved margins. Explicit export uses visible fields even if unsaved, with clear status. Reload clears only framing form state. Unsaved native guidance/effect drafts remain byte-identical and retain their UI dirty indicators. Display pixel units/output dimensions, RGB8-preview label and the limitation about already-cut-off subjects.
- [ ] **Update user/assistant docs in this task.** Explain adding equal space, moving via asymmetric margins, centre-image semantics, saving/reloading, compact framed exports and original-size native editing. Give native versus framed coordinate examples; never use a framed preview to author repair boxes. Describe nonuniform edge bands honestly. CLI examples are marked supported only after their tests pass.
- [ ] **Run Task 3 checks to green** with the red-check command, then perform native browser checks on a small synthetic project under the server's actual unchanged CSP headers: framing bitmap genuinely displays; keyboard-only all fields/buttons; repeat save/reload; rejected stale second client; two preview responses arriving out of order; unsaved effect draft survives polling/export; browser resize/zoom never changes margins. Open real native view afterward and place a known guide at its original coordinate. The Node harness does not enforce CSP. Record observed behavior separately from Node/HTTP evidence.

## Settled-batch verification and handoff

- [ ] Do one focused requirements/DRY/consumer pass: every design requirement maps above; one geometry/preset owner, one renderer, one export publisher; no recipe/native coordinate or shared-asset regression; no unrelated refactor or implementation/gate advancement.
- [ ] Run the complete relevant deterministic suite once after the settled batch: `rtk proxy .venv/bin/python -m pytest -q -p no:cacheprovider -m 'not integration'`. Existing tests mark real inference separately; inspect selected tests/markers and avoid externally configured model downloads. Do not run real-model integration just to test framing.
- [ ] Run `rtk proxy .venv/bin/ruff check src tests --no-cache`, `rtk proxy .venv/bin/ruff format --check src tests --no-cache`, and `rtk proxy .venv/bin/mypy src`. Check UI syntax with the existing Node-driven tests. Record actual exits/counts and limitations; do not repeat successful checks on unchanged inputs.
- [ ] Inspect actual RGB16/PNG exports and manifest dimensions/hashes from synthetic fixtures. Compare native crops byte-for-byte; review edge bands on varied backgrounds and zero-alpha outer margins, no anatomy replication, no source metadata leakage. Measure representative export peak memory/time and confirm the conservative preflight budget; no unsupported performance promise.
- [ ] Obtain one fresh bounded independent implementation review after implementation authorization, scoped to the settled diff and these contracts. No repeat review of unchanged work; fix material defects only and renew affected checks.
- [ ] Present a local example for explicit human photographic acceptance only after the user authorizes the source/project; retain synthetic-only evidence otherwise. Human acceptance cannot be inferred from tests or independent code review.
- [ ] Report exact changed files, tests/static/browser evidence and outstanding human/design questions. No commit/push/PR, deletion, install/download, controller message or external review transfer follows from this plan.

## Planning disposition

This plan is authored with Superpowers brainstorming/writing-plans and is to receive one independent review in a fresh context. Author self-review checks requirement coverage, type/signature consistency, failure-mode coverage and proportion before dispatch. Review findings and dispositions are saved beside this plan. Passing plan review proves only that the proposal was examined; it does not prove runtime correctness or authorize implementation.
