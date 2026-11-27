"""Native and projected optical Cloud behavior with independently computed expectations."""

import numpy as np
import pytest

AREA = {"coverage": [], "clear": [], "focus": None}


def settings(width=6, height=4, **changes):
    return {
        "enabled": True,
        "amount": 0.72,
        "tint_srgb": "#282828",
        "seed": 12,
        "size": 0.32,
        "warp": 0.48,
        "center_xy": [width * 0.53, height * 0.65],
        "radii_xy": [width * 1.45, height * 1.25],
        "light_amount": 0.55,
        **changes,
    }


def operands(density, light, clear, **changes):
    from blackmask.cloud import CloudOperands

    native = np.asarray(density, dtype=np.uint16)
    height, width = native.shape
    return CloudOperands(
        native,
        np.asarray(light, dtype=np.uint16),
        np.asarray(clear, dtype=np.uint16),
        settings(width, height, **changes),
        AREA,
        (width, height),
    )


def test_native_fields_are_broad_deterministic_and_independent_of_optics():
    from blackmask.cloud import make_cloud_fields

    size = (96, 72)
    config = settings(*size)
    density, light = make_cloud_fields(config, AREA, "a" * 64, size)
    for field in (density, light):
        assert field.shape == (72, 96) and field.dtype == np.uint16
        assert int(field.max()) - int(field.min()) > 10000
    native = density.astype(np.int32)
    assert np.abs(np.diff(native, axis=1)).mean() < np.abs(native[:, 24:] - native[:, :-24]).mean()
    changed = dict(config, amount=0.19, tint_srgb="#111C2A", light_amount=1)
    for before, after in zip(
        (density, light), make_cloud_fields(changed, AREA, "a" * 64, size), strict=True
    ):
        np.testing.assert_array_equal(before, after)
    seeded = make_cloud_fields(dict(config, seed=13), AREA, "a" * 64, size)
    assert all(
        np.any(before != after) for before, after in zip((density, light), seeded, strict=True)
    )


@pytest.mark.parametrize("tint", ["#000000", "#282828", "#1F4B22"])
def test_native_cloud_linear_colour_and_exact_off_and_clear(tint):
    from blackmask.cloud import blend_cloud_into_result

    incoming = np.array(
        [[[0, 0, 0], [13000, 22000, 17000], [1, 2, 3], [4, 5000, 32001]]], np.uint16
    )
    cloud = operands(
        [[42000, 52000, 65535, 0]],
        [[12000, 29000, 65535, 10000]],
        [[0, 32768, 65535, 0]],
        tint_srgb=tint,
    )
    expected = incoming.copy()

    def linear(encoded):
        return encoded / 12.92 if encoded <= 0.04045 else ((encoded + 0.055) / 1.055) ** 2.4

    for pixel in (0, 1):
        area = (
            0.72
            * int(cloud.density16[0, pixel])
            * (65535 - int(cloud.clear16[0, pixel]))
            / 65535**2
        )
        multiplier = 0.45 + 0.55 * int(cloud.light16[0, pixel]) / 65535
        for channel in range(3):
            offset = channel * 2 + 1
            tint_channel = linear(int(tint[offset : offset + 2], 16) / 255)
            original = linear(int(incoming[0, pixel, channel]) / 65535)
            mixed = (1 - area) * original + area * tint_channel * multiplier
            encoded = 12.92 * mixed if mixed <= 0.0031308 else 1.055 * mixed ** (1 / 2.4) - 0.055
            expected[0, pixel, channel] = round(encoded * 65535)

    actual = blend_cloud_into_result(incoming.copy(), cloud)
    np.testing.assert_array_equal(actual, expected)
    assert np.any(actual[0, 1] != incoming[0, 1])
    cloud.settings["enabled"] = False
    np.testing.assert_array_equal(blend_cloud_into_result(incoming.copy(), cloud), incoming)


