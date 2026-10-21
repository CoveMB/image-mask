# Fixed-size Series Framing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with the existing persistent implementation owner. The user's selected execution method overrides fresh-implementer-per-task routing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Frame differently shaped saved subjects within identical output dimensions, with reusable portable settings and a documented offline manual workflow.

**Architecture:** Add presentation-only series settings/layout/resampling beside existing exact-padding framing. Extend the existing compact presentation export path and viewer, retaining canonical saved-layer validation, writer locking, source/revision binding, round-trip checks and exclusive publication. Keep native editing assets and acceptance unchanged.

**Tech Stack:** Python >=3.12,<3.13, NumPy 2.3.5, Pillow 13.0.0 scalar F/Lanczos, tifffile 2026.10.15, existing HTML/JavaScript, pytest, Node, Ruff and mypy; no new dependency or model.

**Spec:** [Approved fixed-size series framing design](../specs/2026-10-20-series-framing-design.md), read together with [design-review and predecessor reconciliation](2026-10-20-series-framing-review.md). The user approved the written design and final documentation coverage, then approved this detailed plan on 2026-10-21 with intermediate gates preapproved and an explicit request to finish and create the MR for review.

## Global Constraints

- Presentation only: originals, native masters, masks, guides, effects, coordinates, working/accepted pointers and existing native/Add margins deliveries retain their contracts.
- Fixed output width/height; positive-alpha bounds include every alpha > 0 pixel; no outlier removal, rotations, anatomy detection, generative detail or batch processing.
- One continuous uniform pixel-edge transform; integer rectangles are support envelopes, never a second scale.
- Side and minimum vertical margins are each 0.0–45.0%, in 0.1% steps; first-use defaults are editable 4000 × 5000, 15.0% on each side and 5.0% on each vertical side, not user-selected production values.
- Retain 32768 pixels per output axis, 100000000 output pixels and the existing 10 GiB free-disk reserve plus pending writes. Disk admission is not a RAM guarantee.
- Portable settings-only JSON; explicit project save/reload; no global catalog, arbitrary server-side file paths, silent migration or autosave.
- Regenerate the validated saved backdrop recipe at output dimensions, including beneath partial-alpha edges; legacy revisions use black. Native saved background pixels stay authoritative for native operations and are not rewritten.
- Same geometry/filter for premultiplied colour and alpha; finite values, alpha clamped first, contribution jointly bounded to 65535*alpha; straight RGBA8 has zero RGB wherever quantized alpha is zero.
- Every viewer series preview/export request binds its selected complete revision/master/raw manifest identity and visible settings; draft remains DRAFT, and accepted export requires that exact selection still be accepted.
- Keep existing CSP, meaningful labels, keyboard and non-drag numeric operation, bounded concurrent rendering and explicit stale/recovery status.
- One orchestrator, existing persistent implementation owner, sequential writers and configured model defaults. No controller, ledger, scheduler, recursive fan-out or unsolicited review layers.
- The 2026-10-21 execution approval authorizes necessary local implementation/verification, intermediate checkpoints, commits, pushing this feature branch and creating its MR for the user's review. It does not authorize merging the MR, unrelated publication/actions, downloads or private-photo evaluation. Preserve ignored data, historical branches and other worktrees.

## Review Focus

These concrete risks receive tests in the owning tasks:

1. Unicode names, duplicate JSON keys, oversized UTF-8 and bool-as-int input must fail or round-trip consistently without HTML/path interpretation (Tasks 1, 4, 5, 6).
2. Source-edge singleton/tip masks and large source offsets must retain continuous layout and complete zero support, despite Pillow float32 boxes/crop optimizations (Tasks 1–2).
3. Selected, working and accepted revisions may all differ, or acceptance may change while an action waits; never export a substituted target (Tasks 3, 5–6).
4. Raw-byte CAS changes and post-replace/post-publication failures must preserve edits, prior deliveries and recoverable stages with accurate status (Tasks 3–6).
5. Tiny reductions and maximum output bounds can hide large coefficient/scratch requirements; reject unsafe shapes before expanded allocation, and measure representative resources (Tasks 2–3, 6).

---

## Baseline, ownership and execution evidence

Work in the repository checkout on `series-framing`, created from reconciled `main` at `14e8c83fa3b5a7603c5c240eb96a0081702da0f5`. Remote refs were not refreshed. Repair `2a6029d` is included through `ee9a3d1`; its four files and 44 full-suite input hashes matched. Its 699 passes/3 optional model-cache skips are inherited framing evidence, not series results. Do not repeat that unchanged baseline suite merely to start.

The current checkout has no `.venv`. The task-specific interpreter, referenced below as `$series_python`, was inspected: Python 3.12.14 ARM64, matching Pillow/NumPy/tifffile pins, Ruff and mypy available. Commands below explicitly set `PYTHONPATH=src` so application imports resolve to this checkout. Set `series_python` to that already-verified local interpreter and revalidate it before execution; exact host paths belong only in ignored local evidence. If unavailable or inconsistent, stop for environment authority rather than install/download silently.

Root owns planning documents until handoff. `/root/series_implementation_owner` then owns all implementation/test/documentation/progress writes; root remains read-only while that owner writes. Reuse this owner with follow-up tasks. Final independent reviewers are read-only, with no recursive delegation.

Every Run command and new API/test/CLI name below is an implementation proposal until its task is implemented and verified. Use offline environment variables for tests; unset real model-cache variables as existing synthetic tests require. Preserve raw stdout/stderr for long checks in unique ignored `local/series-framing/` or fresh temporary evidence storage. Record the underlying exit code, warnings/skips, counts and absolute log path; no filter/logger success may hide command failure. Do not run the preserved experimental `run_check.py` unchanged or overwrite older evidence.

| File | Owned change |
| --- | --- |
| New `src/blackmask/series_framing.py` | Settings/portable parser, bounds/layout, bounded sampling, rendering, resource estimates and source-bound preset persistence |
| `src/blackmask/framing.py` | Share only presentation output-size validation; retain existing exact padding, preset schema and error compatibility |
| `src/blackmask/background.py` | Shared canonical field/statistics logic and sampled full-grid backdrop; unchanged native generator bytes |
| `src/blackmask/export.py` | Add series mode inside the existing compact presentation path; reuse contribution, raster/hash validation and safe publication |
| `src/blackmask/cli.py` | Explicit `--series-preset PATH`, exclusive with `--margins`; existing revision/draft rules |
| `src/blackmask/viewer.py` | Independent series state/error, bounded parse/preview routes, save/export actions and identity validation |
| `src/blackmask/ui/review.html` | Mode-specific form/state/actions, portable load/download and selected-revision preview/export |
| New `tests/test_series_framing.py` | Observable settings/layout/render/export/persistence behavior and independent scalar oracles |
| Existing `tests/test_background.py`, `test_cli.py`, `test_viewer.py`, `test_viewer_page.py` | Canonical backdrop, CLI, HTTP and shipped-handler regressions; reuse existing synthetic fixtures/harnesses |
| `README.md`, `docs/workflow.md`, `docs/file-contract.md`, `docs/troubleshooting.md`, `docs/validation.md` | Supported controls/workflow, normative JSON/delivery contracts, recovery and actual evidence |

Do not split unrelated existing modules, introduce a generic renderer/store, change package configuration, or add runtime dependencies on these plans.

## Checkpoint 1 — Precise layout, resampling and reproducible exports

