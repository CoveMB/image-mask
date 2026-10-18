# Package, development and model provenance

Checked 2026-10-18 against official version-specific PyPI JSON metadata, native wheel tags/hashes, installed package metadata and upstream documentation. `requirements-macos-arm64.lock` pins every installed runtime/test/type/lint dependency and the build backend; excludes the bootstrap pip and editable application. The lock selects only compatible CPython 3.12 macOS ARM64 or universal wheels; no source builds. Python is native ARM64 3.12.14. NumPy 2.3.5 and Pillow 12.3.0 retain the bundled runtime versions; rawpy 0.27.1 is pinned for RAW development. Tifffile 2026.10.15 and tomli-w 1.2.0 meet their declared Python/NumPy requirements. Installed imports/tests are separate compatibility evidence from metadata.

| Package | Requires Python | Licence metadata | PyPI published advisories at check |
| --- | --- | --- | --- |
| ast_serialize 0.13.1 | >=3.7 | MIT | 0 |
| iniconfig 2.3.1 | >=3.10 | MIT | 0 |
| librt 0.16.0 | >=3.9 | MIT | 0 |
| mypy 2.4.0 | >=3.10 | MIT | 0 |
| mypy_extensions 1.1.0 | >=3.8 | See wheel licence notices | 0 |
| numpy 2.3.5 | >=3.11 | See wheel licence notices | 0 |
| packaging 26.3 | >=3.9 | Apache-2.0 OR BSD-2-Clause | 0 |
| pathspec 1.1.1 | >=3.9 | See wheel licence notices | 0 |
| pillow 12.3.0 | >=3.10 | MIT-CMU | 0 |
| pluggy 1.7.0 | >=3.10 | MIT | 0 |
| Pygments 2.21.0 | >=3.9 | BSD-2-Clause | 0 |
| pytest 9.1.1 | >=3.10 | MIT | 0 |
| rawpy 0.27.1 | >=3.9 | MIT | 0 |
| ruff 0.17.1 | >=3.7 | MIT | 0 |
| setuptools 83.0.0 | >=3.9 | MIT | 0 |
| tifffile 2026.10.15 | >=3.12 | BSD-3-Clause | 0 |
| tomli_w 1.2.0 | >=3.9 | See wheel licence notices | 0 |
| typing_extensions 4.16.0 | >=3.9 | PSF-2.0 | 0 |

Loaded LibRaw: (0, 22, 1); rawpy feature flags: `{'DNGLOSSYCODEC': True, 'DNGDEFLATECODEC': True, 'OPENMP': False, 'LCMS': True, 'REDCINECODEC': True, 'RAWSPEED': False, 'DEMOSAIC_PACK_GPL2': False, 'DEMOSAIC_PACK_GPL3': False, 'X3FTOOLS': True, '6BY9RPI': True}`. rawpy wheels omit GPL demosaic packs. LibRaw is separate from rawpy's MIT wrapper; retain its LGPL-2.1/CDDL-1.0 and bundled codec notices in installed wheels. PyPI advisory counts and upstream security pages are bounded checks, not exhaustive security clearance. No decoder sandbox or formal security audit is claimed. Only local captures are decoded.

RAW policy: full-size AHD, camera WB only with finite positive RGB coefficients; otherwise explicitly request daylight preview or a trusted developed TIFF. Both routes still require human inspection/approval of WB, clipping and orientation. sRGB output, 16-bit, gamma=(2.4,12.92), bright=1, auto_bright_thr=.01, automatic brightness enabled, median passes=0, FBDD off, no added sharpening, no extra DefaultCropSize crop. LibRaw alone applies RAW orientation. Captured RAW precision is unknown; white level is recorded separately. Boundary stubs verify parameter forwarding, not real RAW decoding/rendering.

No model weights/configuration were downloaded, installed or evaluated for the trusted-master checks. Selection/model evidence follows below; those trusted-master checks did not assess ViTMatte runtime. Future model revisions/configuration/licences require their own verified provenance and runtime checks. General regular-use and user-selected RAW evidence remain pending.

