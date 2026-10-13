"""Native file picker and workflow launcher; optional napari volume rendering."""
from pathlib import Path
import json,queue,subprocess,sys,threading,webbrowser
import numpy as np
from .io import read_stack


def view(a):
    try:import napari
    except ImportError as exc:
        raise RuntimeError('3D viewer is optional. Install with: python -m pip install "ultra-histology[viewer]" (or pip install -e ".[viewer]" in the source directory).') from exc
    import tifffile
    data=read_stack(a.input)
    with tifffile.TiffFile(a.input) as t:
        xml=t.ome_metadata
    scale=[a.z_spacing or 1.,1.,1.]
    if xml:
        import xml.etree.ElementTree as ET
        root=ET.fromstring(xml);pixels=root.find('.//{*}Pixels')
        scale=[a.z_spacing or float(pixels.get('PhysicalSizeZ',1)),float(pixels.get('PhysicalSizeY',1)),float(pixels.get('PhysicalSizeX',1))]
        positions=[float(p.get('PositionZ')) for p in pixels.findall('{*}Plane') if p.get('PositionZ') is not None]
        if len(positions)>2 and not np.allclose(np.diff(positions),np.diff(positions)[0]):
            raise ValueError('Sparse/nonuniform Z cannot be represented as a contiguous physical volume. View individual planes or resample explicitly.')
        if len(positions)>1:scale[0]=positions[1]-positions[0]
        if 'PhysicalSizeZ' not in pixels.attrib and not positions and a.z_spacing is None:
            scale=[1,1,1]
    viewer=napari.Viewer(title='ULTRA_SRS | Zhijie Liu et al. original models | research output')
    if data.ndim==4:
        # Napari RGB volume MIP can wash out histology colors. Match the original
        # Studio's separate translucent additive R/G/B volume layers.
        for channel,color in enumerate(('red','green','blue')):
            viewer.add_image(data[...,channel],name=Path(a.input).name+' / '+color,
                             colormap=color,scale=scale,contrast_limits=(0,255),
                             rendering='translucent',blending='additive')
    else:viewer.add_image(data,name=Path(a.input).name,scale=scale)
    if a.score:
        score=read_stack(a.score)
        if score.shape!=data.shape[:3]:raise ValueError('Score shape does not match image')
        viewer.add_image(score,name='Window probability (research)',scale=scale,colormap='magma',opacity=.45)
    viewer.dims.ndisplay=3;napari.run()


