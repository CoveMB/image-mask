import numpy as np
import pytest

from blackmask import guidance


def region(role, shape="rectangle", **values):
    return {"id": role, "role": role, "shape": shape, "xyxy": [1, 1, 5, 4], **values}


def document(regions):
    return {"schema_version": 1, "master_id": "a" * 64, "width": 7, "height": 5, "regions": regions}


def raster(regions, **kwargs):
    return guidance.rasterize_regions(document(regions), **kwargs)


def test_native_half_open_labels_and_unknown_corridor():
    result = raster([region("foreground"), region("unknown", xyxy=[2, 0, 3, 5])])
    assert set(np.unique(result.trimap)) == {128, 255}
    assert result.trimap[1, 1] == 255 and result.trimap[3, 4] == 255
    assert result.trimap[4, 1] == 128 and result.trimap[1, 5] == 128
    assert np.all(result.trimap[:, 2] == 128)


def test_negative_hints_and_kept_membership_do_not_certify_background():
    r = raster(
        [{"id": "hint", "role": "remove", "shape": "point", "xy": [1, 2], "group_id": "wing"}]
    )
    assert np.all(r.trimap == 128)


def test_foreground_background_conflict_rejected_before_unknown_precedence():
    with pytest.raises(ValueError, match="foreground.*background"):
        raster([region("foreground"), region("background"), region("unknown")])


def test_support_inward_feather_zero_and_scope_clip():
    zero = raster([region("support", feather_px=0)], scope_xyxy=[0, 0, 3, 5]).support16
    assert np.count_nonzero(zero) == 6 and np.all(zero[1:4, 1:3] == 65535)
    feather = raster([region("support", feather_px=2)]).support16
    assert feather[1, 1] == 32768 and feather[2, 2] == 65535
    assert feather[0, 2] == 0


def test_stroke_radius_native_and_categorical():
    r = raster(
        [
            {
                "id": "line",
                "role": "background",
                "shape": "stroke",
                "points": [[1, 2], [5, 2]],
                "radius_px": 1,
            }
        ]
    )
    assert r.trimap[2, 0] == 0 and r.trimap[1, 3] == 0
    assert r.trimap[0, 3] == 128 and r.trimap[2, 6] == 0
    assert set(np.unique(r.trimap)) == {0, 128}


@pytest.mark.parametrize(
    "change",
    [
        {"xyxy": [1, 1, 8, 3]},
        {"xyxy": [1, 1, 1, 3]},
        {"xyxy": [True, 1, 3, 4]},
        {"unexpected": 1},
        {"role": "prose"},
    ],
)
def test_invalid_geometry_unknown_keys_and_roles(change):
    with pytest.raises(ValueError):
        raster([{**region("foreground"), **change}])


def test_saved_partial_locks_conflict_and_new_project_rejection():
    lock = region("lock", revision="rev-001")
    with pytest.raises(ValueError, match="saved"):
        raster([lock])
    saved = np.full((5, 7), 12345, dtype=np.uint16)
    r = raster([lock], saved_alpha={"rev-001": saved})
    assert np.count_nonzero(r.protection) == 12
    assert np.all(r.lock_values16[r.protection] == 12345)
    with pytest.raises(ValueError, match="lock"):
        raster([lock, region("foreground")], saved_alpha={"rev-001": saved})


def test_change_needed_cores_cannot_expand_feathered_support():
    saved = np.full((5, 7), 12345, dtype=np.uint16)
    with pytest.raises(ValueError, match="support"):
        raster([region("foreground"), region("support", feather_px=2)], parent_alpha=saved)
