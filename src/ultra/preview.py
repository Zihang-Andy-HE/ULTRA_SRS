"""Localhost-only manual L/D preview; SSH tunnel is the intended access path."""
import argparse,base64,io,json
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
from PIL import Image
import numpy as np
from .cli import verified_stage
from .io import read_stack,sha,dump
from .calibration import manual_rgb,validate_manual

HTML='''<!doctype html><meta charset="utf-8"><title>ULTRA manual L/D</title>
<style>body{font:16px system-ui;max-width:1100px;margin:30px auto;background:#f5f5f5}input{width:90px}img{max-width:95%;image-rendering:auto}textarea{width:95%;height:170px}label{margin-right:12px}</style>
<h1>ULTRA: manual L / D preview</h1><p>D = max(P − L, 0). One parameter set is replayed across all planes. This replaces V3. Native DN; gamma uses exponent 1/gamma.</p>
<label>Plane index <input id="plane" type="number" min="0" value="0"></label><span id="slice"></span><div id="controls"></div>
<button id="render">Preview</button> <button id="save">Save JSON on server</button><span id="saved"></span> <input id="load" type="file" accept=".json"><pre id="metrics"></pre><img id="image"><textarea id="params" readonly></textarea>
<script>
let state={schema:'ultra.manual.v1',units:'native_DN',L:{low:0,high:2500,gamma:1},D:{low:0,high:2000,gamma:1},operator:'manual preview'};
for(let c of ['L','D']){let div=document.createElement('div');div.innerHTML='<h3>'+c+'</h3>';for(let k of ['low','high','gamma']){let label=document.createElement('label');label.textContent=k+' ';let input=document.createElement('input');input.id=c+k;input.type='number';input.step=k==='gamma'?'0.1':'10';input.value=state[c][k];input.onchange=draw;label.append(input);div.append(label)}document.getElementById('controls').append(div)}
async function draw(){for(let c of ['L','D'])for(let k of ['low','high','gamma'])state[c][k]=Number(document.getElementById(c+k).value);document.getElementById('params').value=JSON.stringify(state,null,2);let r=await fetch('/render',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({plane:Number(document.getElementById('plane').value),params:state})});let x=await r.json();if(!r.ok){document.getElementById('metrics').textContent=x.error;return}document.getElementById('image').src='data:image/png;base64,'+x.png;delete x.png;document.getElementById('metrics').textContent=JSON.stringify(x,null,2)}
document.getElementById('render').onclick=draw;document.getElementById('plane').onchange=draw;
document.getElementById('save').onclick=async()=>{await draw();let r=await fetch('/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(state)});let x=await r.json();document.getElementById('saved').textContent=r.ok?'Saved: '+x.path:x.error};
document.getElementById('load').onchange=async e=>{try{state=JSON.parse(await e.target.files[0].text());for(let c of ['L','D'])for(let k of ['low','high','gamma'])document.getElementById(c+k).value=state[c][k];await draw()}catch(e){document.getElementById('metrics').textContent=e}};draw();
</script>'''


def create_server(stage,port=8765):
    stage=Path(stage);s=verified_stage(stage,'lipid2protein');den=(stage/s['lipid_stage']).resolve();verified_stage(den,'denoise')
    if sha(den/'stage.json')!=s['lipid_stage_sha256']:raise ValueError('Lipid stage changed')
    L=read_stack(den/'lipid_denoised.ome.tif');P=read_stack(stage/'protein_predicted.ome.tif');metadata=json.loads((stage/'metadata.json').read_text())
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path!='/':self.send_error(404);return
            body=HTML.encode();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.end_headers();self.wfile.write(body)
        def do_POST(self):
            try:
                if self.path not in ['/render','/save']:raise ValueError('Unknown endpoint')
                n=int(self.headers.get('Content-Length',0))
                if not 0<n<32768:raise ValueError('Invalid request size')
                data=json.loads(self.rfile.read(n))
                if self.path=='/save':
                    params=validate_manual(data);path=stage.parent/'manual_rgb.json';dump(path,params)
                    self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps({'path':str(path.resolve()),'sha256':sha(path)}).encode());return
                i=data['plane']
                if type(i)!=int or not 0<=i<len(L):raise ValueError('Invalid plane index')
                params=validate_manual(data['params']);rgb=manual_rgb(L[i],P[i],params)
                b=io.BytesIO();Image.fromarray(rgb).save(b,format='PNG')
                result={'png':base64.b64encode(b.getvalue()).decode(),'source_slice':metadata['source_slices'][i],'relative_z_um':metadata['z_positions_um'][i],'parameters':params,'upper_saturation':{c:float((rgb[...,j]>=255).mean()) for c,j in [('L',1),('D',2)]},'lower_clipped':{c:float((rgb[...,j]==0).mean()) for c,j in [('L',1),('D',2)]}}
                self.send_response(200)
            except Exception as e:result={'error':str(e)};self.send_response(400)
            self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(result).encode())
    return HTTPServer(('127.0.0.1',port),Handler)


def main():
    p=argparse.ArgumentParser();p.add_argument('--from',dest='stage',required=True);p.add_argument('--port',type=int,default=8765);a=p.parse_args()
    server=create_server(a.stage,a.port);print(f'ULTRA preview http://127.0.0.1:{server.server_port}',flush=True);server.serve_forever()

if __name__=='__main__':main()
