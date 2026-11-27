from copy import deepcopy
from hashlib import sha256

import numpy as np
import pytest

from blackmask import background_pattern
from blackmask.background_pattern_generation import generate_background_pattern
from blackmask.project import ProjectError


def wave(**changes):
    return {
        "id": "wave",
        "type": "wave",
        "enabled": True,
        "center_xy": [4, 3],
        "rotation_degrees": 0,
        "bend_px": 0,
        "wavelength_px": 8,
        "spacing_px": 2,
        "phase_degrees": 0,
        "band_count": 2,
        "feather_px": 0.5,
        "first_tone": "tone2",
        **changes,
    }


def oval(**changes):
    return {
        "id": "oval",
        "type": "oval",
        "enabled": True,
        "center_xy": [4, 3],
        "rotation_degrees": 0,
        "radii_xy": [2, 2],
        "softness": 0.5,
        "tone": "tone1",
        **changes,
    }


def contour(**changes):
    return {
        "id": "contour",
        "type": "contour",
        "enabled": True,
        "center_xy": [4, 3],
        "rotation_degrees": 0,
        "radii_xy": [8, 7],
        "softness": 0.7,
        "seed": 17,
        **changes,
    }


def pattern_settings(**changes):
    return {
        "enabled": True,
        "strength": 1,
        "tones_srgb": ["#010101", "#202020"],
        "reverse": False,
        "shapes": [wave()],
        **changes,
    }


def test_pattern_wave_signed_field_and_reverse():
    settings = background_pattern.normalize_background_pattern(pattern_settings(), 9, 7)
    field = background_pattern.make_background_pattern(settings, (9, 7))
    background = np.full((7, 9, 3), 2827, dtype=np.uint16)
    np.testing.assert_array_equal(field[[0, 2, 3, 4, 6], 4], [32768, 65535, 32768, 1, 32768])
    result = background_pattern.combine_background_pattern(background, field, settings)
    np.testing.assert_array_equal(result[[2, 3, 4], 4, 0], [8224, 2827, 257])
    settings["reverse"] = True
    result = background_pattern.combine_background_pattern(background, field, settings)
    np.testing.assert_array_equal(result[[2, 3, 4], 4, 0], [257, 2827, 8224])
    assert np.all(background == 2827)


def test_pattern_oval_feather_cancel_and_crop():
    settings = background_pattern.normalize_background_pattern(
        pattern_settings(shapes=[oval()]), 9, 7
    )
    sample = background_pattern.sample_background_pattern(
        settings, (9, 7), np.array([4, 5.5, 7]), np.array([3, 3, 3])
    )
    np.testing.assert_array_equal(sample, [1, 16384, 32768])
    settings["shapes"].append(oval(id="opposite", tone="tone2"))
    assert np.all(background_pattern.make_background_pattern(settings, (9, 7)) == 32768)
    spec = pattern_settings(shapes=[wave(rotation_degrees=12, bend_px=1.4), oval()])
    settings = background_pattern.normalize_background_pattern(spec, 9, 7)
    field = background_pattern.make_background_pattern(settings, (9, 7))
    yy, xx = np.mgrid[1:6, 2:7]
    np.testing.assert_array_equal(
        background_pattern.sample_background_pattern(settings, (9, 7), xx, yy),
        field[1:6, 2:7],
    )


