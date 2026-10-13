import subprocess, sys
import pytest
from ultra.runtime import stage_lock, resolve_device
from ultra.io import parse_planes


@pytest.mark.parametrize('value',['0','2,1','1,1','6','1:8'])
def test_plane_selection_rejects_invalid(value):
    with pytest.raises(ValueError):parse_planes(value,5)

def test_plane_selection_preserves_gaps():
    assert parse_planes('1:3,5',5)==[1,2,3,5]

def test_lock_excludes_other_process_and_releases(tmp_path):
    path=tmp_path/'.lock'
    code='from ultra.runtime import stage_lock;\nwith stage_lock('+repr(str(path))+'):\n print("acquired")'
    with stage_lock(path):
        child=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True)
        assert child.returncode!=0
    child=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True)
    assert child.returncode==0

def test_portable_cpu_selection():assert resolve_device('cpu')=='cpu'
