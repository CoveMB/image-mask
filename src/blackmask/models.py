"""Pinned SAM image selection. Network access exists only in explicit setup_sam."""

import hashlib
import json
import os
import re
import tempfile
import time
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

SAM_REPOSITORY = "facebook/sam2.1-hiera-small"
SAM_REVISION = "ee5bba1d82bb8749febdf90f45e84b687142ba03"
SAM_FILES = {
    "model.safetensors": "0a4067b11ce1e23d5229203f11c718a823060d15a4b23fa2372a7d4b77cbbc60",
    "config.json": "97ff9f65b76d107acda4247885f0a5555d0048850ae3c5f97183df289aaecde9",
    "preprocessor_config.json": "6ebf229ee259368ce4a8d4f2fe893a72b053023710853e257253939e601f583d",
}
# Auto stays CPU until photographic MPS pilot acceptance; explicit MPS is diagnostic.
AUTO_MPS_ENABLED = False


def file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_sam(cache: Path) -> dict[str, str]:
    if cache.absolute().resolve() != cache.absolute():
        raise ValueError("Model cache must not contain symlinks")
    for name, expected in SAM_FILES.items():
        path = cache / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("Pinned SAM assets missing; run explicit setup-model")
        if file_hash(path) != expected:
            raise ValueError(f"Pinned SAM hash mismatch: {name}")
    if (cache / "model.safetensors").stat().st_size != 184305280:
        raise ValueError("Pinned SAM weight size mismatch")
    return dict(SAM_FILES)


def setup_sam(cache: Path) -> dict[str, str]:
    """Explicit public download, verified before non-clobber publication. Never called by inference."""
    import os

    from .project import check_space

    cache = cache.absolute()
    if cache.resolve() != cache:
        raise ValueError("Model cache must not contain symlinks")
    cache.mkdir(parents=True, exist_ok=True)
    check_space(cache, 184305280 * 2 + 1024**2)
    for name, expected in SAM_FILES.items():
        destination = cache / name
        if destination.exists() or destination.is_symlink():
            if destination.is_symlink() or file_hash(destination) != expected:
                raise ValueError(f"Existing SAM asset is invalid; preserved: {name}")
            continue
        descriptor, temporary = tempfile.mkstemp(prefix=".download-", dir=cache)
        url = f"https://huggingface.co/{SAM_REPOSITORY}/resolve/{SAM_REVISION}/{name}"
        with (
            os.fdopen(descriptor, "wb") as output,
            urllib.request.urlopen(url, timeout=60) as response,
        ):
            while block := response.read(1024**2):
                output.write(block)
            output.flush()
            os.fsync(output.fileno())
        if file_hash(Path(temporary)) != expected:
            raise ValueError(f"Downloaded SAM hash mismatch: {name}; temporary retained")
        os.link(temporary, destination, follow_symlinks=False)
        # Temporary verified files are intentionally retained; cleanup needs explicit authority.
    return verify_sam(cache)


def run_device_stage[T](
    stage: Callable[[str], T], device: str, *, auto_mps: bool = AUTO_MPS_ENABLED
) -> tuple[T, str, str | None]:
    if device not in {"cpu", "mps", "auto"}:
        raise ValueError("Device must be cpu, mps or auto")
    selected = "mps" if device == "mps" or (device == "auto" and auto_mps) else "cpu"
    try:
        return stage(selected), selected, None
    except (RuntimeError, MemoryError, FloatingPointError) as error:
        if device == "auto" and selected == "mps":
            return stage("cpu"), "cpu", str(error)
        raise ValueError(f"SAM {selected} stage failed: {error}; try explicit CPU") from error


@dataclass(frozen=True)
class Candidates:
    masks: NDArray[np.bool_]
    scores: NDArray[np.float32]
    metadata: dict[str, Any]