Execution pre-flight: Task 1 settings/layout feed Tasks 2–4; Task 2 sampling/backdrop feeds export and preview; Task 3 explicit revision/identity export feeds Task 5; Task 4 raw CAS feeds Tasks 5–6; Task 5 transport shapes feed Task 6. Interfaces reconcile without conflict. The direct user method supersedes separate skill workspace/ledger scripts and Git steps; progress remains here and root owns final Git actions.

Ruling: routine file round-trip/failure/two-photo fixtures use small output dimensions (for example 40×50); production defaults remain 4000×5000 and the representative default-size export is measured once in Task 6. This preserves contracts while avoiding repeated large allocations; cost if wrong is inadequate large-size evidence, addressed by the required measured run.

Task 1 complete: focused RED failed at the absent module (exit 2); GREEN passed 14 tests (exit 0); existing framing geometry/limit selection passed 31 tests, 52 deselected (exit 0). Raw output and input hashes are retained under ignored `local/series-framing/` in `1792595101630809000-task1-red`, `1792595179535660000-task1-green` and `1792595184968582000-task1-framing` log/JSON pairs. Inputs were unchanged during each command. No Git writes.

### Task 1: Strict settings and continuous subject layout

**Files:** Create `src/blackmask/series_framing.py`, `tests/test_series_framing.py`; modify only shared output-size validation in `src/blackmask/framing.py`.

**Interfaces:**

- Frozen `SeriesSettings` fields: `name: str`, `output_width_px: int`, `output_height_px: int`, `side_margin_tenths_percent: int`, `minimum_vertical_margin_tenths_percent: int`; `to_dict() -> dict[str, object]` returns exactly these fields.
- `validate_series_settings(value: object) -> SeriesSettings` accepts exactly that object shape; revalidate direct dataclass instances at render/export boundaries too.
- Extract `framing.validate_presentation_size(size: tuple[int, int]) -> tuple[int, int]` for strict positive integer width/height and the existing 32768/100000000 output caps; call it from existing margins validation and series settings. Preserve current margin/source validation and bound-error compatibility rather than duplicate the shared limits.
- `parse_series_preset(raw: bytes) -> SeriesSettings`, `portable_series_preset(settings: SeriesSettings) -> bytes`, `read_series_preset_file(path: Path) -> SeriesSettings` own the portable envelope and bounded regular-file read.
- Frozen `SeriesLayout` exposes `subject_bounds_xyxy: tuple[int, int, int, int]`, `output_dimensions_wh: tuple[int, int]`, `scale: float`, `translation_xy: tuple[float, float]`, `transformed_subject_bounds_xyxy: tuple[float, float, float, float]`, `geometric_margins_lrtb_px: tuple[float, float, float, float]`, `fit_reason: Literal["side-margins-matched", "height-limited"]`, `source_edge_contact: bool`; `to_dict() -> dict[str, object]` supplies finite JSON geometry.
- `compute_series_layout(alpha16: np.ndarray, settings: SeriesSettings) -> SeriesLayout` validates a nonempty aligned scalar uint16 mask, scans bounds with bounded row scratch and returns the design's exact scale/translation.

Portable schema 1 is exactly this shape (the numbers are illustrative defaults):

```json
{
  "schema_version": 1,
  "kind": "series-framing-preset",
  "name": "Portrait series",
  "output_width_px": 4000,
  "output_height_px": 5000,
  "side_margin_tenths_percent": 150,
  "minimum_vertical_margin_tenths_percent": 50
}
```

`150` means 15.0% **on each side**; `50` means 5.0% on each vertical side. Both integer fields are in `[0,450]`. Bound raw portable/project metadata to 16384 bytes; read at most 16385. Reject extra/missing/duplicate keys, nonfinite constants, fractional/boolean integer fields, unsupported schema/kind and unsafe file types/symlink aliases. Names contain 1–80 Unicode code points and cannot be whitespace-only; preserve valid name text without using it as a path/HTML. Browser validation must count code points and UTF-8 bytes consistently. Serialize through the existing canonical JSON helper; portable files contain no source identity, image, mask, path or private metadata.

- [x] **Step 1: Add failing settings/layout tests.** Define `series_settings()` and a synthetic project helper by reusing `test_framing.protected_project`/existing test fixture conventions; no new fixture framework. Add `test_series_settings_strict_portable_round_trip`, `test_series_settings_rejects_ambiguous_json_and_unsafe_files`, `test_series_layout_width_height_and_fractional_geometry`, `test_series_layout_all_positive_alpha_and_empty_mask`. Assert exact portable keys/units; widths/heights/product limits before allocation; Unicode/bytes/duplicates/bools; every positive alpha including disconnected value 1; full/empty/source-edge masks; literal rectangle/insect/flower bounds.

```python
layout = compute_series_layout(np.full((1, 10000), 65535, np.uint16),
    series_settings(output_width_px=4000, output_height_px=5001,
                    side_margin_tenths_percent=0))
assert layout.scale == pytest.approx(0.4)
assert layout.transformed_subject_bounds_xyxy[3] - layout.transformed_subject_bounds_xyxy[1] == pytest.approx(0.4)
tall_layout = compute_series_layout(np.full((10000, 1), 65535, np.uint16),
    series_settings(output_width_px=4000, output_height_px=5001,
                    minimum_vertical_margin_tenths_percent=50))
assert tall_layout.geometric_margins_lrtb_px[2:] == pytest.approx((250.05, 250.05))
```

- [x] **Step 2: Demonstrate RED.** Run `rtk proxy env PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PIP_NO_INDEX=1 "$series_python" -m pytest tests/test_series_framing.py -k 'series_settings or series_layout' -q -p no:cacheprovider`; confirm failure is the absent new behavior, not a broken fixture/environment.
- [x] **Step 3: Implement the interfaces.** Use the spec's uniform scale and translations without independent dimension rounding. Bounds scanning must not allocate index arrays proportional to all positive pixels. Return side-match/height-limited status and source-edge contact; empty masks produce actionable errors. No mask edits, thresholding or outlier filtering.
- [x] **Step 4: Demonstrate GREEN with the same focused command.** Also run existing framing geometry/limits cases with `rtk proxy env PYTHONPATH=src "$series_python" -m pytest tests/test_framing.py -k 'geometry or limits or strict_margin or source_and_output' -q -p no:cacheprovider` after extracting shared validation. Inspect the local diff for requirement fit/DRY and record actual results here; no Git write.

### Task 2: Bounded premultiplied sampling and canonical backdrop

**Files:** `series_framing.py`, `background.py`, `test_series_framing.py`, `test_background.py`.

**Interfaces:** Consume Task 1 settings/layout and existing `export._foreground_contribution`. Produce `series_sampling_plan(layout: SeriesLayout, *, display_dimensions_wh: tuple[int, int] | None = None) -> SeriesSamplingPlan`, `estimate_series_resources(sampling: SeriesSamplingPlan, *, retained_native_bytes: int, transparent: bool) -> dict[str, int]`, and `render_series(foreground: np.ndarray, alpha16: np.ndarray, sampling: SeriesSamplingPlan, *, weight16: np.ndarray | None = None, opacity: float = 0, background_settings: dict[str, Any] | None = None, transparent: bool = False) -> np.ndarray`.

`SeriesSamplingPlan` owns the immutable full layout, display dimensions, clipped support envelope, per-axis ideal/effective boxes, pass order and allocation sizes; it is not persisted as a project schema. `render_series` returns composed RGB16, or straight RGBA8 when transparent. Both consume the same deterministic bounded contribution/alpha pair. `background.sample_background(shape: tuple[int, int], settings: dict[str, Any], display_dimensions_wh: tuple[int, int]) -> np.ndarray` returns selected canonical full-grid RGB16 pixels with no full output allocation.

