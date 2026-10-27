"""Configured synthetic storage journey; model stubs are not photographic acceptance."""

import hashlib
import importlib
import json
import os
import select
import shutil
import socket
import stat
import subprocess
import sys
from pathlib import Path
from typing import ClassVar
from unittest.mock import patch

import numpy as np
import pytest
import tifffile
from PIL import Image
from storage_journey_process import filesystem_entries, install_guard, perform, running_process
from test_cache_management import inventory
from test_export import DEFAULT_MEMBERS
from test_ingest import saved_raster, tiff
from test_library import command, configuration
from test_matte import cache_identity
from test_operations import edits, request
from test_previews import jpeg, marker
from test_viewer import http

from blackmask import library, operations, previews, review
from blackmask.export import export_project
from blackmask.framing import read_framing_preset, save_framing_preset
from blackmask.ingest import srgb_profile
from blackmask.project import ProjectError, read_project, read_revision
from blackmask.series_framing import read_series_settings, save_series_settings


class CachedPrediction:
    identity: ClassVar[dict] = {
        name: value for name, value in cache_identity().items() if name != "developed_id"
    }

    def __init__(self, cache):
        pass

    def predict(self, pixels, trimap, device):
        return np.full(trimap.shape, 0.5), {"fixture": "synthetic", "device": device}


