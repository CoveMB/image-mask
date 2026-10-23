# Fade into background design

Status: user-approved oval-plus-arcs direction captured for implementation planning; application behavior is not implemented by this document. Review history distinguishes the superseded oval-only candidate from the current combined design.

## Purpose and accepted amendments

Add one optional appearance mode, **Fade into background**, with an independently enabled oval and independently placed curved fade arcs. The user can use **oval only**, **arcs only**, or **both**. An oval progressively blends outside an unfaded centre; each arc starts a one-sided transition toward a chosen petal tip or branch. All shapes feed one background blend and replace the current inward-shading contribution when selected. Existing inward shading remains available.

The user selected background blending as the only new rendering option. Accordingly:

- Rendered subject RGB may change colour and may become brighter when the selected background is brighter. Replace the earlier “colour preserving” and “darkening only” requirements with convergence toward the background. Original source pixels remain recoverable and unchanged.
- Monotonicity concerns each shape's geometric blend amount along its defined direction, before explicit protections and highlight preservation. The oval is nondecreasing on outward rays; each arc is nondecreasing along its fade arrow at a fixed position across its span. Independently placed shapes cannot promise one global centre-to-edge profile. Final brightness, photographed texture and protected pixels are not monotonic requirements.
- Transparent exports keep the faded appearance by including the selected background tint in RGB, preserve alpha, and deliver unfaded editable layers and effect operands. The user selected compact framed bundles accompanied by a separate native editable export; the paired-delivery contract below makes those actual files portable. On another backdrop that tint remains visible; transparency is not reduced to create the effect.
- **Shadow fade remains separate and independently adjustable.** Preserve the existing example's amount `0.38` and its highlight setting; do not reinterpret either as a new-mode parameter.

## Fit with the current implementation

`effects.make_shadow_weight` deliberately attenuates narrow protrusions and low alpha; its existing tests protect that behavior. It can therefore produce a bright narrow tip, a darker band behind it, and a lighter centre. Keep that algorithm intact for its existing mode. Do not reuse its thickness, distance-to-outline, direction, or automatic low-alpha attenuation for this feature.

The canonical selected foreground is currently cleanup → local exposure → Shadow fade. Inward shading is applied later by the renderers. Put the new mode at that same render stage, after the selected foreground, before final alpha compositing. Keep `export.saved_layers` and editable foreground assets pre-spatial-fade. Do not introduce a second foreground-development pipeline.

`series_framing.render_series` regenerates the selected background at output coordinates. It cannot reuse a foreground already blended into the native background without risking a visible colour mismatch. The presentation-grid contract below handles that explicitly. Add-margins framing remains exact native insertion with existing background extension.

## Controls and geometry

These are compositional regions, not an automatic subject-outline field. One oval supplies a broad fade; separate arcs place transitions on different petals or branches. They need not share a centre or orientation. Neither shape automatically recognizes a petal or isolates neighbouring objects: place the span and its soft ends accordingly, or use explicit protection.

The effect has a master ON/OFF switch, **Use oval**, **Use arcs**, and one shared **Preserve highlights** control independent of all shape strengths. Each arc also has its own ON/OFF switch. Use oval only by disabling the arc group; use arcs only by disabling the oval; enable both to combine them. Switching these controls retains inactive shapes and their settings. An empty arc list contributes zero from the arc group only, regardless of its group switch; an enabled oval continues to work. The combined field is zero where every enabled shape contributes zero, including when both groups are OFF or all enabled strengths are zero. Master OFF suppresses the whole effect. None of these states revives inward shading. Do not store a redundant three-way mode enum.

| Shape | Independent controls |
| --- | --- |
| Oval | Centre X/Y, unfaded centre width/height, rotation, transition width and fade strength. |
| Each arc | Position X/Y, rotation, span, bend, fade direction, transition width, end softness and fade strength. |
| Whole effect | ON/OFF and highlight preservation; zero preservation disables it. |

Use one fixed cubic smoothstep `S(t)=clamp(t,0,1)^2 * (3-2*clamp(t,0,1))`. Transition width controls softness along the fade direction; arc end softness controls a different, lateral boundary. Do not add arbitrary curve/exponent controls. Numeric controls provide complete keyboard alternatives to handles.

