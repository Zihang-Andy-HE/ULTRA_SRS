from pathlib import Path
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def preview(path, arrays, labels):
    fig,axs=plt.subplots(1,len(arrays),figsize=(4*len(arrays),4),squeeze=False)
    for ax,a,label in zip(axs[0],arrays,labels):
        ax.imshow(a,cmap='gray',vmin=0 if a.ndim==2 else None,vmax=4095 if a.ndim==2 else None)
        ax.set_title(label);ax.axis('off')
    fig.tight_layout();fig.savefig(path,dpi=120);plt.close(fig)


def metrics(a):
    return {'min':float(a.min()),'max':float(a.max()),'mean':float(a.mean()),'std':float(a.std()),'saturation_fraction':float(np.mean(a>= (255 if a.dtype==np.uint8 else 4095)))}


def orthogonal(path,a,m):
    # Render each continuous segment separately; gaps are never collapsed into false adjacency.
    ids=np.array(m['source_slices']); cuts=np.r_[0,np.where(np.diff(ids)!=1)[0]+1,len(ids)]
    fig,axs=plt.subplots(len(cuts)-1,3,figsize=(12,3*(len(cuts)-1)),squeeze=False)
    spacing=m['voxel_size_um']; physical=spacing['x'] is not None and spacing['y'] is not None
    for row,(s,e) in enumerate(zip(cuts[:-1],cuts[1:])):
        v=a[s:e];nz,h,w=v.shape[:3]
        ims=[v[nz//2],v[:,h//2],v[:,:,w//2]]
        extents=[[0,w*spacing['x'],0,h*spacing['y']],[0,w*spacing['x'],m['z_positions_um'][e-1]+spacing['z'],m['z_positions_um'][s]],[0,h*spacing['y'],m['z_positions_um'][e-1]+spacing['z'],m['z_positions_um'][s]]] if physical else [None]*3
        for ax,im,name,extent in zip(axs[row],ims,['XY','XZ','YZ'],extents):
            ax.imshow(im,extent=extent,aspect='equal' if physical else 'auto')
            ax.set_title(f'{name}: source {ids[s]}–{ids[e-1]}');ax.set_xlabel('µm' if physical else 'pixels / slices (XY scale unknown)')
    fig.tight_layout();fig.savefig(path,dpi=150);plt.close(fig)
