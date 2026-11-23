"""Native source detail for an opt-in, bounded alpha repair candidate."""

import numpy as np
from scipy.ndimage import gaussian_filter, maximum_filter, minimum_filter

from .exposure import srgb_to_linear


def _smoothstep(fraction: np.ndarray) -> np.ndarray:
    fraction = np.clip(fraction, 0, 1)
    return fraction**2 * (3 - 2 * fraction)


def _local_color(rgb: np.ndarray, anchors: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    # Sample both sides within 36 native pixels (four sigma), including the
    # established foreground at the roots of narrow, extended tips.
    sigma = 9
    mass = gaussian_filter(anchors.astype(np.float64), sigma, mode="constant")
    color_sum = gaussian_filter(rgb * anchors[..., None], (sigma, sigma, 0), mode="constant")
    return color_sum / np.maximum(mass[..., None], 1e-8), mass


def refine_edge_detail(
    source16: np.ndarray,
    trimap: np.ndarray,
    candidate16: np.ndarray,
    background_gaps: np.ndarray | None,
) -> np.ndarray:
    """Blend in source-supported subpixel coverage near an existing matte edge."""
    unknown = trimap == 128
    alpha = candidate16.astype(np.float64) / 65535
    rgb = srgb_to_linear(source16.astype(np.float64) / 65535)
    foreground_anchors = (trimap == 255) | (unknown & (alpha > 0.98))
    background_anchors = (trimap == 0) | (unknown & (alpha < 0.012))
    if background_gaps is not None:
        foreground_anchors &= ~background_gaps
        background_anchors |= background_gaps
    foreground, foreground_mass = _local_color(rgb, foreground_anchors)
    background, background_mass = _local_color(rgb, background_anchors)

    # In a local mixture C = B + alpha(F - B), projection gives coverage in
    # linear RGB. The residual rejects colours poorly explained by that mix.
    color_axis = foreground - background
    from_background = rgb - background
    separation2 = np.sum(color_axis**2, axis=2)
    denominator = np.maximum(separation2, 0.045**2)
    projection = np.sum(from_background * color_axis, axis=2) / denominator
    coverage = np.clip(projection, 0, 1)
    residual = from_background - coverage[..., None] * color_axis
    color_error = np.sqrt(np.sum(residual**2, axis=2) / denominator)

    # A single-pixel ridge and the valley beside it have much more fine-scale
    # variation than a broad defocused falloff. Share that evidence locally so
    # both sides of a strand can move, even at the center of a narrow gap.
    projected_detail = np.clip(projection, -0.2, 1.2)
    detail = np.abs(projected_detail - gaussian_filter(projected_detail, 1.1))
    focus = gaussian_filter(maximum_filter(detail, size=5), 0.8)
    blend = (
        _smoothstep((focus - 0.055) / 0.084)
        * _smoothstep((np.minimum(foreground_mass, background_mass) - 0.004) / 0.029)
        * _smoothstep((np.sqrt(separation2) - 0.055) / 0.065)
        * _smoothstep((0.46 - color_error) / 0.32)
    )
    # Keep the adjustment near the inferred edge. A coincidental colour match
    # in opaque subject texture or remote background is insufficient evidence.
    blend *= _smoothstep((maximum_filter(alpha, size=9) - 0.018) / 0.12)
    blend *= _smoothstep((0.995 - minimum_filter(alpha, size=9)) / 0.12)
    result = candidate16.copy()
    correction = 0.85 * blend[unknown] * np.clip(coverage[unknown] - alpha[unknown], -0.4, 0.4)
    result[unknown] = np.rint((alpha[unknown] + correction) * 65535).astype(np.uint16)
    if background_gaps is not None:
        result[background_gaps] = 0
    return result
