"""Inference-only calibration. Native P remains an L2P output, never ground truth."""
import numpy as np
EPS=1.0

def check(l,p):
 l=np.asarray(l,np.float32);p=np.asarray(p,np.float32)
 if l.shape!=p.shape or l.ndim!=2 or not np.isfinite(l).all() or not np.isfinite(p).all():raise ValueError('Finite matching YX channels required')
 if np.min(l)<0 or np.min(p)<0:raise ValueError('Nonnegative native channels required')
 return l,p

def mask(l,p):
 pos=l[l>0]
 threshold=max(16.,float(np.percentile(pos,10))) if pos.size else 16.
 return (l>threshold)&(l<4095)&(p<4095),threshold

def describe(l,p,d,m):
 if m.sum()<32:raise ValueError('Insufficient valid tissue')
 return {'median_L':float(np.median(l[m])),'median_P':float(np.median(p[m])),'median_D':float(np.median(d[m])), 'P_L_ratio':float(np.median(p[m]/(l[m]+EPS))), 'D_L_ratio':float(np.median(d[m]/(l[m]+EPS)))}

def fit(l,p,ref,ratio_reference):
 l,p=check(l,p);m,threshold=mask(l,p)
 if m.sum()<256:raise ValueError('Insufficient tissue for calibration')
 d=np.maximum(p-l,0);r=float(np.median(p[m]/(l[m]+EPS)))
 if r<=0:raise ValueError('Degenerate predicted protein ratio')
 v2=float(np.clip(ratio_reference/r,.5,2.))
 # A common scalar controls brightness without changing channel relationships.
 gain=float(np.clip(ref['median_L']/np.median(l[m]),.5,2.))
 ll=l[m]*gain;pp=p[m]*gain
 lo,hi=.5,2.
 for _ in range(40):
  a=(lo+hi)/2
  if np.median(np.maximum(a*pp-ll,0)/(ll+EPS))<ref['D_L_ratio']:lo=a
  else:hi=a
 a=(lo+hi)/2
 return {'mask_threshold':threshold,'mask_count':int(m.sum()),'raw_ratio':r,'ratio_reference':ratio_reference,'V2_alpha':v2,'V3_alpha':a,'V3_gain':gain,'V3_target':ref['D_L_ratio'],'V3_gain_unbounded':float(ref['median_L']/np.median(l[m])),'V2_alpha_unbounded':ratio_reference/r,'V1_L_percentiles':np.percentile(l,[1,99]).tolist(),'V1_D_percentiles':np.percentile(d,[1,99]).tolist(),'V3_bounds_hit':bool(a<.50001 or a>1.99999 or gain in [.5,2.]),'fit_scope':'deterministic uniform full-plane sample, max approximately 1 million pixels'}

def apply(l,p,params,version):
 l,p=check(l,p)
 if version=='V0':lc,pc=l,p;d=np.maximum(pc-lc,0)
 elif version=='V1':
  def norm(x,b):return np.clip((x-b[0])/max(b[1]-b[0],1e-6),0,1)*4095
  lc=norm(l,params['V1_L_percentiles']);d=norm(np.maximum(p-l,0),params['V1_D_percentiles']);pc=lc+d
 elif version=='V2':lc=l;pc=p*params['V2_alpha'];d=np.maximum(pc-lc,0)
 elif version=='V3':lc=l*params['V3_gain'];pc=p*params['V3_gain']*params['V3_alpha'];d=np.maximum(pc-lc,0)
 else:raise ValueError(version)
 rgb=np.stack([np.zeros_like(lc),lc,d],-1)
 rgb=np.rint(np.clip(rgb,0,4095)*255/4095).astype(np.uint8)
 return lc,pc,d,rgb
