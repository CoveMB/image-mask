# Dark gradients in 8-bit Results implementation plan

> **For agentic workers** Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` according to the execution method the user selects. Track the steps below.

**Goal** Keep subtle variations visible in near-black backgrounds in the viewer, saved reviews, and exported viewing copies.

**Architecture** Convert the finished, encoded-sRGB RGB16 composite to RGB8 once at the output pixel size. Use one deterministic quantizer for flattened Result and black-composite viewing copies. Keep native compositing, editable assets, model inputs, Source inspection, diagnostic gray/white panels, scalar masks and straight RGBA on their existing paths.

**Tech stack** Python, NumPy, Pillow, tifffile and pytest from the existing environment.

**Spec** [Design and acceptance below](#design-and-acceptance), [saved background](../../file-contract.md#saved-background-appearance), [current Result gallery](../../file-contract.md#current-result-gallery) and [requested deliveries](../../file-contract.md#requested-result-deliveries). This plan can ship independently of the [native shading fix](2026-11-25-inward-shading-soft-edges.md).

## Design and acceptance

The reproducible input is a 512 × 768 RGB16 background made by `make_background((512, 768), {"color_srgb": "#070707", "variation": 0.55})`. Nearest rounding collapses 1,101 native gray values to five codes. Counting unique RGB8 codes is a poor test. A good conversion can still use a handful of codes while distributing them to reproduce the original gradient across neighboring pixels.

Use an 8 × 8 Bayer ordered threshold as the first implementation. Its construction is small, repeatable across readers and suitable for row streaming. For a channel value `v`, choose between `v // 257` and its next code using the remainder. Use the same threshold at coordinate (x, y) for all three channels. Exact multiples of 257, including pure black and white, are fixed points. Use integer arithmetic wide enough for the threshold comparison. Choose the matrix orientation from the construction in Task 1 and bind it to the encoding version. If the photographed or synthetic preview shows an objectionable repeating pattern, compare a fixed blue-noise threshold tile before accepting the encoder. A change in tile requires the same tests and an identifiable encoding. [Krita’s gradient-dithering precedent](https://krita.org/en/release-notes/krita-5-0-release-notes/)

Use mean absolute error of **16 × 16 block means**, measured against RGB16 / 257 in 8-bit gray units. In a planning experiment, ordinary rounding scored 0.200, ordered dithering in lossless pixels 0.006, and the dithered result decoded from the current quality-85 JPEG 0.254. Quality 97 scored 0.122 and quality 98 scored 0.027. Start photo-bearing JPEGs at quality 98 with the existing optimization, profile, limits and ownership checks. Use the actual decoded delivery to qualify it. These figures measure local tone accuracy on this fixture. Human inspection still decides whether grain, repeating texture or bands are visible.

## Global constraints

- Work offline with existing dependencies. Preserve original files, native sample values, color profiles, registration, draft and acceptance pointers. Deliver new immutable artifacts under their new identity. Use normal gallery refresh/recovery for the replaceable owned JPEG.
- Preserve bounded scratch memory. Export currently converts one row at a time. Presentation previews already have bounded display dimensions. Browser zoom and downstream applications may resample a delivered image again.
- Keep existing output modes, filenames, size caps, collision checks and failure recovery. No new user control is proposed. Git writes and use of private photos require the applicable authorization.

## Review focus

| Risk | Verification |
| --- | --- |
| Strips, overlapping crops or alternate panels restart the threshold pattern | Exact native-pixel comparisons in Tasks 1 and 2 |
| Dithering introduces chroma, changes exact codes, or reaches a mask | Neutral/colored ramps, fixed points and diagnostic controls in Tasks 1 and 2 |
| A thumbnail or secondary JPEG encode erases the effect | Decode the actual gallery, overview and comparison files in Task 3 |
| New output collides with an old delivery or appears to own a foreign JPEG | Legacy artifact and gallery receipt tests in Tasks 2 and 3 |
| Memory, compressed size or a visible repeating pattern makes the result impractical | Row-bound, JPEG cap and display checks in Tasks 1–3 |

### Task 1 — Quantize the finished native Result and export it

**Files** Create `src/blackmask/view_encoding.py`. Modify `src/blackmask/export.py`. Test in `tests/test_export.py` and `tests/test_background.py`.

**Interface** Add `result_rgb8(rgb16: np.ndarray, *, origin_xy: tuple[int, int] = (0, 0)) -> np.ndarray` for H × W × 3 encoded-sRGB uint16 input. Return H × W × 3 uint8. Origins are pixel coordinates on the output raster. Use a one-row slice for streamed PNG writes.

- [ ] Add `test_dark_gradient_png_preserves_local_means` through the real PNG writer and decode the file. Require mean block error < 0.03 on the specified fog fixture, a strictly smaller error than ordinary rounding, and identical R/G/B across the neutral image. Separately exercise an RGB ramp, all 256 exact codes, endpoint values adjacent to black/white, a single pixel and strips with nonzero origins. Every channel must be either the lower or upper adjacent code. The reassembled strips must equal the full-frame output. Run `rtk proxy .venv/bin/python -m pytest -q tests/test_export.py -k 'dark_gradient or quantization'` and observe the current PNG miss the tone threshold.
- [ ] Construct ranks from `[[0]]` using three doublings with quadrants `4R+0, 4R+2, 4R+3, 4R+1` in reading order. Compare `128 * (v % 257)` to `257 * (2 * rank + 1)`. Centralize that operation. Route `_write_framed_rgb8` through it with the absolute output row. Preserve the decoded-pixel digest verification, one-row conversion scratch and sRGB profile. The shared writer covers original size, margins, match-series and the optional flattened black variant.
- [ ] Identify the new **RGB8** encoding in the export request/execution identity before destination selection, including Mist, Vapor, lit-fade and native editable companion variants. Use a separate versioned RGB8 encoding field that survives the per-effect export-version branches. Keep native arithmetic, TIFF hashes and straight RGBA conversion semantics explicit in the manifest. Test that two identical new exports reuse one verified destination, an existing old export survives byte-for-byte, and compact and editable delivery still reconstruct the same native Result.
- [ ] Run `rtk proxy .venv/bin/python -m pytest -q tests/test_export.py tests/test_background.py -k 'dark_gradient or quantization or delivery or native_crop'`. Expect the new export tests to pass. Complete any coupled native-view parity update with Task 2 before integrating.