def test_fade_reduction_cache_clear_preserves_frozen_deliveries_and_standalone_reconstruction(
    tmp_path,
):
    """Transferred layout and both reductions survive cache clearing and isolated delivery replay."""
    import inspect

    from test_appearance_recipes import saved_recipe
    from test_background import scalar_background
    from test_cache_management import predictions
    from test_effects import fixture_project
    from test_fade_reduction import area, rectangle, reduction_request, saved_reduction
    from test_series_framing import (
        scalar_background_blend,
        scalar_matrices,
        scalar_sample,
        scalar_weights,
    )
    from test_shadow_fade import fade_request, scalar_fade
    from test_spatial_fade import arc_settings, spatial_request, spatial_settings
    from test_viewer import appearance_layout_request, running

    from blackmask.project import digest
    from blackmask.series_framing import SeriesSettings

    source = (np.arange(72).reshape(4, 6, 3) * 617 + 123).astype(np.uint16)
    project, _, accepted = fixture_project(tmp_path, source)
    protected = np.zeros((4, 6), np.uint16)
    protected[1, 3] = 65535
    Image.fromarray(protected).save(project / "protected.png")
    settings = spatial_settings(6, 4)
    settings["preserve_highlights"] = 0.65
    settings["oval"].update(center_xy=[0, 0], inner_radii_xy=[0.5, 0.5], transition_width=0.5)
    operations.apply_operation(
        project, spatial_request(project, settings, spatial_fade_protection_file="protected.png")
    )
    document = area(
        rectangle(amount=0.5, box=[0, 0, 6, 4]), rectangle("full", 1.0, box=[5, 0, 6, 4])
    )
    result = operations.apply_operation(project, reduction_request(project, document))
    _, saved = saved_reduction(project, result["revision"])
    assert saved.protection[1, 3] and saved.weight16[1, 3] > 0 and saved.reduction16[1, 3] == 32768
    from test_exposure import rectangle as effect_rectangle

    operations.apply_operation(
        project,
        fade_request(
            project,
            amount=0.35,
            preserve=0.4,
            area={
                "regions": [effect_rectangle("all", [0, 0, 6, 4])],
                "protection": [effect_rectangle("protected", [3, 1, 4, 2])],
            },
        ),
    )
    result = operations.apply_operation(
        project, reduction_request(project, document, target="shadow_fade")
    )
    # A different saved source supplies geometry; target operands stay target-owned.
    layout_root = tmp_path / "layout-source"
    layout_root.mkdir()
    layout_project, _, _ = fixture_project(layout_root, np.full((4, 11, 3), 30000, np.uint16))
    source_settings = spatial_settings(11, 4)
    source_settings.update(enabled=False, preserve_highlights=0.65, arcs_enabled=True)
    source_settings["oval"].update(
        center_xy=[1, 0], inner_radii_xy=[1, 1], transition_width=1, rotation_degrees=37
    )
    source_settings["arcs"] = [
        arc_settings(
            center_xy=[6, 2],
            half_span=4,
            bend=-2,
            end_softness=1,
            transition_width=1,
            rotation_degrees=37,
        )
    ]
    source_result = operations.apply_operation(
        layout_project,
        dict(spatial_request(layout_project, source_settings), scope_xyxy=[0, 0, 11, 4]),
    )
    portable = saved_recipe(layout_project, source_result["revision"], ["spatial_layout"])
    recipe_path = layout_root / "saved-layout.json"
    recipe_path.write_bytes(portable)
    source_before = inventory(layout_root)
    target_before = inventory(project)
    previous_revision = project / "revisions" / result["revision"]
    with running(project) as server:
        data = appearance_layout_request(server)
        data.update(recipe_json=portable.decode(), spatial_draft=settings)
        status, body, _ = http(server, "/api/appearance-layout-preview", "POST", data)
        assert status == 200, body
        proposal = json.loads(body)["spatial_fade"]
    assert inventory(project) == target_before
    assert proposal["enabled"] is True  # Source master is OFF; target master is retained.
    assert proposal["oval"]["center_xy"] == [1, 1]
    assert proposal["oval"]["inner_radii_xy"] == [0.5, 0.5]
    assert proposal["oval"]["transition_width"] == 0.5
    assert proposal["oval"]["rotation_degrees"] == 37
    imported_arc = proposal["arcs"][0]
    assert imported_arc["center_xy"] == [3.5, 2]
    assert (imported_arc["half_span"], imported_arc["bend"], imported_arc["end_softness"]) == (
        2,
        -1,
        0.5,
    )
    assert imported_arc["id"] != source_settings["arcs"][0]["id"]
    result = operations.apply_operation(project, spatial_request(project, proposal, candidate=True))
    selected_directory = project / "revisions" / result["revision"]
    manifest = read_revision(project, result["revision"], read_project(project)["developed_id"])
    assert manifest["spatial_fade"]["settings"] == proposal
    assert manifest["spatial_fade"]["candidate_comparison"] is True
    for name in (
        "base_alpha16.png",
        "effects/spatial-fade/protection16.png",
        "effects/spatial-fade/reduction.json",
        "effects/spatial-fade/reduction16.png",
        "effects/shadow-fade/protection16.png",
        "effects/shadow-fade/reduction.json",
        "effects/shadow-fade/reduction16.png",
    ):
        assert (
            saved_raster(selected_directory / name).read_bytes()
            == saved_raster(previous_revision / name).read_bytes()
        )
    assert inventory(layout_root) == source_before
    assert read_project(project)["accepted_revision"] == accepted["revision"]
    selected = result["revision"]
    flat = export_project(project, revision=selected, draft=True, variants=("transparent",))
    assert not flat.get("editable_companion")
    assert not any("reduction" in path.name for path in Path(flat["directory"]).iterdir())
    margins = {"left_px": 1, "right_px": 2, "top_px": 2, "bottom_px": 1}
    modes = [
        {"variants": ("editable", "transparent")},
        {"variants": ("editable",), "framing": margins, "framed_transparent": True},
        {
            "variants": ("editable",),
            "series": SeriesSettings(output_width_px=17, output_height_px=19).to_dict(),
            "framed_transparent": True,
        },
    ]
    deliveries = [export_project(project, revision=selected, draft=True, **mode) for mode in modes]
    frozen = {}
    for delivery in deliveries:
        paths = [Path(delivery["directory"])]
        if delivery.get("editable_companion"):
            paths.append(Path(delivery["editable_companion"]["directory"]))
        for directory in paths:
            frozen[directory] = {p.name: digest(p.read_bytes()) for p in directory.iterdir()}
    predictions(project, count=1)
    permanent_before = inventory(project)
    inspected = operations.inspect_processing_cache(project)
    assert inspected["candidates"] and not inspected["blockers"]
    cleared = operations.clear_processing_cache(project, inspected["candidate_digest"])
    assert inventory(project) == {
        name: value for name, value in permanent_before.items() if name not in cleared["removed"]
    }
    for directory, hashes in frozen.items():
        assert hashes == {p.name: digest(p.read_bytes()) for p in directory.iterdir()}
    assert read_project(project)["accepted_revision"] == accepted["revision"]
    isolated = tmp_path / "delivered-only"
    isolated.mkdir()
    for directory in frozen:
        shutil.copytree(directory, isolated / directory.name)
    retained_project = tmp_path / "project-unavailable"
    project.rename(retained_project)
    capture = tmp_path / "capture-unavailable.tif"
    (tmp_path / "source.tif").rename(capture)
    model_root = tmp_path / "unavailable-models"
    model_root.mkdir()
    model_probe = model_root / "synthetic-model.bin"
    model_probe.write_bytes(b"Synthetic denial probe; no model weights")
    probes = [
        retained_project / "state.json",
        capture,
        layout_project / "state.json",
        recipe_path,
        retained_project / next(iter(frozen)).relative_to(project) / "result_rgb16.tif",
        model_probe,
    ]
    probe_hashes = [digest(path.read_bytes()) for path in probes]
    forbidden_roots = [
        project,
        retained_project,
        tmp_path / "source.tif",
        capture,
        layout_root,
        model_root,
    ]
    program = (
        """import ctypes,errno,fcntl,json,math,os,socket,struct,sys,threading
from pathlib import Path
from types import SimpleNamespace
import numpy as np,tifffile
from PIL import Image
"""
        + inspect.getsource(install_guard)
        + r"""
root=Path(sys.argv[1]).resolve()
probes=json.loads(sys.argv[2]); port=int(sys.argv[3]); mode=sys.argv[4]
runtime_roots=[Path(sys.base_prefix).resolve(),Path(sys.prefix).resolve()]
runtime_roots += [Path(module.__file__).resolve().parent for module in (np,tifffile,Image)]
assert all(not Path(probe).is_relative_to(allowed) for probe in probes for allowed in runtime_roots)
libc=ctypes.CDLL(None,use_errno=True)
def native_connect():
 descriptor=libc.socket(socket.AF_INET,socket.SOCK_STREAM,0)
 assert descriptor>=0,('socket',ctypes.get_errno())
 try:
  family=bytes((16,socket.AF_INET)) if sys.platform=='darwin' else struct.pack('H',socket.AF_INET)
  address=ctypes.create_string_buffer(family+struct.pack('!H',port)+socket.inet_aton('127.0.0.1')+bytes(8))
  status=libc.connect(descriptor,address,16)
  return status,ctypes.get_errno()
 finally: libc.close(descriptor)
if mode=='control':
 for probe in probes:
  assert Path(probe).read_bytes()
  descriptor=libc.open(probe.encode(),0); assert descriptor>=0
  libc.close(descriptor)
 assert native_connect()[0]==0
 print('unguarded existing-file and native loopback controls passed')
 sys.exit(0)
release,observed=install_guard(root,read_roots=[root,*runtime_roots])
for probe in probes:
 try: Path(probe).read_bytes()
 except PermissionError: pass
 else: raise AssertionError('Python read guard failed: '+probe)
 if mode=='sandbox':
  assert libc.open(probe.encode(),0)==-1
  assert ctypes.get_errno() in (errno.EPERM,errno.EACCES)
with socket.socket() as connection:
 try: connection.connect(('127.0.0.1',port))
 except PermissionError: pass
 else: raise AssertionError('Python network guard failed')
if mode=='sandbox':
 status,error=native_connect()
 assert status==-1 and error in (errno.EPERM,errno.EACCES),(status,error)
"""
        + "\n".join(
            inspect.getsource(helper)
            for helper in (
                scalar_background,
                scalar_background_blend,
                scalar_weights,
                scalar_matrices,
                scalar_sample,
                scalar_fade,
            )
        )
        + r"""
root=Path(sys.argv[1])
def scalar(path):
 with Image.open(path) as image: return np.array(image)
def highlights(foreground):
 result=np.empty(foreground.shape[:2])
 for y,x in np.ndindex(result.shape):
  linear=[v/65535/12.92 if v/65535<=0.04045 else ((v/65535+0.055)/1.055)**2.4 for v in foreground[y,x]]
  luminance=sum(v*c for v,c in zip(linear,(0.2126,0.7152,0.0722)))
  t=max(0,min(1,(luminance-.10)/.65)); result[y,x]=t*t*(3-2*t)
 return result
def operands(directory, factor=1, shadow_factor=1):
 record=json.loads((directory/'manifest.json').read_bytes())
 foreground=tifffile.imread(directory/'foreground_rgb16.tif').astype(float)
 unfaded=tifffile.imread(directory/'unfaded_foreground_rgb16.tif')
 alpha=scalar(directory/'alpha16.png').astype(float)/65535
 shadow=json.loads((directory/'shadow_fade_settings.json').read_bytes())
 assert shadow['schema_version']==3 and shadow['enabled']
 support=scalar(directory/'shadow_fade_support16.png')
 shadow_protected=scalar(directory/'shadow_fade_protection16.png')!=0
 shadow_reduction=scalar(directory/'shadow_fade_reduction16.png').astype(float)/65535
 assert json.loads((directory/'shadow_fade_reduction.json').read_bytes())['regions']
 assert np.any(shadow_protected & (alpha>0) & (alpha<1) & (support>0) & (shadow_reduction<1))
 replay=unfaded.copy(); doubled=foreground.copy()
 for y,x in np.ndindex(alpha.shape):
  if alpha[y,x]>0 and support[y,x]>0 and not shadow_protected[y,x]:
   settings=shadow['settings']; r=(1-(1-shadow_reduction[y,x])**shadow_factor)*65535
   replay[y,x]=scalar_fade(unfaded[y,x],int(support[y,x]),settings['amount'],settings['preserve_highlights'],r)
   doubled[y,x]=scalar_fade(foreground[y,x],int(support[y,x]),settings['amount'],settings['preserve_highlights'],shadow_reduction[y,x]*65535)
 if shadow_factor==1:
  np.testing.assert_array_equal(replay,foreground)
  assert np.any(doubled!=foreground),'fixture must detect applying Shadow fade twice'
 foreground=replay.astype(float)
 weight=scalar(directory/'spatial_fade_weight16.png').astype(float)/65535
 protected=scalar(directory/'spatial_fade_protection16.png')!=0
 reduction=scalar(directory/'spatial_fade_reduction16.png').astype(float)/65535
 assert record['spatial_fade']['schema_version']==2
 preserve=record['spatial_fade']['settings']['preserve_highlights']; assert preserve>0
 assert np.any(protected & (alpha>0) & (alpha<1) & (weight>0) & (reduction<1))
 assert json.loads((directory/'spatial_fade_reduction.json').read_bytes())['regions']
 amount=weight*(1-preserve*highlights(foreground))*(1-reduction)**factor
 amount[protected | (alpha==0)]=0
 stale_highlights=weight*(1-preserve*highlights(unfaded))*(1-reduction)**factor
 stale_highlights[protected | (alpha==0)]=0
 assert np.any(amount!=stale_highlights),'fixture must exercise downstream highlight recalculation'
 return foreground,alpha,amount
def composite(foreground,alpha,amount,background):
 straight=np.empty_like(foreground)
 for y,x,c in np.ndindex(foreground.shape):
  straight[y,x,c]=scalar_background_blend(foreground[y,x,c],int(background[y,x,c]),amount[y,x])
 rgb=np.rint(straight*alpha[...,None]+background*(1-alpha[...,None])).astype(np.uint16)
 rgba=np.dstack((np.rint(straight/257).astype(np.uint8),np.rint(alpha*255).astype(np.uint8)))
 return rgb,rgba
native_count=0
for directory in root.iterdir():
 record=json.loads((directory/'manifest.json').read_bytes())
 if not (directory/'spatial_fade_reduction16.png').exists(): continue
 foreground,alpha,amount=operands(directory)
 background=tifffile.imread(directory/'background_rgb16.tif')
 expected,rgba=composite(foreground,alpha,amount,background)
 actual=tifffile.imread(directory/'result_rgb16.tif')
 np.testing.assert_array_equal(expected,actual)
 for wrong in (0,2):
  f,a,q=operands(directory,wrong)
  assert np.any(composite(f,a,q,background)[0]!=actual),'fixture must detect dropped/double reduction'
  f,a,q=operands(directory,shadow_factor=wrong)
  assert np.any(composite(f,a,q,background)[0]!=actual),'fixture must detect dropped/double Shadow reduction'
 if (directory/'transparent_RGBA8_VIEW.png').exists():
  np.testing.assert_array_equal(rgba,scalar(directory/'transparent_RGBA8_VIEW.png'))
 native_count+=1
for directory in root.iterdir():
 record=json.loads((directory/'manifest.json').read_bytes())
 companion=record.get('editable_companion')
 if not companion: continue
 native=root/companion['directory_name']
 foreground,alpha,amount=operands(native)
 if 'margins' in record:
  margins=record['margins']; pad=((margins['top_px'],margins['bottom_px']),(margins['left_px'],margins['right_px']),(0,0))
  background=tifffile.imread(native/'background_rgb16.tif')
  rgb,rgba=composite(foreground,alpha,amount,background)
  expected=np.pad(background,pad,mode='edge')
  x,y=margins['left_px'],margins['top_px']; expected[y:y+rgb.shape[0],x:x+rgb.shape[1]]=rgb
  transparent=np.pad(rgba,pad,mode='constant')
  np.testing.assert_array_equal(expected,tifffile.imread(directory/'result_rgb16.tif'))
  np.testing.assert_array_equal(transparent,scalar(directory/'transparent_RGBA8_VIEW.png'))
 else:
  sampling=json.loads(json.dumps(record['sampling']),object_hook=lambda value:SimpleNamespace(**value))
  width,height=record['layout']['output_dimensions_wh']
  settings=record['background']['settings']; color=[int(settings['color_srgb'][i:i+2],16) for i in (1,3,5)]
  background=scalar_background(height,width,color,settings['variation'])
  x0,y0,x1,y1=record['layout']['subject_bounds_xyxy']; core=np.s_[y0:y1,x0:x1]
  a=np.clip(scalar_sample(alpha[core],sampling,effective=True),0,1)
  q=np.clip(scalar_sample((alpha*amount)[core],sampling,effective=True),0,a)
  ratio=np.divide(q,a,out=np.zeros_like(q),where=a>0)
  straight=np.zeros((*a.shape,3))
  for channel in range(3):
   p=np.clip(scalar_sample((alpha*foreground[...,channel])[core],sampling,effective=True),0,65535*a)
   straight[...,channel]=np.divide(p,a,out=np.zeros_like(p),where=a>0)
  x,y=sampling.x.output_start,sampling.y.output_start; h,w=a.shape
  expected=background.copy(); rgb,rgba=composite(straight,a,ratio,background[y:y+h,x:x+w])
  expected[y:y+h,x:x+w]=rgb
  transparent=np.zeros((height,width,4),np.uint8); rgba[rgba[...,3]==0,:3]=0
  transparent[y:y+h,x:x+w]=rgba
  np.testing.assert_allclose(expected.astype(int),tifffile.imread(directory/'result_rgb16.tif').astype(int),atol=2,rtol=0)
  np.testing.assert_allclose(transparent.astype(int),scalar(directory/'transparent_RGBA8_VIEW.png').astype(int),atol=1,rtol=0)
assert native_count>=1
assert not any(name=='blackmask' or name.startswith('blackmask.') for name in sys.modules)
assert Image.__version__==Image.core.PILLOW_VERSION=='13.0.0'
print('retained native/margins/series deliveries reconstructed without application/project/capture/cache; Pillow/core 13.0.0')
print(json.dumps({'isolation':mode,'denied_existing_files':len(probes),'native_network_denied':mode=='sandbox','observed_reads':sorted(observed)}))
"""
    )
    sandboxed = sys.platform == "darwin" and Path("/usr/bin/sandbox-exec").is_file()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        arguments = [
            sys.executable,
            "-B",
            "-c",
            program,
            str(isolated),
            json.dumps(list(map(str, probes))),
            str(listener.getsockname()[1]),
        ]
        options = {
            "cwd": isolated,
            "env": dict(os.environ, PYTHONPATH=""),
            "capture_output": True,
            "text": True,
            "timeout": 30,
        }
        control = subprocess.run([*arguments, "control"], check=False, **options)
        assert control.returncode == 0, control.stdout + control.stderr
        assert select.select([listener], [], [], 3)[0], "Positive connection did not reach listener"
        connection, _ = listener.accept()
        connection.close()
        arguments.append("sandbox" if sandboxed else "python-audit-only")
        if sandboxed:
            permissions = " ".join(
                "(subpath " + json.dumps(str(path)) + ")" for path in forbidden_roots
            )
            profile = (
                "(version 1)(allow default)(deny network*)(deny file-read* " + permissions + ")"
            )
            arguments = ["/usr/bin/sandbox-exec", "-p", profile, *arguments]
        child = subprocess.run(arguments, check=False, **options)
        assert not select.select([listener], [], [], 0)[0], "Guarded child reached listener"
    assert child.returncode == 0, child.stdout + child.stderr
    assert "retained native/margins/series deliveries reconstructed" in child.stdout
    assert [digest(path.read_bytes()) for path in probes] == probe_hashes
    print(control.stdout.strip())
    print(child.stdout.strip())


