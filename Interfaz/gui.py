"""Editor de CogniaCode; comparte el analizador con la consola."""
import json
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from time import perf_counter
from Compilador.analyzer import analyze, format_report
from Compilador.runtime import execute
from Compilador.language import RULES, TYPES, normalize
from Compilador.lexer import PATTERN
from Compilador.intermediate import format_intermediate
from Interfaz.stage_views import format_tokens, format_ast, format_semantic, format_console
from Interfaz.ui_components import COLORS as C, Motion, Button, ScrollPanel, Scrollbar, label, blend


def dark_title(window):
    import sys
    if sys.platform=='win32':
        try:
            import ctypes
            window.update_idletasks()
            hwnd=ctypes.windll.user32.GetParent(window.winfo_id())
            enabled=ctypes.c_int(1)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd,20,ctypes.byref(enabled),ctypes.sizeof(enabled))
        except (OSError,AttributeError):
            pass

class App:
    def __init__(self,root):
        self.root=root; self.motion=Motion(root)
        self.path=None; self.filename='sin_titulo.cog'; self.saved_source=''
        self.report=None; self.highlight_job=None; self.gutter_job=None
        self.font_size=13; self.tab_buttons={}
        self.current_tab='Análisis semántico'; self.sidebar_visible=True
        root.title('CogniaCode')
        root.geometry(f'{min(1320,root.winfo_screenwidth()-70)}x{min(850,root.winfo_screenheight()-90)}')
        root.minsize(1050,620); root.configure(bg=C['bg'])
        self.configure_style(); self.build_header(); self.build_footer()
        self.workspace=tk.Frame(root,bg=C['border']); self.workspace.pack(fill='both',expand=True)
        self.build_sidebar()
        self.main=tk.Frame(self.workspace,bg=C['editor']); self.main.pack(side='left',fill='both',expand=True,padx=(1,0))
        self.build_editor()
        root.bind('<F5>',lambda e:self.run())
        root.bind('<Control-o>',lambda e:self.open_file())
        root.bind('<Control-s>',lambda e:self.save_file())
        root.bind('<Control-n>',lambda e:self.new_file())
        root.bind('<Control-b>',lambda e:self.toggle_sidebar())
        root.protocol('WM_DELETE_WINDOW',self.close)
        self.set_source('','sin_titulo.cog')
        self.set_window_chrome()

    def set_window_chrome(self):
        self.icon=tk.PhotoImage(width=32,height=32)
        self.icon.put(C['bg'],to=(0,0,32,32))
        for step in range(9):
            for x,y in [(5+step,16-step),(5+step,16+step),(26-step,16-step),(26-step,16+step)]:
                self.icon.put(C['accent'],to=(x,y,x+2,y+2))
        self.root.iconphoto(True,self.icon)
        dark_title(self.root)

    def configure_style(self):
        style=ttk.Style(); style.theme_use('clam')
        style.configure('Treeview',background=C['editor'],fieldbackground=C['editor'],foreground=C['text'],borderwidth=0,rowheight=34,font=('Segoe UI',10))
        style.configure('Treeview.Heading',background=C['panel'],foreground=C['muted'],relief='flat',font=('Segoe UI',9),padding=(10,8))
        style.map('Treeview',background=[('selected',C['accent_dark'])],foreground=[('selected',C['accent'])])
        style.map('Treeview.Heading',background=[('active',C['raised'])])
        for orientation in ('Vertical','Horizontal'):
            style.configure(orientation+'.TScrollbar',background=C['raised'],troughcolor=C['editor'],bordercolor=C['editor'],arrowcolor=C['subtle'],lightcolor=C['raised'],darkcolor=C['raised'],arrowsize=9)

    def build_header(self):
        header=tk.Frame(self.root,bg=C['bg'],height=60); header.pack(fill='x'); header.pack_propagate(False)
        mark=tk.Canvas(header,width=33,height=34,bg=C['bg'],highlightthickness=0); mark.pack(side='left',padx=(22,9))
        mark.create_line(11,9,4,17,11,25,fill=C['accent'],width=2)
        mark.create_line(23,9,30,17,23,25,fill=C['accent'],width=2)
        mark.create_line(19,6,14,28,fill=C['muted'],width=2)
        label(header,'CogniaCode',15,bold=True).pack(side='left')
        Button(header,'Compilar y ejecutar   F5',self.run,self.motion,width=195,primary=True,surface=C['bg']).pack(side='right',padx=(9,20))
        Button(header,'Guardar',self.save_file,self.motion,width=83,surface=C['bg']).pack(side='right',padx=3)
        Button(header,'Nuevo',self.new_file,self.motion,width=70,surface=C['bg']).pack(side='right',padx=3)
        Button(header,'Abrir',self.open_file,self.motion,width=68,surface=C['bg']).pack(side='right')
        tk.Frame(self.root,bg=C['border'],height=1).pack(fill='x')

    def build_footer(self):
        footer=tk.Frame(self.root,bg=C['bg'],height=30); footer.pack(side='bottom',fill='x'); footer.pack_propagate(False)
        self.status=label(footer,'●  Listo',9,color='muted'); self.status.pack(side='left',padx=18)
        self.position=label(footer,'Ln 1, Col 1',9,color='muted'); self.position.pack(side='right',padx=18)
        label(footer,'UTF-8',9,color='subtle').pack(side='right',padx=12)
        label(footer,'CogniaCode',9,color='subtle').pack(side='right',padx=12)

    def build_sidebar(self):
        self.sidebar=tk.Frame(self.workspace,bg=C['sidebar'],width=205)
        self.sidebar.pack(side='left',fill='y'); self.sidebar.pack_propagate(False)
        top=tk.Frame(self.sidebar,bg=C['sidebar']); top.pack(fill='x',padx=15,pady=(18,12))
        label(top,'ARCHIVO',8,color='muted',bold=True).pack(side='left')
        Button(top,'+',self.new_file,self.motion,width=27,height=25,surface=C['sidebar']).pack(side='right')
        self.active_file=Button(self.sidebar,'‹›  sin_titulo.cog',lambda:self.editor.focus_set(),self.motion,height=36,surface=C['sidebar'],anchor='w')
        self.active_file.pack(fill='x',padx=8,pady=2); self.active_file.set_active(True)
        bottom=tk.Frame(self.sidebar,bg=C['sidebar']); bottom.pack(side='bottom',fill='x',padx=15,pady=15)
        tk.Frame(bottom,bg=C['border'],height=1).pack(fill='x',pady=(0,12))
        fontbar=tk.Frame(bottom,bg=C['sidebar']); fontbar.pack(fill='x')
        label(fontbar,'Texto',9,color='muted').pack(side='left')
        Button(fontbar,'A+',lambda:self.resize_font(1),self.motion,width=34,height=29,surface=C['sidebar']).pack(side='right')
        Button(fontbar,'A−',lambda:self.resize_font(-1),self.motion,width=34,height=29,surface=C['sidebar']).pack(side='right')
        self.motion_button=Button(bottom,'Animaciones: sí',self.toggle_motion,self.motion,height=29,surface=C['sidebar'],anchor='w')
        self.motion_button.pack(fill='x',pady=(5,0))

    def build_editor(self):
        self.filebar=tk.Frame(self.main,bg=C['panel'],height=42); self.filebar.pack(fill='x'); self.filebar.pack_propagate(False)
        self.file_label=label(self.filebar,'',10); self.file_label.pack(side='left',padx=18)
        self.dirty_label=label(self.filebar,'',9,color='yellow'); self.dirty_label.pack(side='left',padx=2)
        Button(self.filebar,'Equilibrar paneles',self.balance_panels,self.motion,width=145,height=29,surface=C['panel']).pack(side='right',padx=6)
        Button(self.filebar,'Panel lateral',self.toggle_sidebar,self.motion,width=101,height=29,surface=C['panel']).pack(side='right',padx=10)
        tk.Frame(self.main,bg=C['border'],height=1).pack(fill='x')
        self.split=tk.PanedWindow(self.main,orient='vertical',bg=C['border'],sashwidth=8,bd=0,showhandle=False,opaqueresize=True)
        self.split.pack(fill='both',expand=True)
        container=tk.Frame(self.split,bg=C['editor']); self.split.add(container,minsize=120,stretch='always')
        self.gutter=tk.Canvas(container,width=52,bg=C['editor'],highlightthickness=0); self.gutter.pack(side='left',fill='y')
        code=tk.Frame(container,bg=C['editor']); code.pack(side='left',fill='both',expand=True)
        scrollbar=Scrollbar(code,orient='vertical'); scrollbar.pack(side='right',fill='y')
        xscroll=Scrollbar(code,orient='horizontal'); xscroll.pack(side='bottom',fill='x')
        self.editor=tk.Text(code,undo=True,wrap='none',font=('Consolas',self.font_size),bg=C['editor'],fg=C['text'],insertbackground=C['accent'],insertwidth=2,selectbackground='#374851',selectforeground='#ffffff',bd=0,highlightthickness=0,padx=12,pady=17,spacing1=3,spacing3=3,tabs=('4c',),xscrollcommand=xscroll.set)
        self.editor.pack(fill='both',expand=True)
        scrollbar.configure(command=self.editor.yview); xscroll.configure(command=self.editor.xview)
        def scrolled(first,last): scrollbar.set(first,last); self.schedule_gutter()
        self.editor.configure(yscrollcommand=scrolled)
        self.editor.tag_configure('current',background='#1e2327'); self.editor.tag_configure('error',background=C['red_bg'])
        for tag,color in [('type','accent'),('string','yellow'),('number','violet'),('keyword','blue'),('comment','subtle'),('operator','muted')]: self.editor.tag_configure(tag,foreground=C[color])
        self.editor.bind('<<Modified>>',self.changed)
        self.editor.bind('<KeyRelease>',self.cursor_changed); self.editor.bind('<ButtonRelease-1>',self.cursor_changed)
        self.editor.bind('<Configure>',lambda e:self.schedule_gutter())
        self.editor.bind('<Tab>',self.indent); self.editor.bind('<Return>',self.newline)
        self.editor.bind('<Control-a>',self.select_all)
        self.editor.bind('<Control-plus>',lambda e:self.resize_font(1)); self.editor.bind('<Control-minus>',lambda e:self.resize_font(-1))
        self.build_results()

    def build_results(self):
        panel=tk.Frame(self.split,bg=C['panel'],height=360)
        panel.pack_propagate(False)
        self.split.add(panel,minsize=230,stretch='always')
        toolbar=tk.Frame(panel,bg=C['panel'])
        toolbar.pack(fill='x',padx=6,pady=5)
        names=('Análisis léxico','Análisis sintáctico','Análisis semántico','Código intermedio','Consola')
        for column,name in enumerate(names):
            toolbar.columnconfigure(column,weight=1,uniform='tabs')
            button=Button(toolbar,name,lambda n=name:self.show_tab(n),self.motion,width=1,height=48,surface=C['panel'])
            button.grid(row=0,column=column,sticky='ew',padx=2)
            button.bind('<Configure>',lambda event,b=button,n=name: b.set_text(n if tkfont.Font(font=('Segoe UI',10)).measure(n)+24 <= event.width else n.replace(' ','\n',1)),add='+')
            self.tab_buttons[name]=button
        controls=tk.Frame(panel,bg=C['panel'],height=35)
        controls.pack(fill='x'); controls.pack_propagate(False)
        self.summary=label(controls,'',9,color='muted')
        self.summary.pack(side='left',padx=18)
        Button(controls,'Copiar',self.copy_result,self.motion,width=65,height=30,surface=C['panel']).pack(side='right',padx=6)
        self.export_button=Button(controls,'Exportar código intermedio',self.export_ir,self.motion,width=215,height=30,surface=C['panel'])
        Button(controls,'A+',lambda:self.resize_font(1),self.motion,width=35,height=30,surface=C['panel']).pack(side='right',padx=(0,10))
        Button(controls,'A−',lambda:self.resize_font(-1),self.motion,width=35,height=30,surface=C['panel']).pack(side='right')
        self.indicator=tk.Frame(panel,bg=C['border'],height=2); self.indicator.pack(fill='x')
        self.pages=tk.Frame(panel,bg=C['editor']); self.pages.pack(fill='both',expand=True)
        self.page_widgets={}; self.stage_outputs={}
        for name in names:
            frame=tk.Frame(self.pages,bg=C['editor'])
            vertical=Scrollbar(frame,orient='vertical'); vertical.pack(side='right',fill='y')
            horizontal=Scrollbar(frame,orient='horizontal'); horizontal.pack(side='bottom',fill='x')
            output=tk.Text(frame,font=('Consolas',self.font_size),wrap='none',bg=C['editor'],fg=C['text'],selectbackground='#374851',bd=0,highlightthickness=0,padx=20,pady=15,spacing1=2,spacing3=2,state='disabled',yscrollcommand=vertical.set,xscrollcommand=horizontal.set)
            output.pack(fill='both',expand=True)
            vertical.configure(command=output.yview); horizontal.configure(command=output.xview)
            output.tag_configure('heading',foreground=C['accent'],font=('Consolas',self.font_size,'bold'))
            output.tag_configure('problem',foreground=C['red'])
            output.tag_configure('warning',foreground=C['yellow'])
            self.page_widgets[name]=frame; self.stage_outputs[name]=output
        self.output=self.stage_outputs['Consola']
        self.show_tab('Análisis semántico')

    def show_tab(self,name):
        previous=self.current_tab
        if previous in self.page_widgets and previous!=name:
            self.page_widgets[previous].pack_forget()
        self.current_tab=name
        for key,button in self.tab_buttons.items():
            button.set_active(key==name)
        self.page_widgets[name].pack(fill='both',expand=True)
        self.export_button.pack_forget()
        if name=='Código intermedio':
            self.export_button.pack(side='right',padx=8)

    def show_empty(self):
        self.set_stage('Análisis semántico','Escribe código y pulsa Compilar.')

    def changed(self,event=None):
        if not self.editor.edit_modified(): return
        self.editor.edit_modified(False)
        dirty=self.editor.get('1.0','end-1c')!=self.saved_source
        self.dirty_label.configure(text='●' if dirty else '')
        self.root.title(f'{self.filename}{" *" if dirty else ""} — CogniaCode')
        self.editor.tag_remove('error','1.0','end'); self.report=None
        self.status.configure(text='●  Modificado' if dirty else '●  Listo',fg=C['muted'])
        self.summary.configure(text='Sin analizar',fg=C['subtle'])
        self.show_empty()
        self.set_console(''); self.clear_stages()
        if self.highlight_job: self.root.after_cancel(self.highlight_job)
        self.highlight_job=self.root.after(100,self.highlight); self.cursor_changed()

    def highlight(self):
        self.highlight_job=None
        for tag in ('type','string','number','keyword','comment','operator'): self.editor.tag_remove(tag,'1.0','end')
        for number,line in enumerate(self.editor.get('1.0','end-1c').splitlines(),1):
            for match in PATTERN.finditer(line):
                kind=match.lastgroup; value=match.group(); tag=None
                if kind in ('TEXT','CHAR'): tag='string'
                elif kind in ('INTEGER','DECIMAL'): tag='number'
                elif kind=='COMMENT': tag='comment'
                elif kind=='OP': tag='operator'
                elif kind=='ID':
                    if normalize(value) in TYPES: tag='type'
                    elif value in ('verdadero','falso','Y','O','NO','mostrar'): tag='keyword'
                if tag: self.editor.tag_add(tag,f'{number}.{match.start()}',f'{number}.{match.end()}')
        self.schedule_gutter()
    def cursor_changed(self,event=None):
        line,column=self.editor.index('insert').split('.')
        self.position.configure(text=f'Ln {line}, Col {int(column)+1}')
        self.editor.tag_remove('current','1.0','end'); self.editor.tag_add('current',f'{line}.0',f'{line}.end+1c')
        self.editor.tag_lower('current'); self.schedule_gutter()
    def schedule_gutter(self):
        if self.gutter_job is None:
            self.gutter_job=self.root.after_idle(self.redraw_gutter)

    def redraw_gutter(self):
        self.gutter_job=None
        if not hasattr(self,'editor'): return
        self.gutter.delete('all'); index=self.editor.index('@0,0'); active=self.editor.index('insert').split('.')[0]
        font=tkfont.Font(font=self.editor.cget('font'))
        ascent=font.metrics('ascent')
        width=max(52,font.measure(str(int(self.editor.index('end-1c').split('.')[0])))+24)
        if self.gutter.winfo_width()!=width: self.gutter.configure(width=width)
        for _ in range(200):
            info=self.editor.dlineinfo(index)
            if info is None: break
            number=index.split('.')[0]
            self.gutter.create_text(width-12,info[1]+info[4]-ascent,text=number,anchor='ne',font=self.editor.cget('font'),fill=C['accent'] if number==active else C['subtle'])
            following=self.editor.index(f'{index}+1line')
            if following==index: break
            index=following
    def select_all(self,event=None): self.editor.tag_add('sel','1.0','end-1c'); return 'break'
    def indent(self,event=None): self.editor.insert('insert','    '); return 'break'
    def newline(self,event=None):
        before=self.editor.get('insert linestart','insert')
        self.editor.insert('insert','\n'+before[:len(before)-len(before.lstrip())]); return 'break'
    def resize_font(self,delta):
        self.font_size=max(10,min(20,self.font_size+delta)); self.editor.configure(font=('Consolas',self.font_size))
        for output in self.stage_outputs.values():
            output.configure(font=('Consolas',self.font_size))
            output.tag_configure('heading',font=('Consolas',self.font_size,'bold'))
        self.schedule_gutter(); return 'break'
    def toggle_sidebar(self):
        self.sidebar_visible=not self.sidebar_visible
        if self.sidebar_visible:
            self.sidebar.pack(side='left',fill='y',before=self.main)
        else:
            self.sidebar.pack_forget()
        return 'break'

    def balance_panels(self):
        self.split.sash_place(0,0,int(self.split.winfo_height()*0.5))
        self.schedule_gutter()

    def copy_result(self):
        text=self.stage_outputs[self.current_tab].get('1.0','end-1c')
        self.root.clipboard_clear(); self.root.clipboard_append(text)
        self.status.configure(text='●  Resultado copiado',fg=C['accent'])

    def toggle_motion(self):
        self.motion.enabled=not self.motion.enabled
        if not self.motion.enabled:
            self.motion.close()
            self.sidebar.configure(width=205)
            if not self.sidebar_visible: self.sidebar.pack_forget()
            self.indicator.configure(bg=C['border'])
        self.motion_button.set_text('Animaciones: '+('sí' if self.motion.enabled else 'no'))
    def set_console(self,text):
        self.set_stage('Consola',text)

    def set_stage(self,name,text):
        widget=self.stage_outputs[name]
        widget.configure(state='normal'); widget.delete('1.0','end')
        widget.insert('1.0',text)
        for start,end,tag in getattr(text,'spans',[]):
            widget.tag_add(tag,f'1.0+{start}c',f'1.0+{end}c')
        widget.configure(state='disabled'); widget.yview_moveto(0); widget.xview_moveto(0)

    def clear_stages(self):
        for name in self.stage_outputs:
            self.set_stage(name,'Escribe código y pulsa Compilar.')

    def render_stages(self,report):
        self.set_stage('Análisis léxico',format_tokens(report))
        self.set_stage('Análisis sintáctico',format_ast(report))
        self.set_stage('Código intermedio',format_intermediate(report))

    def export_ir(self):
        if not self.report or not self.report['ok']:
            messagebox.showinfo('Código intermedio','Compila un programa sin errores antes de exportar.',parent=self.root)
            return
        path=filedialog.asksaveasfilename(parent=self.root,initialfile=Path(self.filename).stem+'.cogir',defaultextension='.cogir',filetypes=[('Código intermedio','*.cogir')])
        if not path: return
        try:
            data=dict(format='CogniaCode IR',version=1,source=self.editor.get('1.0','end-1c'),quadruples=self.report['intermediate'])
            Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
            self.status.configure(text='●  Código intermedio exportado',fg=C['accent'])
        except OSError as error:
            messagebox.showerror('No se pudo exportar',str(error),parent=self.root)

    def run(self):
        if self.highlight_job: self.root.after_cancel(self.highlight_job); self.highlight_job=None
        self.highlight(); start=perf_counter()
        report=analyze(self.editor.get('1.0','end-1c')); report['execution']=execute(report); elapsed=(perf_counter()-start)*1000
        self.report=report; self.editor.edit_modified(False); self.editor.tag_remove('error','1.0','end')
        problems=[r for r in report['results'] if not r['ok']]
        for r in problems: self.editor.tag_add('error',f"{r['line']}.0",f"{r['line']}.end")
        self.status.configure(text='●  '+('Sin errores' if report['ok'] else f'{len(problems)} '+('problema' if len(problems)==1 else 'problemas') if problems else 'Sin instrucciones'),fg=C['accent'] if report['ok'] else C['red'])
        count=len(report['symbols'])
        self.summary.configure(text=f'{count} '+('símbolo' if count==1 else 'símbolos')+f'  ·  {elapsed:.1f} ms',fg=C['muted'])
        self.set_console(format_console(report)); self.render_stages(report)
        self.render_diagnostics(report)
        if report['ok']:
            self.show_tab('Consola')
            if not report['execution']['ok']:
                error=report['execution']['error']
                self.editor.tag_add('error',f"{error['line']}.0",f"{error['line']}.end")
                self.status.configure(text='●  Error de ejecución',fg=C['red'])
        color=C['accent'] if report['ok'] and report['execution']['ok'] else C['red']
        self.indicator.configure(bg=color)
        return report
    def render_diagnostics(self,report):
        self.set_stage('Análisis semántico',format_semantic(report))
        widget=self.stage_outputs['Análisis semántico']
        for result in report['results']:
            if not result['ok']:
                index=widget.search(f"Línea {result['line']} ·",'1.0',stopindex='end')
                if index:
                    tag=f"diagnostic_{result['line']}"
                    widget.tag_add(tag,index,f'{index} lineend')
                    widget.tag_configure(tag,underline=True,foreground=C['red'])
                    widget.tag_bind(tag,'<Button-1>',lambda event,r=result:self.goto(r['line'],r['column']))
                    widget.tag_bind(tag,'<Double-Button-1>',lambda event,r=result:self.show_hint(r))

    def show_hint(self,result):
        popup=tk.Toplevel(self.root); popup.title('Ayuda'); popup.configure(bg=C['panel']); popup.transient(self.root); popup.resizable(False,False)
        width=min(530,self.root.winfo_width()-70)
        popup.geometry(f'{width}x280+{self.root.winfo_rootx()+60}+{self.root.winfo_rooty()+100}')
        content=tk.Frame(popup,bg=C['panel']); content.pack(fill='both',expand=True,padx=24,pady=20)
        label(content,f"Línea {result['line']} · {result['phase']}",9,color='muted').pack(anchor='w')
        label(content,result['message'],12,bold=True,wraplength=width-55,justify='left').pack(anchor='w',pady=(10,14))
        label(content,result['hint'],10,color='muted',wraplength=width-55,justify='left').pack(anchor='w')
        Button(content,'Entendido',popup.destroy,self.motion,primary=True,width=110,surface=C['panel']).pack(side='bottom',anchor='e',pady=(12,0))
        popup.bind('<Escape>',lambda e:popup.destroy())
        dark_title(popup)
    def goto(self,line,column=1):
        self.editor.mark_set('insert',f'{line}.{column-1}'); self.editor.see('insert'); self.editor.focus_set(); self.cursor_changed()
    def confirm_replace(self):
        if self.editor.get('1.0','end-1c')==self.saved_source: return True
        choice=messagebox.askyesnocancel('Cambios sin guardar',f'¿Guardar los cambios de {self.filename}?',parent=self.root)
        return self.save_file() if choice else choice is False
    def set_source(self,source,filename,path=None):
        if self.highlight_job: self.root.after_cancel(self.highlight_job); self.highlight_job=None
        self.path=path; self.filename=filename; self.saved_source=source
        self.editor.delete('1.0','end'); self.editor.insert('1.0',source); self.editor.edit_reset(); self.editor.edit_modified(False)
        self.file_label.configure(text='‹›   '+filename)
        self.active_file.set_text('‹›  '+filename)
        self.dirty_label.configure(text=''); self.root.title(filename+' — CogniaCode')
        self.status.configure(text='●  Listo',fg=C['muted']); self.summary.configure(text=''); self.report=None
        self.editor.tag_remove('error','1.0','end')
        self.set_console(''); self.clear_stages(); self.show_empty(); self.highlight(); self.goto(1)
    def new_file(self):
        if self.confirm_replace():
            self.set_source('','sin_titulo.cog')
        return 'break'
    def open_file(self):
        if not self.confirm_replace(): return 'break'
        path=filedialog.askopenfilename(parent=self.root,filetypes=[('CogniaCode','*.cog'),('Texto','*.txt')])
        if path:
            try:
                file=Path(path); self.set_source(file.read_text(encoding='utf-8-sig'),file.name,file)
            except (OSError,UnicodeError) as error: messagebox.showerror('No se pudo abrir',str(error),parent=self.root)
        return 'break'
    def save_file(self):
        path=self.path or filedialog.asksaveasfilename(parent=self.root,initialfile=self.filename,defaultextension='.cog',filetypes=[('CogniaCode','*.cog')])
        if not path: return False
        try:
            source=self.editor.get('1.0','end-1c'); Path(path).write_text(source,encoding='utf-8')
            self.path=Path(path); self.filename=self.path.name; self.saved_source=source
            self.dirty_label.configure(text=''); self.file_label.configure(text='‹›   '+self.filename)
            self.active_file.set_text('‹›  '+self.filename)
            self.root.title(self.filename+' — CogniaCode'); self.status.configure(text='●  Guardado',fg=C['accent']); return True
        except OSError as error: messagebox.showerror('No se pudo guardar',str(error),parent=self.root); return False
    def close(self):
        if not self.confirm_replace(): return
        self.motion.close()
        if self.gutter_job: self.root.after_cancel(self.gutter_job)
        if self.highlight_job: self.root.after_cancel(self.highlight_job)
        self.root.destroy()

def launch():
    root=tk.Tk(); App(root); root.mainloop()

if __name__=='__main__': launch()