def test_pattern_irregularity_preserves_v1_and_crops():
    baseline = pattern_settings(shapes=[wave(), oval()])
    legacy = "2aed1a8ce116623cfe3873c04660da1c4bb37167c9be7fd917a74d6eaca1e06c"
    for settings in (baseline, dict(baseline, irregularity=0)):
        field = background_pattern.make_background_pattern(settings, (9, 7))
        assert sha256(field.astype("<u2").tobytes()).hexdigest() == legacy
        assert "irregularity" not in background_pattern.normalize_background_pattern(settings, 9, 7)
    size = (121, 101)
    settings = pattern_settings(
        shapes=[
            wave(center_xy=[64, 65], bend_px=8, wavelength_px=108, spacing_px=11, feather_px=5),
            oval(center_xy=[71, 28], radii_xy=[24, 31]),
        ],
        generator={"version": 1, "style": "mixed", "seed": 17},
    )
    field = background_pattern.make_background_pattern(settings, size)
    warped = dict(settings, irregularity=0.8)
    result = background_pattern.make_background_pattern(warped, size)
    assert not np.array_equal(result, field)
    np.testing.assert_array_equal(result, background_pattern.make_background_pattern(warped, size))
    assert not np.array_equal(
        result,
        background_pattern.make_background_pattern(
            dict(warped, generator=dict(settings["generator"], seed=18)), size
        ),
    )
    np.testing.assert_array_equal(
        background_pattern.make_background_pattern(warped, size, crop_xyxy=[2, 7, 98, 85]),
        result[7:85, 2:98],
    )


def test_abstract_contours_have_both_tones_and_quiet_space():
    size = (121, 101)
    settings = pattern_settings(shapes=generate_background_pattern("abstract", 17, *size))
    field = background_pattern.make_background_pattern(settings, size)
    assert field.min() >= 1
    assert np.any(field < 32768) and np.any(field > 32768) and np.any(field == 32768)
    different = pattern_settings(shapes=generate_background_pattern("abstract", 18, *size))
    assert not np.array_equal(field, background_pattern.make_background_pattern(different, size))
    np.testing.assert_array_equal(
        background_pattern.make_background_pattern(settings, size, crop_xyxy=[5, 11, 84, 85]),
        field[11:85, 5:84],
    )
    yy, xx = np.mgrid[-5:10, -7:128]
    extended = background_pattern.sample_background_pattern(settings, size, xx, yy)
    assert np.any(extended[:5] != 32768)
    np.testing.assert_array_equal(extended[5:, 7:128], field[:10])


@pytest.mark.parametrize(
    "changes",
    [
        {"shapes": [wave(), wave()]},
        {"shapes": [wave(id=f"wave-{index}") for index in range(9)]},
        {"shapes": [wave(rotation_degrees=360)]},
        {"shapes": [wave(feather_px=2.5)]},
        {"shapes": [wave(band_count=True)]},
        {"shapes": [wave(bend_px=float("nan"))]},
        {"generator": {"version": 2, "style": "mixed", "seed": 17}},
        {"tones_srgb": ["#ffffff", "no"]},
        {"irregularity": True},
        {"irregularity": float("nan")},
        {"irregularity": 1.01},
        {"irregularity": -0.01},
        {"shapes": [{k: v for k, v in contour().items() if k != "seed"}]},
        {"shapes": [contour(seed=True)]},
        {"shapes": [contour(seed=2**32)]},
        {"shapes": [contour(tone="tone1")]},
    ],
)
def test_pattern_validation_and_exact_identity(changes):
    with pytest.raises(ProjectError):
        background_pattern.normalize_background_pattern(
            pattern_settings(enabled=False, **changes), 9, 7
        )


def test_pattern_preserves_exact_disabled_and_zero_samples():
    value = pattern_settings(tones_srgb=["#aa22ec", "#345def"])
    settings = background_pattern.normalize_background_pattern(value, 9, 7)
    old = deepcopy(settings)
    value["shapes"][0]["center_xy"][0] = 0
    assert settings == old
    assert settings["tones_srgb"] == ["#AA22EC", "#345DEF"]
    background = np.arange(7 * 9 * 3, dtype=np.uint16).reshape(7, 9, 3)
    field = background_pattern.make_background_pattern(settings, (9, 7))
    settings["enabled"] = False
    np.testing.assert_array_equal(
        background_pattern.combine_background_pattern(background, field, settings), background
    )
    settings.update(enabled=True, strength=0)
    np.testing.assert_array_equal(
        background_pattern.combine_background_pattern(background, field, settings), background
    )
    for invalid in (field.astype(np.int16), field[:-1], np.zeros_like(field)):
        with pytest.raises(ProjectError):
            background_pattern.combine_background_pattern(background, invalid, settings)
