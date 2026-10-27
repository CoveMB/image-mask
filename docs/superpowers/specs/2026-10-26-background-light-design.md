# Background light design

Status: proposed feature, planning only. The user selected **A — keep the existing fade** on 2026-10-26 after comparing illustrative alternatives. This does not authorize implementation or claim the control exists.

## Intent and scope

Make dark subjects readable against a black backdrop with one separately editable **Background light** adjustment. Offer **Soft oval** and **Broad directional gradient** as alternative shapes of that adjustment. Preserve original/source RGB, selected foreground RGB, alpha, protection, and all foreground effect settings and operands. Keep the existing fade target unlit. Document gentle Local exposure as an existing, separately chosen alternative when actual subject detail needs brightening.

No automatic contour glow, subject detection, invented rim lighting, mask edits, relighting, texture generation, new dependency, multiple-light stack, or automatic exposure. No new option to fade toward the lit backdrop: the user selected A. A broad directional gradient changes the backdrop, not the subject's exposure or fade geometry.

## Baseline and approaches

Inspected local `main` at `db907cf4603b1a8d40eabb7c32aa0937de1852df`, tree `519da182d9efd59fe375f6be51be7555e709d748`, on 2026-10-26. This includes Local sharpening. No remote refresh was needed for planning. Preserve unrelated modified QA/fade-review documents and untracked earlier feature plans. Rebind the implementation baseline before editing product files; this document is not authority to replace newer work.

Current owners are `background.py` for saved base pixels/settings; `export.py` for foreground contribution and alpha composition; `spatial_fade.py` for colour fade; `series_framing.py` for output-grid rendering; and `effects.py`, `operations.py`, `project.py`, `review.py`, `viewer.py`, `previews.py` for lifecycle and consumers. `docs/file-contract.md` owns current arithmetic and saved contracts. Existing Background variation multiplies the base in linear light and cannot lift pure black.

Considered approaches:

1. **Separate background light, unlit fade target — selected A.** Adds backdrop separation without changing the current foreground contribution. Requires consumers to distinguish the unlit base from the displayed backdrop; the renderer already accepts separate `background16` and `fade_background16` arguments.
2. **Fold light into the fade target — rejected by the user's choice.** Faded opaque areas would brighten/tint toward the halo, changing the chosen subject appearance.
3. **Use Local exposure alone — useful alternative, not a substitute.** It brightens selected captured subject detail and cannot create a backdrop light. It remains separately opt-in.

## One adjustment and manual controls

Place **Background light** beside existing Background appearance controls. Keep base tone/variation and light Apply/draft state separate. New/legacy projects have no saved light and render exactly as before until explicit Apply.

Proposed recipe section `background_light` has exactly `enabled`, `brightness`, `color_srgb`, `geometry`. Validate finite numbers excluding booleans, exact keys, six-digit colour normalized uppercase, and geometry even when OFF. These ranges/defaults are engineering proposals, not calibrated photographic quality settings.

| Control / field | Contract |
| --- | --- |
| Light ON / `enabled` | Boolean; initial draft false. |
| Brightness / `brightness` | [0,1], shown as 0–100%; initial draft 0.10. This is encoded-sRGB peak light level on black with a white tint, not EV or opacity. Numeric input accepts fractions; never round saved values through a slider. |
| Light colour / `color_srgb` | Default `#FFFFFF` (neutral). Optional colour changes only the backdrop contribution. Black produces zero light. |
| Shape | One active geometry: Soft oval or Broad directional gradient. No stacking. |
| Apply Background light | Explicitly save the visible light settings, independently of pending base-background or foreground drafts. |
| Compare Background light OFF | Read-only comparison retaining the saved base and every foreground effect. |
| Turn light OFF | Use the validated saved settings with only `enabled:false`, inherit the exact saved field and retain pending edits; unavailable when no light record exists. |
| Reload saved light | Explicitly discard this control's pending edits and reload its saved settings; preserve unrelated drafts. |

Geometry uses the existing oriented native-image coordinate convention: sample coordinates are integer x/y, centres use the same convention, x increases right and y down. Let D=max(width,height). The two strict alternatives are:

- Oval: `type:"oval"`, `center_xy:[x,y]`, `radii_xy:[rx,ry]`, `rotation_degrees`, `softness`. Centre x in [0,width], y in [0,height]; radii in [0.5,2D]; rotation in [0,360); softness in [0.05,1]. Defaults: centre `[(width-1)/2,(height-1)/2]`, radii `[max(0.5,width*0.35),max(0.5,height*0.35)]`, rotation 0, softness 1. Radii describe the outer zero-light boundary; softness is the fraction of each radius occupied by the transition.
- Directional: `type:"directional"`, `center_xy:[x,y]`, `rotation_degrees`, `transition_width`. Centre and angle have the same bounds; width in [0.5,2D] native pixels, initially D. Default centre is `[(width-1)/2,(height-1)/2]` and angle 0°. Its centre is the half-weight line in linear light, not half the encoded-sRGB Brightness value. The angle points from light to dark: 0° is left-to-right, 90° top-to-bottom. **Reverse direction** adds 180° modulo 360. A wider transition gives a broader wash, not a repeated band.

