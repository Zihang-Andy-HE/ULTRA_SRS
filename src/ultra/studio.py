"""Portable ULTRA workflow, inspection, asset registration and viewing commands."""
import argparse,json,os,sys,time,traceback
from pathlib import Path
import numpy as np
import tifffile
from .io import dump,sha,read_stack
from .runtime import resolve_device,stage_lock
from .inspection import inspect_tiff,doctor


def register_studio(source,out,inference_only=False):
    root=Path(source).resolve();out=Path(out)
    candidates={'denoise':'*poisson_epochs_100.pkl','lipid2protein':'*size512_epochs_100.pkl',
                'virtual_stain':'mapping.pkl','glioblastoma':'glioblastoma.pkl',
                'astrocytoma':'astrocytoma.pkl','oligodendroglioma':'oligodendroglioma.pkl'}
    manifest={'source':'https://doi.org/10.5281/zenodo.18323493','schema':'ultra.studio.assets.v1','assets':{}}
    for kind,pattern in candidates.items():
        matches=list(root.rglob(pattern))
        if inference_only and kind in ('glioblastoma','astrocytoma','oligodendroglioma') and not matches:continue
        if len(matches)!=1:raise ValueError(f'Expected exactly one {pattern}; found {len(matches)}')
        p=matches[0];manifest['assets'][kind]={'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size}
    dump(out,manifest)
    return manifest


def parse_planes(value,n):
    if value=='all':return list(range(1,n+1))
    values=[]
    for item in value.split(','):
        if ':' in item:
            a,b=map(int,item.split(':'));values.extend(range(a,b+1))
        else:values.append(int(item))
    if not values or sorted(set(values))!=values or values[0]<1 or values[-1]>n:
        raise ValueError('Planes must be unique, increasing, 1-based file ordinals within the TIFF')
    return values


def load_assets(a):
    if a.profile=='studio':
        entries=json.loads(Path(a.assets).read_text(encoding='utf-8'))['assets']
    else:
        registry=json.loads((Path(__file__).parent/'data/model_registry.json').read_text())
        entries={k:{'path':str(Path(a.weights)/v['filename']),'sha256':v['sha256']} for k,v in registry.items()}
    for kind in ['denoise','lipid2protein','virtual_stain']:
        entry=entries[kind];p=Path(entry['path'])
        if not p.is_file() or sha(p)!=entry['sha256']:raise ValueError(f'Missing or corrupt asset: {kind}')
    return entries


def write_volume(path,arr,info,planes,z_spacing=None):
    meta={'axes':'ZYXS' if arr.ndim==4 else 'ZYX',
          'Description':json.dumps({'file_plane_ordinals':planes,'source_slice_mapping':'not established',
                                   'input_sha256':info['sha256']})}
    for axis in ['x','y']:
        value=info['voxel_size_um'][axis]
        if value:
            meta['PhysicalSize'+axis.upper()]=value;meta['PhysicalSize'+axis.upper()+'Unit']='µm'
    if z_spacing:
        if all(y-x==1 for x,y in zip(planes,planes[1:])):meta['PhysicalSizeZ']=z_spacing;meta['PhysicalSizeZUnit']='µm'
        meta['Plane']={'PositionZ':[(p-1)*z_spacing for p in planes],'PositionZUnit':['µm']*len(planes)}
    path=Path(path);tmp=path.with_name(path.stem+'.partial.ome.tif')
    tifffile.imwrite(tmp,arr,ome=True,bigtiff=True,metadata=meta,photometric='rgb' if arr.ndim==4 else 'minisblack')
    if not np.array_equal(read_stack(tmp),arr):raise RuntimeError('Output TIFF readback mismatch')
    os.replace(tmp,path)


def pipeline(a):
    import torch
    from . import models,calibration,qc,__version__
    from .cli import code_hash
    from .studio_algorithms import preprocess_plane,studio_denoise,tiled,studio_rgb
    a.device=resolve_device(a.device)
    if a.batch<1 or not 1<=a.protein_stride<=512 or not 1<=a.he_stride<=512:raise ValueError('Invalid tile batch/stride')
    if a.z_spacing is not None and (not np.isfinite(a.z_spacing) or a.z_spacing<=0):raise ValueError('Z spacing must be positive')
    info=inspect_tiff(a.input)
    if a.z_spacing is None:a.z_spacing=info['voxel_size_um']['z']
    if len(info['shape'])!=3 or info['shape'][1:]!=[1024,1024] or info['dtype'] not in ('uint16','>u2','<u2'):
        raise ValueError('This workflow requires a scalar uint16 1024 x 1024 stack')
    if a.profile=='native-exploratory' and info['range'][1]>4095:raise ValueError('Native exploratory mode requires 0..4095 input')
    planes=parse_planes(a.planes,info['shape'][0]);entries=load_assets(a)
    if a.profile=='studio' and max(planes)>200:raise ValueError('Original Studio schedule supports file planes 1..200 only')
    if not 0<=a.denoise_t<=999:raise ValueError('denoise-t must be 0..999')
    out=Path(a.out).resolve()
    if out.exists() and not a.resume:raise FileExistsError('Output exists. Choose a new output or --resume')
    identity={'input_sha256':info['sha256'],'profile':a.profile,'planes':planes,'device':a.device,
              'batch':a.batch,'protein_stride':a.protein_stride,'he_stride':a.he_stride,'denoise_t':a.denoise_t,
              'z_spacing':a.z_spacing,'seed':a.seed,'code':code_hash(),
              'assets':{k:entries[k]['sha256'] for k in ['denoise','lipid2protein','virtual_stain']}}
    out.mkdir(parents=True,exist_ok=True)
    with stage_lock(out/'.lock'):
        manifest=out/'workflow.json'
        if manifest.exists():
            old=json.loads(manifest.read_text())
            if old['identity']!=identity:raise ValueError('Resume identity mismatch; choose a new directory')
            if old['status']=='complete':
                for name,digest in old['files'].items():
                    if sha(out/name)!=digest:raise ValueError('Output checksum mismatch: '+name)
                print('COMPLETE: verified existing workflow',flush=True);return old
        elif any(p.name!='.lock' for p in out.iterdir()):raise ValueError('Unidentified output directory is not resumable')
        state={'schema':'ultra.workflow.v1','version':__version__,'identity':identity,'status':'running',
               'warnings':info['warnings']+(['Exploratory transfer: no G5_998 depth mapping; no diagnostic validation'] if a.profile!='studio' else ['Original Studio normalization, schedule and stochastic sampler; seeded per file plane for reproducibility']),
               'files':{},'stages':{}}
        started=time.perf_counter();dump(manifest,state);dump(out/'input_inspection.json',info)
        try:
            raw=read_stack(a.input)
            # Upstream float32 means after division, pooled across the entire input (even for a pilot).
            means=np.array([np.mean(np.float32(p)/65535) for p in raw]);maxmean=means.max()
            prep=np.stack([preprocess_plane(raw[p-1],means[p-1],maxmean,safe=False) if a.profile=='studio'
                           else raw[p-1].astype(np.uint16) for p in planes])
            write_volume(out/'00_preprocessed.ome.tif',prep,info,planes,a.z_spacing)
            arrays={'preprocessed':prep};schedule=np.around(np.r_[np.ones(10)*10,np.linspace(10,90,190)])
            for kind,output_name in [('denoise','01_lipid_denoised'),('lipid2protein','02_protein_predicted'),('virtual_stain','04_virtual_HE')]:
                then=time.perf_counter();cache=out/'cache'/kind;cache.mkdir(parents=True,exist_ok=True)
                net=None;values=[];rows=[]
                if kind=='virtual_stain':
                    if a.profile=='studio':rgb=np.stack([studio_rgb(l,p) for l,p in zip(arrays['denoise'],arrays['lipid2protein'])]);params={'formula':'D=clip((P/65535 - 0.85*L/65535)*10,0,1)'}
                    else:
                        ref=json.loads((Path(__file__).parent/'data/references/v3_reference.json').read_text())
                        params=calibration.fit_stack(arrays['denoise'],arrays['lipid2protein'],list(range(len(planes))),ref)
                        params['fit_file_planes']=planes
                        rgb=np.stack([calibration.rgb(l,p,params) for l,p in zip(arrays['denoise'],arrays['lipid2protein'])])
                        if params['V3_bounds_hit']:state['warnings'].append('V3 calibration bound reached: review color transfer')
                    dump(out/'calibration.json',params);write_volume(out/'03_rgb_input.ome.tif',rgb,info,planes,a.z_spacing)
                    rgb=read_stack(out/'03_rgb_input.ome.tif');arrays['rgb']=rgb
                for i,plane in enumerate(planes):
                    tick=time.perf_counter();cp=cache/f'{plane:04d}.npy';rp=cp.with_suffix('.json');reused=False
                    if cp.exists() and rp.exists() and sha(cp)==json.loads(rp.read_text())['sha256']:
                        value=np.load(cp,allow_pickle=False);reused=True
                    else:
                        if net is None:net=models.load(kind,Path(entries[kind]['path']),a.device)
                        torch.manual_seed(a.seed+plane);np.random.seed(a.seed+plane)
                        if kind=='denoise':
                            if a.profile=='studio':value=studio_denoise(net,prep[i],a.device,int(schedule[plane-1]),eta=1.)
                            else:value=models.denoise_plane(net,prep[i],{'gain':65535/4095,'offset':0,'t':a.denoise_t},a.device)
                        elif kind=='lipid2protein':
                            if a.profile=='native-exploratory' and a.protein_stride==64:value=models.l2p_plane(net,arrays['denoise'][i],a.device,a.batch)
                            else:value=tiled(net,arrays['denoise'][i],a.device,'protein',a.protein_stride,a.batch,65535 if a.profile=='studio' else 4095)
                        else:
                            if a.profile=='native-exploratory' and a.he_stride==32:value=models.he_plane(net,rgb[i],a.device,a.batch)
                            else:value=tiled(net,rgb[i],a.device,'he',a.he_stride,a.batch)
                        tmp=cp.with_suffix('.tmp')
                        with tmp.open('wb') as f:np.save(f,value,allow_pickle=False)
                        os.replace(tmp,cp);dump(rp,{'sha256':sha(cp)})
                    expected=(1024,1024,3) if kind=='virtual_stain' else (1024,1024)
                    if value.shape!=expected or not np.isfinite(value).all():raise ValueError('Invalid cached/computed plane')
                    values.append(value);row=qc.metrics(value)
                    limit=255 if kind=='virtual_stain' else 65535 if a.profile=='studio' else 4095
                    row.update(saturation_fraction=float(np.mean(value>=limit)),intensity_scale=limit,file_plane=plane,seconds=time.perf_counter()-tick,reused=reused);rows.append(row)
                    print(f'{kind} plane {plane} ({i+1}/{len(planes)}) {row["seconds"]:.2f}s cached={reused}',flush=True)
                    state['current']={'stage':kind,'completed':i+1,'total':len(planes)};dump(manifest,state)
                arrays[kind]=np.stack(values);write_volume(out/(output_name+'.ome.tif'),arrays[kind],info,planes,a.z_spacing)
                dump(out/(kind+'_metrics.json'),rows);state['stages'][kind]={'seconds':time.perf_counter()-then,'planes':len(planes)};dump(manifest,state)
                del net
                if a.device.startswith('cuda'):torch.cuda.empty_cache()
            # Self-contained quick review with the SAME scale per scalar stage.
            from PIL import Image
            thumbs=out/'previews';thumbs.mkdir(exist_ok=True)
            for i,p in enumerate(planes):
                Image.fromarray(arrays['virtual_stain'][i]).resize((512,512)).save(thumbs/f'HE_{p:04d}.png')
            html='<!doctype html><meta charset="utf-8"><title>ULTRA results</title><h1>ULTRA '+a.profile+'</h1><p>Research output; no matched H&amp;E ground truth. Plane labels are file ordinals.</p>'
            html+=''.join(f'<figure style="display:inline-block"><img width="320" src="previews/HE_{p:04d}.png"><figcaption>File plane {p}</figcaption></figure>' for p in planes)
            (out/'report.html').write_text(html,encoding='utf-8')
            state.update(status='complete',elapsed_seconds=time.perf_counter()-started)
            state['files']={str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file() and p.name not in ('workflow.json','.lock') and 'cache' not in p.parts}
            dump(manifest,state);print('COMPLETE',out,flush=True);return state
        except BaseException as exc:
            state.update(status='cancelled' if isinstance(exc,KeyboardInterrupt) else 'failed',error=str(exc))
            dump(manifest,state);(out/'error.log').write_text(traceback.format_exc(),encoding='utf-8');raise


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    q=sub.add_parser('inspect');q.add_argument('--input',required=True);q.add_argument('--out')
    q=sub.add_parser('doctor');q.add_argument('--out')
    q=sub.add_parser('register-studio');q.add_argument('--source',required=True);q.add_argument('--out',required=True);q.add_argument('--inference-only',action='store_true')
    q=sub.add_parser('run');q.add_argument('--input',required=True);q.add_argument('--out',required=True)
    q.add_argument('--profile',choices=['studio','native-exploratory'],required=True)
    q.add_argument('--assets',help='Studio checkpoint manifest');q.add_argument('--weights',help='ULTRA_SRS tensor-only weight directory')
    q.add_argument('--planes',default='all',help='1-based file ordinals: all, 1,75,150, or 1:10')
    q.add_argument('--device',default='auto');q.add_argument('--batch',type=int,default=1)
    q.add_argument('--protein-stride',type=int,default=480);q.add_argument('--he-stride',type=int,default=480)
    q.add_argument('--denoise-t',type=int,default=10,help='Exploratory native profile only; Studio retains its original schedule')
    q.add_argument('--seed',type=int,default=31415);q.add_argument('--z-spacing',type=float)
    q.add_argument('--resume',action='store_true')
    q=sub.add_parser('view');q.add_argument('--input',required=True);q.add_argument('--z-spacing',type=float);q.add_argument('--score')
    q=sub.add_parser('score');q.add_argument('--input',required=True);q.add_argument('--assets',required=True);q.add_argument('--out',required=True)
    q.add_argument('--tumor',choices=['glioblastoma','astrocytoma','oligodendroglioma'],required=True)
    q.add_argument('--device',default='auto');q.add_argument('--z-spacing',type=float,required=True);q.add_argument('--z-repeat',type=int,default=5)
    q.add_argument('--resume',action='store_true')
    sub.add_parser('gui')
    a=p.parse_args(argv)
    try:
        if a.command=='inspect':print(json.dumps(inspect_tiff(a.input,a.out),indent=2,ensure_ascii=True))
        elif a.command=='doctor':
            result=doctor()
            if a.out:dump(a.out,result)
            print(json.dumps(result,indent=2))
        elif a.command=='register-studio':register_studio(a.source,a.out,a.inference_only);print('Registered',a.out)
        elif a.command=='run':
            if a.profile=='studio' and not a.assets:p.error('--assets is required for Studio')
            if a.profile!='studio' and not a.weights:p.error('--weights is required for native mode')
            pipeline(a)
        elif a.command=='view':
            from .desktop import view
            view(a)
        elif a.command=='gui':
            from .desktop import gui
            gui()
        elif a.command=='score':
            from .scoring import score
            score(a)
    except Exception as exc:p.exit(1,f'ERROR: {exc}\n')


if __name__=='__main__':main()