**Sampling decisions pinned before code:**

For one axis with source positive-alpha core `[x0,x1)`, full transform `q=s*x+t` and output extent `N`, define `rho=3*max(1,s)`, `o0=max(0,floor(s*x0+t-rho))`, `o1=min(N,ceil(s*x1+t+rho))`. For this support envelope use:

```text
U=o1-o0; u0=(o0-t)/s-x0; u1=(o1-t)/s-x0
R=3*max(1,1/s)
L=floor(min(0,u0-R))-1; J=ceil(max(x1-x0,u1+R))+1
padded_extent=J-L; fractional_box=(u0-L,u1-L)
```

Place the core at offset `-L` in real transparent zero support. Compute actual float32 box endpoints/subtraction and their effective filter neighborhoods before allocation; expand the integer support if necessary, never truncate/renormalize at a tight core edge. Use explicit separable scalar F/Lanczos passes with `reducing_gap=None`, native strips of at most 64 rows/columns, and the pass order minimizing first-pass intermediate size. Transpose bounded strips when needed for the opposite order. Retain one scalar intermediate and filtered alpha, never three native float RGB planes or a padded 2D zero source. All four planes use exactly the same sampling plan. Exact `s==1` with integer translation bypasses F/filtering through bounded canonical float64 contribution/composition; do not treat a rounded near-identity box as identity.

For reduced display, calculate each axis's source mapping from its sample centres on the full output canvas, retain the full layout in status, and keep the long edge <=1600 without allocating the full output. Display integer-size rounding is an explicitly reduced-preview approximation, never a replacement output geometry.

Use an independent float64 scalar `sinc(z)*sinc(z/3)` oracle on the complete zero-extended integer lattice, normalized over all contributing samples. Its implementation must not call production sampling helpers/Pillow. Keep ideal coordinates and effective Pillow boxes separate. For full export, require effective centre drift <=1/64 **output** pixel per axis; the endpoint error is sufficient because spacing error is linear. Initial arithmetic targets versus the independent effective-box oracle are `rtol=0`, `atol=0.125` RGB16 contribution units and `atol=2e-6` alpha. These are predeclared verification targets, not measured results. Compare the ideal image separately using the scalar coefficient-difference bound `M*(||kxF-kxI||1*||kyF||1 + ||kxI||1*||kyF-kyI||1)`, plus measured arithmetic error. Never hide placement error by quantizing the ideal oracle. Failure blocks production integration: correct mapping/support or stop for a material design decision; do not widen tolerances or change filters silently.

Reject nonfinite outputs; clamp alpha to `[0,1]` first, then colour to `[0,65535*A]`. Compose `P+B*(1-A)` and quantize once with existing rounding. Unpremultiply only where A>0 for RGBA8, then zero RGB wherever quantized alpha is zero. Apply saved shading and alpha once through the existing contribution owner.

Resource estimates explicitly account for retained native arrays; RGB16 output `6*O`; filtered alpha `4*E`; scalar intermediate `4*I`; padded/returned strip transfer headroom `12*P*c` / `12*Q*c`; native contribution scratch conservatively `64*native_strip_pixels`; and coefficient storage `8*U*(K+1)`, `K=2*ceil(3*max(1,effective_spacing))+1`, plus unchanged-axis/allocator and row/encoding overhead. Here O is output pixels, E is support pixels, I is first-pass pixels, P/Q are strip axis extents and c<=64. Check Pillow int/coefficient arithmetic and NumPy/Python allocation bounds before allocations. Do not invent a new global RAM limit or lower output/precision limits silently. RGB16 alone is 600 MB at the existing 100-million-pixel ceiling; estimates and bounded scratch are not a RAM guarantee.

- [x] **Step 1: Add failing precision/support/backdrop tests.** Add `test_series_sampling_scalar_oracles_and_phase`, `test_series_sampling_zero_extended_edges_singletons_and_identity`, `test_series_sampling_bounds_alpha_and_rgba`, `test_series_resource_estimate_precedes_large_allocation`; parameterize noninteger reduction/enlargement, large source offsets, near-identity boxes, hidden saturated RGB, non-257 RGB16, genuine negative lobes, partial-alpha contrasting edges and nonblack composites. Assert the targets above, finite/joint bounds, quantized zero-alpha RGB and source-byte preservation. For backdrop add `test_sampled_background_matches_full_grid_without_full_output_allocation`: vary colour/variation, odd output/display sizes, black/constant and singleton axes; compare literal selected pixels of `make_background`.

```python
np.testing.assert_allclose(actual_contribution, effective_scalar_contribution, rtol=0, atol=0.125)
np.testing.assert_allclose(actual_alpha, effective_scalar_alpha, rtol=0, atol=2e-6)
assert maximum_output_phase_error <= 1 / 64
assert np.all((bounded_contribution >= 0) & (bounded_contribution <= 65535 * bounded_alpha[..., None]))
assert not rgba[rgba[..., 3] == 0, :3].any()
np.testing.assert_array_equal(sampled_background, full_background[np.ix_(sample_y, sample_x)])
```
- [x] **Step 2: Run RED** with `rtk proxy env PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PIP_NO_INDEX=1 "$series_python" -m pytest tests/test_series_framing.py tests/test_background.py -k 'series_sampling or series_resource or sampled_background' -q -p no:cacheprovider`.
- [x] **Step 3: Implement bounded sampling and prove the oracle targets before export integration.** Release Pillow images and temporary buffers on success/failure. Begin composed output with the canonical generated backdrop and update bounded regions in place; recompute deterministic colour planes for a later transparent variant rather than retaining three full float planes.
- [x] **Step 4: Factor one canonical background field/statistics/encoding owner.** Preserve full requested grid width, 64-row chunks, each row's float64 reduction order and `math.fsum` row order. Preview chooses full-grid pixel indices after that full-grid statistics pass; it never normalizes on its display grid. Keep legacy/constant fast paths and existing native generator bytes; no regeneration in `read_background`.
- [x] **Step 5: Run GREEN** with the same focused command, then the unchanged existing background tests if not already exercised. Record numerical/phase results and estimated buffers; unresolved target failures stop this checkpoint. No Git write.

### Task 3: Canonical series delivery and usable CLI

Task 2 complete: initial missing-API RED exited 2. The first GREEN attempt caught a fixture whose requested canvas clipped off the negative lobe; widening that synthetic canvas's margins retained the actual negative-lobe assertion. An added scratch regression then failed on full-envelope alpha quantization (exit 1), which was corrected to bounded rows. Existing background behavior passed in the coherent contracts run; its sole failure was an additional arbitrary ideal-image threshold, replaced by the approved independent coefficient-difference bound rather than widening arithmetic/phase tolerances. Final focused sampling/backdrop check passed 13 tests, 56 deselected (exit 0), raw evidence `local/series-framing/1792595713935647000-task2-oracles-green.{log,json}`. Maximum measured errors: contribution 0.001166732 RGB16 units, alpha 2.918983e-8, phase 1.760276e-6 output pixels. Targets remain 0.125 / 2e-6 / 1/64. All check input hashes were unchanged; no Git writes.

**Files:** `export.py`, `cli.py`, `test_series_framing.py`, `test_cli.py`; retain existing `test_framing.py` protection.

