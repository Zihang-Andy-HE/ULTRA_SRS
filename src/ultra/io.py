import hashlib,json,os
from pathlib import Path
import numpy as np
import tifffile


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8388608),b''): h.update(b)
    return h.hexdigest()


def dump(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    tmp.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    os.replace(tmp,path)


def read_stack(path):
    with tifffile.TiffFile(path) as f:
        shape=f.series[0].shape
        axes=f.series[0].axes
    a=tifffile.imread(path)
    return a[None] if len(shape)==2 or (len(shape)==3 and axes.endswith("S")) else a


def validate_input(a,m):
    required = ['sample_id','acquisition_id','axes','voxel_size_um','z_origin_um',
                'measured_band_cm_1','dtype','native_intensity_max','offset',
                'file_plane_ordinals','z_positions_um']
    for key in required:
        if key not in m: raise ValueError(f'Missing metadata field: {key}')
    if m['axes']!='ZYX' or a.ndim!=3: raise ValueError('Explicit ZYX input required')
    if str(a.dtype)!=m['dtype'] or a.dtype!=np.uint16: raise ValueError('Input must match declared uint16 dtype')
    if m['native_intensity_max']!=4095: raise ValueError('Native exploratory profile requires maximum 4095')
    if a.min()<0 or a.max()>4095: raise ValueError('Input exceeds declared native range')
    if a.shape[1:]!=(1024,1024): raise ValueError('Denoising requires full 1024x1024 planes')
    if 'shape' in m and list(a.shape)!=m['shape']: raise ValueError('Input shape disagrees with metadata')
    ids=m['file_plane_ordinals'];z=np.asarray(m['z_positions_um'],float)
    if not isinstance(ids,list) or len(ids)!=len(a) or len(z)!=len(a) or any(type(i)!=int or i<1 for i in ids):
        raise ValueError('Invalid file plane ordinals')
    if len(set(ids))!=len(ids) or np.any(np.diff(ids)<=0) or not np.isfinite(z).all() or np.any(np.diff(z)<=0):
        raise ValueError('File plane coordinates must be finite and strictly increasing')
    if set(m['voxel_size_um'])!={'z','y','x'}: raise ValueError('voxel_size_um must contain z/y/x')
    for v in m['voxel_size_um'].values():
        if v is not None and (not np.isfinite(v) or v<=0): raise ValueError('Invalid voxel size')
    spacing=m['voxel_size_um']['z']
    if spacing is None: raise ValueError('z spacing required')
    if not np.allclose(z,(np.array(ids)-1)*spacing): raise ValueError('z positions disagree with file-relative spacing')


def write_ome(path,a,m):
    path=Path(path);tmp=path.with_name(path.stem+'.partial.ome.tif')
    isrgb=a.ndim==4
    meta={'axes':'ZYXS' if isrgb else 'ZYX', 'Description':json.dumps({'file_plane_ordinals':m['file_plane_ordinals'], 'source_slices':m.get('source_slices'),'depth_coordinate_reference':m.get('depth_coordinate_reference'),'z_positions_um':m['z_positions_um']})}
    for axis in ['x','y']:
        v=m['voxel_size_um'][axis]
        if v is not None:meta['PhysicalSize'+axis.upper()]=v;meta['PhysicalSize'+axis.upper()+'Unit']='µm'
    # Sparse segments are NOT advertised as a regularly spaced contiguous stack.
    if len(a)<2 or np.allclose(np.diff(m['file_plane_ordinals']),1):
        meta['PhysicalSizeZ']=m['voxel_size_um']['z'];meta['PhysicalSizeZUnit']='µm'
    meta['Plane']={'PositionZ':m['z_positions_um'],'PositionZUnit':['µm']*len(a)}
    tifffile.imwrite(tmp,a,ome=True,bigtiff=True,photometric='rgb' if isrgb else 'minisblack',metadata=meta)
    with tifffile.TiffFile(tmp) as f:
        b=f.asarray()
        if b.shape!=a.shape and len(a)==1:b=b[None]
        if not f.is_ome or not np.array_equal(a,b): raise RuntimeError('TIFF read-back verification failed')
    os.replace(tmp,path)


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
