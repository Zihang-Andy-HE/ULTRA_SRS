"""Adapters derived from Zhijie Liu et al., Zenodo 18323493 Ultra 3D Studio.

Retains original architecture/normalization; explicit fixes are named in profiles.
See THIRD_PARTY_NOTICES.md for source, license scope and modification history.
"""
import numpy as np
import torch
from .models import positions


def preprocess_plane(raw,mean,max_mean,safe=True):
    if not np.isfinite(mean) or mean<=0 or max_mean<=0:
        if safe:return np.zeros_like(raw,dtype=np.uint16)
        raise ValueError('Original preprocessing divides by zero on a blank plane')
    # Match upstream float32 operations, including division by 65535.
    arr=np.float32(raw)/65535
    arr=arr/np.float32(mean/max_mean)*65535
    if safe:arr=np.clip(arr,0,65535)
    return arr.astype(np.uint16)


def studio_rgb(lipid,protein):
    l=np.float32(lipid)/65535;p=np.float32(protein)/65535
    d=np.clip((p-l*.85)*10,0,1)
    return np.stack([np.zeros_like(d,dtype=np.uint8),np.uint8(l*255),np.uint8(d*255)],axis=-1)


@torch.inference_mode()
def studio_denoise(net,raw,device,t,eta=1.):
    if raw.shape!=(1024,1024):raise ValueError('Denoising currently requires full 1024 x 1024 planes')
    x=torch.from_numpy(raw.astype(np.float32))[None,None].to(device)/65535*2-1
    ab=torch.cumprod(1-torch.linspace(1e-4,.02,1000).double(),0).to(device)
    times=np.flipud(np.arange(t-1,0,-10));previous=np.concatenate([[0],times[:-1]])
    for current,prev in reversed(list(zip(times,previous))):
        a,b=ab[int(current)].float().reshape(1,1,1,1),ab[int(prev)].float().reshape(1,1,1,1)
        eps=net(x,torch.full((1,),int(current),device=device,dtype=torch.long))[0]
        sigma=eta*torch.sqrt((1-b)/(1-a)*(1-a/b))
        noise=torch.randn_like(x) if prev>0 else 0
        x=torch.sqrt(b/a)*x+(torch.sqrt(1-b-sigma**2)-torch.sqrt(b*(1-a)/a))*eps+sigma*noise
    return ((x[0,0].clamp(-1,1).cpu().numpy()/2+.5)*65535).astype(np.uint16)


@torch.inference_mode()
def tiled(net,plane,device,kind,stride=480,batch=1,scale=65535):
    if kind not in ('protein','he'):raise ValueError('Unknown tile kind')
    if not 1<=stride<=512 or batch<1:raise ValueError('Stride must be 1..512 and batch positive')
    h,w=plane.shape[:2];acc=np.zeros(plane.shape,np.float32);count=np.zeros((h,w),np.uint32)
    coords=[(y,x) for y in positions(h,stride=stride) for x in positions(w,stride=stride)]
    for start in range(0,len(coords),batch):
        cc=coords[start:start+batch];a=np.stack([plane[y:y+512,x:x+512] for y,x in cc]).astype(np.float32)
        t=torch.from_numpy(a).to(device)
        t=t[:,None]/scale*2-1 if kind=='protein' else t.permute(0,3,1,2)/255*2-1
        v=net(t).clamp(-1,1).cpu()
        if kind=='protein':v=v[:,0].numpy()
        else:v=((v.permute(0,2,3,1).numpy()+1)/2*255).astype(np.uint8)
        if not np.isfinite(v).all():raise ValueError('Nonfinite network output')
        for (y,x),patch in zip(cc,v):acc[y:y+512,x:x+512]+=patch;count[y:y+512,x:x+512]+=1
    # Keep original float32 division while allowing wide counters for dense overlaps.
    denominator=count.astype(np.float32)
    if kind=='protein':return ((acc/denominator/2+.5)*scale).astype(np.uint16 if scale==65535 else np.float32)
    return (acc/denominator[...,None]).astype(np.uint8)
