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
    ttk.Label(frame,text='ULTRA_SRS — 数据检查、处理与结果查看',font=('Microsoft YaHei UI',16)).pack(anchor='w')
    ttk.Label(frame,text='原始算法与模型：Zhijie Liu 等 / Ultrarapid-Deep-3D-Histology · 本地研究流程').pack(anchor='w',pady=(4,12))
    def field(label,key,default='',directory=False):
        row=ttk.Frame(frame);row.pack(fill='x',pady=3)
        ttk.Label(row,text=label,width=24).pack(side='left');var=tk.StringVar(value=default);fields[key]=var
        ttk.Entry(row,textvariable=var).pack(side='left',fill='x',expand=True)
        def browse():
            path=filedialog.askdirectory() if directory else filedialog.askopenfilename()
            if path:var.set(path)
        ttk.Button(row,text='浏览',command=browse).pack(side='left',padx=5)
    base=Path.cwd()
    if (base/'G5.tif').exists():default=str(base/'G5.tif')
    else:default=''
    field('输入 TIFF','input',default)
    field('输出目录（新建）','out',str(base/'results'/'new_run'),True)
    field('Studio 权重清单 JSON','assets',str(base/'studio_assets.json'))
    field('ULTRA_SRS 权重目录','weights',str(base/'weights_srs'),True)
    controls=ttk.Frame(frame);controls.pack(fill='x',pady=10)
    fields['profile']=tk.StringVar(value='studio');fields['planes']=tk.StringVar(value='1,75,150');fields['z']=tk.StringVar(value='')
    fields['device']=tk.StringVar(value='auto');fields['resume']=tk.BooleanVar(value=False)
    for label,key,values in [('流程','profile',['studio','native-exploratory']),('设备','device',['auto','cpu','cuda:0'])]:
        ttk.Label(controls,text=label).pack(side='left');ttk.Combobox(controls,textvariable=fields[key],values=values,state='readonly',width=20).pack(side='left',padx=6)
    ttk.Label(controls,text='文件层号').pack(side='left');ttk.Entry(controls,textvariable=fields['planes'],width=15).pack(side='left')
    ttk.Label(controls,text='Z µm（可留空）').pack(side='left');ttk.Entry(controls,textvariable=fields['z'],width=6).pack(side='left')
    ttk.Checkbutton(frame,text='恢复已中断的相同参数任务（缓存校验）',variable=fields['resume']).pack(anchor='w')
    ttk.Label(frame,text='Studio 使用原始 16 位流程；native-exploratory 为 12 位探索性迁移。此界面用 480 像素步长快速试跑。').pack(anchor='w',pady=4)
    buttons=ttk.Frame(frame);buttons.pack(fill='x',pady=8)
    text=tk.Text(frame,height=18,wrap='word',font=('Consolas',10));text.pack(fill='both',expand=True)
    def start(args):
        if process[0] and process[0].poll() is None:messagebox.showinfo('任务运行中','请等待当前任务或停止后再运行。');return
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
        if process[0] and process[0].poll() is None:process[0].terminate();events.put('已停止；用相同参数勾选恢复可继续。\n')
    def open_report():
        path=Path(fields['out'].get())/'report.html'
        if path.exists():webbrowser.open(path.resolve().as_uri())
        else:messagebox.showinfo('尚无报告','处理完成后会生成 report.html。')
    def show_volume():
        path=filedialog.askopenfilename(title='选择 TIFF 体数据')
        if path:start(['view','--input',path]+(['--z-spacing',fields['z'].get()] if fields['z'].get() else []))
    for label,callback in [('环境检查',lambda:start(['doctor'])),('检查 TIFF',lambda:start(['inspect','--input',fields['input'].get()])),('开始处理',run),('停止',cancel),('打开结果',open_report),('3D 查看器',show_volume)]:
        ttk.Button(buttons,text=label,command=callback).pack(side='left',padx=4)
    scorebar=ttk.Frame(frame);scorebar.pack(fill='x',pady=5)
    tumor=tk.StringVar(value='glioblastoma')
    ttk.Label(scorebar,text='3D 窗口概率图（研究用，输入为 5 µm H&E）').pack(side='left')
    ttk.Combobox(scorebar,textvariable=tumor,values=['glioblastoma','astrocytoma','oligodendroglioma'],state='readonly',width=20).pack(side='left',padx=4)
    def score():
        path=filedialog.askopenfilename(title='选择 5 µm 间距的 RGB H&E 体数据（至少 10 层）')
        if not path:return
        dest=filedialog.askdirectory(title='选择评分输出的父目录')
        if not dest:return
        start(['score','--input',path,'--assets',fields['assets'].get(),'--out',str(Path(dest)/('score_'+tumor.get())),
               '--tumor',tumor.get(),'--device',fields['device'].get(),'--z-spacing','5'])
    ttk.Button(scorebar,text='选择 H&E 并评分',command=score).pack(side='left')
    def poll():
        while not events.empty():text.insert('end',events.get());text.see('end')
        root.after(150,poll)
    def close():cancel();root.destroy()
    root.protocol('WM_DELETE_WINDOW',close);poll();root.mainloop()
