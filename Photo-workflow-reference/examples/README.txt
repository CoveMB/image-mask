LIMITED REFERENCE FIXTURES
These full-size assets are for source/alpha/layer contract inspection. They do not make the original working scripts portable. Paths under examples/ differ deliberately from the historical experiment output paths.
spider-repair-v3:1536x2040 aligned original developed RGB, separate repaired RGB, current/previous16-bit alpha, trimap, local support and black composite. No original DNG or8-bit RGBA duplicate is included.
dragonfly:2047x2048 original selected JPEG and final16-bit alpha. Its decoded RGB equals the aligned source used for this final mask; original JPEG bytes are retained. The final mask includes two full matting passes and an additional local correction, so a single rerun can differ.
shading:3072x4080 dahlia relative shadow weight and unchanged base mask only. The full source RGB is in the earlier photo deliverables, not repeated here. Do not treat shadow weight as alpha. Other-photo coordinates and native-size image paths in scripts must be adapted explicitly.
Previews are labeled visual examples and may be resized. No additional full-size data should be inferred from preview dimensions.
