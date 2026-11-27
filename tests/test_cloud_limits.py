"""Cloud series must not visit unbounded inactive exterior or visible support."""

import numpy as np
import pytest
from test_cloud import operands, settings

from blackmask.cloud import CloudOperands, CloudProjector
from blackmask.project import ProjectError


def test_far_exterior_zero_density_requires_no_field_sampling(monkeypatch):
    cloud = operands([[60000, 50000]], [[65535, 65535]], [[0, 0]])
    projector = CloudProjector(cloud)

    def unexpected(*_args):
        pytest.fail("Visited a source tile outside all sample footprints")

    monkeypatch.setattr(projector, "_samples", unexpected)
    result = projector.project(np.array([-596_000_000.0, 596_000_000.0]), np.array([0.5]), (1, 1))
    np.testing.assert_array_equal(result.opacity, [[0, 0]])


def test_huge_analytic_projection_rejects_before_visiting_a_source_tile(monkeypatch):
    width, height = 1, 32768
    plane = np.zeros((height, width), np.uint16)
    cloud = CloudOperands(
        plane,
        plane,
        plane,
        settings(width, height, radii_xy=[2 * height, 2 * height]),
        {"coverage": [], "clear": [], "focus": None},
        (width, height),
    )
    projector = CloudProjector(cloud)

    def unexpected(*_args):
        pytest.fail("Started evaluating an inadmissible source footprint")

    monkeypatch.setattr(projector, "_samples", unexpected)
    with pytest.raises(ProjectError, match="Cloud projection.*sample"):
        projector.project(np.array([0.5]), np.array([height / 2]), (50_000_000, 50_000_000))


def test_outside_clear_edge_is_counted_even_when_its_optical_density_is_zero():
    cloud = operands(
        [[65535, 65535]],
        [[65535, 65535]],
        [[65535, 0]],
        tint_srgb="#FFFFFF",
        amount=1,
        light_amount=1,
    )
    grid = CloudProjector(cloud).project(np.array([1.0]), np.array([0.5]), (100, 1))
    np.testing.assert_array_equal(grid.opacity, [[0]])
    np.testing.assert_array_equal(grid.light_rgb, [[[0, 0, 0]]])


def test_extreme_series_can_render_when_only_a_small_source_strip_is_active(monkeypatch):
    from blackmask.series_framing import (
        SeriesSettings,
        compute_series_layout,
        render_series,
        series_sampling_plan,
    )

    width, height = 1, 32768
    shape = (height, width)
    alpha = np.full(shape, 65535, np.uint16)
    foreground = np.zeros((*shape, 3), np.uint16)
    cloud = CloudOperands(
        alpha.copy(),
        alpha.copy(),
        np.zeros(shape, np.uint16),
        settings(width, height, tint_srgb="#FFFFFF"),
        {"coverage": [], "clear": [], "focus": None},
        (width, height),
    )
    original = CloudProjector._samples

    def bounded(projector, x, y):
        assert np.max(np.abs(x)) < 10
        return original(projector, x, y)

    monkeypatch.setattr(CloudProjector, "_samples", bounded)
    layout = compute_series_layout(
        alpha,
        SeriesSettings(
            output_width_px=32768,
            output_height_px=1,
            side_margin_tenths_percent=150,
            minimum_vertical_margin_tenths_percent=50,
        ),
    )
    result = render_series(foreground, alpha, series_sampling_plan(layout), cloud=cloud)
    assert result.shape == (1, 32768, 3)
    assert np.any(result > 0)
    assert np.all(result[0, (0, -1)] == 0)