Canvas movement/rotation/size handles have labelled numeric keyboard equivalents, visible focus, and a hide-overlays option. Rendered pixels remain the saved result until Apply; outlines describe drafts and must be labelled accordingly. Switching shape changes only the draft. Keep each shape's draft while switching within the form session; only the active geometry is saved, and the previous saved geometry remains recoverable through revision history. Show that applying another shape replaces this adjustment's saved shape. Do not silently transfer oval dimensions to gradient width.

**Turn light OFF** is independent of pending light controls, including invalid or stale drafts. Submit the current saved settings with only `enabled:false` and the current raw revision identity; inherit L16 byte-for-byte and retain the unsaved form with its pending/stale status. Do not relabel retained pending values as saved after completion. Repeated OFF may reuse the same validated result; no-record OFF must not create a record. **Apply Background light** is different: it explicitly saves the visible settings even when the user has chosen OFF, generating a field if brightness/colour/geometry changed. Only an enabled-only change may inherit the previous field; ordinary same-input reuse remains subject to asset validation.

Require a complete current working native view and existing candidate-comparison consent where applicable. Pending matting guides must be saved/reloaded first. A busy writer, stale source/revision, or invalid draft preserves controls and previous state. Changing a base-colour shortcut must not toggle the light. Update existing copy: **Pure black sets the base; turn Background light OFF for an unlit black backdrop.** Explicit black diagnostic/export variants remain black regardless of light state.

## Deterministic light field

Use existing NumPy and shared sRGB conversion helpers. A new focused `background_light.py` owns the light field and saved validation; do not repurpose the subject-fade effect or change its geometry math.

For sample coordinates, rotate centre-relative coordinates by the same clockwise image-angle convention: u=cos(theta)*dx+sin(theta)*dy, v=-sin(theta)*dx+cos(theta)*dy. Let S(t)=t*t*(3-2*t) for t clamped to [0,1].

- Oval: r=hypot(u/rx,v/ry), weight=S((1-r)/softness). Weight is one inside the inner plateau and exactly zero at/outside the outer ellipse. Softness=1 removes the plateau except at the centre.
- Directional: weight=1-S(u/transition_width+0.5). The bright side is constant one, the dark side zero, with one monotonic smooth transition. It is not an oval and does not return to light on the far side.
- Decode colour C from `color_srgb/255` and peak b from `brightness`, each through the existing sRGB transfer. Save `L16=linear_to_rgb16(C*b*weight)`. Generate at most 64 rows per temporary float64 field; no full-image coordinate meshes or alpha-dependent blur. Geometry and light pixels do not depend on alpha, viewport, crop, or base colour.
- `enabled` controls composition, not the saved field. Saving OFF retains a valid recoverable field. Brightness zero or black colour generates exact zero. Absent/OFF/zero light must take an exact identity path for the displayed base.

## Selected A: two backdrops, one unchanged foreground contribution

Keep existing `background/background_rgb16.tif` as **B0**, the unlit base. Missing legacy background means zero. Keep **L16** separate. When the light is enabled, calculate displayed backdrop **B1** by adding decoded B0 and decoded L16 in linear sRGB, clamping to [0,1], then encoding with the existing RGB16 ties-to-even helper. A zero-light pixel copies B0 exactly. Highlight clipping of a bright base is allowed by this bounded display operation and does not change captured source data; document that lower light brightness preserves backdrop variation.

The source-over alpha stage must retain the project's existing **encoded-sRGB** arithmetic and rounding. Do not silently migrate it to linear-light alpha composition. If P is the current unrounded foreground contribution, use `round(P + B1*(1-A))`, A=alpha16/65535. In inward-shading mode, P=F*A*H. In spatial-fade mode, obtain P exactly as today by blending F toward **B0**, then multiplying by A. Shadow fade, exposure and sharpening run in their existing order.

Consequences and invariants:

