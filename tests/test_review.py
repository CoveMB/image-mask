import json
from pathlib import Path

import numpy as np
from PIL import Image
from test_matte_operations import approve, prepared, run_matte


def test_same_native_crops_and_manifest_mapping(tmp_path):
    from blackmask.review import review_project

    _, project, result = prepared(tmp_path)
    approve(project, result)
    matted = run_matte(project)
    output = review_project(
        project, revision=matted["revision"], crops=[[1, 0, 3, 2], [0, 0, 1, 1]]
    )
    manifest = json.loads(Path(output["manifest_file"]).read_text())
    assert manifest["crops"][0]["displayed_dimensions_wh"] == [2, 2]
    assert manifest["crops"][0]["native_origin_xy"] == [1, 0]
    directory = Path(output["manifest_file"]).parent
    black = np.array(Image.open(directory / manifest["crops"][0]["files"]["black_RGB8_VIEW"]))
    assert black.shape == (2, 2, 3)
    assert (
        review_project(project, revision=matted["revision"], crops=[[1, 0, 3, 2], [0, 0, 1, 1]])
        == output
    )