### Oval

The inner ellipse defines the unfaded centre; the outer ellipse expands each semi-axis by transition width `d`. Inner-axis handles change centre size; an outer handle changes `d` without resizing the inner ellipse. Width is an axis expansion, not constant Euclidean distance around an eccentric ellipse.

After rotating a sample into ellipse coordinates, let `rho` be its distance from the centre. Along that ray compute inner and outer boundary distances `r_inner` and `r_outer` from axes `(a,b)` and `(a+d,b+d)`. Define `G_oval=0` at the centre; elsewhere `G_oval=S((rho-r_inner)/(r_outer-r_inner))`. It is zero inside, one at/beyond the outer ellipse, and nondecreasing on each exact outward ray.

### Independent arcs

Use a simple parabolic bow with a straight-line case at bend zero, not a freehand or multi-node spline editor. Each arc is an editable start boundary, not a soft dark stroke. A direction arrow selects which side fades; after the transition, strength stays constant along that direction through the image edge. There is no trailing taper that would make a tip brighten again.

Let `(u,v)` be native coordinates relative to `center_xy`, rotated so `u` follows the chord joining the arc endpoints and `v` is perpendicular to that chord. Positive rotation uses the existing image convention (x right, y down). `L=half_span`, `b=bend`, `w=transition_width`, `e=end_softness`; `sigma=+1` for `fade_side="positive"`, otherwise `-1`:

```text
boundary(u) = b * (1 - (u/L)^2)
d = sigma * (v - boundary(u))
lateral(u) = 1 - S((abs(u) - (L-e)) / e)
G_arc(u,v) = lateral(u) * S(d/w)     when abs(u) < L
G_arc(u,v) = 0                     when abs(u) >= L
```

The endpoints are `(u,v)=(-L,0)` and `(L,0)`; a midpoint handle at `(0,b)` controls bend. Span is chord length `2L`, not curved path length. Transition width is measured along the displayed arrow, perpendicular to the chord, not perpendicular to every local curve tangent. Draw the zero and full-strength boundaries with that same convention. End softness is measured inward from each endpoint: full lateral influence through `abs(u)<=L-e`, smoothly reaching zero at `abs(u)=L`. Extend both endpoint influence boundaries in the fade direction in the overlay so affected neighbouring detail is visible.

At each fixed `u`, G is nondecreasing along the arrow and remains at its lateral plateau beyond `d=w`. Within the core span that plateau is one; in the softened ends it is lower by design. A tip falling outside the span or within end softness may remain visible. This is explicit user placement, not automatic thin-detail protection. The whole real tip profile must be checked with the tip inside the intended core span.

### Combination and limits of the guarantee

Compute `C=max(amount_oval*G_oval, amount_arc_1*G_arc_1, …, 0)` over enabled shapes, respecting the arc-group switch. Do not add strengths, average them, or apply multiple RGB blends. Each shape includes its own strength before the maximum. Reordering or duplicating an identical arc cannot change C. Adding an arc cannot reduce existing fading; an arc can raise the oval's local fade, not restore a region faded by the oval. For restoration lower the oval or use explicit protection.

The maximum is continuous but can change slope where the winning shape changes. Do not claim a globally smooth derivative or a globally monotonic profile with arbitrary, opposing arcs. Test crossing transitions, opposing directions and oval/arc junctions for numeric continuity and visible seams; show combined and selected-shape maps. No smoothing, blur or alternative overlap algorithm may be added silently to hide a failure, because it changes endpoints, scope or strength. Any material visible failure must be resolved before photographic acceptance.

Quantizing values evaluated on the same exact ray/arc-direction path may plateau but must not reverse that individual shape's profile. Nearest-pixel stair-step paths can move between rays or arc cross-sections; compare raster values against their actual pixel centres separately. No field uses subject thickness, low-alpha attenuation, local luminance or foreground topology. Use full native coordinates even for crops.

### Saved settings and editing defaults