def imported_project(tmp_path):
    config_file, destination = configuration(tmp_path)
    for name in ("sam", "vitmatte"):
        directory = tmp_path / "shared-models" / name
        directory.mkdir(parents=True)
        (directory / "retained-model.bin").write_bytes(
            b"Synthetic placeholder, not installed weights"
        )
    with config_file.open("a") as stream:
        stream.write(
            '[models]\nsam_cache = "../shared-models/sam"\nvitmatte_cache = "../shared-models/vitmatte"\n'
        )
    config = library.load_storage_config(config_file)
    library.ensure_library(config)
    y, x = np.indices((64, 96))
    pixels = np.stack(
        (20001 + 17 * x + 31 * y, 30002 + 43 * x + 7 * y, 40003 + 11 * x + 29 * y), axis=-1
    ).astype(np.uint16)
    source = tiff(destination / "Inbox/CAMERA.tif", pixels, profile=srgb_profile())
    sidecar = source.with_suffix(".xmp")
    sidecar.write_bytes(b"synthetic original sidecar")
    originals = {
        path.name: (path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
        for path in (source, sidecar)
    }
    project = library.import_photo(
        config, source, subject="synthetic", development={}, sidecars=(sidecar,)
    )
    assert not source.exists() and not sidecar.exists()
    assert inventory(project.parent / "original") == originals
    assert len(list((destination / "Photos").iterdir())) == 1
    regions = [
        {"id": "empty", "role": "background", "shape": "rectangle", "xyxy": [0, 0, 8, 64]},
        {"id": "solid", "role": "foreground", "shape": "rectangle", "xyxy": [88, 0, 96, 64]},
    ]
    operations.apply_operation(
        project, request(project, guide_edits_file=edits(project, regions)), storage_config=config
    )
    return config_file, config, project, pixels


def matte(project, config):
    selected = config.vitmatte_cache or Path("explicit-synthetic-model-boundary")
    with patch.object(operations, "VitMatteSession", wraps=CachedPrediction) as construct:
        result = operations.apply_operation(
            project,
            request(project, kind="matte"),
            model_cache=selected,
            storage_config=config,
        )
        assert construct.call_count == 1 and construct.call_args.args == (selected,)
        return result


def shade(project, opacity, *, opacity_only=False):
    result = request(
        project,
        kind="effects",
        scope_xyxy=[8, 0, 88, 64],
        candidate_comparison=True,
        support_file="shading-support.png",
        shading={"enabled": True, "opacity": opacity, "width_px": 3.0, "direction_degrees": 90.0},
    )
    if opacity_only:
        result["opacity_only"] = True
    else:
        result["shading_protection_file"] = "shading-protection.png"
    return result


def assert_delivery(directory, size, members=DEFAULT_MEMBERS):
    assert {path.name for path in directory.iterdir()} == members
    with tifffile.TiffFile(directory / "result_rgb16.tif") as image:
        assert image.pages[0].dtype == np.dtype("uint16")
        assert image.pages[0].tags[34675].value == srgb_profile()
        pixels = image.asarray()
    assert pixels.shape == (size[1], size[0], 3)
    with Image.open(directory / "result_RGB8_VIEW.png") as image:
        assert image.info["icc_profile"] == srgb_profile()
        np.testing.assert_array_equal(
            np.array(image), np.rint(pixels.astype(float) / 257).astype(np.uint8)
        )
    return pixels


def assert_editable_native(
    directory, foreground, alpha, weight, background, expected, *, expected_opacity=0.12
):
    members = DEFAULT_MEMBERS | {
        "foreground_rgb16.tif",
        "alpha16.png",
        "source_rgb16.tif",
        "shadow_weight16.png",
        "shading_settings.json",
        "background_rgb16.tif",
        "background_settings.json",
    }
    np.testing.assert_array_equal(assert_delivery(directory, (96, 64), members), expected)
    record = json.loads((directory / "manifest.json").read_bytes())
    assert record["mode"] == "native" and record["requested_variants"] == ["editable"]
    assert set(record["files"]) == members - {"manifest.json"}
    profile_digest = hashlib.sha256(srgb_profile()).hexdigest()
    for name, metadata in record["files"].items():
        raw = (directory / name).read_bytes()
        assert metadata["bytes"] == len(raw)
        assert metadata["sha256"] == hashlib.sha256(raw).hexdigest()
        if name.endswith(".tif"):
            assert metadata["precision_bits"] == 16 and metadata["mode"] == "RGB"
            assert metadata["dimensions_wh"] == [96, 64]
            assert metadata["icc_profile_sha256"] == profile_digest
            with tifffile.TiffFile(directory / name) as image:
                assert image.pages[0].dtype == np.dtype("uint16")
                assert image.pages[0].tags[34675].value == srgb_profile()
        elif name in {"alpha16.png", "shadow_weight16.png"}:
            assert metadata["precision_bits"] == 16 and metadata["mode"] == "I;16"
            assert metadata["dimensions_wh"] == [96, 64]
            assert metadata["icc_profile_sha256"] is None
            assert raw[24:26] == bytes((16, 0))
            with Image.open(directory / name) as image:
                assert "icc_profile" not in image.info and "gamma" not in image.info
    delivered_foreground = tifffile.imread(directory / "foreground_rgb16.tif")
    delivered_background = tifffile.imread(directory / "background_rgb16.tif")
    with Image.open(directory / "alpha16.png") as image:
        delivered_alpha = np.array(image)
    with Image.open(directory / "shadow_weight16.png") as image:
        delivered_weight = np.array(image)
    for actual, saved in (
        (delivered_foreground, foreground),
        (delivered_background, background),
        (delivered_alpha, alpha),
        (delivered_weight, weight),
        (tifffile.imread(directory / "source_rgb16.tif"), foreground),
    ):
        np.testing.assert_array_equal(actual, saved)
    settings = json.loads((directory / "shading_settings.json").read_bytes())
    assert settings["enabled"] is True and settings["opacity"] == expected_opacity
    assert record["shading"]["opacity"] == settings["opacity"]
    reconstructed = np.rint(
        delivered_foreground.astype(float)
        * (delivered_alpha.astype(float) / 65535)[..., None]
        * (1 - settings["opacity"] * delivered_weight.astype(float) / 65535)[..., None]
        + delivered_background.astype(float)
        * (1 - delivered_alpha.astype(float) / 65535)[..., None]
    ).astype(np.uint16)
    np.testing.assert_array_equal(reconstructed, expected)
    return record


def assert_intact_editable_reuse(project, selected, options, deliveries):
    export_module = importlib.import_module("blackmask.export")
    with (
        patch.object(export_module, "_write_delivery", side_effect=AssertionError("output staged")),
        patch.object(
            export_module, "render_background", side_effect=AssertionError("native rendered")
        ),
        patch("blackmask.framing.frame_result", side_effect=AssertionError("margins rendered")),
        patch(
            "blackmask.series_framing.render_series", side_effect=AssertionError("series rendered")
        ),
    ):
        for mode, original in zip(options, deliveries, strict=True):
            repeated = export_project(
                project, revision=selected, draft=True, variants=("editable",), **mode
            )
            assert repeated == {**original, "reused": True}


def test_configured_storage_cache_and_forced_saved_reconstruction(tmp_path):
    release, _ = install_guard(tmp_path)
    try:
        with pytest.raises(PermissionError, match="outside workspace"):
            (tmp_path.parent / "blocked-journey-escape").write_bytes(b"must not be written")
        storage_journey(tmp_path)
    finally:
        release()


def storage_journey(tmp_path):
    config_file, config, project, pixels = imported_project(tmp_path)
    original_inventory = inventory(project.parent / "original")
    master_inventory = inventory(project / "assets")
    model_root = tmp_path / "shared-models"
    models_before = inventory(model_root)
    assert len(models_before) == 2
    with running_process(project, config_file, tmp_path) as server:
        first_pid = server.pid
        first = perform(server, "matte")
        perform(server, "accept", revision=first["revision"])
        first_snapshot = json.loads(http(server)[1])
    assert server.process.poll() is not None
    preserved_after_close = inventory(project)
    with running_process(project, config_file, tmp_path) as server:
        assert server.pid != first_pid
        reopened = json.loads(http(server)[1])
        for field in (
            "developed_id",
            "working_revision",
            "accepted_revision",
            "latest_result_revision",
            "guides",
            "revisions",
            "inputs_digest",
            "authoring_digest",
        ):
            assert reopened[field] == first_snapshot[field]
        assert inventory(project) == preserved_after_close
    # A saved lock protects real partial alpha through a second native operation.
    lock = edits(
        project,
        [
            {
                "id": "partial",
                "role": "lock",
                "shape": "rectangle",
                "xyxy": [30, 20, 31, 21],
                "revision": first["revision"],
            }
        ],
    )
    operations.apply_operation(
        project, request(project, guide_edits_file=lock), storage_config=config
    )
    native = matte(project, config)
    assert native["revision"] == "rev-004"
    support = np.zeros((64, 96), dtype=np.uint16)
    support[:, 8:88] = 65535
    protection = np.zeros((64, 96), dtype=np.uint16)
    protection[20, 30] = 65535
    Image.fromarray(support).save(project / "shading-support.png")
    Image.fromarray(protection).save(project / "shading-protection.png")
    twelve = operations.apply_operation(project, shade(project, 0.12), storage_config=config)
    with running_process(project, config_file, tmp_path) as server:
        perform(server, "accept", revision=twelve["revision"])
    accepted_before_newer = inventory(project / "revisions" / twelve["revision"])
    accepted_delivery = export_project(project)
    accepted_export_before_newer = inventory(Path(accepted_delivery["directory"]))
    twenty_four = operations.apply_operation(
        project, shade(project, 0.24, opacity_only=True), storage_config=config
    )
    old_manifest = read_revision(project, twelve["revision"], read_project(project)["developed_id"])
    manifest = read_revision(
        project, twenty_four["revision"], read_project(project)["developed_id"]
    )
    for role in (
        "foreground_rgb16.tif",
        "base_alpha16.png",
        "shadow_weight16.png",
        "supports/support16.png",
        "supports/protection.png",
        "effects/shading/protection16.png",
    ):
        assert old_manifest["assets"][role] == manifest["assets"][role]
    before_reuse = inventory(project)
    with (
        patch.object(operations, "VitMatteSession", side_effect=AssertionError("unexpected model")),
        patch("blackmask.effects.make_shadow_weight", side_effect=AssertionError("unexpected W")),
        patch.object(
            previews, "_render_latest", side_effect=AssertionError("unexpected result render")
        ),
    ):
        repeated = operations.apply_operation(
            project, shade(project, 0.24, opacity_only=True), storage_config=config
        )
    assert repeated["reused"] is True and repeated["revision"] == "rev-006"
    assert inventory(project) == before_reuse
    gallery = jpeg(config, project)
    assert marker(gallery)["status"] == "Draft"
    assert inventory(project / "revisions" / twelve["revision"]) == accepted_before_newer
    assert inventory(Path(accepted_delivery["directory"])) == accepted_export_before_newer
    # A remains accepted while newer B owns the latest gallery result.
    assert marker(gallery)["revision"] == twenty_four["revision"]
    assert marker(gallery)["status"] == "Draft"
    accepted_delivery = export_project(project)
    assert (
        json.loads(Path(accepted_delivery["manifest_file"]).read_bytes())["revision"]
        == twelve["revision"]
    )

    margins = {"left_px": 2, "right_px": 3, "top_px": 4, "bottom_px": 5}
    series = {
        "name": "Synthetic",
        "output_width_px": 137,
        "output_height_px": 181,
        "side_margin_tenths_percent": 150,
        "minimum_vertical_margin_tenths_percent": 50,
    }
    identity = read_project(project)["developed_id"]
    save_framing_preset(project, margins, expected_digest=None, expected_developed_id=identity)
    save_series_settings(project, series, expected_digest=None, expected_developed_id=identity)
    presets = {
        name: (project / name).read_bytes() for name in ("framing.json", "series-framing.json")
    }
    # Literal selected, working and accepted identities differ.
    operations.restore_revision(
        project, native["revision"], replace_drafts=True, storage_config=config
    )
    assert read_project(project)["working_revision"] == "rev-004"
    assert read_project(project)["accepted_revision"] == "rev-005"
    assert read_project(project)["latest_result_revision"] == "rev-006"
    selected = twelve["revision"]
    assert selected == "rev-005"
    state_before = (project / "state.json").read_bytes()
    comparison = review.review_project(
        project,
        revision=selected,
        crops=[[80, 0, 96, 9]],
        comparison=True,
        retain_native=True,
        storage_config=config,
    )
    assert Path(comparison["comparison_manifest_file"]).is_file()
    assert (project / "state.json").read_bytes() == state_before
    assert len(list((config.destination / "Results Preview").glob("*.jpg"))) == 1
    assert marker(gallery)["revision"] == "rev-006" and marker(gallery)["status"] == "Draft"
    before_reopen = inventory(project)
    with running_process(project, config_file, tmp_path) as server:
        reopened = json.loads(http(server)[1])
        assert (
            reopened["working_revision"],
            reopened["accepted_revision"],
            reopened["latest_result_revision"],
        ) == ("rev-004", "rev-005", "rev-006")
        assert reopened["framing"] == margins and reopened["series_settings"] == series
        assert inventory(project) == before_reopen
        draft_delivery = perform(server, "export", revision="rev-006", draft=True)
        assert (
            json.loads(Path(draft_delivery["manifest_file"]).read_bytes())["revision"] == "rev-006"
        )

    options = ({}, {"framing": margins}, {"series": series})
    default_deliveries = [
        export_project(project, revision=selected, draft=True, **mode) for mode in options
    ]
    native_pixels = assert_delivery(Path(default_deliveries[0]["directory"]), (96, 64))
    framed_pixels = assert_delivery(Path(default_deliveries[1]["directory"]), (101, 73))
    series_pixels = assert_delivery(Path(default_deliveries[2]["directory"]), (137, 181))
    for result in default_deliveries:
        record = json.loads(Path(result["manifest_file"]).read_bytes())
        assert record["requested_variants"] == [] and "editable_companion" not in record
    np.testing.assert_array_equal(framed_pixels[4:68, 2:98], native_pixels)
    background = tifffile.imread(
        saved_raster(project / f"revisions/{selected}/background/background_rgb16.tif")
    )
    expected_padding = np.pad(background, ((4, 5), (2, 3), (0, 0)), mode="edge")
    expected_padding[4:68, 2:98] = native_pixels
    np.testing.assert_array_equal(framed_pixels, expected_padding)
    # Independently evaluate the saved native scalar equation at every pixel/channel.
    alpha = np.array(
        Image.open(saved_raster(project / f"revisions/{selected}/base_alpha16.png")),
        dtype=np.uint16,
    )
    weight = np.array(
        Image.open(saved_raster(project / f"revisions/{selected}/shadow_weight16.png")),
        dtype=np.uint16,
    )
    assert np.all(alpha[:, :8] == 0) and np.all(alpha[:, 88:] == 65535)
    assert alpha[20, 30] == 32768 and weight[20, 30] == 0
    assert np.any(weight > 0) and np.any((alpha > 0) & (alpha < 65535))
    expected = np.rint(
        pixels.astype(float)
        * (alpha.astype(float) / 65535)[..., None]
        * (1 - 0.12 * weight.astype(float) / 65535)[..., None]
        + background.astype(float) * (1 - alpha.astype(float) / 65535)[..., None]
    ).astype(np.uint16)
    np.testing.assert_array_equal(native_pixels, expected)
    assert np.any(native_pixels % 257)
    deliveries = [
        export_project(project, revision=selected, draft=True, variants=("editable",), **mode)
        for mode in options
    ]
    native_directory = Path(deliveries[0]["directory"])
    native_record = assert_editable_native(
        native_directory, pixels, alpha, weight, background, expected
    )
    saved_revision = project / "revisions" / selected
    assert native_record["revision"] == selected and native_record["draft"] is True
    assert (
        native_record["revision_manifest_sha256"]
        == hashlib.sha256((saved_revision / "manifest.json").read_bytes()).hexdigest()
    )
    for delivered_name, saved_name in (
        ("recipe.toml", "recipe.toml"),
        ("background_settings.json", "background/settings.json"),
    ):
        assert (native_directory / delivered_name).read_bytes() == (
            saved_revision / saved_name
        ).read_bytes()
    assert (
        json.loads((native_directory / "shading_settings.json").read_bytes())
        == native_record["shading"]
    )
    for output, size, expected_pixels in zip(
        deliveries[1:], ((101, 73), (137, 181)), (framed_pixels, series_pixels), strict=True
    ):
        primary = Path(output["directory"])
        np.testing.assert_array_equal(assert_delivery(primary, size), expected_pixels)
        record = json.loads((primary / "manifest.json").read_bytes())
        assert record["requested_variants"] == ["editable"]
        assert record["editable_companion_request"] == {
            "directory_name": native_directory.name,
            "identity_sha256": native_record["identity_sha256"],
        }
        binding = {
            "directory_name": native_directory.name,
            "manifest_sha256": hashlib.sha256(
                (native_directory / "manifest.json").read_bytes()
            ).hexdigest(),
            "files_sha256": {name: item["sha256"] for name, item in native_record["files"].items()},
        }
        assert record["editable_companion"] == binding
        assert output["editable_companion"] == {
            "directory": str(native_directory),
            "manifest_file": str(native_directory / "manifest.json"),
            "manifest_sha256": binding["manifest_sha256"],
        }
    assert_intact_editable_reuse(project, selected, options, deliveries)

    save_framing_preset(
        project,
        {key: value + 1 for key, value in margins.items()},
        expected_digest=read_framing_preset(project, identity, (96, 64))[1],
        expected_developed_id=identity,
    )
    save_series_settings(
        project,
        series | {"name": "Changed", "output_width_px": 139},
        expected_digest=read_series_settings(project, identity, (96, 64))[1],
        expected_developed_id=identity,
    )
    assert all((project / name).read_bytes() != raw for name, raw in presets.items())
    failure = project / "exports/.retained-failure"
    failure.mkdir()
    (failure / "diagnostic.txt").write_bytes(b"preserved synthetic failed export stage")
    before_clear = inventory(config.destination)
    inspected = operations.inspect_processing_cache(project)
    assert inspected["candidates"] and inspected["blockers"] == []
    cleared = operations.clear_processing_cache(
        project, inspected["candidate_digest"], storage_config=config
    )
    assert cleared["status"] == "cleared"
    removed = {str((project / name).relative_to(config.destination)) for name in cleared["removed"]}
    assert inventory(config.destination) == {
        name: data for name, data in before_clear.items() if name not in removed
    }
    assert inventory(model_root) == models_before
    assert_intact_editable_reuse(project, selected, options, deliveries)

    # Reconstruction has no existing exports/cache or reachable original capture/model.
    reconstructed = tmp_path / "reconstruction"
    shutil.copytree(
        project,
        reconstructed,
        ignore=shutil.ignore_patterns("exports", "cache", "framing.json", "series-framing.json"),
    )
    reference_root = tmp_path / "retained-original-bundle"
    relative_deliveries = [
        Path(result["directory"]).relative_to(project.parent) for result in deliveries
    ]
    project.parent.rename(reference_root)
    assert not project.exists() and not (reconstructed / "exports").exists()
    assert not any((reconstructed / name).exists() for name in presets)
    frozen = [
        json.loads((reference_root / path / "manifest.json").read_bytes())
        for path in relative_deliveries
    ]
    # No links may escape the independent reconstruction workspace.
    entries = filesystem_entries(reconstructed)
    assert all(
        item[0] != "symlink" and (item[0] != "file" or item[1] == 1) for item in entries.values()
    )
    program = """import importlib,json,socket,sys
from pathlib import Path
from unittest.mock import patch
from blackmask.export import export_project
from storage_journey_process import install_guard
roots=[Path(sys.argv[1]),Path(sys.base_prefix),Path(sys.prefix)]
roots += [Path(p) for p in sys.path if p and Path(p).is_absolute()]
enabled,observed=install_guard(Path(sys.argv[1]),read_roots=roots)
for forbidden in json.loads(sys.argv[3]):
    try: Path(forbidden).read_bytes()
    except PermissionError: pass
    else: raise AssertionError('read guard failed: '+forbidden)
if sys.argv[4] == 'sandbox':
    import ctypes,errno
    libc=ctypes.CDLL(None,use_errno=True)
    for forbidden in json.loads(sys.argv[3])[:2]:
        assert libc.open(forbidden.encode(),0) == -1
        assert ctypes.get_errno() == errno.EPERM
outputs=[]
with patch.object(socket,'socket',side_effect=AssertionError('offline')):
    for record in json.loads(sys.argv[2]):
        module=importlib.import_module({'native':'blackmask.export','add-margins':'blackmask.framing','match-series':'blackmask.series_framing'}[record['mode']])
        name={'native':'render_background','add-margins':'frame_result','match-series':'render_series'}[record['mode']]
        arguments={'revision':record['revision'],'draft':record['draft'],'variants':tuple(record['requested_variants'])}
        if record['mode']=='add-margins': arguments['framing']=record['margins']
        if record['mode']=='match-series': arguments['series']=record['settings']
        with patch.object(module,name,wraps=getattr(module,name)) as render:
            output=export_project(Path(sys.argv[1]),**arguments)
            assert render.call_count>0 and output['reused'] is False
        outputs.append(dict(output,render_calls=render.call_count))
print(json.dumps(outputs))
"""
    arguments = [
        sys.executable,
        "-B",
        "-c",
        program,
        str(reconstructed),
        json.dumps(frozen),
        json.dumps(
            [
                str(reference_root / relative_deliveries[0] / "result_rgb16.tif"),
                str(model_root / "sam/retained-model.bin"),
                str(project / "state.json"),
            ]
        ),
    ]
    sandboxed = sys.platform == "darwin" and Path("/usr/bin/sandbox-exec").is_file()
    arguments.append("sandbox" if sandboxed else "python-audit-only")
    if sandboxed:
        forbidden_roots = (reference_root, project, model_root, project / "cache")
        permissions = " ".join(
            "(subpath " + json.dumps(str(value)) + ")" for value in forbidden_roots
        )
        # Python's read allowlist covers all data reads; the OS also blocks native reads
        # of the original capture/project, prior exports, cache and configured models.
        profile = "(version 1)(allow default)(deny network*)(deny file-read* " + permissions + ")"
        arguments = ["/usr/bin/sandbox-exec", "-p", profile, *arguments]
    child = subprocess.run(
        arguments,
        cwd=reconstructed,
        env=dict(
            os.environ,
            PYTHONPATH=os.pathsep.join(
                (
                    str(Path(__file__).resolve().parents[1] / "src"),
                    str(Path(__file__).resolve().parent),
                )
            ),
            BLACKMASK_VITMATTE_CACHE=str(tmp_path / "unavailable-models"),
            BLACKMASK_SAM_CACHE=str(tmp_path / "unavailable-models"),
        ),
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert child.returncode == 0, child.stdout + child.stderr
    outputs = json.loads(child.stdout)
    assert inventory(model_root) == models_before
    for relative, output in zip(relative_deliveries, outputs, strict=True):
        reference, rebuilt = reference_root / relative, Path(output["directory"])
        assert inventory(reference) == inventory(rebuilt)
        assert (reference / "manifest.json").read_bytes() == (
            rebuilt / "manifest.json"
        ).read_bytes()
        np.testing.assert_array_equal(
            tifffile.imread(reference / "result_rgb16.tif"),
            tifffile.imread(rebuilt / "result_rgb16.tif"),
        )
        with (
            Image.open(reference / "result_RGB8_VIEW.png") as first_view,
            Image.open(rebuilt / "result_RGB8_VIEW.png") as second_view,
        ):
            assert (
                first_view.info["icc_profile"] == second_view.info["icc_profile"] == srgb_profile()
            )
            np.testing.assert_array_equal(np.array(first_view), np.array(second_view))
        record = json.loads((rebuilt / "manifest.json").read_bytes())
        if record["mode"] == "native":
            assert_editable_native(rebuilt, pixels, alpha, weight, background, expected)
        else:
            companion = Path(output["editable_companion"]["directory"])
            assert companion == Path(outputs[0]["directory"])
            assert inventory(
                reference.parent / record["editable_companion"]["directory_name"]
            ) == inventory(companion)
            assert_editable_native(companion, pixels, alpha, weight, background, expected)
    assert inventory(reference_root / "original") == original_inventory
    retained_assets = inventory(reference_root / "project/assets")
    assert all(retained_assets[name] == value for name, value in master_inventory.items())
    assert (
        inventory(reference_root / "project/revisions" / twelve["revision"])
        == accepted_before_newer
    )
    (tmp_path / "journey-evidence.json").write_text(
        json.dumps(
            {
                "removed": cleared,
                "selected_revision": selected,
                "working_revision": "rev-004",
                "accepted_revision": "rev-005",
                "latest_result_revision": "rev-006",
                "process_restart": True,
                "browser_coverage": False,
                "read_guard": "OS sandbox and Python audit with native/Python negative controls"
                if sandboxed
                else "Python audit only; native reads unverified",
                "model_locators": {
                    "sam": str(config.sam_cache),
                    "vitmatte": str(config.vitmatte_cache),
                },
                "model_fixture": "Two retained synthetic placeholders; no installed weights or download",
                "model_files_preserved": len(models_before),
                "before_clear_files": len(before_clear),
                "before_clear_logical_bytes": sum(len(value[0]) for value in before_clear.values()),
                "reconstructed": outputs,
                "retained_file_count": len(inventory(reference_root)),
                "retained_logical_bytes": sum(
                    len(value[0]) for value in inventory(reference_root).values()
                ),
            },
            indent=2,
        )
    )


@pytest.mark.parametrize("boundary", ["CAMERA.tif", "bundle"])
def test_combined_import_processing_and_gallery_interruption_recovery(tmp_path, boundary):
    config_file, destination = configuration(tmp_path)
    config = library.load_storage_config(config_file)
    library.ensure_library(config)
    source = tiff(destination / "Inbox/CAMERA.tif", profile=srgb_profile())
    original = source.read_bytes()
    sidecar = source.with_suffix(".xmp")
    sidecar.write_bytes(b"retained sidecar")
    rename = library._exclusive_rename
    triggered = []

    def interrupt_move(start, end, **kwargs):
        rename(start, end, **kwargs)
        if start.name == boundary and kwargs.get("source_directory") is not None and not triggered:
            triggered.append(start.name)
            raise OSError("injected after visible import move")

    with (
        patch.object(library, "_exclusive_rename", side_effect=interrupt_move),
        pytest.raises(OSError, match="visible import"),
    ):
        library.import_photo(
            config, source, subject="synthetic", development={}, sidecars=(sidecar,)
        )
    assert triggered == [boundary]
    pending = next((destination / "Inbox/.imports").glob("*/import.json"))
    retained = inventory(pending.parent)
    child = command("--config", config_file, "import-resume", pending, cwd=tmp_path)
    assert child.returncode == 0, child.stderr
    project = Path(json.loads(child.stdout)["project"])
    assert (project.parent / "original/CAMERA.tif").read_bytes() == original
    assert (project.parent / "original/CAMERA.xmp").read_bytes() == b"retained sidecar"
    assert not source.exists() and not sidecar.exists()
    assert len(list((destination / "Photos").iterdir())) == 1 and retained
    operations.apply_operation(project, request(project), storage_config=config)
    state_before = (project / "state.json").read_bytes()
    publish = operations._atomic_json

    def fail_pointer(path, value, **kwargs):
        if path.name == "state.json":
            raise OSError("injected before native pointer")
        return publish(path, value, **kwargs)

    with (
        patch.object(operations, "_atomic_json", side_effect=fail_pointer),
        pytest.raises(OSError, match="native pointer"),
    ):
        matte(project, config)
    assert (project / "state.json").read_bytes() == state_before
    operation = next((project / "requests").glob("matte-*"))
    assert (operation / "completion.json").is_file()
    report = operations.inspect_processing_cache(project)
    assert report["candidates"] and report["blockers"]
    preserved = inventory(project)
    with pytest.raises(ProjectError):
        operations.clear_processing_cache(
            project, report["candidate_digest"], storage_config=config
        )
    assert inventory(project) == preserved
    with patch.object(
        operations, "VitMatteSession", side_effect=AssertionError("completed stage loaded model")
    ):
        resumed = operations.resume_operation(project, operation.name, storage_config=config)
    assert resumed["resumed_completed_stage"] is True
    assert marker(jpeg(config, project))["status"] == "Draft"

    def fail_after_pointer(path, value, **kwargs):
        publish(path, value, **kwargs)
        if path.name == "state.json":
            raise OSError("injected after visible acceptance")

    with (
        patch.object(operations, "_atomic_json", side_effect=fail_after_pointer),
        pytest.raises(OSError, match="visible acceptance"),
    ):
        operations.accept_revision(project, resumed["revision"], storage_config=config)
    assert read_project(project)["accepted_revision"] == resumed["revision"]
    assert marker(jpeg(config, project))["status"] == "Draft"
    assert previews.result_preview_status(project, config)["status"] == "pending"
    assert previews.refresh_result_preview(project, config)["status"] == "current"
    assert marker(jpeg(config, project))["status"] == "Accepted"
    export = Path(export_project(project)["directory"])
    delivery = inventory(export)
    operations.apply_operation(project, request(project), storage_config=config)
    with patch.object(previews, "_atomic_json", side_effect=OSError("injected gallery receipt")):
        newer = matte(project, config)
    assert newer["preview_pending"] is True
    assert read_project(project)["accepted_revision"] == resumed["revision"]
    assert read_project(project)["latest_result_revision"] == newer["revision"]
    assert marker(jpeg(config, project))["status"] == "Draft"
    assert previews.refresh_result_preview(project, config)["status"] == "current"
    report = operations.inspect_processing_cache(project)
    assert report["candidates"] and report["blockers"] == []
    before_clear = inventory(project)
    result = operations.clear_processing_cache(
        project, report["candidate_digest"], storage_config=config
    )
    assert result["status"] == "cleared"
    assert inventory(project) == {
        name: value for name, value in before_clear.items() if name not in result["removed"]
    }
    assert inventory(export) == delivery
    assert (project.parent / "original/CAMERA.tif").read_bytes() == original