**Interfaces:** Extend `export_project` with keyword-only `series: dict[str, object] | None = None`, `expected_master_id: str | None = None`, `expected_revision_manifest_sha256: str | None = None`; keep every existing argument/default. Expectations are an all-or-neither pair for series calls; viewer always supplies both. CLI may omit them and captures its selected revision atomically under the existing writer lock. `framed_transparent` supports either explicit margins or explicit series settings; it still fails without either. `series` and `framing` are mutually exclusive.

Reuse `_export_framed`'s source/manifest snapshot, compact variant writing/readback, `_pixel_digest`, `_write_framed_rgb8`, `_verify_framed_png`, `_check_flat_delivery` and repaired publication/reuse path. Add a series-specific render/record branch inside that owner; do not copy the native or compact publication pipeline. Preserve existing margin/native manifest bytes and identities. Select the exact requested revision under lock, validate expected identities immediately and immediately before publication, and recheck the accepted pointer for accepted series delivery. Draft always stays DRAFT.

Use kind `series-framed-presentation`, schema 1, algorithm `series-lanczos-premultiplied-v1`, backend/version/rounding policy, full settings/layout/support, source/raw revision/effect/background identities, encoding and variants in the immutable record. Keep only relative native asset references, with no capture paths or private metadata. Directory: `exports/<revision[-DRAFT]>-series-framed-<full-sha256>/`. Members are `result_rgb16.tif`, `result_RGB8_VIEW.png`, optional `transparent_RGBA8_VIEW.png`, `README.txt`, `manifest.json`. Notes label resized presentation, enlargement, saved backdrop regeneration and absent separate photographic acceptance. Bind identity to validated semantic settings, not portable-file whitespace.

CLI: `export PROJECT --series-preset PATH [--framed-transparent] [--revision REV --draft]`; argparse makes `--series-preset` exclusive with `--margins`. Parse a bounded non-symlink regular file, not a server path. Retain the existing accepted/default and explicit-draft rules. Do not read project series settings implicitly when the flag is absent.

- [x] **Step 1: Add failing export/CLI tests.** Add `test_series_export_round_trip_identity_and_preservation`, `test_series_export_selected_revision_expected_identity`, `test_series_export_failures_reuse_and_recovery`, and `test_series_cli_saved_only_replay_and_exclusive_modes`. Read actual RGB16 TIFF, RGB8 and RGBA8 PNG, profiles, manifest and notes. Assert settings/layout/output size; non-257 samples; project/native/Add margins and earlier delivery hashes unchanged; exact repeated reuse; optional variant identity; DRAFT for accepted selection when explicitly drafted. Use selected != working != accepted and changed master/raw manifest/acceptance at lock acquisition and prepublication.

```python
record = json.loads(Path(output["manifest_file"]).read_bytes())
assert record["kind"] == "series-framed-presentation"
assert record["revision"] == selected_revision
assert record["settings"] == settings.to_dict()
assert tifffile.imread(Path(output["directory"]) / "result_rgb16.tif").shape == (5000, 4000, 3)
assert record["draft"] is True  # explicit draft stays draft even for an accepted selection
assert native_hashes_after == native_hashes_before
```
- [x] **Step 2: Demonstrate RED** using `rtk proxy env PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PIP_NO_INDEX=1 "$series_python" -m pytest tests/test_series_framing.py tests/test_cli.py -k 'series_export or series_cli' -q -p no:cacheprovider`.
- [x] **Step 3: Implement the shared export branch and CLI.** Admission includes the Task 2 estimates, existing native pending-write allowance, variants/readback and 10 GiB reserve before expanded allocation/staging. Validate the saved backdrop/settings/algorithm and reject stale enabled effects rather than using BASE. Sequence output release/readback/variants. Capture and recheck the exact validated input bytes; do not change acceptance.
- [x] **Step 4: Exercise failure behavior before marking usable.** Cover allocation/disk refusal, busy lock, interrupted writer, corrupt/missing/extra/symlinked collisions, raster readback mismatch, source/revision changes and sync/partial-cleanup failures. A retry removes only its verified duplicate after durable publication; earlier failed stages and prior usable deliveries remain. In a fresh process, make only the synthetic original capture/model caches unavailable and reconstruct from saved assets; do not touch private originals.
- [x] **Step 5: Run GREEN and checkpoint regression.** Run `rtk proxy env PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PIP_NO_INDEX=1 "$series_python" -m pytest tests/test_series_framing.py tests/test_framing.py tests/test_cli.py tests/test_background.py -q -p no:cacheprovider`. Record actual counts/exit/skips. Checkpoint 1 is usable only when these application paths pass; no full-suite rerun yet and no Git write.

## Checkpoint 2 — Portable reuse, persistence and recovery

Checkpoint 1 complete: all 170 series/framing/CLI/background tests passed, exit 0, with unchanged captured inputs; raw evidence `local/series-framing/1792596003246821000-checkpoint1.{log,json}`. Task 3 RED produced nine expected absent-interface/flag failures; focused GREEN passed nine tests. A further pre-staging admission RED caught a recoverable stage being created before estimator rejection; moved the estimator before staging, then the complete checkpoint passed. Existing native/Add margins, publication-reuse cleanup and background tests remained green. No skips, model downloads, private photos or Git writes.

### Task 4: Source-bound project settings and portable reuse

**Files:** `series_framing.py`, `test_series_framing.py`; consume Task 1 parser and Task 3 export.

**Interfaces:** `read_series_settings(project: Path, source_id: str, source_size: tuple[int, int]) -> tuple[SeriesSettings, str | None]`; `save_series_settings(project: Path, value: dict[str, object], *, expected_digest: str | None, expected_source_id: str) -> dict[str, object]`; `SeriesSaveUncertain(ProjectError)` exposes `.visible` with `series_settings`, `series_digest`, `series_reload_required: True`.

Project `series-framing.json` contains exactly `schema_version: 1`, `master_id`, `source_dimensions_wh: [width,height]`, `settings: <SeriesSettings.to_dict()>`. Reuse the existing project lock, bounded raw-byte digest CAS, `_atomic_json` and source-before-publication validation pattern. Absence gives in-memory defaults/null digest without a file. Saving unchanged valid settings preserves exact bytes. Invalid metadata stays preserved and disables only the affected series save/reload flow. A portable file is independent of every saved photo snapshot and existing export.

- [x] **Step 1: Add failing persistence tests.** Add `test_series_settings_save_raw_cas_and_native_preservation`, `test_series_settings_two_process_lock_and_uncertain_write`, `test_series_portable_reuse_two_photos_independent_snapshots`. Assert invalid/oversized/unknown/foreign/symlink files are preserved; semantically equal external byte rewrites cause stale CAS; at most one same-digest two-process save wins; no source/recipe/revision/pointer/cache changes. Shared portable settings yield identical output dimensions on differently shaped subjects. Later portable edits change neither saved photo snapshot nor prior exports.

```python
assert first_export["output_dimensions_wh"] == second_export["output_dimensions_wh"] == [4000, 5000]
assert first_project_preset_after_portable_edit == first_project_preset_before
assert second_project_preset_after_portable_edit == second_project_preset_before
assert uncertain.visible["series_reload_required"] is True
assert uncertain.visible["series_digest"] == hashlib.sha256(visible_preset_bytes).hexdigest()
```
- [x] **Step 2: Run RED** using `rtk proxy env PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PIP_NO_INDEX=1 "$series_python" -m pytest tests/test_series_framing.py -k 'series_settings_save or series_settings_two_process or series_portable_reuse' -q -p no:cacheprovider`.
- [x] **Step 3: Implement explicit save/read and accurate recovery.** Failures before replace retain old bytes. If post-replace durability is uncertain, reread actual visible settings/digest where possible, retain form edits and require explicit reload before another save; do not claim rollback. Source identity and raw preset bytes are checked under lock and before publication. Do not widen the strict project-state schema.
- [x] **Step 4: Run GREEN** with the same focused command. Include failure injection both before and after replacement and independent process contention. Record checkpoint 2 evidence here; no repeated checkpoint 1 suite unless its inputs changed, no Git write.