`spatial_fade` settings have exactly `enabled`, `preserve_highlights`, `oval`, `arcs_enabled`, and `arcs`. The oval object is always present and has exactly `enabled`, `center_xy`, `inner_radii_xy`, `rotation_degrees`, `transition_width`, `amount`. Each arc has exactly `id`, `enabled`, `center_xy`, `rotation_degrees`, `half_span`, `bend`, `fade_side`, `transition_width`, `end_softness`, `amount`. Arrays have exact length two where stated; `arcs` is an ordered list with zero to **32** entries including disabled ones. The list order is only for editing. Stable, unique lowercase UUID-v4 IDs identify arcs across snapshots and requests; no arbitrary ID is a filesystem path. Disabled entries are validated too.

Let `M=max(width,height)`. Pixel centres are `(x+0.5,y+0.5)`. Shape centres lie in `[0,width] × [0,height]`; semi-axes, half-span and transition width are finite in `[0.5,2M]`; `bend` is finite in `[-half_span,half_span]`; end softness is finite in `[0.5,half_span]`; rotations are finite in `[0,360)`; each amount and preservation is finite in `[0,1]`. Switches are booleans; fade side is exactly `positive` or `negative`. Reject numeric booleans, NaN/infinity, invalid IDs, duplicates, excessive count, unknown keys and unsupported algorithms. UI rotations wrap before submission; persisted invalid values are not silently clamped or dropped.

New effect defaults: master OFF, preservation zero, oval selected with centre at the image centre, radii `(width/4,height/4)`, transition `min(width,height)/4`, rotation zero and strength zero; clamp geometric lengths to their minimums. Arc group OFF and list empty. Add arc creates a fresh ID at the clicked native position (image centre for keyboard Add), rotation zero, `half_span=max(0.5,min(width,height)/5)`, bend one quarter of half-span, transition `max(0.5,min(width,height)/10)`, end softness `max(0.5,half_span/5)`, positive fade side, strength zero, arc enabled and arc group enabled in the draft. It does not change the oval or shared highlight setting. Duplicate copies shape controls with a fresh ID; disable retains them; remove deletes only that arc from the unapplied draft. Cancel restores saved shapes; earlier saved revisions remain recoverable after Apply. No shape creation or drag saves a revision automatically.

Rasterize 64-row tiles, reducing one shape at a time into a float maximum, then quantize the combined field once as W16. Store one full native W16, not one full-frame plane per arc. Selected-shape overlays evaluate only that shape for the requested crop. Bound work by the 32-arc cap plus one oval and existing source dimensions; include combined-field/q and tile buffers in resource estimates. Reuse validated saved W during ordinary rendering; bounded semantic validation recomputes it only under the existing manifest/cache rules.

## Colour and protection contract

Let `F` be selected pre-spatial RGB, `B` the selected background field, and `A` the unchanged alpha. Reuse Shadow fade's existing linear-sRGB luminance thresholds and cubic highlight factor `h`: luminance weights `(0.2126,0.7152,0.0722)`, transition `clamp((Y-0.10)/0.65,0,1)`. Extract a shared helper only with bit-identical regression coverage for existing Shadow fade.

```text
q = (W16 / 65535) * (1 - preserve_highlights * h(F))
q = 0 where alpha is zero or explicit protection applies
F_faded_linear = (1-q) * decode_srgb(F) + q * decode_srgb(B)
F_faded = encode_srgb_float(F_faded_linear)
result = round(F_faded*A + B*(1-A))
```

W16 is the quantized combined geometric-strength field C; there is no additional master-strength multiplier. Keep the existing encoded-sRGB alpha-compositing contract; only the new foreground blend is linear-sRGB. Carry float precision through blending and composite once before RGB16 quantization. Copy original RGB exactly for `q=0`; use target RGB exactly for `q=1`. For the selected background, complete fading must yield exactly that background even at partial alpha. No repeated application to previously faded RGB, and no per-arc RGB layers stacked together.

