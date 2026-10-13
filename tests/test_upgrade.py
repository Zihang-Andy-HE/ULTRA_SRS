import json,subprocess,sys
from argparse import Namespace
from pathlib import Path
import numpy as np
import pytest,torch,tifffile
from ultra.runtime import stage_lock,resolve_device
from ultra.inspection import inspect_tiff
from ultra.studio import parse_planes,write_volume
from ultra.studio_algorithms import preprocess_plane,studio_rgb,tiled
from ultra.io import read_stack
from ultra.scoring import score_volume


def test_inspection_does_not_invent_z(tmp_path):
    path=tmp_path/'G5.tif';tifffile.imwrite(path,np.ones((3,20,20),np.uint16),imagej=True,resolution=(2,2),metadata={'axes':'ZYX','unit':'micron'})
    result=inspect_tiff(path)
    assert result['voxel_size_um']=={'x':.5,'y':.5,'z':None}
    assert not result['full_plane_shape_supported']
    assert result['source_slice_mapping'].startswith('unknown')


@pytest.mark.parametrize('value',['0','2,1','1,1','6','1:8'])
def test_plane_selection_rejects_invalid(value):
    with pytest.raises(ValueError):parse_planes(value,5)


def test_plane_selection_preserves_gaps():
    assert parse_planes('1:3,5',5)==[1,2,3,5]


def test_blank_and_overflow_preprocessing():
    raw=np.array([[0,65535]],np.uint16)
    assert preprocess_plane(raw,1.,2.,safe=True).tolist()==[[0,65535]]
    assert not preprocess_plane(raw,0.,2.,safe=True).any()
    with pytest.raises(ValueError):preprocess_plane(raw,0.,2.,safe=False)


def test_studio_rgb_known_channels():
    l=np.array([[0,65535]],np.uint16);p=np.array([[65535,0]],np.uint16)
    assert studio_rgb(l,p).tolist()==[[[0,0,255],[0,255,0]]]


def test_lock_excludes_other_process_and_releases(tmp_path):
    path=tmp_path/'.lock'
    code='from ultra.runtime import stage_lock;\nwith stage_lock('+repr(str(path))+'):\n print("acquired")'
    with stage_lock(path):
        child=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True)
        assert child.returncode!=0
    child=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True)
    assert child.returncode==0


def test_portable_cpu_selection():assert resolve_device('cpu')=='cpu'


def test_tiling_covers_non_multiple_edges():
    class Identity(torch.nn.Module):
        def forward(self,x):return x
    a=np.full((513,529),30000,np.uint16)
    output=tiled(Identity(),a,'cpu','protein',480)
    assert np.abs(output.astype(int)-a).max()<=1
    rgb=np.full((513,529,3),127,np.uint8)
    output=tiled(Identity(),rgb,'cpu','he',480)
    assert np.abs(output.astype(int)-rgb).max()<=1


def test_unknown_z_not_written_as_physical_spacing(tmp_path):
    a=np.zeros((2,16,16),np.uint16);path=tmp_path/'stack.ome.tif'
    info={'sha256':'test','voxel_size_um':{'x':.4,'y':.4,'z':None}}
    write_volume(path,a,info,[1,100])
    with tifffile.TiffFile(path) as t:assert 'PhysicalSizeZ' not in t.ome_metadata and 'PositionZ=' not in t.ome_metadata
    assert np.array_equal(read_stack(path),a)


def test_score_small_input_rejected():
    with pytest.raises(ValueError,match='at least'):
        score_volume(None,np.zeros((3,120,120,3),np.uint8),'cpu')


def test_score_eval_mode_and_probability():
    class Fixed(torch.nn.Module):
        def forward(self,x):
            assert not self.training
            return torch.tensor([[0.,0.]])
    output=score_volume(Fixed(),np.zeros((10,120,120,3),np.uint8),'cpu')
    assert output.shape==(10,120,120) and np.all(output==.5)
