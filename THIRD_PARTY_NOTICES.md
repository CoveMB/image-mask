# Third-party notices

The tool installs dependencies from their official PyPI wheels; their complete licence files remain in the environment's distribution metadata. This document does not replace those notices. No model is shipped and no photograph is included in application/test distributions. Photographs and private reference/planning material are excluded from public history and application distributions.

The DNG white-balance helper includes Robertson isotemperature lookup data from
Colour v0.4.6 (Copyright 2013 Colour Developers, BSD-3-Clause). The complete notice
and disclaimer are retained in `blackmask/dng_white_balance.py`, including in
installed wheels. No Colour package or Adobe DNG SDK source is bundled or needed
at runtime. This product includes DNG technology under license by Adobe.

Runtime dependencies: NumPy (BSD and bundled component licences), Pillow (MIT-CMU and bundled codec/LittleCMS licences), tifffile (BSD-3-Clause), rawpy (MIT, with separately licensed LibRaw/codecs), tomli-w (MIT). LibRaw offers LGPL-2.1/CDDL-1.0 terms; rawpy's wheels do not include optional GPL demosaic packs. Pillow's LittleCMS library has its own MIT licence. Preserve installed upstream notices when redistributing native libraries.

Verification/build packages and their exact metadata are recorded in docs/model-provenance.md and the hash-pinned lock. Setuptools/pytest/mypy and their components retain upstream terms. No licence for original project code has been chosen. Model checkpoint labels do not license research implementations or photographs; verify each future model and implementation licence before download/use.


Selection dependencies include Torch/torchvision (BSD-3-Clause and bundled component notices),
Transformers (Apache-2.0), safetensors (Apache-2.0), SciPy (BSD-3-Clause plus
bundled numerical-library/GCC runtime notices), and their hash-pinned transitive
packages. Preserve complete installed wheel licence/notice files when distributing
native dependencies; this summary does not replace them. The separately downloaded
SAM2.1 checkpoint is labelled Apache-2.0 at its pinned upstream revision. No
standalone SAM2 research implementation is installed/vendored. See exact
[model/package provenance](docs/model-provenance.md) and its security limitations.