@pytest.mark.parametrize("bad", ["#000", "#000000FF", "black", "#ZZBCAA", "", None, 32])
def test_cloud_colour_requires_a_six_digit_hex_even_while_off(bad):
    from blackmask.cloud import validate_cloud_settings

    with pytest.raises(ValueError, match="colour"):
        validate_cloud_settings(settings(tint_srgb=bad, enabled=False), 6, 4)
    assert validate_cloud_settings(settings(tint_srgb="#1a2B3c"), 6, 4)["tint_srgb"] == "#1A2B3C"


@pytest.mark.parametrize(
    ("density", "light", "clear", "shade", "opacity", "added"),
    [
        ([65535, 0], [0, 65535], [0, 0], 1, 0.5, 0),
        ([0, 65535], [0, 65535], [0, 0], 1, 0.5, 0.5),
        ([65535, 0], [0, 65535], [0, 0], 0.5, 0.5, 0.25),
        (
            [65535, 65535],
            [0, 65535],
            [0, 32768],
            1,
            1 - 32768 / (2 * 65535),
            (1 - 32768 / 65535) / 2,
        ),
        ([65535, 65535], [0, 65535], [0, 65535], 1, 0, 0),
    ],
)
def test_projection_filters_the_two_optical_moments(density, light, clear, shade, opacity, added):
    from blackmask.cloud import CloudProjector

    cloud = operands([density], [light], [clear], amount=1, tint_srgb="#FFFFFF", light_amount=shade)
    projected = CloudProjector(cloud).project(np.array([1.0]), np.array([0.5]), (2.0, 1.0))
    np.testing.assert_allclose(projected.opacity, [[opacity]], rtol=0, atol=1e-14)
    np.testing.assert_allclose(projected.light_rgb, [[[added] * 3]], rtol=0, atol=1e-14)


def test_projector_uses_saved_interior_and_analytic_exterior_in_crossing_footprint(monkeypatch):
    from blackmask import cloud as module

    cloud = operands(
        [[12000, 24000]], [[65535, 65535]], [[0, 0]], amount=1, tint_srgb="#FFFFFF", light_amount=1
    )
    projector = module.CloudProjector(cloud)

    def density(settings, size, x, y):
        assert np.all((x < 0) | (x >= size[0]))
        return np.broadcast_to(np.uint16(48000), np.broadcast_shapes(x.shape, y.shape))

    def light(settings, size, x, y):
        assert np.all((x < 0) | (x >= size[0]))
        return np.zeros(np.broadcast_shapes(x.shape, y.shape), np.uint16)

    monkeypatch.setattr(module, "sample_cloud_density", density)
    monkeypatch.setattr(module, "sample_cloud_light", light)
    interior = projector.project(np.array([1.0]), np.array([0.5]), (2.0, 1.0))
    crossing = projector.project(np.array([0.0]), np.array([0.5]), (2.0, 1.0))
    np.testing.assert_allclose(interior.opacity, [[18000 / 65535]])
    np.testing.assert_allclose(crossing.opacity, [[30000 / 65535]])
    np.testing.assert_allclose(crossing.light_rgb, [[[6000 / 65535] * 3]])


def test_projection_honors_subject_support_outside_optical_footprint():
    from blackmask.cloud import CloudProjector

    cloud = operands(
        [[65535, 65535, 65535, 65535]],
        [[65535] * 4],
        [[65535, 0, 0, 0]],
        amount=1,
        tint_srgb="#FFFFFF",
        light_amount=1,
    )
    projected = CloudProjector(cloud).project(
        np.array([1.5, 2.5]),
        np.array([0.5]),
        (1.0, 1.0),
        subject_support_xyxy=(np.array([0, 1]), np.array([0]), np.array([2, 3]), np.array([1])),
    )
    np.testing.assert_array_equal(projected.opacity, [[0, 1]])
    np.testing.assert_array_equal(projected.light_rgb, [[[0, 0, 0], [1, 1, 1]]])