Do not multiply `q` by alpha magnitude. Alpha gates eligibility only. Honour explicit saved effect protections and guide alpha/RGB locks, including partially transparent locked pixels. On switching from inward shading, retain its explicit protection mask in the new protection union; do not treat its automatically attenuated W as a protection. Preserve existing lock snapshot semantics, which bind pre-render appearance, rather than baking background tint into locks.

Highlight preservation can intentionally retain a bright tip or interrupt the effective fade profile. It is one shared setting applied after combining shapes; explicit protection applies to the whole effect. Label that consequence and provide Fade OFF, selected-shape and combined geometric-strength maps, and the effective-strength map after protection/highlights. Monotonic tests run per shape with highlight preservation and protections disabled; separate tests verify intentional exceptions and combined-field behavior. Natural texture is blended, not reconstructed. At full blending texture necessarily disappears; “preserve detail” means no source destruction, invented detail, or unintended processing, not visible texture at `q=1`.

## Mode switching, persistence and compatibility

Add an optional `spatial_fade` recipe/manifest record with algorithm `linear-srgb-oval-arcs-background-fade-v1`, schema version 1. Missing record means OFF and must not change legacy rendering or require rewriting projects. The prior ellipse-only algorithm/settings existed only in an unimplemented plan: replace that proposal, do not invent a migration or claim existing projects contain it. New projects with this feature require the updated application; older executables may reject their new fields, as existing strict readers do. Do not claim backward readability by old executables.

At most one of inward shading and spatial fade may be enabled. Enabling either atomically disables the other, retaining the other's saved settings, masks and operands. Turning spatial fade OFF leaves inward shading OFF. Re-enabling inward shading requires explicit selection. Reject malformed saved states with both enabled, including when a comparison hides effects. Background and Shadow fade edits must not toggle either mode.

New `effects/spatial-fade/` assets are `weight16.png` (combined geometry including per-shape strengths), `protection16.png` (categorical explicit protection), `alpha16.png` (dependency snapshot), and `settings.json` (including all shape vectors, switches and IDs). W includes group/individual switches but excludes master ON/OFF, alpha, protection and highlight preservation, so changing only master ON/OFF retains the same field. Bind all bytes through the existing manifest file table and dedicated hashes. The record contains exactly schema_version, enabled, settings, stale, source_id, algorithm, alpha_sha256, weight_sha256, protection_sha256, candidate_comparison, and scope_xyxy. Settings JSON mirrors that record; record enabled equals settings enabled. Scope is the complete native image; it must not clip shapes or retain an old shading band outside an edited rectangle. Any shape or strength edit replaces the entire combined W, including regions vacated by moved/removed/disabled arcs, even if those settings are saved while the master is OFF.

The schema-1 effects operation has the existing seven required identity/scope/comparison fields plus `spatial_fade` settings and, only when enabled, optional `spatial_fade_protection_file`. No other effect, support/area or amount-only fields may accompany this operation; a standalone protection field is invalid. The protection input must be a registered, aligned PNG with categorical 8-bit `{0,255}` or 16-bit `{0,65535}` values, resolved through existing project input-path validation and byte-bound request validation. Its nonzero values are added to the saved protection union, never used to remove prior protection. Omission retains saved explicit protections and current locks. A disable operation may not include a protection file and retains existing protection operands. Use the identical field name in the viewer submission allowlist, viewer-to-operation forwarding and `run_effects` validation.

Every operation sends the complete settings snapshot; there are no index-based arc patches or per-arc filesystem assets. Bind the exact snapshot, all vectors/IDs and existing input identity to the request and saved result. Enforce the existing accepted-base gate explicitly: every request with `spatial_fade.enabled=true`, including all-zero strengths or no active shapes, requires `base_revision == state["accepted_revision"]` or explicit `candidate_comparison=true`. Merely carrying the boolean does not enforce this rule. Reject an unaccepted base with false comparison before staging or mode switching. Explicit master disable remains available on a valid current working revision without candidate comparison, preserving recovery. Toggling only a shape/group OFF while the master remains ON is still an enabled request. The UI supplies a separate, initially unchecked candidate-comparison choice; it must not silently opt in or imply photographic acceptance.

