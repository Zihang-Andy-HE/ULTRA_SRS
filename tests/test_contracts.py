"""Unit/contract tests, separate from the real GPU acceptance summarized in docs/validation.json."""
import json
from pathlib import Path
import numpy as np
import pytest,tifffile
from ultra.io import validate_input,write_ome,read_stack,dump
from ultra.calibration import manual_rgb,validate_manual
from ultra.models import positions
from ultra.cli import verified_stage,validate_config

R=Path(__file__).resolve().parents[1]
@pytest.fixture
def metadata():
    """Historical three-plane core-contract fixture, separate from the public input."""
    return {'sample_id': 'G5',
 'acquisition_id': 'G5_998_native',
 'axes': 'ZYX',
 'voxel_size_um': {'z': 1.0, 'y': 0.4143204, 'x': 0.4143204},
 'z_origin_um': None,
 'depth_coordinate_reference': 'relative to original source slice 1; not absolute '
                               'tissue depth',
 'measured_band_cm_1': None,
 'dtype': 'uint16',
 'native_intensity_max': 4095,
 'offset': {'applied': False,
            'value': 0,
            'note': 'Not a measured dark-current correction'},
 'source_slices': [49, 50, 51],
 'z_positions_um': [48.0, 49.0, 50.0]}


@pytest.mark.parametrize('change',[{'axes':'XYZ'},{'native_intensity_max':65535},{'dtype':'float32'},{'source_slices':[1,1,2]},{'z_positions_um':[48,50,51]},{'voxel_size_um':{'z':1,'y':0,'x':1}}])
def test_reject_invalid_metadata(metadata,change):
    metadata.update(change)
    with pytest.raises(ValueError):validate_input(np.ones((3,1024,1024),np.uint16),metadata)

def test_reject_range(metadata):
    a=np.full((3,1024,1024),4096,np.uint16)
    with pytest.raises(ValueError):validate_input(a,metadata)

def test_no_uncovered_edges():
    p=positions(1057);count=np.zeros(1057)
    for x in p:count[x:x+512]+=1
    assert count.min()>0 and p[-1]==545
    with pytest.raises(ValueError):positions(511)

def test_manual_formula():
    p=json.loads((R/'configs/manual_rgb.json').read_text());p['L'].update(low=0,high=100,gamma=2);p['D'].update(low=0,high=100,gamma=1)
    l=np.array([[0,25,100]],np.float32);pr=l+50
    a=manual_rgb(l,pr,p)
    assert a.tolist()==[[[0,0,128],[0,128,128],[0,255,128]]]
    assert np.array_equal(a,manual_rgb(l,pr,json.loads(json.dumps(p))))
    p['D']['gamma']=0
    with pytest.raises(ValueError):validate_manual(p)

def test_sparse_ome_positions(tmp_path,metadata):
    metadata['source_slices']=[49,50,499];metadata['z_positions_um']=[48,49,498]
    a=np.zeros((3,16,20,3),np.uint8);p=tmp_path/'test.ome.tif';write_ome(p,a,metadata)
    with tifffile.TiffFile(p) as f:
        assert f.is_ome and 'PhysicalSizeX="0.4143204"' in f.ome_metadata
        assert 'PhysicalSizeZ=' not in f.ome_metadata and 'PositionZ="498' in f.ome_metadata
    assert np.array_equal(read_stack(p),a)

def test_failed_upstream_refused(tmp_path):
    dump(tmp_path/'stage.json',{'execution_status':'failed'})
    with pytest.raises(ValueError):verified_stage(tmp_path)

def test_contract_config():
    c=json.loads((R/'configs/ultra.yaml').read_text());validate_config(c);c['lipid2protein']['stride']=256
    with pytest.raises(ValueError):validate_config(c)


def test_valid_historical_mapping_still_accepted(metadata):
    validate_input(np.ones((3,1024,1024),np.uint16),metadata)


def test_new_acquisition_is_not_silently_mapped_to_frozen_policy():
    m=json.loads((R/'examples/metadata.json').read_text())
    # Broadcast a plane to avoid allocating a full synthetic input volume.
    a=np.broadcast_to(np.zeros((1024,1024),np.uint16),tuple(m['shape']))
    with pytest.raises(ValueError,match='Original acquisition slice mapping is unknown'):
        validate_input(a,m)
