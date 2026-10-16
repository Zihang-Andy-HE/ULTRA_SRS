"""Core orchestration with synthetic model adapters; not neural accuracy tests."""
import json
from argparse import Namespace
from pathlib import Path
import numpy as np
import pytest
import tifffile
from ultra import cli
from ultra.io import sha, read_stack

ROOT = Path(__file__).resolve().parents[1]


def prepare(tmp_path):
    config = json.loads((ROOT/'configs/ultra.yaml').read_text())
    for kind, spec in config['assets'].items():
        path = tmp_path / ('asset_'+kind)
        if kind == 'reference':
            path.write_bytes((ROOT/'references/visual_reference.json').read_bytes())
        else:
            path.write_bytes(b'synthetic test asset')
        spec.update(path=str(path), sha256=sha(path))
    cp = tmp_path/'config.json';cp.write_text(json.dumps(config))
    raw = np.broadcast_to(np.arange(1024,dtype=np.uint16),(3,1024,1024)).copy()
    ip = tmp_path/'input.tif';tifffile.imwrite(ip,raw,metadata={'axes':'ZYX'},photometric='minisblack')
    metadata = json.loads((ROOT/'examples/metadata.json').read_text())
    metadata.update(shape=list(raw.shape), input_sha256=sha(ip),
                    file_plane_ordinals=[1,2,3], z_positions_um=[0.,1.,2.])
    mp = tmp_path/'metadata.json';mp.write_text(json.dumps(metadata))
    return Namespace(command='denoise',input=str(ip),metadata=str(mp),
                     config=str(cp),out=str(tmp_path/'denoise'),device='cpu',
                     batch=1,resume=False,planes='1,3'), config


def test_three_stages_selection_resume_and_integrity(tmp_path,monkeypatch):
    args,config = prepare(tmp_path)
    calls=[]
    monkeypatch.setattr(cli.models,'load',lambda *a: object())
    def denoise(net,raw,policy,device):
        calls.append(dict(policy));return raw.copy()
    monkeypatch.setattr(cli.models,'denoise_plane',denoise)
    monkeypatch.setattr(cli.models,'l2p_plane',lambda net,a,*rest:a.astype(np.float32)+20)
    monkeypatch.setattr(cli.models,'he_plane',lambda net,a,*rest:a.copy())
    cli.run(args)
    den=Path(args.out);m=json.loads((den/'metadata.json').read_text())
    assert m['source_slices'] is None and m['file_plane_ordinals']==[1,3]
    assert m['z_positions_um']==[0.,2.] and m['shape']==[2,1024,1024]
    assert calls==[{'gain':65535/4095,'offset':0,'t':10}]*2
    args.resume=True;cli.run(args);assert len(calls)==2
    lp=tmp_path/'protein'
    cli.run(Namespace(command='lipid2protein',from_dir=str(den),out=str(lp),device='cpu',batch=1,resume=False))
    he=tmp_path/'he'
    cli.run(Namespace(command='virtual-stain',from_dir=str(lp),out=str(he),device='cpu',batch=1,resume=False,manual_params=None))
    assert read_stack(he/'virtual_HE.ome.tif').shape==(2,1024,1024,3)
    with tifffile.TiffFile(he/'virtual_HE.ome.tif') as f:
        assert 'PhysicalSizeZ=' not in f.ome_metadata and 'PositionZ="2' in f.ome_metadata
    assert json.loads((he/'calibration/parameters.json').read_text())['fit_file_planes']==[1,3]
    assert json.loads((he/'stage.json').read_text())['profile']=='native-exploratory'
    args.planes='1'
    with pytest.raises(ValueError,match='Resume identity mismatch'):cli.run(args)
    (den/'lipid_denoised.ome.tif').write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='hash mismatch'):cli.verified_stage(den)


def test_wrong_input_checksum_rejected_before_model_load(tmp_path,monkeypatch):
    args,_=prepare(tmp_path)
    p=Path(args.metadata);m=json.loads(p.read_text());m['input_sha256']='0'*64;p.write_text(json.dumps(m))
    def unexpected(*args):raise AssertionError('Model must not load')
    monkeypatch.setattr(cli.models,'load',unexpected)
    with pytest.raises(ValueError,match='checksum disagrees'):cli.run(args)