Validate disabled records and assets as strictly as active ones. Recompute geometry to verify W against settings in the bounded semantic-validation cache, after fresh asset hashes. Changed alpha marks an enabled effect stale; follow the current explicit rebuild/disable and acceptance-blocking behavior. Add the new record to prepare, matte/repair inheritance, saved comparisons, accept validation, and replay checks. Source/mask/alpha/background bytes remain unchanged by a fade operation. Background changes render against the new bound background without baking it into the saved W; output provenance must identify both effect and target background.

Use the existing project lock, request digest, complete staging, state-last publication and collision-safe export paths. A failure before publication preserves usable state. A failure after rename/during directory sync must report uncertain publication and reconcile existing state before retry; never report that nothing was published without checking.

## Views, framing and export

“Fade OFF” disables only this mode; retain cleanup, exposure, Shadow fade, selected background and framing. BASE retains its existing all-effects-OFF meaning. Black/gray/white diagnostic backdrops do not retarget the fade: its target remains the selected Background setting. Label this distinction. The saved black-background export consequently may contain burgundy-tinted foreground when burgundy was selected; it still has a black display backdrop.

The UI lists oval and arcs with stable selections, per-shape switches and Add/Duplicate/Remove actions. Numeric fields and canvas handles change only the selected shape; overlapping shapes remain selectable through the list. Keyboard users can position, size, bend, flip and change strength without dragging. Draw pending outlines locally while editing. Image and intensity-map previews remain tied to the saved revision until Apply; mark unapplied changes visibly so a moved draft arc is never presented as the geometry of an unchanged rendered image. Apply, cancel and reload must preserve unrelated dirty controls and restore selections by stable ID, falling back safely after removal.

A saved selected-shape overlay takes `shape_id="oval"` or a validated arc UUID from the bound revision and evaluates its strength-weighted field using global native crop coordinates. It respects shape/group enablement; disabled shapes can retain outlines but their contribution map is zero. Unknown IDs or a request for an ID from a different revision fail explicitly. Combined maps show C; effective maps show q. Overlay display opacity never changes effect strength. UI-only selection/visibility does not enter recipe/output identity; actual geometry, strengths and switches do.

Native and Add-margins outputs blend against the native saved background. Series-framed output blends against the background generated at the final output coordinates. Keep layout derived from alpha bounds, not faded brightness. For series resampling, reuse the existing kernel, registration, fractional placement and tile bounds:

1. Sample the pre-fade encoded premultiplied foreground `P=R(A*F)` and alpha `A'=R(A)` as today, retaining existing clamps.
2. Sample one additional scalar contribution `Q=R(A*q)` with the identical transform/kernel; clamp to `[0,A']`. Set `q'=Q/A'` only where `A'>0`.
3. Reconstruct straight foreground `P/A'`, blend it toward output `B` using `q'`, then composite once using `A'`. Preserve the existing contribution exactly when `q'=0`; return target B exactly when `q'=1`.

This explicitly defines blending at the presentation grid; it is not claimed equivalent to filtering an already blended native image. Native locked-pixel identity is guaranteed; resized pixels retain the existing resampling contract rather than a false native-pixel identity promise. Keep hidden RGB zero wherever output alpha quantizes to zero in framed transparent output.

Apply the same presentation-grid blend to transparent RGB while retaining its existing alpha sampling/quantization. Include selected pre-spatial foreground, source/base assets, masks, background settings/identity and spatial operands in editable exports. Keep `foreground_rgb16.tif`'s existing pre-shading/pre-spatial meaning. Mark the transparent view as RGB8/alpha8; never imply that it is the precision master. No added full-resolution float64 RGB cache: use existing channel/tile processing for series framing, add one bounded scalar plane, and update resource estimates and limits before execution.

### Compact framed output with a native editable companion

For a revision containing a `spatial_fade` record, including disabled or zero-strength settings, every Add-margins or series-framed export also produces or byte-verifies the ordinary native editable export at `exports/<revision[-DRAFT]>/`. This applies with or without the optional framed transparent view, so changing presentation variants never loses editability. Framed exports without the new record retain their existing behavior and exact file sets. Native-only export produces its normal single folder; no packaging selector or third archive is added.

