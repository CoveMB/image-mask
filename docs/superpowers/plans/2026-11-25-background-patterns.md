# Background Patterns Implementation Plan

> **For agentic workers** Use superpowers:executing-plans or superpowers:subagent-driven-development for the execution method the user authorizes. Steps use checkboxes. This plan is proposed for review.

**Goal**

Give each photo an editable background pattern with subtle waves, ovals and other combinations of those shapes, plus a generator for repeatable per-photo variations.

**Architecture**

Save editable shapes and a native 16-bit pattern field as a separate appearance effect. Use the pattern to colour the visible backdrop after resolving the foreground and its fade target. Manual authoring and the generator produce the same shape data and use the same renderer.

**Tech stack**

Python 3.12, the existing NumPy, Pillow, tifffile and tomli-w pins, the loopback HTML/JavaScript viewer, pytest and the existing Node page harness. Use Python's `hashlib` for deterministic generation. [Package configuration](../../../pyproject.toml) · [Python SHA-256](https://docs.python.org/3.12/library/hashlib.html)

**Spec**

[Proposed design](#proposed-design), based on the user's background-only direction, the mixed-pattern preview and the request for per-photo generation. [Repository guidance](../../../AGENTS.md) · [Existing background workflow](../../workflow.md#background-light) · [Saved background light contract](../../file-contract.md#saved-background-light)

## Global constraints

- Keep the effect local and offline. Use the existing source, native dimensions and revision identities. The generator consumes identity and dimensions, so its layout selection requires zero photograph pixels or models.
- The pattern contributes only through the background fraction of the saved matte. An opaque sample, including an opaque petal with **Lit backdrop** fade applied, has identical Result RGB with the pattern ON or OFF. Transparent gaps and partial-alpha edges show the effect in proportion to their transparency.
- Keep the developed master, guides, saved RGB/alpha locks, matte and accepted revision recoverable. Carry validated pattern operands through same-master prepare, matte, repair, effects, restore and export. Use the existing writer lock and state-last publication.
- Publish a pattern only on explicit Apply. Generation and preview operate on a candidate. Keep legacy schema-2 reads and no-pattern results byte-compatible when opening, comparing or exporting.
- Use native oriented pixel centres, clockwise rotations, strictly typed fields, sRGB RGB16 and existing precision conversions. Include new buffers in actual resource estimates. Process native fields and presentation output in row strips of at most 64 rows.
- Implementation basis is `f1057cfa6584c49f01055228a989b9e728202430`, verified against the remote `main` SHA before branching. This base includes coordinate-stable RGB8 backdrop dithering. Reuse it for active pattern Result views and keep the existing encoding-selection rules for other outputs. Use the isolated feature branch. Private-photo evaluation and package downloads require their own applicable authorization.

## Review focus

1. **Lit backdrop and partial alpha.** Changing the visible backdrop must leave fully opaque RGB exact and affect a locked translucent sample only through background coverage. Use a nonzero saved fade in the test. Tasks 3 and 4.
2. **Saved-file integrity and drift.** A valid pattern survives a background-colour edit or same-source rematte. Changed bytes, invalid fields and foreign-source references reject on both cold and warm reads. Task 3.
3. **Per-photo variation.** Test the exact seed derivation, changed seeds, skinny and small dimensions, and stable results after reopening an edited generated layout. Tasks 2 and 3.
4. **Presentation and delivery.** Margins, off-image series sampling, reduced previews and editable replay agree on which backdrop is displayed. Existing delivered records still validate under their original identities. Task 4.
5. **Concurrent drafts.** A late Generate, Preview or Apply must never overwrite a newer edit or publish against stale revision bytes. Test draft replacement, authorization and request bounds through the normal viewer routes. Task 5.

---

## Proposed design

**Confirmed behavior.** The flower sits in front of the pattern at every setting. A composition may contain several soft waves and an oval at once. The user can make the effect more or less apparent, change the alternating colours and generate different arrangements for different photos.

**Proposed first release.** Add a **Background pattern** section beside **Background appearance**. It starts OFF with **Strength** 28% and **Neutral gray** selected. Presets populate two editable sRGB colour controls. Neutral gray uses `#010101` and `#202020`, Cool charcoal uses `#010205` and `#141D27`, and Warm charcoal uses `#040201` and `#251913`. **Reverse tones** swaps the palette destinations. Tone values are absolute colour targets, so the apparent lift or shading depends on the saved backdrop. Strength 0% uses the exact current backdrop.

The shape list supports **Add wave**, **Add oval**, selection, independent enable switches and removal from the draft. Both shapes have a canvas centre and rotation with keyboard-operable numeric equivalents. A Wave has **Bend**, **Wavelength**, **Phase**, **Spacing**, **Bands**, **Feather** and **Starting tone**. An Oval has two outer radii, **Softness** and **Tone**. Manual and generated shapes remain editable in the same list. Editable curved gradients and ellipse feathering provide an interaction precedent. [darktable drawn shapes](https://docs.darktable.org/usermanual/development/en/darkroom/masking-and-blending/masks/drawn/#shape-controls)

**Generate pattern** proposes an arrangement in the selected style, **Waves**, **Ovals** or **Mixed**. Mixed combines broad lower waves, a side wave and a soft oval. The first seed comes from the current developed identity and style. **Next variation** advances that seed within the proposal. Show the proposed shape outlines while deciding. **Use this pattern** takes the proposed shapes and their generator origin into the editable draft. **Cancel** returns to the current draft. Use **Pattern ON** and **Preview pattern** to render the current draft with the chosen palette and strength. **Apply pattern** saves the draft through the normal revision flow, including reuse of an equivalent result. **Compare pattern OFF** is a read-only comparison of the saved result. **Turn pattern OFF** disables the saved effect and retains its settings and field for reuse.

**Decisions to review.** Confirm editable parametric waves and ovals as the first authoring model. Review the saved-project compatibility policy with the user. The updated app reads existing schema-2 projects and writes the optional record on Apply. Use the updated app for pattern-bearing projects and retain a pre-feature project copy or delivery wherever an older app version is required.

### Approaches considered

| Approach | Fit and tradeoff |
| --- | --- |
| Add patterns to Background variation | This is the smallest UI change. Its current fixed wash would need new editable geometry, a palette and a generator. Giving those controls to fixed Variation would mix two different editing jobs. |
| Extend Background light | Its shape-placement and preview binding are useful precedents. Its additive light and optional use as a subject fade target make it a poor owner for alternating lighter and darker backdrop tones. |
| **Separate Background pattern effect** | The signed field supports dark and light regions, independent shapes and palette edits. It adds one saved effect and requires explicit integration wherever Result is composed. This is the proposed approach. |

### Shape and rendering contract

Use an optional schema-2 `background_pattern` recipe value with exactly `enabled: bool`, `strength` in [0, 1], `tones_srgb` containing two `#RRGGBB` strings, `reverse: bool` and `shapes` containing at most eight shapes. Optionally include `generator: {version: 1, style, seed}` to record the starting layout. Omit the generator key for a manually started layout. Keep the origin metadata after shape edits and use the actual shapes as the saved authority. An enabled pattern requires at least one enabled shape. Use uppercase colours and preserve fractional native geometry and strength. Reject booleans in numeric fields, nonfinite data, unknown keys and duplicate shape IDs, including when the effect is OFF.

Each shape has `id` matching `[a-z0-9][a-z0-9-]{0,31}`, `type`, `enabled`, `center_xy` within [0, width] × [0, height], and clockwise `rotation_degrees` in [0, 360). Shape extents may cross the frame. Let D be the larger native dimension.

| Type | Additional settings |
| --- | --- |
| `wave` | `bend_px` in [0, 2D], `wavelength_px` and `spacing_px` in [0.5, 2D], `phase_degrees` in [0, 360), integer `band_count` in [1, 4], `feather_px` in [0.5, spacing_px], `first_tone` equal to `tone1` or `tone2`. |
| `oval` | `radii_xy` in [0.5, 2D] on both axes, `softness` in [0.05, 1], `tone` equal to `tone1` or `tone2`. |

Manual Add creates an enabled shape with the next available ID of its type. Use zero rotation. The Wave starts at [0.5 × width, 0.76 × height], with bend 0.07 S, wavelength 1.0 S, spacing 0.12 S, zero phase, three bands, feather 0.35 × spacing and Tone 2 first. S is the smaller frame dimension. The Oval starts at [0.5 × width, 0.5 × height], with radii 0.25 × width and 0.25 × height, softness 0.85 and Tone 1. Apply the same 0.5 px minimums as generation.

For each shape, rotate the sample offset into local `u,v` using the existing background-light convention. Let `S(t)` be the smoothstep of `t` clamped to [0, 1]. Oval weight is `S((1 - hypot(u/rx,v/ry))/softness)` with the selected tone's sign. Wave bands centre on `v - bend_px*sin(2π*u/wavelength_px + phase_radians)`. For band `k`, its lower bound is `(k - band_count/2)*spacing_px` and its upper bound is one spacing above that. Its weight is the difference of `S((v_warped - bound)/feather_px + 0.5)` at those two bounds. Alternate the sign for each band starting with the selected tone. Tone 1 is negative and Tone 2 is positive. Sum enabled shape fields in saved order, clamp once to [-1, 1] and encode `rint(32768 + 32767 * field)` as scalar16. Codes 1, 32768 and 65535 represent full Tone 1, zero and full Tone 2. Code 0 is invalid. Opposing overlaps cancel and matching overlaps increase coverage up to the bound.

Let B0 be the existing base and B1 be the displayed backdrop after existing Background light. Compute a new displayed backdrop B2 by blending B1 toward the selected palette tone in linear sRGB with weight `strength * abs(field)`. Reverse flips the field sign at this stage. Copy B1 exactly at zero weight or OFF. Use the existing RGB16 quantizer for B2. The foreground contribution P still uses B0 or B1 according to its saved fade setting. Keep the existing native compositing encoding and rounding for `rint(P + B2 * (1 - A))`, where A is normalized alpha. Mist follows the composite at its existing stage. This applies the source-over backdrop coverage rule while preserving the application's established encoding. [W3C source-over compositing](https://www.w3.org/TR/compositing-1/#simplealphacompositing) · [Current Result compositor](../../../src/blackmask/export.py)

### Generator rules

Use generator version 1 with an unsigned 32-bit seed. Derive the default seed as the first four bytes, big endian, of SHA-256 over `b"image-mask/background-pattern/v1\0" + bytes.fromhex(developed_id) + b"\0" + style.encode("ascii")`. For a shape attribute, hash the ASCII key `background-pattern-v1/{seed}/{style}/{shape_id}/{attribute}`. Interpret the first eight bytes as big endian, shift right by 11, and divide by 2^53 for a unit draw. Map that to the interval for the attribute and retain native fractional precision. Use stable IDs `lower-wave`, `side-wave`, `upper-oval` and `side-oval`. Next variation uses `(seed + 1) mod 2^32`. Keep the version and resolved geometry in the saved recipe so reproducibility does not depend on a default RNG stream. [Python SHA-256](https://docs.python.org/3.12/library/hashlib.html) · [NumPy generator compatibility](https://numpy.org/doc/stable/reference/random/generator.html)

| Style | Shapes |
| --- | --- |
| Waves | Lower wave, side wave |
| Ovals | Upper oval, side oval |
| Mixed | Lower wave, side wave, upper oval |

Use the following ranges for variation. Centre pairs are fractions of width and height. Let S be the smaller native dimension. Scale ratios to native units and floor distances and radii at 0.5 px. Clamp feather to the resulting spacing and wrap rotation into [0, 360). Use a phase draw from [0, 360) for each wave.

| Placement | Centre X / Y | Rotation | Shape values and tone |
| --- | --- | --- | --- |
| Lower wave | 0.40–0.58 / 0.77–0.87 | −12° to 16° | Three bands. Bend 0.035–0.11 S, wavelength 0.65–1.25 S, spacing 0.085–0.16 S, feather 0.22–0.45 × spacing. Starts Tone 2. |
| Side wave | 0.12–0.24 / 0.43–0.59 | 68° to 104° | Two bands. Bend 0.025–0.075 S, wavelength 0.75–1.40 S, spacing 0.10–0.20 S, feather 0.30–0.56 × spacing. Starts Tone 1. |
| Upper oval | 0.60–0.80 / 0.15–0.32 | −30° to 25° | Outer radii 0.19–0.35 × width and 0.20–0.38 × height. Softness 0.70–1.00. Uses Tone 1. |
| Side oval | 0.14–0.30 / 0.48–0.77 | −40° to 35° | Outer radii 0.12–0.27 × width and 0.16–0.33 × height. Softness 0.75–1.00. Uses Tone 2. |

## File ownership

| Files | Responsibility |
| --- | --- |
| New `src/blackmask/background_pattern.py` | Settings validation, native weights, palette blend and saved pattern operands |
| New `src/blackmask/background_pattern_generation.py` | Versioned seed and editable layout generation |
| `src/blackmask/recipe.py`, `project.py`, `effects.py`, `operations.py` | Optional recipe, immutable validation, exclusive Apply, inheritance, reuse and recovery |
| `src/blackmask/export.py`, `review.py`, `series_framing.py` | Backdrop composition, native review and gallery, framed delivery, editable reconstruction |
| `src/blackmask/viewer.py`, `ui/review.html` | Bound preview/generation routes, saved comparison and draft editor. Reuse the native transforms in `ui/coordinates.js`. |
| New `tests/test_background_pattern.py`, `tests/test_background_pattern_generation.py`, `tests/test_background_pattern_project.py`, `tests/test_background_pattern_delivery.py`, `tests/test_background_pattern_viewer.py` | Focused geometry, generation, saved-state, delivery and viewer checks |
| `tests/test_lifecycle_browser.py` | Real loopback pattern authoring, Generate, keyboard controls, Apply and reopen through the browser runner's actual selected suite |
| `README.md`, `docs/workflow.md`, `docs/file-contract.md`, `docs/assistant-workflow.md`, `docs/troubleshooting.md`, `docs/validation.md` | Supported controls, exact format, typed usage, recovery and measured verification |

## Task 1 — Validate and render pattern geometry

**Interfaces**

- `normalize_background_pattern(settings: object, width: int, height: int) -> PatternSettings` returns validated settings with owned nested values and normalized colours. Define `PatternSettings`, `WaveShape`, `OvalShape` and `PatternShape = WaveShape | OvalShape` in `background_pattern.py`.
- `sample_background_pattern(settings: PatternSettings, native_wh: tuple[int, int], x: np.ndarray, y: np.ndarray) -> np.ndarray` returns aligned scalar16 weights at equal-shaped finite native sample coordinates, including outside the native rectangle.
- `make_background_pattern(settings: PatternSettings, native_wh: tuple[int, int]) -> np.ndarray` samples integer centres in bounded row strips.
- `combine_background_pattern(background16: np.ndarray, weight16: np.ndarray, settings: PatternSettings) -> np.ndarray` returns RGB16. Use existing `exposure.srgb_to_linear` and `linear_to_rgb16`.

- [ ] **Write geometry, precision and validation tests** in `tests/test_background_pattern.py`. Use a 9×7 frame and an unrotated two-band Wave at [4, 3], spacing 2, bend 0, wavelength 8, feather 0.5, phase 0 and starting Tone 2.

```python
# Rows 0, 2, 3, 4 and 6 at the centre column exercise outside, both tones and the join.
np.testing.assert_array_equal(field[[0, 2, 3, 4, 6], 4], [32768, 65535, 32768, 1, 32768])
np.testing.assert_array_equal(combined[2, 4], [8224, 8224, 8224])  # Tone 2 #202020
np.testing.assert_array_equal(combined[4, 4], [257, 257, 257])    # Tone 1 #010101
np.testing.assert_array_equal(combined[3, 4], background[3, 4])   # Exact zero weight
```

  Add `test_pattern_wave_signed_field_and_reverse`, `test_pattern_oval_feather_cancel_and_crop`, and `test_pattern_validation_and_exact_identity`. For a Tone 1 oval centred at [4, 3] with radii [2, 2] and softness 0.5, x coordinates [4, 5.5, 7] at y=3 produce [1, 16384, 32768]. Assert same-geometry opposite ovals cancel, cropped coordinates match full native slices, OFF/zero copy every background sample and invalid OFF records reject. Parameterize the invalid cases for duplicate IDs, a ninth shape, bad rotation, feather greater than spacing, boolean and NaN numerics, unsupported generator version, bad operand dtype/shape and code 0.
- [ ] **Run RED.** `rtk proxy .venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_background_pattern.py`. Expect the planned functions to be missing.
- [ ] **Implement the four interfaces** using the shape rules above. Reuse the existing sRGB conversions and native coordinate convention. Validate inputs before allocation and keep all geometry and palette evaluation in this module.
- [ ] **Run GREEN.** Repeat the Task 1 command. Expect all cases to pass, including exact zero and fractional feather samples.

## Task 2 — Generate editable layouts from a stable seed

**Interfaces**

- `default_pattern_seed(developed_id: str, style: str) -> int` uses the versioned hash above and rejects invalid identities or styles.
- `generate_background_pattern(style: str, seed: int, width: int, height: int) -> list[PatternShape]` returns the ordered valid shape list for the given style. Each output is a fresh object.

- [ ] **Write generation tests** in `tests/test_background_pattern_generation.py`.

```python
assert default_pattern_seed("1" * 64, "mixed") == 450512810
assert default_pattern_seed("2" * 64, "mixed") == 3022267830
assert generate_background_pattern("mixed", 17, 3072, 4080) == generate_background_pattern(
    "mixed", 17, 3072, 4080
)
assert [shape["id"] for shape in generate_background_pattern("mixed", 17, 3072, 4080)] == [
    "lower-wave", "side-wave", "upper-oval"
]
```

  Add `test_pattern_generation_reference_seeds_and_style_members` and `test_pattern_generation_uses_distinct_editable_geometry`. Assert successive seeds 17 and 18 and the two source-derived seeds change resolved geometry. Check every style on 1×1, 9×61 and 3072×4080, and validate all emitted layouts with Task 1. Alter a returned shape and assert the next identical call still matches its original output. Pin the complete Mixed layout for seed 17 at 9×61 inline in this test module as the version-1 reference. Reject invalid seed types, −1, 2^32 and unknown styles. A 1×1 frame only exercises valid bounds.
- [ ] **Run RED.** `rtk proxy .venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_background_pattern_generation.py`. Expect the generator interface to be missing.
- [ ] **Implement the two functions** in `background_pattern_generation.py` with the version-1 roles, ranges and hash specified above. Keep preview/render code out of generation. Pass the proposed shape list through the shared validator at its consuming boundary.
- [ ] **Run GREEN.** Repeat the Task 2 command. Expect the reference seeds, fixture, shape members and supported dimensions to pass.

## Task 3 — Save, recover and compose the native effect

**Interfaces**

- `PatternOperands` exposes `settings: PatternSettings`, `weight16: np.ndarray` and `crop(x0: int, y0: int, x1: int, y1: int) -> PatternOperands`.
- `read_background_pattern(project: Path, directory: Path, manifest: dict[str, Any]) -> PatternOperands | None` reads and validates the saved effect. Absence returns `None`.
- Extend `export.render_background` with optional keyword `display_background16: np.ndarray | None = None`. Keep the existing `background16` argument as B1 and use the override only for the background term. This is the critical caller contract because the current `render_background` obtains its Lit backdrop fade target from `background16`.
- The request has `schema_version: 2`, `kind: "effects"`, `developed_id`, `base_revision`, `inputs_digest`, full native `scope_xyxy`, boolean `candidate_comparison` and exclusive `background_pattern` settings. Apply requires an accepted base or explicit candidate comparison. Viewer Apply binds the raw revision-manifest hash through the existing action path.

Bind a version-1 manifest record with exactly `schema_version`, `algorithm: "signed-background-pattern-v1"`, `developed_id`, `width`, `height`, `settings`, `weight_sha256` and `settings_sha256`. Bind logical `background_pattern/weight16.png` through shared rasters and `background_pattern/settings.json` as canonical normalized settings JSON. Validate exact inventories, source/dimensions, dtype, valid code range, hashes and equality of recipe, record and settings JSON before cached semantic reuse. Treat saved native samples as authoritative. Reuse the field for colour, strength, reversal and ON/OFF changes when normalized shapes match. Same-source changes to alpha or B0/B1 use the same pattern field. Disabled saved settings remain fully readable.

- [ ] **Write saved-path tests** in `tests/test_background_pattern_project.py`, using the existing synthetic project helpers used by `tests/test_background_light.py` and `tests/test_spatial_fade_target.py`. Add `test_saved_pattern_never_enters_lit_fade_target` with nonzero Lit backdrop fade at an opaque sample and a separate partial-alpha protected sample. Compare saved Result ON versus OFF and assert the opaque RGB, alpha hash, protected saved RGB and acceptance pointer match. In a flat fixture with RGB=30000, alpha=32768 and visible backdrop 8224, assert a Result code of 19112. Toggle the existing light and assert an independent pattern stays visible.

```python
np.testing.assert_array_equal(result_on[alpha16 == 65535], result_off[alpha16 == 65535])
assert result_on[partial_y, partial_x, 0] == 19112  # Flat fixture
assert result_off[partial_y, partial_x, 0] == 17000  # B1 = 4000
```

- [ ] **Write integrity and recovery assertions** in the same file. `test_pattern_inheritance_restore_and_field_reuse` asserts field hash reuse after palette, OFF, base-light and same-master matte changes, plus exact reopening of a manually adjusted generated layout. `test_pattern_rejects_stale_tampered_and_partial_writes` checks foreign and stale identities, exclusive full scope, a warm read after tampering with the field, a request with unaccepted base and candidate comparison false, and a publication fault before state-last. Assert the previous working/accepted state and unrelated draft bytes survive. Start a legacy project and assert no-pattern reopen leaves its recipe bytes exact.
- [ ] **Run RED.** `rtk proxy .venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_background_pattern_project.py`. Expect the planned saved effect or compositor override to be missing.
- [ ] **Connect revision publication and inheritance.** Implement the saved operand interfaces in `background_pattern.py`, optional recipe and validation in `recipe.py` and `project.py`, the exclusive request in `effects.py` and same-master prepared/matte/repair inheritance in `operations.py`. Use the existing content-addressed write, writer lock, stale checks and effective-recipe snapshots. Bind the algorithm to reuse identity only for pattern-bearing work. Synchronize the selected pattern recipe section and preserve other pending controls. For saved-only OFF use the validated saved settings with `enabled=false`. Restore and accept use the current validated revision rules.
- [ ] **Wire native Result and its consumers.** In `export.py` compute B2 with Task 1 from the saved field and B1, using aligned zero B1 for a legacy black base. Pass B2 only as `display_background16`. Extend `review.review_panels` to carry the same optional display operand through Result, native crops and before/after overviews. Supply it from the common saved-render path, effect/matte/repair overviews and viewer Result/OFF paths. `previews._render_latest` uses `render_saved_result`, so verify the gallery at that entry point. Use the existing all-effects-off and stale BASE behavior and keep the pattern out of diagnostic, source and alpha pixels. Account for 2 bytes per native sample of the field, 6 bytes per sample of any additional RGB16 backdrop and the live strip buffers.
- [ ] **Run GREEN.** Repeat the Task 3 command and include `tests/test_background_light.py tests/test_spatial_fade_target.py tests/test_review.py tests/test_previews.py`. Expect all selected tests to pass.

## Task 4 — Preserve the effect across native and framed delivery

**Interfaces**

- Extend `series_framing.render_series` with optional `background_pattern_settings: PatternSettings | None = None`. Its sampling inputs and return type remain those of the existing renderer.
- Native editable delivery adds exactly `background_pattern_weight16.png` and `background_pattern_settings.json` when the saved record exists, including OFF. Bind their hashes in the existing delivery manifest. Compact delivery follows the existing five-file contract.

- [ ] **Write delivery tests** in `tests/test_background_pattern_delivery.py`. Reuse the small project/delivery harnesses in `tests/test_background_light.py` and `tests/test_mist_delivery.py`. `test_pattern_replays_from_native_editable_delivery` reconstructs the selected Result independently from saved foreground, alpha, unpatterned fade target operands, field and palette. Compare RGB16 exactly with the native Result TIFF. Assert black and transparent variants match the corresponding pattern-OFF output. Keep old native delivery member hashes and idempotent reuse.
- [ ] **Write framing assertions** in the same file. `test_pattern_margins_series_and_actual_preview_share_backdrop` verifies the Add margins native rectangle, edge extension of B2 and saved preview parity. Test Match series at unit translation and at a minified output with a native coordinate beyond the image edge, both with nonzero Lit backdrop fade. Assert B2 at the sampled coordinate agrees with the analytic geometry and the opaque subject colour agrees with pattern OFF. `test_pattern_delivery_rejects_unbound_and_tampered_members` replaces the field or settings in an editable delivery and checks exact member validation and recovery.

```python
np.testing.assert_array_equal(replayed_native_result, exported_result_rgb16)
np.testing.assert_array_equal(margins_result[top:top + height, left:left + width], exported_result_rgb16)
np.testing.assert_array_equal(series_pattern_on[opaque_series_region], series_pattern_off[opaque_series_region])
```

- [ ] **Run RED.** `rtk proxy .venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_background_pattern_delivery.py`. Expect the new delivery bindings or framing behaviors to be missing.
- [ ] **Integrate delivery and framed preview.** In `export.py`, update the selected rendering, editable members, effective-operand metadata, validation, resource accounting and reconstruction notes. Give pattern-bearing deliveries a bound pattern algorithm and field/settings identity. Add margins uses the exact native Result and extends B2 with the existing edge behaviour. In `series_framing.py`, sample pattern geometry using the same mapped full-output pixel centres and native-space transform as Background light. Keep the bound B0 or B1 target available through subject compositing. Use separate B2 storage when the fade target aliases the pre-pattern backdrop. Pattern and other backdrop work share the same existing row bounds, and transparent/black series bypass the pattern. Pass the selected settings from both export and `review.render_presentation_preview`, and check the native editable companion on both framing routes.
- [ ] **Run GREEN.** Repeat the Task 4 command with `tests/test_export.py tests/test_series_framing.py tests/test_framing.py tests/test_mist_delivery.py`. Expect exact editable reconstruction and legacy deliveries to pass.

## Task 5 — Add the offline editor, preview and Generate workflow

**Interfaces**

- `POST /api/background-pattern-generate` takes exactly `developed_id`, `revision`, `revision_manifest_sha256`, `inputs_digest`, `style` and `seed`. `seed: null` selects the per-photo default. Return the four identity fields plus `version`, `style`, resolved `seed` and `shapes`. Use `ReviewServer.generate_background_pattern(self, data: Any) -> dict[str, Any]`.
- `POST /api/background-pattern-preview` takes the same four identity fields plus `crop_xyxy` and `background_pattern`. Return those four identity fields and `crop_xyxy`, `settings_sha256` over canonical normalized settings JSON, `png_base64` (RGB8), `display_dimensions_wh`, `scale_xy` and `label`. Use `ReviewServer.preview_background_pattern(self, data: Any) -> dict[str, Any]`. Use the existing bounded preview guard and a long-side limit of 1024 display pixels. Check current bindings before and after calculation. Reuse native composition and convert for display with the existing preview convention.
- Extend the saved `/api/state` effect data and the existing authenticated Result image route for the pattern-OFF comparison. Submit Apply through `/api/action` using Task 3's exclusive request. Both new routes use the existing same-origin token, bounded JSON, duplicate-key rejection and working-revision validation. Accept no path inputs on either route.

- [ ] **Write HTTP and page tests** in `tests/test_background_pattern_viewer.py` using the handlers and shipped-HTML harness in `tests/test_mist_viewer.py`. `test_pattern_generate_and_preview_are_bound_and_read_only` asserts response fields, no state/recipe/directory changes, route rejection on a missing token, oversized input, duplicate keys, invalid crop and changed base manifest. Compare expected RGB8 inside a saved native crop when the preview renders the same settings at native size.
- [ ] **Write draft and operator assertions** in the same file. In `test_page_pattern_edits_generate_cancel_and_apply`, type in a wave centre using the keyboard, add an oval, set a fractional Strength, change the two tones, swap them, and generate two Mixed proposals. Verify Cancel retains the exact draft, Use changes the shapes and generator origin, and Apply creates a draft with the chosen geometry. In `test_page_pattern_ignores_stale_generation_preview_and_apply_replies`, inject a late response after a newer edit and a competing working revision. Assert no overwrite, clear stale status and recovery through Reload. Assert Compare OFF retains Background light, existing foreground effects and unrelated pending forms.

```javascript
assert.deepEqual(draftAfterCancel, draftAtGenerate);
assert.deepEqual(draftAfterUse.shapes, acceptedProposal.shapes);
assert.deepEqual(draftAfterUse.tones_srgb, draftAtGenerate.tones_srgb);
assert.deepEqual(draftAfterLateResponse, latestUserDraft);
```

- [ ] **Run RED.** `rtk proxy .venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_background_pattern_viewer.py`. Expect missing routes or controls.
- [ ] **Implement authenticated server actions.** Extend `viewer.py` through the existing validation and route patterns. Generate uses only validated live identity and dimensions. Preview renders the proposed field from the selected foreground and B1 in place of the saved pattern. Estimate the work before rendering and return labelled temporary view pixels without publishing a revision or cache entry. Recheck identity before response. Return one clear stale, busy or invalid-input diagnostic through the existing error route.
- [ ] **Implement the page controls.** Add the section and an authoring mode in `ui/review.html`. Reuse existing native transform and pointer/keyboard patterns. Give controls clear labels and a numeric alternative for each handle. Include **Explicitly compare pattern on an unaccepted candidate** for the Apply contract. Use a single pattern draft bound to the working identity and independent from other controls. Match each response to its identity and the specific draft version. Show unapplied changes and stale state, and label the preview separately from the saved Result. A saved-only OFF action retains a newer or stale pending draft. Keep the generation proposal cancellable before assigning any shapes.
- [ ] **Run GREEN.** Repeat the Task 5 command with `tests/test_viewer.py tests/test_viewer_page.py tests/test_viewer_coordinates.py tests/test_mist_viewer.py`. Expect endpoint, stale-draft and keyboard-entry assertions to pass.

## Final verification and handoff

- [ ] **Update maintained docs with the settled change.** Document the exact labels, defaults, ranges, two colour targets, generation seed, preview precision and compare behavior in `README.md` and `docs/workflow.md`. Add the request, shape, weight, compatibility and replay contracts to `docs/file-contract.md`. Give the assisted workflow one typed request example and the recovery guide the stale/disabled/reopen steps. Record actual results in `docs/validation.md`. Validate links and exercise the example on a synthetic project.
- [ ] **Add the pattern journey to the suite selected by the real browser runner.** Extend `tests/test_lifecycle_browser.py` with keyboard entry, Generate, choose variation, edit, Preview, Apply, and reopen through the real loopback endpoints on an isolated synthetic project. Run the documented runner with an available authorized locked package target and keep its receipt. If that package target is unavailable, record the runner limitation and exercise the same shipped-page journey with the installed local browser tooling. Exercise compare OFF, restore and native editable, Add margins and Match series delivery across the real browser and delivery tests. [Isolated browser setup and runner](../../validation.md#reusable-isolated-browser-setup)
- [ ] **Inspect near-black rendering.** Compare the 16-bit TIFF and the actual RGB8 preview/export and gallery at their normal viewing scale. Check distinguishable subtle waves and ovals, soft boundaries and opaque subject identity. Enable the existing dither for pattern-visible Result views and preserve its pure-backdrop selection, native crop registration and reduced subject-footprint rules. Keep synthetic structural evidence, observed visual behavior and the user's photographic acceptance distinct.
- [ ] **Run the full settled checks once.** Run `rtk proxy .venv/bin/python -B -m pytest -q -p no:cacheprovider`, `rtk proxy .venv/bin/ruff check src tests --no-cache`, `rtk proxy .venv/bin/ruff format --check src tests --no-cache` and `rtk proxy .venv/bin/mypy src`. Record actual exit status, skipped tiers and any unverified behavior.
- [ ] **Review the five focus cases and checkpoint if authorized.** After each coherent task, inspect its focused diff and verification. Create a checkpoint commit only with the user's explicit Git-write authority. Before a release or merge, verify that the integrated effects, saved data, delivery and docs meet the requirements above. The user reviews the proposed authoring model and chooses the execution method before implementation.

Native execution is the proposed approach because saving, rendering, framing and the viewer all depend on the same backdrop operands and revision identities.