## Checkpoint 3 — Viewer, browser verification and maintained documentation

Checkpoint 2 complete: three focused persistence/reuse tests passed, exit 0, 33 deselected, unchanged captured inputs. They cover raw-byte CAS, invalid metadata preservation, two real competing processes (exactly one same-digest save succeeds), pre/post-replace errors with observed visible digest/reload-required state, and independent saved snapshots/exports for differently shaped synthetic projects. Raw evidence: `local/series-framing/1792596226316476000-checkpoint2.{log,json}`; RED: `1792596179154258000-task4-red.{log,json}`. No unchanged checkpoint 1 rerun or Git write.

### Task 5: Authenticated preview/import/save/export contracts

**Files:** `viewer.py`, `test_viewer.py`; consume Tasks 1–4.

**Interfaces:** Snapshot fields `series_settings`, `series_digest`, `series_error` remain independent of existing framing/native state. Add `POST /api/series-preset-validate` with exactly `{preset_json: str}`; parse bounded UTF-8 bytes through Task 1 and return `{settings, preset_json}` with validated settings/canonical portable text, never a path. Add `POST /api/series-preview` with exactly `{master_id, revision, revision_manifest_sha256, settings}`; response echoes those fields plus full layout, display dimensions, algorithms, reduced-preview label and `png_base64`.

Add actions `series-save` (`settings`, `expected_digest`) and `series-export` (`revision`, `draft`, `revision_manifest_sha256`, `settings`, `transparent`) alongside the existing common action identity fields. Both use existing action machinery; save calls the canonical source-CAS owner, export calls Task 3 with explicit master/manifest expectations. Validate boolean/shape/types. Never derive a series target from `working_revision`/`accepted_revision` when an explicit selection was supplied.

Share the existing nonblocking framing render guard across both preview modes; no second expensive concurrent queue. Use existing token/origin/content-type/body-size guards and production CSP. Preview captures/revalidates source/state/raw revision and selected saved-layer identities before/after rendering and writes no project state. Unsupported backdrop algorithm/stale enabled effects block instead of falling back. Release guard and images/buffers on error/disconnect.

- [x] **Step 1: Add failing HTTP/action tests.** Add `test_series_http_validation_preview_and_independent_errors`, `test_series_preview_busy_disconnect_and_identity_races`, `test_series_actions_bind_selected_revision_and_preserve_other_drafts`. Exercise token/origin/extra-field/byte bounds, invalid portable content, no path endpoint, two clients, delayed preview, changed raw manifests/master/acceptance, stale enabled effects, selected != working != accepted and independent invalid project presets.

```python
assert preview_result["revision"] == request["revision"]
assert preview_result["revision_manifest_sha256"] == request["revision_manifest_sha256"]
assert preview_result["settings"] == request["settings"]
assert changed_manifest_status == 409
assert "img-src 'self' blob:" in response_headers["Content-Security-Policy"]
assert source_recipe_and_revision_hashes_after == source_recipe_and_revision_hashes_before
```
- [x] **Step 2: Run RED** using `rtk proxy env PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PIP_NO_INDEX=1 "$series_python" -m pytest tests/test_viewer.py -k series -q -p no:cacheprovider`.
- [x] **Step 3: Implement only the series interfaces above.** Bind body values to validated saved data under canonical locks and at prepublication; retain current Add margins handlers/semantics. Keep import validation read-only and bounded, and unrelated dirty forms unsaved.
- [x] **Step 4: Run GREEN and direct-consumer regression** using `rtk proxy env PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PIP_NO_INDEX=1 "$series_python" -m pytest tests/test_viewer.py tests/test_series_framing.py -q -p no:cacheprovider`. Record counts, status and scope without treating HTTP tests as browser evidence; no Git write.

Task 5 complete: initial HTTP/action RED had three expected failures; focused GREEN passed 3 tests, 35 deselected (exit 0). The subsequent connected viewer/series/shipped-page regression passed 144 tests (exit 0; 35.26 seconds), with unchanged captured inputs. Raw evidence: `local/series-framing/1792596422463223000-task5-green.{log,json}` and `1792596908826041000-viewer-series-handler-regression.{log,json}`. These are HTTP/handler results, not actual browser evidence.

Task 6 implementation progress: all four new shipped-handler cases failed before implementation, then passed (4 passed, 66 deselected, exit 0). The connected 144-test regression includes the complete shipped-page suite. Targeted mypy passed the six changed source files after correcting eight initial diagnostics; initial changed-file Ruff found 15 import/alias issues, then its fix and formatting operations exited 0 (their records correctly show changed inputs). Raw evidence: `1792596670797422000-task6-handlers-red`, `1792596798301541000-task6-handlers-green`, `1792596827663088000-changed-files-lint`, `1792596827663159000-changed-source-types`, `1792596889506777000-changed-files-lint-fix`, `1792596889726865000-changed-files-format` and `1792596908826043000-changed-source-types-green`, all under ignored `local/series-framing/` as raw log/JSON pairs. No final full-suite/static batch has run.

Contract reconciliation added the exact raw source-record hash to series delivery identity. Its round-trip regression first failed for the absent field, then the affected export/CLI selection passed 10 tests, 35 deselected (exit 0; unchanged inputs). Raw evidence: `1792597052643574000-series-source-record-red.{log,json}` and `1792597060481583000-series-source-record-green.{log,json}`. Native/Add margins identity is unchanged.

README, workflow, normative file contract, recovery and validation drafts now describe actual controls, JSON, explicit selected-revision behavior, portable reuse, geometry/alpha/background mechanisms and delivery recovery. At that initial UI handoff, actual browser, resources, review and final verification were still pending; the final disposition below records their later completion. Host-specific interpreter/checkout/archive paths are removed from these tracked planning records; exact paths remain in ignored evidence/native handoffs.

### Task 6: Mode-specific controls, actual browser journey and user documentation

**Files:** `ui/review.html`, `test_viewer_page.py`, maintained documentation listed below; consume Task 5 response/action shapes.

**Interfaces:** Keep the current `framing*` form/state/functions for Add margins; introduce a separate `series*` form/state with settings, source/digest, dirty/reload-required, selected-revision key, request sequence and owned bitmap. Add mode selector `framingMode` with `add-margins`/`match-series`. Every series preview/export captures the same explicit complete selection, raw manifest digest and visible validated settings. Accepted export is enabled only for selected==accepted; explicit draft never changes that label. No implicit save, preview or export on mode/file changes.

Define `seriesSettings()` for the validated Task 1 object, `seriesRequest()` for the exact Task 5 preview request, `seriesKey(request)` for all identities/settings, `previewSeries()` for sequence-checked decode/display, and `loadSeriesState()` for explicit project reload. `seriesAction(action, extra)` uses the existing common action identity/transport machinery without publishing unrelated forms. These are local page functions, not a new framework.

