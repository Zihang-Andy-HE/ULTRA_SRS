import argparse,csv,json,os,sys,time,traceback,hashlib
from .runtime import stage_lock,peak_rss_kib,resolve_device
from pathlib import Path
import numpy as np
import yaml
from . import models,calibration,qc,__version__
from .io import sha,dump,read_stack,validate_input,write_ome


def code_hash():
    root=Path(__file__).parent
    return hashlib.sha256(''.join(sha(p) for p in sorted(root.rglob('*.py'))).encode()).hexdigest()


def verified_stage(directory,expected=None):
    directory=Path(directory)
    s=json.loads((directory/'stage.json').read_text())
    if s['execution_status']!='complete': raise ValueError('Upstream stage is incomplete or failed')
    if expected and s['stage']!=expected: raise ValueError('Wrong upstream stage')
    for name,digest in s['files'].items():
        if sha(directory/name)!=digest: raise ValueError(f'Upstream hash mismatch: {name}')
    return s


def asset_paths(cfg,base):
    found={}
    for name,item in cfg['assets'].items():
        p=(base/item['path']).resolve()
        if not p.is_file() or sha(p)!=item['sha256']: raise ValueError(f'Asset absent or SHA256 mismatch: {name}')
        found[name]=p
    return found


def validate_config(cfg):
    if cfg.get('schema')!='ultra.config.v1':raise ValueError('Unsupported configuration schema')
    expected={'denoise':{'checkpoint_key':'net_model','preprocessing':'P2_full_zero','sampler':'interval','stride':10,'eta':0,'terminal_clean':False,'seed':31415,'precision':'FP32 TF32 allowed'},'lipid2protein':{'checkpoint_key':'G','patch':512,'stride':64,'input_scale':4095,'precision':'FP32 TF32 disabled','blend':'uniform float64 accumulation','output':'float32 native DN'},'virtual_stain':{'checkpoint_key':'G_A','patch':512,'stride':32,'precision':'FP32 TF32 disabled','input':'RGB8 /127.5 -1','blend':'uint8 patch quantization then float32 uniform average and uint8 truncation'}}
    for section,values in expected.items():
        if any(cfg[section].get(k)!=v for k,v in values.items()):raise ValueError(f'Unsupported numerical contract: {section}')
    if cfg['calibration']['mode']!='v3_pooled_fixed' or cfg['calibration']['bounds']!=[.5,2.]:raise ValueError('Only selected fixed V3 policy is supported')

def run(a):
    a.device=resolve_device(a.device)
    out=Path(a.out).resolve()
    if out.exists() and not a.resume: raise FileExistsError('Output exists; use --resume or a new directory')
    out.mkdir(parents=True,exist_ok=True)
    with stage_lock(out/'.lock'):
        return _run_locked(a)


