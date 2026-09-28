"""One public V3 policy and deterministic manual L/D display conversion."""
import numpy as np
from .vendor.calibration import fit, apply


def fit_stack(lipid, protein, indices, reference):
    if not indices:
        raise ValueError('At least one explicitly selected calibration plane is required')
    # Full XY on each selected plane, equal pixel contribution. No patch fitting.
    l = np.concatenate([np.asarray(lipid[i],np.float32).ravel() for i in indices])[None]
    p = np.concatenate([np.asarray(protein[i],np.float32).ravel() for i in indices])[None]
    params = fit(l,p,reference['target'],float(reference.get('ratio_reference',1.6367064714431763)))
    params['fit_scope'] = 'pooled full XY planes; fixed gain and alpha across stack'
    return params


def validate_manual(params):
    if params.get('schema') != 'ultra.manual.v1' or params.get('units') != 'native_DN':
        raise ValueError('Manual JSON requires schema ultra.manual.v1 and units native_DN')
    for channel in ['L','D']:
        c = params[channel]
        vals = [float(c[k]) for k in ['low','high','gamma']]
        if not np.isfinite(vals).all() or vals[1] <= vals[0] or vals[2] <= 0:
            raise ValueError(f'Invalid {channel} display range/gamma')
    return params


def manual_rgb(lipid,protein,params):
    validate_manual(params)
    l,p = np.asarray(lipid,np.float32),np.asarray(protein,np.float32)
    if l.shape != p.shape or not np.isfinite(l).all() or not np.isfinite(p).all():
        raise ValueError('Finite matching L/P arrays required')
    channels = []
    for name,a in [('L',l),('D',np.maximum(p-l,0))]:
        c = params[name]
        channels.append(np.clip((a-c['low'])/(c['high']-c['low']),0,1)**(1/c['gamma']))
    return np.rint(np.stack([np.zeros_like(l),*channels],-1)*255).astype(np.uint8)


def rgb(l,p,params,manual=False):
    return manual_rgb(l,p,params) if manual else apply(l,p,params,'V3')[3]