- [x] **Step 1: Add failing shipped-handler tests.** Add `test_series_mode_and_portable_controls_preserve_independent_forms`, `test_series_preview_sequence_selection_and_bitmap_lifecycle`, `test_series_buttons_export_the_named_selection_and_visible_settings`, `test_series_uncertain_save_requires_explicit_reload`. Extend the existing Node DOM boundary only for actual APIs used (file bytes, object URLs, download link), not a second fake app. Assert Unicode/HTML-like names render as text; cancelled/malformed/oversized file selection changes nothing; successful load changes only the local series form; downloads never save the project or claim filesystem success; delayed validation/preview cannot replace newer fields; replaced/rejected bitmaps and object URLs are released.

```javascript
assert.equal(posts.at(-1).revision, $('viewRevision').value);
assert.deepEqual(posts.at(-1).settings, seriesSettings());
assert.equal(posts.at(-1).draft, true);
assert.equal(seriesNeedsReload, true);
assert.equal($('seriesSave').disabled, true);
assert.deepEqual(unrelatedDraftsAfter, unrelatedDraftsBefore);
```
- [x] **Step 2: Run RED** using `rtk proxy env PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PIP_NO_INDEX=1 "$series_python" -m pytest tests/test_viewer_page.py -k series -q -p no:cacheprovider`.
- [x] **Step 3: Implement labelled controls and isolated state.** Include name, width/height, linked side slider+numeric field, numeric minimum vertical clearance, preview, bounds display, project Save/Reload, portable Load/Download and both explicit export buttons. File picker bytes are bounded before UTF-8 decoding; fatal decoding prevents silent replacement of invalid bytes, and server validates raw JSON. Download validated canonical text via a Blob with fixed safe filename `series-framing-preset.json`; report only the browser action initiated, not a guaranteed disk save. Keep unrelated authoring/effect drafts through polling/actions/mode switching. Invalidate/clear stale preview on mode switch and settings/selection changes; show actual margins, fit reason, enlargement, source-edge warning and approximation. No native authoring handlers on this canvas. Preserve focus/status/CSP and existing `#canvas` positioning scope.
- [x] **Step 4: Run GREEN** with the same handler command, then all `tests/test_viewer_page.py` once for the settled UI. Passing Node checks do not establish actual browser rendering/usability.
- [x] **Step 5: Perform the actual browser journey with synthetic saved projects only.** Prepare distinct long/round/tall/partial-edge fixtures using reviewed existing test builders in a fresh ignored/temporary location; start the current checkout's loopback server through `rtk proxy env PYTHONPATH=src "$series_python" -m blackmask open --project SYNTHETIC_PROJECT`, replacing `SYNTHETIC_PROJECT` with the builder's actual returned path. Use the actual available browser tool and unchanged production CSP. Verify keyboard traversal/numeric-slider alternatives, focus/status/layout, mode retention, bounds/fit/enlargement, two tabs, stale delayed response, saved-only revisions selected != working != accepted, explicit accepted/draft targets, portable file load/reuse on a second project, explicit save/reload, reopen and unsaved settings. Validate the generated download bytes with the canonical parser; do not initiate any separately unauthorized download. Read back actual exported TIFF/PNG/manifest and compare target/settings/layout. Capture relevant screenshots/console/network errors, with launch-token fragments excluded from logs. If browser/file-picker capability is unavailable, record that exact gap and do not substitute Node proof or claim completion of S9.
- [x] **Step 6: Measure representative resources.** After admission/free-space checks, run one synthetic 3000×2000 saved-source export to default 4000×5000 plus its reduced preview, reporting all retained input/estimated scratch bytes, peak RSS, latency, delivery bytes and temporary/preserved stage sizes. Use a fresh process (macOS `ru_maxrss` is bytes) and normal project controls. Keep the 10 GiB reserve; insufficient disk/resources is a blocker, not permission for cleanup or silent downsizing. These measurements do not benchmark every supported extreme or certify photographic quality.
- [x] **Step 7: Update maintained user documentation from the implemented, verified behavior.** Keep one normative file-contract owner and link to it from workflow/recovery. Complete the following exact coverage before delivery:

| Document | Required content |
| --- | --- |
| `README.md` | Supported Match series availability, link to manual workflow and explicit distinction from existing exact Add margins behavior |
| `docs/workflow.md` | All control labels/defaults/units; select a complete revision; Preview/Show bounds; width target and height-limited centring; every positive-alpha pixel; source-edge/enlargement/fine-detail warnings; reduced preview; saved backdrop regeneration under partial edges; project save/reload versus portable load/download; two-photo manual reuse; unsaved settings; selected accepted/draft exports; actual filenames; native editable project retention; CLI examples |
| `docs/file-contract.md` | Exact portable JSON example above and field types/ranges/units/16 KiB bound; explicit operation/validation/no image/path data; project envelope/full snapshot/raw-byte CAS; absence/invalid/uncertain-write rules; renderer/rounding/identity/background versions; selected raw revision binding; immutable delivery/file/precision meanings; resampling versus native exact-copy contracts |
| `docs/troubleshooting.md` | Malformed/oversized/foreign/symlink/unsupported presets, empty/outlier/source-edge alpha, height-limited fit, stale revision/effects/acceptance, busy render/writer, reload-required saves, low resources, export collision/durability/partial-cleanup failures and preservation-first recovery |
| `docs/validation.md` | Actual source candidate and command/status/count/log evidence; scalar/phase tolerances and measured results; file round trips/offline replay; browser and resource observations; inherited framing evidence separately labelled; unrun extremes and human photographic/accessibility limitations |

Parse the documentation's JSON example with the implemented parser; exercise documented CLI examples/help against synthetic data and reopen the portable/project snapshots. Link maintained contracts rather than copy every rule into README. Inspect actual delivery files for private paths/metadata and confirm plans/evidence remain outside installable packages. Do not describe any planned-but-unimplemented capability as available.
- [x] **Step 8: Record checkpoint 3 evidence and inspect the coherent diff.** Check every requested document topic, preservation and meaningful DRY reuse; remove speculative flexibility. No Git write.

## Final independent review, fixes and completion evidence

- [x] Freeze the concrete local candidate by recording changed/new source/test/config/doc hashes and the `14e8c83` comparison scope; preserve all dirty/untracked work. Do not commit merely to create a review boundary.
- [x] Dispatch one fresh-context, configured-default, read-only independent code reviewer with exact candidate/scope and evidence: connected geometry/alpha/backdrop/export/persistence/UI paths, security/privacy, compatibility and regression tests. Root separately reconciles S1–S10 requirements with actual source/tests/evidence. The reviewer cannot edit, send source externally or spawn agents. No redundant generic review layers.
- [x] Wait for and verify all material findings. The persistent owner applies confirmed in-scope fixes and affected tests; root does not overlap writes. Stop for material design/interface/precision changes or additional authority. Reject/defer only with concrete evidence. Renew only affected independent review scopes after fixes.
- [x] On the settled candidate, run the full deterministic suite once: `rtk proxy env PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PIP_NO_INDEX=1 "$series_python" -m pytest -q -ra -p no:cacheprovider`. Capture raw complete output, actual exit/count/skips and input identities. Optional cache skips remain disclosed; no model download/inference is implied.
- [x] Run final static checks: `rtk proxy "$series_python" -m ruff check src tests --no-cache`; `rtk proxy "$series_python" -m ruff format --check src tests --no-cache`; `rtk proxy env PYTHONPATH=src "$series_python" -m mypy src`. Record exact results. If formatting changes relevant inputs, rerun affected verification; never repeat successful unchanged checks routinely.
- [x] Reconcile the table below with concrete test/report/log references and actual outcomes; ensure implementation, QA assertions, maintained docs and evidence describe the same candidate. Report source/runtime/browser/resource/human evidence separately. Resolve relevant failures or explicitly report the remaining blocker; no fabricated pass/acceptance or Git/publication claim.

