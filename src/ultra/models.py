"""Inference adapters preserving the audited numerical contracts."""
import numpy as np
import torch
from diffusers import UNet2DModel
from .vendor.l2p_networks import ResnetGenerator
from .vendor.he_model import Generator


def configure(device, tf32=False):
    torch.set_num_threads(2)
    torch.backends.cuda.matmul.allow_tf32 = tf32
    torch.backends.cudnn.allow_tf32 = tf32
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    if str(device).startswith('cuda'):
        free, total = torch.cuda.mem_get_info(device)
        if free < 24 * 2**30:
            raise RuntimeError('Need at least 24 GiB free GPU memory; retry when available')
        torch.cuda.set_per_process_memory_fraction(.20, device)


def load(kind, path, device):
    configure(device, kind == 'denoise')
    if kind == 'denoise':
        net = UNet2DModel(sample_size=1024, in_channels=1, out_channels=1,
            layers_per_block=2, block_out_channels=(64,64,128,128,256,256),
            down_block_types=('DownBlock2D',)*4+('AttnDownBlock2D',)*2,
            up_block_types=('AttnUpBlock2D',)*2+('UpBlock2D',)*4)
        key = 'net_model'
    elif kind == 'lipid2protein':
        net, key = ResnetGenerator(1,1,64), 'G'
    else:
        net, key = Generator(3,32,3,6), 'G_A'
    # Tensor-only release weights are verified against the fixed SHA256 registry.
    ck = torch.load(path, map_location='cpu', weights_only=True)
    net.load_state_dict(ck[key], strict=True)
    return net.to(device).eval()


@torch.inference_mode()
def denoise_plane(net, raw, policy, device):
    gain, offset, t = np.float64(policy['gain']), np.float64(policy['offset']), int(policy['t'])
    raw = np.asarray(raw, np.float32)
    if t == 0:
        return raw.astype(np.uint16)
    x = torch.from_numpy((np.clip((raw-offset)*gain,0,65535)[None,None]/65535*2-1).astype(np.float32)).to(device)
    # Same float32 linspace -> float64 cumulative product -> float32 extract as upstream.
    ab = torch.cumprod(1-torch.linspace(1e-4,.02,1000).double(),0).to(device)
    times = np.flipud(np.arange(t-1,0,-10))
    previous = np.concatenate([[0],times[:-1]])
    for current, prev in reversed(list(zip(times,previous))):
        a, b = ab[int(current)].float().reshape(1,1,1,1), ab[int(prev)].float().reshape(1,1,1,1)
        eps = net(x, torch.full((1,),int(current),device=device,dtype=torch.long))[0]
        x = torch.sqrt(b/a)*x+(torch.sqrt(1-b)-torch.sqrt(b*(1-a)/a))*eps
    pred = x.clamp(-1,1).cpu().numpy()[0,0]
    native = (pred+1)*32767.5/gain+offset
    if not np.isfinite(native).all():
        raise ValueError('Nonfinite denoiser output')
    return np.rint(np.clip(native,0,4095)).astype(np.uint16)


def positions(n, size=512, stride=64):
    if n < size:
        raise ValueError('Plane dimensions must be >=512; no implicit padding')
    p = list(range(0,n-size+1,stride))
    if p[-1] != n-size:
        p.append(n-size)
    return p


@torch.inference_mode()
def l2p_plane(net, lipid, device, batch=1):
    h,w = lipid.shape
    acc = np.zeros((h,w),np.float64)
    count = np.zeros((h,w),np.uint16)
    coords = [(y,x) for y in positions(h) for x in positions(w)]
    for start in range(0,len(coords),batch):
        cc = coords[start:start+batch]
        a = np.stack([lipid[y:y+512,x:x+512] for y,x in cc]).astype(np.float32)
        pred = net(torch.from_numpy(a[:,None]).to(device)/4095*2-1).cpu().numpy()[:,0]
        if not np.isfinite(pred).all():
            raise ValueError('Nonfinite L2P prediction')
        for (y,x),v in zip(cc,pred):
            acc[y:y+512,x:x+512] += np.clip(v,-1,1)
            count[y:y+512,x:x+512] += 1
    return ((acc/count/2+.5)*4095).astype(np.float32)


@torch.inference_mode()
def he_plane(net, rgb, device, batch=1):
    h,w = rgb.shape[:2]
    acc, count = np.zeros(rgb.shape,np.float32), np.zeros((h,w),np.float32)
    coords = [(y,x) for y in positions(h,stride=32) for x in positions(w,stride=32)]
    for start in range(0,len(coords),batch):
        cc = coords[start:start+batch]
        a = np.stack([rgb[y:y+512,x:x+512] for y,x in cc])
        t = torch.from_numpy(a).permute(0,3,1,2).float().to(device)/127.5-1
        v = net(t).cpu().permute(0,2,3,1).numpy()
        if not np.isfinite(v).all():
            raise ValueError('Nonfinite virtual stain prediction')
        v = ((v+1)*127.5).clip(0,255).astype(np.uint8)
        for (y,x),patch in zip(cc,v):
            acc[y:y+512,x:x+512] += patch
            count[y:y+512,x:x+512] += 1
    return (acc/count[...,None]).astype(np.uint8)