- B1 is never passed as `fade_background16`. Spatial q, highlight weighting, masks, saved protection and source/selected RGB remain unchanged by light edits.
- Opaque pixels are identical with light ON/OFF, including opaque pixels already faded to black. This can leave a dark silhouette against the light; that is selected behaviour A, not a defect to erase.
- At partial alpha, the flattened colour changes naturally, including protected translucent edges. Protection preserves underlying RGB/alpha, not the former flattened composite. Do not erode, expand, threshold, unpremultiply with a new alpha, recolour edges, or synthesize rim light.
- Do not pre-mask L16 by (1-A) and then composite again: that would attenuate the light twice. Do not add a glow to the already flattened result: it would brighten opaque pixels.
- For the same base and foreground state, the pre-rounding difference ON minus OFF is `(B1-B0)*(1-A)`. Quantized results may differ by ordinary final rounding; pin both exact endpoints and independently calculated partial cases.
- Unchanged source, alpha, lock, selected-foreground and fade-operand hashes are required evidence, not merely visual similarity.

## Every view and output

| Consumer | Required behaviour |
| --- | --- |
| Native Result, crops, saved review/gallery | Compose the saved light once with B0; crops slice the native fields. Never generate on a crop-sized grid. |
| Light OFF comparison | Use B0 for both display and fade target, keeping other saved effects. No revision or acceptance change. |
| Black/gray/white diagnostics; explicit black export | Keep diagnostic display backdrops; retain B0 as spatial fade target. Light has no effect. |
| Source/alpha and transparent RGBA8 | Unchanged by Background light. No background light baked into transparent foreground RGB. |
| Exposure/Shadow fade/sharpening/spatial-fade OFF comparisons | Preserve displayed B1 and the existing comparison's foreground recalculation; spatial fade, when active, still targets B0. |
| Global BASE/stale foreground comparison | Retain the existing all-effects-off black fallback; do not bypass stale gates. |
| Add margins | Copy the native result exactly and extend B1's saved edge pixels using existing `frame_result`. Document possible constant edge bands; do not invent a new extension rule. |
| Match series | Generate the existing B0 on the canonical full output grid. Evaluate the light at native coordinates given by the inverse existing subject scale/translation, so light placement stays relative to the subject. Apply the existing sampled foreground/q pipeline toward output B0, then compose against B1 once. |

For series, both oval and directional geometry follow the same affine mapping; no independent auto-fit/recentring. SeriesLayout maps pixel-edge coordinates, while light fields use integer pixel-centre samples. For full output integer coordinates (X,Y), use `x_native=(X+0.5-tx)/scale-0.5` and `y_native=(Y+0.5-ty)/scale-0.5`. The analytic light extends beyond the transformed native rectangle on the output canvas. Reduced previews first choose `X=floor((2*i+1)*output_width/(2*display_width))` and corresponding Y, matching existing background sampling, then apply that same inverse. Do not use `(X-tx)/scale`, a new display-sized geometry, or a separately normalized preview field. This is the established approximate preview convention, not a claim of an exact downsampled full-render image. Carry the light algorithm/settings and transform in delivery metadata. No light-driven change to subject bounds, sampling kernel, native source coordinates, or alpha. Document that Match series regenerates output fields, unlike native saved-pixel replay and Add margins.

## Saved identity, compatibility and recovery

Add an optional recipe section and optional manifest `background_light`, without expanding or reinterpreting the existing two-key background settings. Proposed record fields are exactly `schema_version:1`, `algorithm:"linear-srgb-background-light-v1"`, `developed_id`, `width`, `height`, `settings`, `light_sha256`, `settings_sha256`. Save `background_light/light_rgb16.tif` as an asset and `background_light/settings.json` as a file. Settings JSON equals normalized recipe/record settings. Validate registration, RGB16/sRGB profile, hashes, strict inventories, supported algorithm and exact field sets, including OFF records. Zero brightness or black tint must bind an exactly zero saved field. Other native saved pixels are authoritative; read/review/export must not regenerate them. Reject malformed or unbound light assets even on warm-cache reads.

Absence stays absent through reads, unrelated operations and restoring old revisions. Rendered RGB16 pixels are exact when absent/OFF; a newly saved OFF record can legitimately change revision/export metadata, so complete delivery-byte identity is not promised. Only explicit Apply introduces a light record. Same-source alpha repair inherits light unchanged and does not stale it, since its geometry is independent of alpha; existing foreground staleness still applies. A different developed source/dimensions must reject mismatched inherited light rather than silently scale/rebind it. Base-background changes inherit L16 unchanged; light edits inherit B0 unchanged. Unrelated drafts and accepted revisions survive both.

Use an exclusive schema-2 `effects` operation carrying `background_light`, full native scope and the existing master/base/draft/candidate identities. Do not combine it with base-background or foreground edits. The viewer envelope additionally requires the exact raw `revision_manifest_sha256`; validate it through the canonical under-project-lock expected-manifest guard. The actual POST action parser must reject duplicate keys for this action, not only for a preview path. Preserve origin/token/body guards; no paths, external assets, models or uploads in light settings.