Official sources: [rawpy 0.27.1 metadata](https://pypi.org/project/rawpy/0.27.1/), [RAW parameters](https://letmaik.github.io/rawpy/api/rawpy.Params.html), [LibRaw licences](https://www.libraw.org/about), [Pillow colour management](https://pillow.readthedocs.io/en/stable/reference/ImageCms.html), [Pillow security/release notes](https://pillow.readthedocs.io/en/stable/releasenotes/index.html), [tifffile](https://github.com/cgohlke/tifffile), [rawpy security](https://github.com/letmaik/rawpy/security), [Python flock](https://docs.python.org/3.12/library/fcntl.html). Each locked package's exact JSON metadata is at `https://pypi.org/pypi/NAME/VERSION/json`; advisory state can change.

Security correction: the initial setuptools 82.0.1 proposal had CVE-2026-59890 / GHSA-h35f-9h28-mq5c (Unicode exclusion bypass while building source distributions on macOS). Changed to minimum fixed 83.0.0; its exact PyPI metadata reports zero published advisories at check. No source distribution was built or published with that vulnerable version. [Upstream advisory](https://github.com/pypa/setuptools/security/advisories/GHSA-h35f-9h28-mq5c).

Non-finite rejected camera WB entries are recorded as JSON null, with coefficient shape and validity flag. Daylight selection can therefore create an unapproved preview project without inventing valid camera coefficients.


## Bounded actual RAW evidence

The existing local upstream [Kodak DC50 KDC fixture](https://raw.githubusercontent.com/letmaik/rawpy/main/test/RAW_KODAK_DC50_%C3%A9.KDC) was used without further download or redistribution. Git blob `32354628d6653b83db905417e25e77b037337c94`, 92,675 bytes, SHA-256 `37e290dbd0053f00e508d02a6b3a2a990432dad1eb74c40a52ca899f0f225ecc` binds the exact bytes; the main-branch URL can change. Its first TIFF page is a 96×64 RGB8 preview without DNG tag. Native rawpy 0.27.1/LibRaw 0.22.1 recognizes it and full-size AHD/daylight/sRGB/gamma=(2.4,12.92) yields 768×512 RGB16. Ingest pixels and saved/reopened master match direct LibRaw exactly; source bytes remain unchanged. Captured precision remains unknown, and development approval stays false.

Fixture redistribution rights have not been established, so the capture and derived project remain outside tracked/public source. No human appearance judgement or user RAW acceptance is claimed, and one supported camera is not comprehensive RAW validation. [Primary CR2 format documentation](https://libopenraw.freedesktop.org/formats/cr2/) independently illustrates why RAW data may be outside IFD0; it does not establish an executed CR2 test. Filename suffixes and camera registries are not used for routing.


## SAM selection environment — checked 2026-10-18

Native ARM64 Python 3.12.14, macOS 26.5.2. Torch 2.13.0 and torchvision 0.28.0
have matching cp312 macOS14 ARM64 wheels; torchvision's official wheel metadata
requires exactly Torch 2.13.0. This pair replaces the older proposed 2.9.1/0.24.1
after current advisory inspection. Torch 2.13.0, torchvision 0.28.0, SciPy 1.17.1,
safetensors 0.8.0 and every added transitive package had no listed PyPI advisories
at check. The lock pins exact wheel hashes and preserves the original ingest pins.
Official [Torch metadata](https://pypi.org/pypi/torch/2.13.0/json) and
[torchvision metadata](https://pypi.org/pypi/torchvision/0.28.0/json) establish package
availability/declared compatibility; actual SAM execution supplies runtime evidence.

Transformers 4.57.6 retains the reference-compatible explicit image API. Its
[version-specific metadata](https://pypi.org/pypi/transformers/4.57.6/json) listed
11 advisory records (including duplicate aliases): checkpoint conversion
PYSEC-2025-217; Trainer RNG loading GHSA-69w3-r845-3855/PYSEC-2026-2288;
custom attention/config loading GHSA-29pf-2h5f-8g72/PYSEC-2026-2289;
LightGlue GHSA-fgcw-684q-jj6r/PYSEC-2026-2290;
custom generation GHSA-x9r9-c232-4q39/PYSEC-2026-4174;
processor/tokenizer chat-template save traversal GHSA-xrqw-3rrv-vx5w/PYSEC-2026-3929.
This application uses none of those training/conversion/Auto/generation/save paths.
Only the exact hash-verified configs below enter explicit Sam2Config/Sam2Model and
Sam2ImageProcessorFast/Sam2Processor, with eager attention and local-only
safetensors. No arbitrary model directory/config, remote custom code, pickle
checkpoint, torch.load, chat template or custom kernels are accepted. That bounded
exposure decision is not package-wide security clearance; re-evaluate before
adding any other model/API path. See upstream [security guidance](https://github.com/huggingface/transformers/blob/main/SECURITY.md).

| Pinned SAM asset | Bytes | SHA-256 |
| --- | --- | --- |
| model.safetensors | 184305280 | 0a4067b11ce1e23d5229203f11c718a823060d15a4b23fa2372a7d4b77cbbc60 |
| config.json | 5698 | 97ff9f65b76d107acda4247885f0a5555d0048850ae3c5f97183df289aaecde9 |
| preprocessor_config.json | 683 | 6ebf229ee259368ce4a8d4f2fe893a72b053023710853e257253939e601f583d |

Source: [facebook/sam2.1-hiera-small at ee5bba1d82bb8749febdf90f45e84b687142ba03](https://huggingface.co/facebook/sam2.1-hiera-small/tree/ee5bba1d82bb8749febdf90f45e84b687142ba03),
Apache-2.0 checkpoint label. The pinned config/processor advertises video
architecture/classes; the application deliberately selects the explicit image
classes documented by upstream and validates actual tensors instead of using
Auto/video dispatch. Runtime hashes all three files before first session use.
No weights or third-party model source are distributed with blackmask.

Observed synthetic 97×65 RGB8 selection: actual input `[1,3,1024,1024]`, native
outputs `[3,65,97]`, float32, eager attention, mean `[.485,.456,.406]`, std
`[.229,.224,.225]`, rescale `1/255`. A zero corner independently normalizes to
approximately `[-2.117904,-2.035714,-1.804444]`. Native point `[40,30]` becomes
`[422.268036,472.615387]` through the pinned processor; recorded tensors preserve
the actual mapping. Three source-supported synthetic-object candidate masks were
nonempty. Warm prompt updates reuse one session embedding; changed master,
pixels, geometry/backend invalidate it. Unknown master identity disables reuse.
Separate CLI calls do not promise persistent model caching.

Separate real MPS float32 smoke succeeded with identical binary masks on that
fixture, small score differences, and unchanged geometry. CPU cold stage ~0.73s,
warm prompt/box stage ~0.025s, MPS first stage ~6.37s; model construction ~0.035s
(excludes imports/hash verification and cold filesystem effects). Observed process
peak RSS ~1.93GB. These are one fixture/run, not general latency or quality claims.
Auto remains CPU; explicit MPS errors stay visible. Failed-stage auto fallback is
covered by injected failure tests, distinct from the successful actual MPS smoke.

VitMatteForImageMatting/VitMatteImageProcessor import in this same environment;
this is compatibility direction only. No ViTMatte weights/configs/download/runtime
or native matte correctness was established by the selection checks. Native
matting requires its separately pinned revision/hash and its own CPU/MPS/geometry checks.


## Native ViTMatte evidence — checked 2026-10-18

Pinned [official checkpoint](https://huggingface.co/hustvl/vitmatte-small-composition-1k/tree/6a58ad7646403c1df626fbd746900aec7361ea1d)
has Apache-2.0 label. Weight103294572bytes SHA256
`bda9289db1bb6762d978b42d1c62ae3f34daf7497171a347a1d09657efd788cb`;
config837bytes SHA256 `ae1006f5a83227048b563b2e60709d4203e432b2276949ebef41a8cfeeeaf45f`;
processor284bytes SHA256 `0db558038b96a3f5c97e46d4ec8966fcc479e9aa58a391bca60b5094a5f7fee0`.
The pinned assets were explicitly downloaded and verified; runtime
revalidates all bytes per session. Explicit VitMatteConfig/VitMatteForImageMatting/
VitMatteImageProcessor only, local safetensors, eager attention, float32.
No Auto classes, remote custom code, checkpoint conversion, Trainer/generation or
processor saving. The same Transformers advisory exposure decision above applies
to these bounded APIs; current PyPI metadata still lists those11 records. Torch/
torchvision pins retain no listed advisories at check. No dependency upgrade.

Installed version-specific processor source and official pinned configs establish
mean/std `[.5,.5,.5]`, rescale1/255 and bottom/right divisor32 padding, no resize.
Legacy config `size_divisibility` is explicitly mapped to identical `size_divisor`
before construction, avoiding the deprecated property setter. Actual65×97 input
is `[1,4,96,128]`, output `[1,1,96,128]`, unpadded to65×97; RGB zero corner is
`[-1,-1,-1]`, categorical trimap128 becomes128/255. CPU and explicit MPS smokes
passed finite/native/core checks separately. Observed CPU~.046s, MPS~1.92s,
peak RSS~560MB for that small run; auto remains CPU. Two actual1024-native CPU
tiles for1025×1024 used origins0,1 and tensors `[1,4,1024,1024]`, positive coverage,
~3.49s stage and~7.86GB peak RSS. Costs are bounded smoke observations, not general
latency/memory guarantees or photographic quality. Synthetic mixed alpha/core and
backend differences do not establish human seam/wing/web quality.

Sources: [Transformers ViTMatte API](https://huggingface.co/docs/transformers/v4.57.6/en/model_doc/vitmatte),
[pinned processor implementation](https://github.com/huggingface/transformers/blob/v4.57.6/src/transformers/models/vitmatte/image_processing_vitmatte.py),
[model implementation](https://github.com/huggingface/transformers/blob/v4.57.6/src/transformers/models/vitmatte/modeling_vitmatte.py).
Web rendering of the versioned docs was unavailable; official raw config/model card,
PyPI JSON and installed matching version source were inspected directly. No model
weights, third-party research framework or photos ship in the distribution.