The framed folder still contains only `result_rgb16.tif`, `result_RGB8_VIEW.png`, optional `transparent_RGBA8_VIEW.png`, `README.txt` and `manifest.json`. The separate native folder retains the existing native-export inventory and conditional exposure/Shadow fade/background layers, plus `spatial_fade_weight16.png`, `spatial_fade_protection16.png`, `spatial_fade_alpha16.png` and `spatial_fade_settings.json`, with a `spatial_fade` manifest record. Bind every new delivered operand to its actual file hash. The existing `foreground_rgb16.tif`, `source_rgb16.tif`, `alpha16.png` and conditional base/unexposed/unfaded layers remain real precision assets, not references to project files. Preserve authored inactive vectors and IDs. Native reconstruction starts from the delivered pre-spatial foreground; series reconstruction additionally uses the compact manifest's layout/sampling/background recipe. Neither reconstruction needs the original project directory. This is portable layer/render reconstruction, not a promise to import a complete revision history or regenerate matting without its project.

Add optional `editable_companion` to the framed schema-1 manifest before calculating its directory identity. Its exact fields are `directory_name` (the validated native sibling basename, never an absolute path or traversal), `manifest_sha256` (the exact delivered native manifest bytes) and `files_sha256` (a filename-to-SHA256 map of every native delivery member except its manifest, including README). The binding must agree with master, revision, draft status, raw revision-manifest hash, complete spatial settings and target identity in both deliveries. Existing native manifest asset hashes remain authoritative for reconstruction; the companion map also binds notes and the exact portable inventory. No reverse dependency from the native manifest to a particular frame: several layouts can share the same verified native export. Return an additional `editable_companion` object from framed export with `directory`, `manifest_file` and `manifest_sha256`; existing top-level fields continue to identify the presentation. UI success and the framed README show both folders and instruct the user to keep/copy both for editability. Store only the sibling basename in shipped notes/manifests, while local API responses can follow the existing absolute-path convention.

Under the existing writer lock, preflight the selected immutable revision, both inventories, framing geometry and total resource needs before publishing either delivery. Reuse a private native-export helper with the already loaded foreground/alpha rather than recursively calling public `export_project` or building a second native exporter. Publish or verify the native companion first, establish its durability, then publish the frame bound to its freshly verified bytes; verify both again before returning success. Each folder uses existing exclusive no-overwrite publication and exact reuse. The pair is sequential, not one atomic transaction. If native publication succeeds but framing fails, retain the valid native folder and report the failed/incomplete pair with its path. A failure after either rename/directory sync reports visible output and uncertain durability; never claim rollback or delete completed output. An identical retry verifies existing members and confirms parent-directory sync before completing the missing frame. Differing, missing, extra or symlinked companion members are a collision, never silently repaired or overwritten. Preserve earlier/failed stages under the existing recovery policy; only a verified current duplicate stage may be cleaned after durable reuse.

Admission counts pending bytes for both folders, including any duplicate verification stages, and retained native arrays plus peak scratch for the sequential render phases. Keep the existing 10-GiB reserve and canvas limits; do not load a second copy of foreground/alpha simply to export the companion. Reuse is still byte-verified, not assumed from a directory name. Copy only the existing native delivery allowlist plus these four effect assets; do not copy the project tree, `source.json`, model configuration or local planning/evaluation files. The native companion is editable source material with the existing native recipe/notes semantics; compact presentations keep their existing metadata exclusions. No external transfer is part of export.

## Verification and photographic acceptance

Automated synthetic tests cover oval-only, arcs-only and combined operation on circles, rotated elongated ellipses, narrow tapering tips, concave/star petals and disconnected branches. Include straight/bowed/reversed arcs, both soft ends, full directional plateau, adjacent/crossing/opposing overlaps, zero/one/32 arcs, invalid IDs and a rejected 33rd arc, whole-field replacement after moves/removals, partial alpha, explicit locks, dark pixels on burgundy, zero/full strengths, off-edge shape extents and corrupt/stale inputs. Check full exact oval rays, fixed-u arc-direction paths and actual tip-to-centre traces; compare selected, combined and effective fields separately from final brightness. Overlap tests assert max/order/duplicate invariance and continuity, not an invalid global monotonicity promise.