| Spec coverage | Concrete source / QA / observed evidence |
| --- | --- |
| S1 | `series_framing.compute_series_layout`; `test_series_layout_width_height_and_fractional_geometry`, export round-trip and two-photo persistence tests; checkpoint 1 (170 passes), checkpoint 2 (3 passes), representative exact 4000×5000 TIFF. |
| S2 | Same layout owner; literal tall/250.05-clearance/0.4-pixel assertions in the fractional geometry test; tall synthetic browser fixture computes height-limited status. Actual tall preview/bounds/height-limit status were observed in Brave Private. |
| S3 | Bounded all-positive-alpha scan and zero-support sampling; `test_series_layout_all_positive_alpha_and_empty_mask`, scalar/support/singleton/identity tests; partial-edge fixture has nonempty partial alpha and captured-edge contact. |
| S4 | `_foreground_contribution` reuse plus `series_sampling_plan`/`render_series`; independent float64 ideal/effective scalar tests, phase bound, genuine negative lobes, joint premultiplied bounds, shading and zero-alpha RGBA checks. Focused 13-pass oracle log and independent 48-case review remain distinct evidence. |
| S5 | Canonical `background` field/statistics/sample helpers and saved-recipe regeneration; `test_sampled_background_matches_full_grid_without_full_output_allocation`, existing background tests and series composites/RGBA readbacks. Root's actual draft/accepted deliveries bind their selected saved backgrounds. |
| S6 | Shared compact `export._export_framed`; round-trip, expected-master/raw-manifest identity, non-257/profile/hash/privacy tests and saved-only fresh-process CLI replay. Actual browser deliveries, representative default export and actual wheel/delivery inspection add file evidence. |
| S7 | Strict portable parser plus source-bound raw CAS persistence; settings/unsafe-file/persistence/two-process tests, shipped file/download handlers, actual file picker/load/save/reopen/two-tab stale/reload journey; exact 224 generated Blob bytes passed the canonical parser. Actual round-project file-picker reuse and separate saved snapshots were verified. |
| S8 | Size/support/coefficient/resource estimates before expanded allocation/staging; `test_series_resource_estimate_precedes_large_allocation`, export failure/recovery parameterization and inherited duplicate-stage repair tests. Representative reserve, RSS, latency and exact stage/delivery byte evidence below; estimates are not a whole-process RAM guarantee. |
| S9 | Three HTTP/action tests, four new shipped-handler scenarios and connected 144-test regression; real production-CSP long-project preview/keyboard/Unicode/file/export/two-tab/reopen observations. Actual round/tall/source-edge previews, screenshots, file-picker cancellation and bounded console inspection completed after user handoff. No complete network trace or forced live ordering injection; deterministic handlers cover forced ordering. |
| S10 | Existing native/Add margins/background/CLI regression in checkpoint 1, connected viewer/page regression and fresh independent source review. Root's full suite passed 746 tests/3 optional cache skips; lint/type checks passed, and final formatting passed after the AST-equivalent test-only wrap plus affected round-trip test. Private-photo comparison, photographic acceptance and full accessibility acceptance are not supplied. |

## Plan review and handoff

- [x] Root self-review maps every design section and S1–S10 row to an owning task, reconciles settings/JSON/API/field names, supplies assertions/commands for application paths, covers all five Review Focus items and retains the selected execution/authorization boundaries. Numerical targets are declared rather than represented as proven results; no extra subsystem or review layer is proposed.
- [x] User approves this detailed plan before implementation: on 2026-10-21 the user wrote “approved (I also pre-aprove any intermediate gates finish and create MR I will review)”. Preserve the selected persistent-owner method; ordinary intermediate pauses are preapproved, while verification and material correctness/safety constraints remain.
- [x] Persistent owner resumes with Superpowers executing-plans, TDD for application paths, and these three sequential tested checkpoints. Keep progress/evidence here; add no separate handoff controller or ledger.

