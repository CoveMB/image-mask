"""Synthetic witnesses for the native Local Texture transfer and pixel contract."""

import numpy as np
import pytest

from blackmask.exposure import linear_to_rgb16, srgb_to_linear
from blackmask.project import ProjectError

SETTINGS = {
    "enabled": True,
    "strength": 0.5,
    "scale_px": 4,
    "grain_guard": 0.0,
    "preserve_highlights": 0.0,
}


def gray16(luminance, height=1):
    return linear_to_rgb16(np.broadcast_to(luminance[None, :, None], (height, luminance.size, 3)))


def render(rgb, **settings):
    from blackmask.texture import apply_local_texture

    opaque = np.full(rgb.shape[:2], 65535, np.uint16)
    return apply_local_texture(
        rgb, opaque, opaque, np.zeros_like(opaque, bool), SETTINGS | settings
    )


def contrast_gain(period, scale, *, level=0.16, amplitude=0.014, **settings):
    columns = np.arange(384)
    pattern = np.cos(2 * np.pi * columns / period)
    rgb = gray16(level + amplitude * pattern)
    adjusted = render(rgb, scale_px=scale, **settings)
    weights = pattern[128:256]
    before = srgb_to_linear(rgb[0, 128:256, 0] / 65535)
    after = srgb_to_linear(adjusted[0, 128:256, 0] / 65535)
    return float((after @ weights) / (before @ weights))


def test_texture_selects_midband_and_scale_moves_the_response():
    assert 1.20 < contrast_gain(16, 4) < 1.25
    assert 0.99 < contrast_gain(128, 4) < 1.01
    assert 0.99 < contrast_gain(2, 4) < 1.01
    assert contrast_gain(8, 2) > contrast_gain(8, 8) + 0.15
    assert contrast_gain(32, 8) > contrast_gain(32, 2) + 0.15


def test_texture_guard_attenuates_weak_responses_and_highlights():
    faint = {"level": 0.025, "amplitude": 0.002}
    assert contrast_gain(16, 4, **faint) > 1.20
    assert 1.03 < contrast_gain(16, 4, grain_guard=0.0005, **faint) < 1.15
    assert contrast_gain(16, 4, grain_guard=0.001, **faint) == pytest.approx(1)
    highlights = {"level": 0.83, "amplitude": 0.02}
    assert contrast_gain(16, 4, **highlights) > 1.20
    assert contrast_gain(16, 4, preserve_highlights=1, **highlights) == pytest.approx(1)


@pytest.mark.parametrize("ramp_width", [1, 3])
@pytest.mark.parametrize("dark,bright", [(0.2, 0.5), (0.12, 0.55)])
def test_texture_bounds_halos_on_steps(ramp_width, dark, bright):
    position = np.arange(161) - 80
    step = dark + (bright - dark) * np.clip(position / ramp_width + 0.5, 0, 1)
    rgb = gray16(step)
    difference = srgb_to_linear(render(rgb) / 65535) - srgb_to_linear(rgb / 65535)
    assert np.max(np.abs(difference[:, np.abs(position) >= ramp_width / 2])) <= 0.002


def test_texture_paste_boundary_copies_exclusions_and_bounds_alpha_outlier():
    from blackmask.texture import apply_local_texture

    rgb = gray16(0.15 + 0.02 * np.cos(np.arange(112) * np.pi / 8), height=140)
    alpha = np.full(rgb.shape[:2], 65535, np.uint16)
    alpha[66:76, 51:57] = 24000
    alpha[:, :12] = 0
    alpha[62, 84] = 1
    rgb[alpha == 0] = 65535
    support = np.full_like(alpha, 65535)
    support[:, :27] = 0
    support[:, 27:31] = 30000
    protection = np.zeros_like(alpha, bool)
    protection[69:72, 52:55] = True
    excluded = (alpha == 0) | (support == 0) | protection
    original = rgb.copy(), alpha.copy(), support.copy(), protection.copy()
    result = apply_local_texture(rgb, alpha, support, protection, SETTINGS)
    np.testing.assert_array_equal(result[excluded], rgb[excluded])
    assert np.any(result[(alpha == 24000) & ~protection] != rgb[(alpha == 24000) & ~protection])
    assert np.any(result[:, 27:31] != rgb[:, 27:31])
    for array, expected in zip((rgb, alpha, support, protection), original):
        np.testing.assert_array_equal(array, expected)
    for off in ({"enabled": False}, {"strength": 0}):
        np.testing.assert_array_equal(
            apply_local_texture(rgb, alpha, support, protection, SETTINGS | off), rgb
        )

    rgb[62, 84] = 65535
    outlier = apply_local_texture(rgb, alpha, support, protection, SETTINGS)
    # One near-invisible sample must not disable enhancement around it.
    np.testing.assert_allclose(outlier[61, 80:88], result[61, 80:88], atol=1, rtol=0)


