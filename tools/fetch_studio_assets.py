import concurrent.futures,http.client,io,json,struct,time,urllib.request,zipfile,zlib
from pathlib import Path
import argparse
parser=argparse.ArgumentParser(description='Fetch original Zenodo ULTRA weights with resumable byte ranges and ZIP CRC checks.')
parser.add_argument('--out',type=Path,required=True,help='Download workspace; writes reference_studio and downloads/parts')
ROOT=parser.parse_args().out.resolve();ROOT.mkdir(parents=True,exist_ok=True)
URL='https://zenodo.org/api/records/18323493/files/Ultra%203D%20Studio.zip/content'
SIZE=1782772812
def chunk(start,end):
    received=b''
    for attempt in range(8):
        try:
            req=urllib.request.Request(URL,headers={'Range':f'bytes={start+len(received)}-{end}'})
            with urllib.request.urlopen(req,timeout=90) as r:
                if r.status!=206:raise ValueError('Range unavailable')
                try:received+=r.read()
                except http.client.IncompleteRead as exc:received+=exc.partial
            if len(received)!=end-start+1:continue
            return received
        except Exception as exc:
            print('Retry',start,exc,flush=True);time.sleep(min(2**attempt,15))
    raise RuntimeError(start)
class Remote(io.RawIOBase):
    def __init__(self):self.pos=0
    def seek(self,o,w=0):self.pos=o if w==0 else self.pos+o if w==1 else SIZE+o;return self.pos
    def tell(self):return self.pos
    def read(self,n=-1):
        n=SIZE-self.pos if n<0 else n
        if not n:return b''
        b=chunk(self.pos,min(SIZE,self.pos+n)-1);self.pos+=len(b);return b
with zipfile.ZipFile(Remote()) as z:
    infos=sorted([i for i in z.infolist() if i.filename.endswith('.pkl')],key=lambda i:('/classification/' in i.filename,i.compress_size))
for info in infos:
    out=ROOT/'reference_studio'/info.filename
    if out.exists() and out.stat().st_size==info.file_size:continue
    out.parent.mkdir(parents=True,exist_ok=True)
    header=chunk(info.header_offset,info.header_offset+29)
    n,e=struct.unpack_from('<HH',header,26);start=info.header_offset+30+n+e
    spans=[(s,min(s+4*1024*1024,start+info.compress_size)-1) for s in range(start,start+info.compress_size,4*1024*1024)]
    parts=ROOT/'downloads/parts'/out.stem;parts.mkdir(parents=True,exist_ok=True)
    def fetch(span):
        a,b=span;p=parts/str(a)
        if not p.exists() or p.stat().st_size!=b-a+1:p.write_bytes(chunk(a,b))
        return p
    print('Fetching',info.filename,len(spans),'chunks',flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for i,p in enumerate(pool.map(fetch,spans)):
            if i%8==0:print('Chunks',i+1,'/',len(spans),flush=True)
    dec=zlib.decompressobj(-15);crc=0;length=0
    with out.with_suffix('.partial').open('wb') as f:
        for a,b in spans:
            data=dec.decompress((parts/str(a)).read_bytes());f.write(data);crc=zlib.crc32(data,crc);length+=len(data)
        data=dec.flush();f.write(data);crc=zlib.crc32(data,crc);length+=len(data)
    if crc!=info.CRC or length!=info.file_size:raise ValueError('ZIP CRC/size mismatch')
    out.with_suffix('.partial').replace(out);print('CRC VERIFIED',out,flush=True)