class SamSession:
    """One model and one bounded image-embedding cache per explicit session."""

    def __init__(self, cache: Path):
        self.hashes = verify_sam(cache)
        import torch
        from transformers import Sam2Config, Sam2ImageProcessorFast, Sam2Model, Sam2Processor

        started = time.monotonic()
        # Pinned repository describes video; explicit image classes ignore video-only fields.
        configuration = Sam2Config.from_dict(json.loads((cache / "config.json").read_text()))
        self.model = Sam2Model.from_pretrained(
            cache,
            config=configuration,
            local_files_only=True,
            use_safetensors=True,
            attn_implementation="eager",
            dtype=torch.float32,
        ).eval()
        processor_config = json.loads((cache / "preprocessor_config.json").read_text())
        self.image_processor = Sam2ImageProcessorFast.from_dict(processor_config)
        self.processor = Sam2Processor(self.image_processor)
        self.load_seconds = time.monotonic() - started
        self.embedding_key: str | None = None
        self.embeddings: Any = None

    def select(
        self,
        pixels: NDArray[np.uint8],
        points: list[list[int]],
        labels: list[int],
        box: list[int] | None,
        device: str,
        *,
        master_id: str | None = None,
    ) -> Candidates:
        import torch

        from .guidance import coordinates

        if pixels.dtype != np.uint8 or pixels.ndim != 3 or pixels.shape[2] != 3:
            raise ValueError("SAM requires separate RGB8 proxy")
        if master_id is not None and (
            not isinstance(master_id, str) or re.fullmatch("[0-9a-f]{64}", master_id) is None
        ):
            raise ValueError("Invalid SAM master identity")
        height, width = pixels.shape[:2]
        if (
            len(points) != len(labels)
            or not (points or box)
            or any(type(v) is not int or v not in {0, 1} for v in labels)
        ):
            raise ValueError("SAM requires typed native hints")
        for point in points:
            coordinates(point, width, height)
        if box is not None:
            coordinates(box, width, height, box=True)
        kwargs: dict[str, Any] = {"images": pixels, "return_tensors": "pt"}
        if points:
            kwargs.update(input_points=[[points]], input_labels=[[labels]])
        if box is not None:
            kwargs["input_boxes"] = [[box]]
        inputs = self.processor(**kwargs)
        tensor = inputs["pixel_values"]
        if (
            list(tensor.shape) != [1, 3, 1024, 1024]
            or tensor.dtype != torch.float32
            or not torch.isfinite(tensor).all()
        ):
            raise ValueError("Pinned SAM preprocessing geometry/dtype failed")
        started = time.monotonic()
        reused = False

        def stage(selected: str) -> tuple[Any, Any]:
            nonlocal reused
            if selected == "mps" and os.environ.get("PYTORCH_ENABLE_MPS_FALLBACK") == "1":
                raise RuntimeError(
                    "Disable PYTORCH_ENABLE_MPS_FALLBACK; explicit backend failures must stay visible"
                )
            if selected == "mps" and not torch.backends.mps.is_available():
                raise RuntimeError("MPS unavailable")
            self.model.to(device=selected, dtype=torch.float32)
            image_key = hashlib.sha256(
                pixels.tobytes()
                + str(pixels.shape).encode()
                + selected.encode()
                + (master_id or "unknown").encode()
            ).hexdigest()
            arguments = {
                key: value.to(selected) for key, value in inputs.items() if key != "original_sizes"
            }
            with torch.inference_mode():
                reused = (
                    master_id is not None
                    and image_key == self.embedding_key
                    and self.embeddings is not None
                )
                if not reused:
                    self.embedding_key = None
                    self.embeddings = None
                    embeddings = self.model.get_image_embeddings(arguments["pixel_values"])
                    if not all(torch.isfinite(value).all() for value in embeddings):
                        raise FloatingPointError("Non-finite SAM embedding")
                    self.embeddings = embeddings
                    self.embedding_key = image_key
                arguments.pop("pixel_values")
                output = self.model(
                    image_embeddings=self.embeddings, **arguments, multimask_output=True
                )
                if (
                    not torch.isfinite(output.pred_masks).all()
                    or not torch.isfinite(output.iou_scores).all()
                ):
                    self.embedding_key = None
                    self.embeddings = None
                    raise FloatingPointError("Non-finite SAM predictions")
                masks = self.processor.post_process_masks(
                    output.pred_masks.cpu(), inputs["original_sizes"]
                )[0][0]
            return masks.numpy().astype(bool), output.iou_scores.detach().cpu().numpy()[
                0, 0
            ].astype(np.float32)

        (masks, scores), selected, fallback = run_device_stage(stage, device)
        if masks.shape != (3, height, width) or scores.shape != (3,):
            raise ValueError("SAM native mask geometry mismatch")
        metadata = {
            "model": SAM_REPOSITORY,
            "revision": SAM_REVISION,
            "hashes": self.hashes,
            "packages": {
                name: version(name)
                for name in (
                    "torch",
                    "torchvision",
                    "transformers",
                    "safetensors",
                    "numpy",
                    "Pillow",
                )
            },
            "pixel_values_shape": list(tensor.shape),
            "native_shape": [height, width],
            "original_sizes": inputs["original_sizes"].tolist(),
            "dtype": "float32",
            "device": selected,
            "attention": self.model.config._attn_implementation,
            "processor": "Sam2Processor/Sam2ImageProcessorFast",
            "normalization": {
                "mean": self.image_processor.image_mean,
                "std": self.image_processor.image_std,
                "rescale_factor": self.image_processor.rescale_factor,
            },
            "corner_tensor": tensor[0, :, 0, 0].tolist(),
            "input_points_tensor": inputs["input_points"].tolist() if points else None,
            "input_boxes_tensor": inputs["input_boxes"].tolist() if box is not None else None,
            "embedding_reused": reused,
            "load_seconds": self.load_seconds,
            "stage_seconds": time.monotonic() - started,
            "fallback": fallback,
        }
        return Candidates(masks, scores, metadata)