def gui():
    import tkinter as tk
    from tkinter import ttk,filedialog,messagebox
    root=tk.Tk();root.title('ULTRA_SRS 0.3 | Original ULTRA models: Zhijie Liu et al.');root.geometry('1000x780')
    fields={};events=queue.Queue();process=[None]
    frame=ttk.Frame(root,padding=14);frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='ULTRA_SRS - Inspect, process and view',font=('TkDefaultFont',16)).pack(anchor='w')
    ttk.Label(frame,text='Original methods and models: Zhijie Liu et al. / Ultrarapid-Deep-3D-Histology').pack(anchor='w',pady=(4,12))
    def field(label,key,default='',directory=False):
        row=ttk.Frame(frame);row.pack(fill='x',pady=3)
        ttk.Label(row,text=label,width=24).pack(side='left');var=tk.StringVar(value=default);fields[key]=var
        ttk.Entry(row,textvariable=var).pack(side='left',fill='x',expand=True)
        def browse():
            path=filedialog.askdirectory() if directory else filedialog.askopenfilename()
            if path:var.set(path)
        ttk.Button(row,text='Browse',command=browse).pack(side='left',padx=5)
    base=Path.cwd()
    field('Input TIFF','input')
    field('Output directory (new)','out',str(base/'results'/'new_run'),True)
    field('Studio asset manifest JSON','assets',str(base/'studio_assets.json'))
    field('ULTRA_SRS weights directory','weights',str(base/'work'/'models'),True)
    controls=ttk.Frame(frame);controls.pack(fill='x',pady=10)
    fields['profile']=tk.StringVar(value='studio');fields['planes']=tk.StringVar(value='1');fields['z']=tk.StringVar(value='')
    fields['device']=tk.StringVar(value='auto');fields['resume']=tk.BooleanVar(value=False)
    for label,key,values in [('Profile','profile',['studio','native-exploratory']),('Device','device',['auto','cpu','cuda:0'])]:
        ttk.Label(controls,text=label).pack(side='left');ttk.Combobox(controls,textvariable=fields[key],values=values,state='readonly',width=20).pack(side='left',padx=6)
    ttk.Label(controls,text='File planes').pack(side='left');ttk.Entry(controls,textvariable=fields['planes'],width=15).pack(side='left')
    ttk.Label(controls,text='Z um (optional)').pack(side='left');ttk.Entry(controls,textvariable=fields['z'],width=6).pack(side='left')
    ttk.Checkbutton(frame,text='Resume an interrupted run with identical parameters (verify cache)',variable=fields['resume']).pack(anchor='w')
    ttk.Label(frame,text='Studio uses the original 16-bit workflow; native-exploratory transfers to 12-bit data. GUI stride: 480 pixels.').pack(anchor='w',pady=4)
    buttons=ttk.Frame(frame);buttons.pack(fill='x',pady=8)
    text=tk.Text(frame,height=18,wrap='word',font=('TkFixedFont',10));text.pack(fill='both',expand=True)
    def start(args):
        if process[0] and process[0].poll() is None:messagebox.showinfo('Run in progress','Wait for the current run or stop it before starting another.');return
        command=[sys.executable,'-u','-m','ultra.studio',*args]
        text.insert('end',' '.join(command)+'\n')
        process[0]=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        child=process[0]
        def collect():
            for line in child.stdout:events.put(line)
            events.put(f'Process exit: {child.wait()}\n')
        threading.Thread(target=collect,daemon=True).start()
    def run():
        args=['run','--input',fields['input'].get(),'--out',fields['out'].get(),'--profile',fields['profile'].get(),
              '--assets',fields['assets'].get(),'--weights',fields['weights'].get(),'--planes',fields['planes'].get(),'--device',fields['device'].get()]
        if fields['z'].get():args+=['--z-spacing',fields['z'].get()]
        if fields['resume'].get():args+=['--resume']
        start(args)
    def cancel():
        if process[0] and process[0].poll() is None:process[0].terminate();events.put('Stopped. Select Resume with the same parameters to continue.\n')
    def open_report():
        path=Path(fields['out'].get())/'report.html'
        if path.exists():webbrowser.open(path.resolve().as_uri())
        else:messagebox.showinfo('Report unavailable','Processing generates report.html when complete.')
    def show_volume():
        path=filedialog.askopenfilename(title='Select a TIFF volume')
        if path:start(['view','--input',path]+(['--z-spacing',fields['z'].get()] if fields['z'].get() else []))
    for label,callback in [('Environment',lambda:start(['doctor'])),('Inspect TIFF',lambda:start(['inspect','--input',fields['input'].get()])),('Run',run),('Stop',cancel),('Open results',open_report),('3D viewer',show_volume)]:
        ttk.Button(buttons,text=label,command=callback).pack(side='left',padx=4)
    scorebar=ttk.Frame(frame);scorebar.pack(fill='x',pady=5)
    tumor=tk.StringVar(value='glioblastoma')
    ttk.Label(scorebar,text='3D window probabilities (research; 5 um H&E input)').pack(side='left')
    ttk.Combobox(scorebar,textvariable=tumor,values=['glioblastoma','astrocytoma','oligodendroglioma'],state='readonly',width=20).pack(side='left',padx=4)
    def score():
        path=filedialog.askopenfilename(title='Select RGB H&E at 5 um Z spacing (at least 10 planes)')
        if not path:return
        dest=filedialog.askdirectory(title='Select the parent directory for score output')
        if not dest:return
        start(['score','--input',path,'--assets',fields['assets'].get(),'--out',str(Path(dest)/('score_'+tumor.get())),
               '--tumor',tumor.get(),'--device',fields['device'].get(),'--z-spacing','5'])
    ttk.Button(scorebar,text='Select H&E and score',command=score).pack(side='left')
    def poll():
        while not events.empty():text.insert('end',events.get());text.see('end')
        root.after(150,poll)
    def close():cancel();root.destroy()
    root.protocol('WM_DELETE_WINDOW',close);poll();root.mainloop()