def test_texture_never_pushes_a_channel_to_a_new_endpoint():
    scale = 0.8 + 0.19 * np.cos(np.arange(160) * np.pi / 8)
    input_rgb = scale[:, None] * np.array([1.0, 0.22, 0.00001])
    rgb = linear_to_rgb16(input_rgb[None])
    rgb[0, 80, 0] = 65535
    rgb[0, 96, 0] = 65534
    rgb[0, 88, 2] = 1
    result = render(rgb, strength=1)
    assert np.any(result != rgb)
    assert not np.any((rgb < 65535) & (result == 65535))
    assert not np.any((rgb > 0) & (result == 0))
    np.testing.assert_array_equal(result[0, 80], rgb[0, 80])


def test_texture_ignores_hidden_rgb_in_neighborhood_evidence():
    from blackmask.texture import apply_local_texture

    rgb = gray16(0.16 + 0.02 * np.cos(np.arange(96) * np.pi / 8), height=4)
    alpha = np.full(rgb.shape[:2], 65535, np.uint16)
    alpha[:, :24] = 0
    visible = alpha != 0
    support = np.full_like(alpha, 65535)
    protection = np.zeros_like(alpha, bool)
    rgb[~visible] = 0
    white_hidden = rgb.copy()
    white_hidden[~visible] = 65535
    black = apply_local_texture(rgb, alpha, support, protection, SETTINGS)
    white = apply_local_texture(white_hidden, alpha, support, protection, SETTINGS)
    assert np.any(black[:, 24:36] != rgb[:, 24:36])
    np.testing.assert_array_equal(black[visible], white[visible])


def test_texture_strips_preserve_registration_across_a_core_boundary():
    from blackmask.texture import apply_local_texture

    height, width = 147, 15
    rows = np.arange(height)[:, None]
    columns = np.arange(width)[None, :]
    luminance = 0.16 + 0.012 * np.cos(rows * np.pi / 16) + 0.007 * np.sin(columns * np.pi / 8)
    rgb = linear_to_rgb16(np.broadcast_to(luminance[..., None], (height, width, 3)))
    alpha = np.full(luminance.shape, 65535, np.uint16)
    alpha[126:131, :6] = 22000
    support = np.full_like(alpha, 65535)
    support[:, 0] = 29000
    protection = np.zeros_like(alpha, bool)
    protection[127:130, 3:6] = True
    settings = SETTINGS | {"scale_px": 16, "grain_guard": 0.0005, "preserve_highlights": 1}
    striped = apply_local_texture(rgb, alpha, support, protection, settings)
    single_strip = apply_local_texture(
        rgb.transpose(1, 0, 2), alpha.T, support.T, protection.T, settings
    )
    assert np.any(striped[126:130, 6:] != rgb[126:130, 6:])
    np.testing.assert_array_equal(striped, single_strip.transpose(1, 0, 2))


def test_default_guards_keep_broad_lighting_and_fine_grain_in_a_mixed_signal():
    columns = np.arange(384)
    rng = np.random.default_rng(903)
    lighting = 0.006 * np.cos(2 * np.pi * columns / 128)
    detail = 0.012 * np.cos(2 * np.pi * columns / 16)
    grain = rng.normal(0, 0.0012, columns.shape)
    original = gray16(0.10 + lighting + detail + grain)
    adjusted = render(original, grain_guard=0.0005, preserve_highlights=1)
    before = srgb_to_linear(original[0, 128:256, 0] / 65535)
    after = srgb_to_linear(adjusted[0, 128:256, 0] / 65535)
    original_band, adjusted_band = np.abs(np.fft.rfft(before)), np.abs(np.fft.rfft(after))
    assert abs(after.mean() - before.mean()) < 0.00025
    assert 0.98 < adjusted_band[1] / original_band[1] < 1.02
    assert adjusted_band[8] / original_band[8] > 1.12
    assert np.linalg.norm(adjusted_band[32:]) < 1.06 * np.linalg.norm(original_band[32:])


def test_texture_rejects_malformed_numbers_and_unregistered_operands():
    from blackmask.texture import apply_local_texture

    rgb = gray16(np.full(16, 0.15))
    alpha = np.full(rgb.shape[:2], 65535, np.uint16)
    protection = np.zeros_like(alpha, bool)
    for fields in (
        {"enabled": 1},
        {"strength": True},
        {"scale_px": 17},
        {"grain_guard": float("nan")},
    ):
        with pytest.raises(ProjectError):
            apply_local_texture(rgb, alpha, alpha, protection, SETTINGS | fields)
    with pytest.raises(ProjectError):
        apply_local_texture(rgb, alpha, alpha.T, protection, SETTINGS)