### Task 2 — Make native inspection and presentation agree

**Files** Modify `src/blackmask/review.py`, `src/blackmask/viewer.py` and `src/blackmask/framing.py`. Test in `tests/test_background.py`, `tests/test_review.py`, `tests/test_framing.py` and `tests/test_series_framing.py`.

**Interfaces** Extend `review_panels` with keyword-only `origin_xy=(0, 0)`. Preserve the existing panel keys and geometry metadata. Use `result_rgb8` after the current RGB16 presentation sampler in `framing_preview` and `render_presentation_preview`.

- [ ] Extend `test_result_native_crop_review_viewer_export_and_saved_only_replay` using a nonuniform region with fractional codes. Request overlapping odd-origin crops from the live Result and the saved native review. Compare both pixel-for-pixel to the same windows of the decoded whole export. Include black-as-Result, a separate chosen backdrop, a comparison/off route and a diagnostic alpha panel. Read the precision TIFF and compare to the independent native compositing oracle. Run the targeted test red.
- [ ] Pass each actual crop origin through `write_review`, viewer Result and comparison routes. Apply the conversion only to finished flattened Result and black views. Preserve black-as-Result aliasing when there is no separate Result panel. Keep the existing support, Source, RGBA and alpha comparisons exact. Update old RGB8 rounding assertions only for surfaces whose documented conversion changes.
- [ ] In the margins and match-series previews use the sampled **display** coordinates for the threshold. Same-size previews must agree with the corresponding export. For resized previews compare against quantization of the sampled RGB16 display image. Keep the virtual-canvas memory bound. Include a nonzero margin, a downscaled series layout and a small no-upscale layout.
- [ ] Bind the encoding to newly generated native review manifests and comparison requests that identify native PNG evidence. Confirm that old review directories remain readable and successive identical new reviews reuse their content-addressed output. Run `rtk proxy .venv/bin/python -m pytest -q tests/test_background.py tests/test_review.py tests/test_framing.py tests/test_series_framing.py`.

### Task 3 — Preserve the gradient through resizing, JPEG and gallery recovery

**Files** Modify `src/blackmask/view_encoding.py`, `src/blackmask/previews.py`, `src/blackmask/review.py` and `src/blackmask/appearance_recipes.py`. Test in `tests/test_previews.py`, `tests/test_review.py`, `tests/test_appearance_recipes.py` and `tests/test_viewer.py`. Update `docs/file-contract.md` and `docs/workflow.md`. Check `README.md` for affected descriptions.

**Interface** Add `resized_result_rgb8(rgb16: np.ndarray, size_wh: tuple[int, int]) -> np.ndarray`. Accept the caller's final photo-panel size. For Lanczos paths, resize one channel at a time at higher precision, clamp overshoot to the encoded range, then quantize at the target size. Keep sampling used by margins and match-series in their current owners.

- [ ] Add tests with the specified fog at native size and a larger source downscaled to a bounded preview. Measure decoded JPEG photo pixels alone against the high-precision resized reference, excluding the footer/labels and partial metric blocks. Require < 0.05 for the native neutral fixture, and improved block error over the old encoded route for the reduced fixture. Decode the newly generated recipe PNG too. The current quality-85 and pre-rounded thumbnail paths must fail their relevant checks.
- [ ] Route gallery photos, new recipe references, revision overviews and focused comparison Result/black panels through final-size conversion. Gallery and recipe reference caps are 1600 and 512 pixels respectively. The comparison builder currently reopens `preview.jpg`, may shrink a presentation panel a second time, and encodes another JPEG. Compose the final comparison from high-precision inputs or lossless final-size panels in memory. Reuse the existing layout, evidence bindings and labels. Keep historical JPEG panels at their actual recorded precision when only those bytes are available.
- [ ] Apply the qualified JPEG setting to newly rendered photo-bearing JPEGs. Version gallery encoding and focused-comparison identity. In `_validate_record`, recognize only the known old/new encodings for ownership and verify the original identity, manifest binding and receipt. An owned old gallery becomes eligible for ordinary refresh. A foreign or malformed file remains protected. Status checks stay read-only. Verify interrupted replacement, old immutable comparison reuse boundaries, footer geometry, 1 MiB recipe PNG cap and 16 MiB gallery JPEG cap on detailed synthetic input.
- [ ] Run `rtk proxy .venv/bin/python -m pytest -q tests/test_previews.py tests/test_appearance_recipes.py tests/test_review.py tests/test_viewer.py`. Inspect a decoded PNG and gallery JPEG at 100% on a dark neutral and subtly colored gradient, plus a detailed subject. Record tonal improvement, repeating texture, JPEG bytes and peak scratch on a representative large input. A passing metric alone does not qualify the appearance.
- [ ] Document the viewing-copy encoding, remaining display/JPEG limitations, recovery of old derivatives and the role of the native RGB16 TIFF. Run the repository's [verification commands](../../../README.md) once on the settled change, including pytest, Ruff and mypy. Preserve earlier successful checks on identical inputs. If both plans land together, one final full run covers the combined state.