Evidence at plan approval (historical): read-only source inspection and prerequisite/hash reconciliation; installed runtime/version import checks; no new resampling experiment, application test, browser run, export, private-photo evaluation, download or external publication. Sampling targets were unverified at approval; the Task 2 record above reports the later focused results. Public API/source applicability was checked on 2026-10-21 against [Pillow modes](https://pillow.readthedocs.io/en/stable/handbook/concepts.html), [resize](https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.resize), [float box binding](https://github.com/python-pillow/Pillow/blob/13.0.0/src/_imaging.c#L2101), [resampling](https://github.com/python-pillow/Pillow/blob/13.0.0/src/libImaging/Resample.c), [W3C compositing](https://www.w3.org/TR/compositing-1/#simplealphacompositing) and [non-drag alternatives](https://www.w3.org/WAI/WCAG22/Understanding/dragging-movements.html). These sources inform the implementation contract, not proof of this product's numerical or photographic result.

Historical frozen review/browser handoff: product source, tests and maintained documentation were paused for the one independent reviewer and root's actual browser journey. Candidate hashes/comparison and exact source/test/config identities are in ignored `local/series-framing/1792597656705713000-review-candidate.json`. Four fresh synthetic long/round/tall/partial-edge projects have different masters, nonempty partial alpha, saved 400×500 settings and accepted/selected/working revisions 003/004/005; the tall fixture is height-limited and partial-edge touches captured bounds. Builder evidence: `1792597586453289000-browser-fixtures-distinct-masters.{log,json}` (exit 0; unchanged code/test inputs). The first builder refused a relative managed path (exit 1, preserved in `1792597530484246000-browser-fixtures.{log,json}`); using canonical absolute project paths succeeded, then distinct synthetic master pixels were deliberately generated for the final fixtures. No private assets or model inference were used.

Documentation checks passed (exit 0): the normative portable JSON example parses through the canonical parser with production defaults, eight maintained/planning files have valid local links/balanced fences, planning host paths are absent, and actual CLI export help contains the documented options. Raw evidence: `1792597586453433000-documentation-contract-check.{log,json}`. Read-only searches also reported absent historical guessed paths `tests/test_pipeline.py`, `src/blackmask/edits.py` and `src/blackmask/matting.py` (each exit 2); subsequent inspection used the existing canonical operations/test modules. These were inspection errors, not test results or blockers. Browser connections/capabilities stay only in ignored local evidence and native handoff; no launch tokens enter tracked documents.

The initial freeze-record command failed before writing its manifest because it named nonexistent `requirements.lock` (exit 1). The canonical repository input is `requirements-macos-arm64.lock`; the corrected freeze record includes that file. All earlier test metadata already used the correct lock filename; no runtime/test rerun was needed.

## Post-review resource and evidence reconciliation

The independent fresh-context reviewer checked the unchanged frozen candidate (20 changed/new files and 46 runtime/test/config hashes), reported **No material improvements recommended**, and ran 48 additional read-only numerical cases (exit 0). Maximum observed errors were alpha 1.2200124044348115e-7 and contribution 0.005682509865437169 RGB16 units, below the declared 2e-6/0.125 targets. This is the native reviewer report, not photographic or universal numerical certification. No production fix was warranted. The apparent browser accessibility-tree slider value was disproved by actual keyboard behavior; no speculative change was made.

Root's actual browser report verifies production CSP, selected 004 versus working 005 versus accepted 003, accepted-button eligibility, long preview/bounds/fit/enlargement, keyboard numeric/slider linkage, literal Unicode/HTML-like names, project save/reopen, real portable file load into an unsaved form, exact selected draft/accepted exports using visible settings, two-tab raw-CAS rejection/explicit reload and retention of dirty native Add margins Left=7. Both actual 400×500 deliveries passed root readback/profile/hash/member/privacy/partial-alpha/zero-RGB assertions (exit 0), with saved backgrounds #16304B/#203040 rather than working #291A35. No acceptance pointer changed. The server interruption and safe restart preserved 638 project/export file hashes. Browser warnings were respected; the user reopened the round fixture manually. Root subsequently completed the bounded synthetic journey recorded below; no forced real-network-delay, full accessibility or photographic acceptance is claimed.

Representative resource preparation exited 0 in 9.62 seconds using existing normal project/guide/stub-matte/background/series-save controls. Source dimensions are 3000×2000; defaults remain 4000×5000. Exact host paths are confined to ignored records. Preparation raw stem: `1792603392423389000-representative-resource-fixture`. The first measurement harness call exited 1 before export because of an incorrect keyword; `framed_transparent` is the canonical argument. Its failure is retained in `1792603469024511000-representative-export-measurement`; it did not produce an export or stage.

The sole completed default export, including transparent variant, took 4.6506 seconds with 750,387,200-byte fresh-process peak RSS. Reduced 1280×1600 preview took 1.1047 seconds (+0.1643 initialization) with 638,976,000-byte peak RSS and 125,455 PNG bytes. Canonical estimates were respectively 302,949,184 and 108,559,856 bytes, retaining 48,000,000 native bytes. Full component estimates and actual stage/delivery/file bytes are recorded in `docs/validation.md` and ignored `local/series-framing/1792603392951081000-resource-fixture/`. The estimates account for sampling buffers/retained inputs and do not bound whole-process RAM; both measured peaks include surrounding validation/encoding/readback and allocator lifetime. No new global RAM policy/limit was introduced and no extreme-size guarantee is claimed.

Actual admission preserved the 10,737,418,240-byte reserve with 34,672,177,152 free and 1,114,097,152 pending bytes. Complete prepublication stage and published delivery each held 120,674,213 logical bytes (120,692,736 allocated); no stages remained and all native input hashes were unchanged. Raw success stems `1792603481515345000-representative-export-measurement-corrected-invocation` and `1792603509379832000-representative-preview-measurement` exited 0 with unchanged runtime/test/config inputs.

Actual shipped download-handler Blob bytes matched all 224 canonical UTF-8 bytes and parsed through the canonical Python parser; no project save or actual browser download ran. Raw stem `1792603573783174000-shipped-download-bytes-canonical-parser` exited 0. Offline wheel build/actual-member/privacy inspection passed (27 members, plans/tests/local/VCS excluded, exactly existing pinned dependencies, no personal/local evidence markers); raw stem `1792603610067323000-offline-wheel-inspection` exited 0, disclosing pip's disabled unwritable user cache. Actual representative TIFF/PNG/manifest/note metadata and five-member/privacy/hash inspection passed, raw stem `1792603639586263000-representative-delivery-privacy-inspection`. Wheel SHA-256 is `2f724cff0d49ca4985bfa4dc6917cc763fce0d113e11b370f496760913076814`; no installation/download occurred.

The maintained workflow label now matches the actual **Compare revision** control. Coherent requirements/DRY pass retains canonical size validation, contribution arithmetic, background statistics, compact publication and existing viewer action/preview machinery; no generic framework or adjacent refactor was introduced. All source/test/config hashes remained unchanged after measurements and artifact checks. Root subsequently completed the one final full/static batch, reconciled below; this owner changed only the approved AST-equivalent test formatting and documentation. An unrelated concurrent incremental QA-plan amendment is outside this owner’s work and is preserved/excluded from this feature's publication scope.

## Final browser and verification disposition

Root completed the remaining actual synthetic browser journey after the user opened Brave Private manually; no browser security settings were changed. Round-project real file-picker reuse loaded the shared 400×500/15% portable preset into an unsaved form; selected revision 004 preview/bounds reported 60/60/110/110 and 4.75× enlargement, then Save was explicit. Direct saved-state inspection (exit 0) verified different masters and independent long/round snapshots (long `Second tab saved`, 16.3%; round `Synthetic shared series`, 15%). Tall selected-004 preview reported 135.34/135.34/25/25, 5.17× enlargement and height-limited wider sides. Source-edge selected-004 preview reported 60/60/66.25/66.25, 5.83× enlargement and the captured-edge warning. Screenshots were visually inspected. File-picker Cancel preserved the form/preview. The inspected private console showed only pre-existing favicon HTTP 403, with no application JavaScript/CSP errors visible; no adjacent favicon change was made.

S9's observed synthetic journey is complete with explicit boundaries: no complete browser network trace, forced live out-of-order delay injection or actual download-to-disk proof. Deterministic shipped handlers cover forced response ordering and malformed portable bytes; the separate exact Blob-byte canonical-parser proof is retained. Basic keyboard/status/form/layout use was observed, while full accessibility and human photographic/private-photo acceptance remain unclaimed.

Root's one full deterministic suite exited 0 with 746 passed/3 optional pinned model-cache skips; wrapper elapsed 195.55 seconds, pytest 194.85 seconds. Input hashes were unchanged. Raw stem `1792603569077075000-final-full-suite`. Full Ruff exited 0 (`1792603764677463000-final-ruff`); mypy exited 0, no issues in 20 source files, 17.20 seconds (`1792603765088686000-final-mypy`). The initial format check exited 1 solely for the newly added raw-source-hash assertion line; 41 other files were already formatted (`1792603764949617000-final-format`). All root records were inspected against their raw tails and metadata.

The sole owner applied Ruff formatting only to `tests/test_series_framing.py`. Exact AST equivalence and a single assertion-wrap diff were verified (exit 0), raw stem `1792603842905889000-targeted-format-ast-proof`; its changed-input flag is intentional. Test SHA-256 changed from `f840bf18ff9e3ded992a3e926d8979082035da8a3fc187f4163b28792769ab0f` to `8b8f00107f9ac1d54427e099c077adc45ba5c460cb9d9608bebc3eb840ead41a`; application source remained byte-identical. The affected `test_series_export_round_trip_identity_and_preservation` then passed (1 test, exit 0, 4.18 seconds), targeted test-file Ruff passed, and full format check passed (42 files). Raw stems `1792603851042334000-formatted-source-record-roundtrip`, `1792603851041054000-formatted-series-test-ruff`, `1792603851041732000-final-format-after-bounded-fix`. Inputs were unchanged during those checks. Per the bounded final ruling, no full-suite/mypy rerun or redundant review was added for this AST-equivalent test-only change.

Checkpoints 1–3 are implemented and have the recorded numerical, persistence, UI, browser, resource and documentation evidence. Full/static evidence and final formatting proof are reconciled without promoting synthetic/model-stub evidence to real inference or photographic acceptance. Root retains final Git/publication ownership; this owner will halt mutations after the documentation consistency/identity handoff. The unrelated concurrent QA-plan amendment remains preserved and excluded.

Final owner handoff: all required checkpoint/review/verification evidence is reconciled above. The exact 20 owned publication-path hashes, 46 current runtime/test/config hashes and sole AST-equivalent test-format exception are recorded in ignored `local/series-framing/1792604084862066000-final-owned-candidate.json`. The separate unowned incremental QA plan is preserved/excluded. All implementation-owner mutations halt after this handoff; root alone owns final Git/publication.