Extend effective recipe snapshots, strict file inventories, request/execution equivalence, semantic/cache dependency identity, retained asset references, disk/resource estimates, restore and interrupted state-last publication. No orphan cleanup or accepted-data deletion. A failed Apply cannot advance acceptance. Native editable deliveries include `background_light_rgb16.tif` and `background_light_settings.json` when a record exists, including OFF, plus light record/hash identity and existing B0/foreground/alpha/effect operands. Keep `background_rgb16.tif` meaning B0. Reconstruct B1 from delivered B0/L16 and compose with the existing active-mode formula; saved-only native replay must need neither project, generator, model, cache nor network.

Old binaries are not promised to understand the optional new record; preserve pre-feature revisions for rollback, never strip unknown fields to force compatibility. Existing compact default deliveries keep their member count; only optional editable deliveries add operands. Freeze new output identity/version where necessary to prevent old/new exporter destination reuse; never overwrite earlier exports. Implementer must inspect the current delivery validators before selecting the precise compatible version change.

The earlier Reduce fade here and appearance-recipes plans remain separate and are not prerequisites. If implemented before this feature, reduction changes q through its existing owner; light still uses the resulting unchanged P. Existing appearance recipes' `background` section means base tone/variation only and must leave saved/pending light alone. Automatic light/geometry transfer through portable recipes is outside this plan. A reference thumbnail may depict a light without transferring it; its existing reference-only role must remain clear.

## Documentation deliverables

Update maintained docs only when the corresponding product behaviour exists. Until then this design and its plan are proposals, not the user manual.

- `README.md`: feature summary and source-map entry, link to the workflow.
- `docs/workflow.md`: oval walkthrough, broad-gradient walkthrough with angle/reverse/width examples, saved versus draft state, Compare/OFF/reload, selected-A dark-silhouette explanation, partial-alpha limitations, black-base distinction, diagnostics, framing differences and editable recovery.
- `docs/file-contract.md`: exact settings/geometry, field generation and colour spaces, B0/B1 separation, saved inventories/identity, no-light legacy behaviour, native/series replay and export compatibility.
- `docs/assistant-workflow.md`: exclusive typed light operation, current source/revision binding, explicit candidate comparison, no source/alpha modifications, no automatic exposure, and human photographic acceptance.

The manual's **Gentle local exposure on the subject** subsection uses the already implemented Local exposure workflow. Complete the matte; select Local exposure area; author a feathered Apply area over captured dark detail and Protect areas over highlights/details to retain. Suggest an optional +0.1 EV starting comparison, then +0.2 or +0.3 only if useful; these are examples within the existing -3 to +3 range, not a guaranteed enhancement or a new automatic preset. Use Apply / replace exposure area once, then Apply amount to saved area for adjustments. Compare exposure OFF with authoring marks hidden. Inspect noise, clipping and fine edges; Reset exposure retains the saved area. Do not imply that increasing exposure restores missing/clipped detail or fixes a mask. Its selected subject RGB changes by design while the source and alpha stay recoverable. Downstream fade highlight weighting may change because exposure precedes fading; exposure OFF recomputes that weighting. The Background light workflow never enables it automatically.

## Acceptance and evidence

Required implementation evidence: independent scalar field/compositing oracles; exact no-light and opaque identity; nonempty protected and unprotected partial-alpha samples; separate Shadow/spatial/inward-shading cases; native/crop/diagnostic/transparent/framed/series parity; actual HTTP/draft races; malformed/tampered/OFF and warm-cache validation; reload/restore/repair/interruption; and saved-only editable replay. A series fixture must expose accidentally using B1 as fade target, not just exercise a path with q=0.

Use synthetic fixtures for engineering. A human must judge the final effect on a user-authorized photograph in a colour-managed native RGB16 view, including whether the halo is discreet and fades remain pleasing. RGB8 previews can band. AI comparison illustrations are explanatory only, not pixel-preservation, runtime, UI or photographic-acceptance evidence. No private-photo trial is authorized by this plan alone.

## Current primary references

- [W3C Compositing and Blending, simple alpha composition](https://www.w3.org/TR/compositing-1/#simplealphacompositing), consulted 2026-10-26: supports the separate foreground/backdrop contributions and one alpha application. It does not establish this repository's colour-space or saved-format contract; current code/file-contract does.
- [Adobe Lightroom masking guide](https://helpx.adobe.com/lightroom/desktop/edit-photos/masking.html), updated 2026-08-07, consulted 2026-10-26: supports oval feathering and broad monotonic gradient interaction as familiar controls, and local exposure as a separate adjustment. It does not specify our algorithm, default brightness, or photographic acceptance.

These are design inputs, not requirements to reproduce another product or add its other controls. The user selected A; numeric defaults, one-light scope and subject-relative series mapping are proposed engineering choices recorded for review.
