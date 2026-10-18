# I01 package and development provenance

Checked 2026-10-18 against official version-specific PyPI JSON metadata, native wheel tags/hashes, installed package metadata and upstream documentation. `requirements-macos-arm64.lock` pins every installed runtime/test/type/lint dependency and the build backend; excludes the bootstrap pip and editable application. The lock selects only compatible CPython 3.12 macOS ARM64 or universal wheels; no source builds. Python is native ARM64 3.12.14. NumPy 2.3.5 and Pillow 12.3.0 retain the bundled runtime versions; rawpy 0.27.1 retains the source candidate. Tifffile 2026.10.15 and tomli-w 1.2.0 meet their declared Python/NumPy requirements. Installed imports/tests are separate compatibility evidence from metadata.

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

Historical ten-photo daylight development used camera/auto WB disabled and no extra DefaultCropSize. The spider approximate conversion and .0001 threshold remain frozen reference provenance; their incomplete AsShotWhiteXY implementation is not generalized. Current code uses neither those numerical multipliers nor their threshold.

No model weights/configuration were downloaded, installed or evaluated in I01. SAM2.1/ViTMatte, Torch/torchvision pairing, CPU/MPS and model licences are future I02/I03 responsibilities. Frozen MODEL_REFERENCE.json remains checkpoint provenance, not runtime proof. General regular-use and real RAW evidence remain pending I10.

Official sources: [rawpy 0.27.1 metadata](https://pypi.org/project/rawpy/0.27.1/), [RAW parameters](https://letmaik.github.io/rawpy/api/rawpy.Params.html), [LibRaw licences](https://www.libraw.org/about), [Pillow colour management](https://pillow.readthedocs.io/en/stable/reference/ImageCms.html), [Pillow security/release notes](https://pillow.readthedocs.io/en/stable/releasenotes/index.html), [tifffile](https://github.com/cgohlke/tifffile), [rawpy security](https://github.com/letmaik/rawpy/security), [Python flock](https://docs.python.org/3.12/library/fcntl.html). Each locked package's exact JSON metadata is at `https://pypi.org/pypi/NAME/VERSION/json`; advisory state can change.

Security correction: the initial setuptools 82.0.1 proposal had CVE-2026-59890 / GHSA-h35f-9h28-mq5c (Unicode exclusion bypass while building source distributions on macOS). Changed to minimum fixed 83.0.0; its exact PyPI metadata reports zero published advisories at check. No source distribution was built or published. [Upstream advisory](https://github.com/pypa/setuptools/security/advisories/GHSA-h35f-9h28-mq5c).

Non-finite rejected camera WB entries are recorded as JSON null, with coefficient shape and validity flag. Daylight selection can therefore create an unapproved preview project without inventing valid camera coefficients.