The local flower case has an existing upper-left petal defect with full support and no explicit protection: its old added shading rises from zero at the substantially opaque tip to about 48%, then falls near the centre. Reopen its frozen revision, verify hashes and registration, and reproduce that baseline. Produce oval-only, arc-only and combined candidates through application controls in separate local outputs. For the arc candidate put the whole tip inside the core span, beyond its transition, with the arrow pointing from petal centre toward tip; place a second arc elsewhere to demonstrate independent strength. Inspect the entire actual petal, at full resolution and in context, with three adjacent full traces, selected/combined/effective overlays and OFF comparisons. Inspect combined junctions for bands or seams; do not dismiss a photographic defect merely because each isolated field passes mathematics. Preserve Shadow fade at 38% in contextual comparisons, and isolate it only in clearly labelled diagnostics when necessary.

Use a synthetic branching subject for deterministic render/framing tests and the supplied warm-burgundy branching-flower reference for aesthetic comparison. The flattened reference is not an editable subject/mask fixture and cannot prove source or alpha preservation. Do not upload it or derive invented details. If no suitable editable branching source exists, record that actual photographic use-case validation remains pending while completing synthetic coverage and reference comparison. Human photographic acceptance remains separate from automated preservation and reviewer judgment.

## Requirement assessment and exclusions

| Earlier wording or possible expectation | Resolution |
| --- | --- |
| Preserve rendered colours / darken only | Explicitly amended by the user's selection of background blending. Preserve original recoverable data instead. |
| Every tip fades equally / follows outline | Neither shape recognizes the outline; independent arcs let the user place and tune each region. |
| One global monotonic profile with arbitrary arcs | Explicitly replaced by per-shape directional guarantees plus inspection of the combined field; opposing arcs can create intentional spatial variation. |
| Monotonic appearance with highlights protected | Protection can interrupt effective weight, and photo brightness is unconstrained. |
| Restore detail by adding a weak arc over a strong oval | Strongest-wins cannot lower the oval; reduce the oval or use explicit protection. |
| Soft arc ends versus maximum fade at every tip | Put desired tips inside the core span; lateral softness intentionally lowers the effect near endpoints. |
| Preserve visible texture at complete disappearance | Incompatible at full blend; original detail stays editable and recoverable. |
| Width and separate arbitrary softness curve | One width control with fixed smoothstep is sufficient initially. |
| Transparent appearance independent of backdrop | User chose baked RGB tint with unchanged alpha and separate editable layers. |
| Preserve framing while adjusting the fade | Preserve layout/alpha; series background varies with presentation dimensions by current design. |
| Reproduce the entire reference automatically | This mode supports its selective disappearing-subject treatment; it does not reproduce lighting, colour grading, background texture or subject arrangement. |

No new model/dependency, automatic outline mode, multiple ovals, arbitrary freehand/spline editor, per-arc colour targets or highlight settings, selectable overlap algorithms, black-only alternative, alpha erosion, generic effect framework, new masking workflow, or automatic acceptance.

## Current references

Checked 2026-10-22 against current repository owners; the drawn-mask documentation was refreshed for the arcs amendment. [W3C Compositing and Blending](https://www.w3.org/TR/compositing-1/) distinguishes blending from alpha compositing; the linear blend and existing encoded composite combination above is this project's explicit design choice, not a claim that W3C mandates it. [darktable 5.6 drawn masks](https://docs.darktable.org/usermanual/5.6/en/darkroom/masking-and-blending/masks/drawn/) provides interaction precedent for editable ellipses and curved gradients. The finite-span parabolic formula, soft ends and strongest-wins combination here are our own bounded design choices; no code or dependency is imported.

Canonical existing owners: [file contract](../../file-contract.md), [workflow](../../workflow.md), [assisted workflow](../../assistant-workflow.md), and the implementation plan's file map. Commands in the plan are proposed verification, not evidence of tests already run.
