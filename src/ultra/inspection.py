"""TIFF inspection without guessing acquisition identity from the filename."""
import platform,re
from pathlib import Path
import numpy as np
import tifffile
from .io import sha,dump


def inspect_tiff(path, out=None):
    path=Path(path).resolve()
    with tifffile.TiffFile(path) as f:
        series=f.series[0];ij=f.imagej_metadata or {};info=ij.get('Info','')
        spacing={'z':None,'y':None,'x':None};evidence={}
        if ij.get('unit') in ('micron','um','µm'):
            for axis,tag in [('x','XResolution'),('y','YResolution')]:
                if tag in f.pages[0].tags:
                    n,d=f.pages[0].tags[tag].value
                    if n>0:spacing[axis]=d/n;evidence[axis]='ImageJ unit=micron + TIFF '+tag
            if ij.get('spacing',0)>0:
                spacing['z']=float(ij['spacing']);evidence['z']='ImageJ spacing'
        # Olympus OIR acquisition axis, recorded as a candidate, not confirmed physical Z.
        candidate=re.search(r'^axis step #1 = ([\d.]+)$',info,re.M)
        z_length=re.search(r'^length z #1 = ([\d.]+)$',info,re.M)
        z_count=re.search(r'^axis maxSize #1 = (\d+)$',info,re.M)
        z_axis=re.search(r'^axis axis #1 = ZSTACK$',info,re.M)
        if spacing['z'] is None and z_length and candidate and z_axis and z_count and len(series.shape)==3:
            if int(z_count[1])==series.shape[0] and float(z_length[1])==float(candidate[1]) and float(z_length[1])>0:
                spacing['z']=float(z_length[1]);evidence['z']='OIR length z #1 agrees with ZSTACK axis step #1 and axis maxSize equals TIFF Z length'
        result={'schema':'ultra.inspect.v1','path':str(path),'sha256':sha(path),
                'shape':list(series.shape),'axes':series.axes,'dtype':str(series.dtype),
                'voxel_size_um':spacing,'spacing_evidence':evidence,
                'candidate_z_step_um':float(candidate[1]) if candidate else None,
                'candidate_z_note':'OIR axis step #1; confirm axis interpretation before physical analysis',
                'source_slice_mapping':'unknown; file plane ordinal is not original acquisition slice ID',
                'warnings':[]}
        arr=series.asarray()
        result['range']=[float(arr.min()),float(arr.max())]
        if arr.ndim==3 and series.axes in ('ZYX','QYX','IYX'):
            means=np.mean(arr,axis=(1,2),dtype=np.float64)
            result['plane_means']=means.tolist()
            result['zero_mean_planes']=(np.flatnonzero(means==0)+1).tolist()
            result['frozen_g5_shape_compatible']=arr.shape[1:]==(1024,1024)
            result['frozen_default_fit_possible_by_file_ordinal']=arr.shape[0]>=949
        if spacing['z'] is None:result['warnings'].append('Physical Z spacing requires confirmation')
        if len(result['shape'])==3 and result['shape'][0]!=998:
            result['warnings'].append('Not the frozen 998-plane G5 contract; no automatic depth-policy mapping')
    if out:dump(out,result)
    return result


def doctor():
    import torch,psutil
    from . import __version__
    return {'version':__version__,'platform':platform.platform(),'python':platform.python_version(),
            'torch':torch.__version__,'cuda_available':torch.cuda.is_available(),
            'recommended_device':'cuda:0' if torch.cuda.is_available() else 'cpu',
            'ram_available_bytes':psutil.virtual_memory().available,
            'cpu_count':psutil.cpu_count(),'note':'CPU inference is supported; full volume inference can be slow.'}
