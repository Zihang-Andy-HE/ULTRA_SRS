"""Window-based research probability maps from original ULTRA classifier weights.

This is overlapping-window classification, not a validated cell segmentation.
"""
import itertools,json,time
from pathlib import Path
import numpy as np
import torch
from .io import sha,dump,read_stack
from .runtime import resolve_device,stage_lock
from .models import positions,configure
from .vendor.score_model import CNN3D_1um


@torch.inference_mode()
def score_volume(net,volume,device,z_repeat=5,progress=None):
    if volume.ndim!=4 or volume.shape[-1]!=3 or volume.dtype!=np.uint8:
        raise ValueError('Scoring requires uint8 ZYXS RGB')
    if any(n<s for n,s in zip(volume.shape[:3],(10,120,120))):
        raise ValueError('Scoring requires at least 10 x 120 x 120 voxels')
    if z_repeat not in (1,5):raise ValueError('z-repeat must be 1 (1 um input) or 5 (original 5 um input)')
    if 10*z_repeat<32:raise ValueError('The five-pooling classifier needs >=32 input Z voxels; use the 5 um protocol or resample explicitly')
    coords=list(itertools.product(positions(len(volume),10,4),positions(volume.shape[1],120,40),positions(volume.shape[2],120,40)))
    acc=np.zeros(volume.shape[:3],np.float32);count=np.zeros(volume.shape[:3],np.uint16)
    net.eval()
    for index,(z,y,x) in enumerate(coords):
        roi=volume[z:z+10,y:y+120,x:x+120]
        t=torch.from_numpy(np.repeat(roi,z_repeat,axis=0).astype(np.float32)).permute(3,0,1,2)[None].to(device)/255
        probability=torch.softmax(net(t),dim=1)[0,1].item()
        if not np.isfinite(probability):raise ValueError('Nonfinite classifier probability')
        acc[z:z+10,y:y+120,x:x+120]+=probability;count[z:z+10,y:y+120,x:x+120]+=1
        if progress:progress(index+1,len(coords))
    return acc/count


def score(a):
    import tifffile
    from scipy.ndimage import gaussian_filter
    from .cli import code_hash
    if not np.isfinite(a.z_spacing) or a.z_spacing<=0:raise ValueError('Invalid spacing')
    if a.z_repeat!=5 or not np.isclose(a.z_spacing,5.):
        raise ValueError('Original scoring protocol requires 5 um input and z-repeat=5. Explicitly prepare and record resampling first; no implicit geometry change.')
    device=resolve_device(a.device);out=Path(a.out)
    spec=json.loads(Path(a.assets).read_text())['assets'][a.tumor]
    if sha(spec['path'])!=spec['sha256']:raise ValueError('Score checkpoint checksum mismatch')
    identity={'input':sha(a.input),'asset':spec['sha256'],'tumor':a.tumor,'device':device,'z_spacing':a.z_spacing,'z_repeat':a.z_repeat,'code':code_hash(),'eval_mode':True}
    if out.exists() and not a.resume:raise FileExistsError('Output exists; use a new directory or --resume')
    out.mkdir(parents=True,exist_ok=True)
    with stage_lock(out/'.lock'):
        status=out/'score.json'
        if status.exists():
            old=json.loads(status.read_text())
            if old['identity']!=identity:raise ValueError('Resume identity mismatch')
            if old['status']=='complete':
                for name,digest in old['files'].items():
                    if sha(out/name)!=digest:raise ValueError('Score output hash mismatch')
                return old
        elif any(p.name!='.lock' for p in out.iterdir()):raise ValueError('Unknown output directory')
        state={'status':'running','identity':identity,'note':'Research window probability, no diagnostic validation; eval() fixes upstream train-mode BatchNorm'};dump(status,state)
        try:
            configure(device);net=CNN3D_1um(3,2)
            ck=torch.load(spec['path'],map_location='cpu',weights_only=True);net.load_state_dict(ck['model'],strict=True);net.to(device).eval()
            volume=read_stack(a.input)
            with tifffile.TiffFile(a.input) as source:
                if source.ome_metadata:
                    import xml.etree.ElementTree as ET
                    pixels=ET.fromstring(source.ome_metadata).find('.//{*}Pixels')
                    positions=[float(p.get('PositionZ')) for p in pixels.findall('{*}Plane') if p.get('PositionZ') is not None]
                    if positions and len(positions)!=len(volume):raise ValueError('OME plane coordinates do not match stack')
                    if len(positions)>1 and not np.allclose(np.diff(positions),a.z_spacing):raise ValueError('Input OME Z coordinates disagree with scoring spacing')
                    if 'PhysicalSizeZ' in pixels.attrib and not np.isclose(float(pixels.get('PhysicalSizeZ')),a.z_spacing):raise ValueError('Input OME Z spacing disagrees with scoring spacing')
            probability=score_volume(net,volume,device,a.z_repeat,lambda i,n:print(f'score {i}/{n}',flush=True))
            tifffile.imwrite(out/'probability.tif',probability,metadata={'axes':'ZYX','PhysicalSizeZ':a.z_spacing})
            smoothed=gaussian_filter(probability,sigma=(2,16,16),mode='nearest')
            tifffile.imwrite(out/'probability_smoothed.tif',smoothed,metadata={'axes':'ZYX'})
            state.update(status='complete',files={p.name:sha(p) for p in out.glob('*.tif')});dump(status,state);return state
        except BaseException as exc:
            state.update(status='failed',error=str(exc));dump(status,state);raise