def _run_locked(a):
    out=Path(a.out).resolve();started=time.time();previous=None
    if a.command=='denoise':
        config_path=Path(a.config).resolve();cfg=yaml.safe_load(config_path.read_text());assets=asset_paths(cfg,config_path.parent)
        m=json.loads(Path(a.metadata).read_text());L=read_stack(a.input);validate_input(L,m)
        if m['acquisition_id']!=cfg['denoise']['acquisition_id']: raise ValueError('G5 depth policy cannot silently apply to a different acquisition')
        identity={'input':sha(a.input),'metadata':sha(a.metadata),'config':sha(config_path)};warnings=[]
    else:
        upstream=Path(a.from_dir).resolve();previous=verified_stage(upstream,'denoise' if a.command=='lipid2protein' else 'lipid2protein')
        cfg=yaml.safe_load((upstream/'config.resolved.yaml').read_text());assets=asset_paths(cfg,upstream)
        m=json.loads((upstream/'metadata.json').read_text());warnings=list(previous['warnings'])
        if a.command=='lipid2protein':L=read_stack(upstream/'lipid_denoised.ome.tif')
        else:
            den=(upstream/previous['lipid_stage']).resolve();verified_stage(den,'denoise')
            if sha(den/'stage.json')!=previous['lipid_stage_sha256']:raise ValueError('Referenced lipid stage changed')
            L=read_stack(den/'lipid_denoised.ome.tif');P=read_stack(upstream/'protein_predicted.ome.tif')
        identity={'upstream':sha(upstream/'stage.json')}
    validate_config(cfg)
    identity.update(stage=a.command,code=code_hash(),assets={k:sha(v) for k,v in assets.items()},device=a.device,batch=a.batch)
    manual=None
    if getattr(a,'manual_params',None):
        manual=calibration.validate_manual(json.loads(Path(a.manual_params).read_text()));identity['manual']=sha(a.manual_params)
    if any(v is None for v in m['voxel_size_um'].values()):warnings.append('XY physical size unverified: omitted, no physical aspect claim')
    if m['z_origin_um'] is None:warnings.append('Absolute z origin unknown: depth is relative to first source slice')
    if m['measured_band_cm_1'] is None:warnings.append('Measured Raman band metadata unavailable')
    if out.exists() and not (out/'stage.json').exists() and any(p.name!='.lock' for p in out.iterdir()):raise ValueError('Existing files without a stage identity cannot be resumed')
    out.mkdir(parents=True,exist_ok=True)
    if (out/'stage.json').exists():
        old=json.loads((out/'stage.json').read_text())
        if old['identity']!=identity:raise ValueError('Resume identity mismatch; use a new output directory')
        if old['execution_status']=='complete':verified_stage(out);print('COMPLETE: verified existing output',out);return
    for d in ['qc','logs','cache','calibration']:(out/d).mkdir(exist_ok=True)
    state={'schema':'ultra.stage.v1','stage':a.command,'identity':identity,'execution_status':'running','qc_status':'pending','warnings':sorted(set(warnings)),'files':{},'version':__version__}
    dump(out/'stage.json',state)
    def log(s):
        print(s,flush=True)
        with (out/'logs/run.log').open('a') as f:f.write(s+'\n')
    try:
        cfg=json.loads(json.dumps(cfg))
        for k,p in assets.items():cfg['assets'][k]['path']=os.path.relpath(p,out)
        (out/'config.resolved.yaml').write_text(yaml.safe_dump(cfg,sort_keys=True));dump(out/'metadata.json',m)
        if previous:dump(out/'upstream_manifest.json',previous)
        if a.command=='denoise':
            rows=list(csv.DictReader(assets['policy'].open()));policy={int(r['source_slice']):r for r in rows}
            params={'policy':'G5 P2_full_zero / interval stride10 / eta0 / non-clean endpoint','source_slices':m['source_slices']}
        elif a.command=='virtual-stain':
            ref=json.loads(assets['reference'].read_text());dump(out/'calibration/reference.json',ref)
            if manual:params=manual
            else:
                selected=cfg['calibration']['fit_source_slices'];indices=[i for i,z in enumerate(m['source_slices']) if z in selected]
                if len(indices)!=len(selected):raise ValueError('Configured calibration slices absent from input')
                params=calibration.fit_stack(L,P,indices,ref);params['fit_source_slices']=selected
                if params['V3_bounds_hit']:warnings.append('V3 gain/alpha hit bounds')
            dump(out/'calibration/parameters.json',params)
            RGB=np.stack([calibration.rgb(l,p,params,manual is not None) for l,p in zip(L,P)])
            write_ome(out/'rgb_input.ome.tif',RGB,m)
            if np.mean(RGB[...,1:]>=255)>.001:warnings.append('RGB upper saturation exceeds 0.1%')
            # Persist and read back complete RGB BEFORE loading virtual-stain model / tiling.
            RGB=read_stack(out/'rgb_input.ome.tif')
        else:params=cfg['lipid2protein']
        dump(out/'parameters.json',params)
        kind={'virtual-stain':'virtual_stain'}.get(a.command,a.command)
        net=models.load(kind,assets[kind],a.device)
        outputs=[];metrics=[]
        import torch
        if a.device.startswith('cuda'):torch.cuda.reset_peak_memory_stats()
        for i,z in enumerate(m['source_slices']):
            t=time.time();cache=out/'cache'/f'{z:04d}.npy';record=cache.with_suffix('.json')
            if cache.exists() and record.exists() and sha(cache)==json.loads(record.read_text())['sha256']:
                v=np.load(cache,allow_pickle=False);cached=True
            else:
                cached=False
                if a.command=='denoise':
                    torch.manual_seed(31415+z);np.random.seed(31415+z);v=models.denoise_plane(net,L[i],policy[z],a.device)
                elif a.command=='lipid2protein':v=models.l2p_plane(net,L[i],a.device,a.batch)
                else:v=models.he_plane(net,RGB[i],a.device,a.batch)
                tmp=cache.with_suffix('.tmp')
                with tmp.open('wb') as f:np.save(f,v,allow_pickle=False)
                os.replace(tmp,cache);dump(record,{'sha256':sha(cache),'source_slice':z})
            expected=L[i].shape+((3,) if a.command=='virtual-stain' else ())
            if v.shape!=expected or not np.isfinite(v).all():raise ValueError('Invalid cached/computed plane')
            outputs.append(v);row=qc.metrics(v);row.update(source_slice=z,z_um=m['z_positions_um'][i],seconds=time.time()-t,reused=cached)
            if a.command=='denoise':row.update(t=int(policy[z]['t']),gain=float(policy[z]['gain']))
            metrics.append(row);log(f'{a.command} source_slice={z} seconds={row["seconds"]:.3f} reused={cached}')
        arr=np.stack(outputs)
        name={'denoise':'lipid_denoised.ome.tif','lipid2protein':'protein_predicted.ome.tif','virtual-stain':'virtual_HE.ome.tif'}[a.command]
        write_ome(out/name,arr,m)
        if a.command=='lipid2protein':state.update(lipid_stage=os.path.relpath(upstream,out),lipid_stage_sha256=sha(upstream/'stage.json'))
        if a.command=='denoise':qc.preview(out/'qc/preview.png',[L[0],arr[0],np.abs(L[0].astype(float)-arr[0])],['Raw','Denoised','Absolute residual (0–4095)'])
        elif a.command=='lipid2protein':qc.preview(out/'qc/preview.png',[L[0],arr[0],np.maximum(arr[0]-L[0],0)],['L','Predicted P','D=max(P-L,0)'])
        else:
            qc.preview(out/'qc/preview.png',[RGB[0],arr[0]],['Full-plane calibrated RGB','Virtual H&E']);qc.orthogonal(out/'qc/orthogonal.png',arr,m)
            (out/'report.html').write_text('<!doctype html><meta charset="utf-8"><h1>ULTRA virtual histology</h1><p>Proxy outputs; no H&amp;E ground truth. See stage.json for QC warnings and metadata.json for measured/missing scales.</p><img width="900" src="qc/preview.png"><img width="900" src="qc/orthogonal.png">')
        with (out/'qc/metrics.csv').open('w') as f:
            w=csv.DictWriter(f,fieldnames=list(metrics[0]));w.writeheader();w.writerows(metrics)
        state.update(execution_status='complete',qc_status='review_required' if warnings else 'pass',warnings=sorted(set(warnings)),elapsed_seconds=time.time()-started,max_rss_kib=peak_rss_kib(),gpu_peak_allocated_bytes=torch.cuda.max_memory_allocated() if a.device.startswith('cuda') else 0)
        dump(out/'qc/qc.json',{'status':state['qc_status'],'warnings':state['warnings']})
        state['files']={str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file() and p.name not in ['stage.json','.lock'] and 'cache' not in p.parts and p.suffix!='.tmp'}
        dump(out/'stage.json',state);print('COMPLETE',out,flush=True)
    except Exception as e:
        state.update(execution_status='failed',qc_status='error',error=str(e));dump(out/'stage.json',state);log(traceback.format_exc());raise


def main():
    p=argparse.ArgumentParser(description='ULTRA: frozen three-stage inference')
    sub=p.add_subparsers(dest='command',required=True)
    for name in ['denoise','lipid2protein','virtual-stain']:
        q=sub.add_parser(name);q.add_argument('--out',required=True);q.add_argument('--device',default='auto');q.add_argument('--batch',type=int,default=1);q.add_argument('--resume',action='store_true')
        if name=='denoise':
            for k in ['input','metadata','config']:q.add_argument('--'+k,required=True)
        else:q.add_argument('--from',dest='from_dir',required=True)
        if name=='virtual-stain':q.add_argument('--manual-params')
    a=p.parse_args()
    if a.batch<1:p.error('--batch must be positive')
    try:run(a)
    except Exception as e:p.exit(1,f'ERROR: {e}\n')

if __name__=='__main__':main()
