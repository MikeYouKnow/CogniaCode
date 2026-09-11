"""Editor de CogniaCode; comparte el analizador con la consola."""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from time import perf_counter
from analyzer import analyze, format_report, RULES, PATTERN, TYPES, normalize
from ui_components import COLORS as C, Motion, Button, ScrollPanel, Scrollbar, label, blend


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
        self.report=None; self.highlight_job=None
        self.font_size=12; self.tab_buttons={}
        self.current_tab='Diagnósticos'; self.sidebar_visible=True
        root.title('CogniaCode')
        root.geometry(f'{min(1120,root.winfo_screenwidth()-70)}x{min(620,root.winfo_screenheight()-90)}')
        root.minsize(840,540); root.configure(bg=C['bg'])
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
        Button(header,'Analizar   F5',self.run,self.motion,width=124,primary=True,surface=C['bg']).pack(side='right',padx=(9,20))
        Button(header,'Guardar',self.save_file,self.motion,width=83,surface=C['bg']).pack(side='right',padx=3)
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
        label(top,'EXPLORADOR',8,color='muted',bold=True).pack(side='left')
        Button(top,'+',self.new_file,self.motion,width=27,height=25,surface=C['sidebar']).pack(side='right')
        self.active_file=Button(self.sidebar,'‹›  sin_titulo.cog',lambda:self.editor.focus_set(),self.motion,height=36,surface=C['sidebar'],anchor='w')
        self.active_file.pack(fill='x',padx=8,pady=2); self.active_file.set_active(True)
        bottom=tk.Frame(self.sidebar,bg=C['sidebar']); bottom.pack(side='bottom',fill='x',padx=15,pady=15)
        tk.Frame(bottom,bg=C['border'],height=1).pack(fill='x',pady=(0,12))
        fontbar=tk.Frame(bottom,bg=C['sidebar']); fontbar.pack(fill='x')
        label(fontbar,'Editor',9,color='muted').pack(side='left')
        Button(fontbar,'A+',lambda:self.resize_font(1),self.motion,width=34,height=29,surface=C['sidebar']).pack(side='right')
        Button(fontbar,'A−',lambda:self.resize_font(-1),self.motion,width=34,height=29,surface=C['sidebar']).pack(side='right')
        self.motion_button=Button(bottom,'Animaciones: sí',self.toggle_motion,self.motion,height=29,surface=C['sidebar'],anchor='w')
        self.motion_button.pack(fill='x',pady=(5,0))

    def build_editor(self):
        self.filebar=tk.Frame(self.main,bg=C['panel'],height=42); self.filebar.pack(fill='x'); self.filebar.pack_propagate(False)
        self.file_label=label(self.filebar,'',10); self.file_label.pack(side='left',padx=18)
        self.dirty_label=label(self.filebar,'',9,color='yellow'); self.dirty_label.pack(side='left',padx=2)
        Button(self.filebar,'Panel lateral',self.toggle_sidebar,self.motion,width=101,height=29,surface=C['panel']).pack(side='right',padx=10)
        tk.Frame(self.main,bg=C['border'],height=1).pack(fill='x')
        self.split=tk.PanedWindow(self.main,orient='vertical',bg=C['border'],sashwidth=4,bd=0,showhandle=False,opaqueresize=True)
        self.split.pack(fill='both',expand=True)
        container=tk.Frame(self.split,bg=C['editor']); self.split.add(container,minsize=120,stretch='always')
        self.gutter=tk.Canvas(container,width=52,bg=C['editor'],highlightthickness=0); self.gutter.pack(side='left',fill='y')
        code=tk.Frame(container,bg=C['editor']); code.pack(side='left',fill='both',expand=True)
        scrollbar=Scrollbar(code,orient='vertical'); scrollbar.pack(side='right',fill='y')
        xscroll=Scrollbar(code,orient='horizontal'); xscroll.pack(side='bottom',fill='x')
        self.editor=tk.Text(code,undo=True,wrap='none',font=('Consolas',self.font_size),bg=C['editor'],fg=C['text'],insertbackground=C['accent'],insertwidth=2,selectbackground='#374851',selectforeground='#ffffff',bd=0,highlightthickness=0,padx=12,pady=17,spacing1=3,spacing3=3,tabs=('4c',),xscrollcommand=xscroll.set)
        self.editor.pack(fill='both',expand=True)
        scrollbar.configure(command=self.editor.yview); xscroll.configure(command=self.editor.xview)
        def scrolled(first,last): scrollbar.set(first,last); self.redraw_gutter()
        self.editor.configure(yscrollcommand=scrolled)
        self.editor.tag_configure('current',background='#1e2327'); self.editor.tag_configure('error',background=C['red_bg'])
        for tag,color in [('type','accent'),('string','yellow'),('number','violet'),('keyword','blue'),('comment','subtle'),('operator','muted')]: self.editor.tag_configure(tag,foreground=C[color])
        self.editor.bind('<<Modified>>',self.changed)
        self.editor.bind('<KeyRelease>',self.cursor_changed); self.editor.bind('<ButtonRelease-1>',self.cursor_changed)
        self.editor.bind('<Configure>',lambda e:self.redraw_gutter())
        self.editor.bind('<Tab>',self.indent); self.editor.bind('<Return>',self.newline)
        self.editor.bind('<Control-a>',self.select_all)
        self.editor.bind('<Control-plus>',lambda e:self.resize_font(1)); self.editor.bind('<Control-minus>',lambda e:self.resize_font(-1))
        self.build_results()

    def build_results(self):
        panel=tk.Frame(self.split,bg=C['panel'],height=215); panel.pack_propagate(False)
        self.split.add(panel,minsize=150,stretch='never')
        toolbar=tk.Frame(panel,bg=C['panel'],height=43); toolbar.pack(fill='x'); toolbar.pack_propagate(False)
        for name,width in [('Diagnósticos',118),('Símbolos',90),('Reglas',74),('Consola',83)]:
            button=Button(toolbar,name,lambda n=name:self.show_tab(n),self.motion,width=width,height=33,surface=C['panel'])
            button.pack(side='left',padx=(8 if name=='Diagnósticos' else 0,0),pady=5); self.tab_buttons[name]=button
        self.summary=label(toolbar,'',9,color='muted'); self.summary.pack(side='right',padx=15)
        self.indicator=tk.Frame(panel,bg=C['border'],height=2); self.indicator.pack(fill='x')
        self.pages=tk.Frame(panel,bg=C['editor']); self.pages.pack(fill='both',expand=True)
        self.diagnostics=ScrollPanel(self.pages,C['editor'])
        self.symbol_frame=tk.Frame(self.pages,bg=C['editor'])
        scroll=Scrollbar(self.symbol_frame,orient='vertical'); scroll.pack(side='right',fill='y')
        self.symbols=ttk.Treeview(self.symbol_frame,columns=('name','type','value','line'),show='headings',yscrollcommand=scroll.set); scroll.configure(command=self.symbols.yview)
        for key,title,width in [('name','IDENTIFICADOR',180),('type','TIPO',100),('value','INICIALIZADO',100),('line','LÍNEA',70)]:
            self.symbols.heading(key,text=title,anchor='w'); self.symbols.column(key,width=width,minwidth=65,anchor='w')
        self.symbols.pack(fill='both',expand=True,padx=12,pady=9); self.symbols.bind('<Double-1>',self.symbol_selected)
        self.rule_panel=ScrollPanel(self.pages,C['editor'])
        for rule,description in RULES.items():
            row=tk.Frame(self.rule_panel.content,bg=C['editor']); row.pack(fill='x',padx=18,pady=7)
            label(row,rule,9,color='accent',bold=True,width=5,anchor='w').pack(side='left',anchor='n')
            content=label(row,description,10,color='muted',justify='left',anchor='w',wraplength=600); content.pack(side='left',fill='x',expand=True)
            row.bind('<Configure>',lambda e,l=content:l.configure(wraplength=max(150,e.width-70))); self.rule_panel.bind_wheel(row)
        self.console_frame=tk.Frame(self.pages,bg=C['editor'])
        scroll=Scrollbar(self.console_frame,orient='vertical'); scroll.pack(side='right',fill='y')
        self.output=tk.Text(self.console_frame,font=('Consolas',10),wrap='word',bg=C['editor'],fg=C['muted'],bd=0,highlightthickness=0,padx=18,pady=13,state='disabled',yscrollcommand=scroll.set)
        scroll.configure(command=self.output.yview); self.output.pack(fill='both',expand=True)
        self.page_widgets={'Diagnósticos':self.diagnostics,'Símbolos':self.symbol_frame,'Reglas':self.rule_panel,'Consola':self.console_frame}
        self.show_tab('Diagnósticos')

    def show_tab(self,name):
        self.current_tab=name
        for key,widget in self.page_widgets.items(): widget.pack_forget(); self.tab_buttons[key].set_active(key==name)
        self.page_widgets[name].pack(fill='both',expand=True)
    def show_empty(self):
        self.diagnostics.clear()
        row=tk.Frame(self.diagnostics.content,bg=C['editor']); row.pack(fill='x',padx=24,pady=25)
        label(row,'Listo para analizar',13,bold=True).pack(anchor='w')
        label(row,'F5 para comprobar tu código.',10,color='muted').pack(anchor='w',pady=(7,0))
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
        for item in self.symbols.get_children(): self.symbols.delete(item)
        self.set_console('')
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
                    elif value in ('verdadero','falso','Y','O','NO'): tag='keyword'
                if tag: self.editor.tag_add(tag,f'{number}.{match.start()}',f'{number}.{match.end()}')
        self.redraw_gutter()
    def cursor_changed(self,event=None):
        line,column=self.editor.index('insert').split('.')
        self.position.configure(text=f'Ln {line}, Col {int(column)+1}')
        self.editor.tag_remove('current','1.0','end'); self.editor.tag_add('current',f'{line}.0',f'{line}.end+1c')
        self.editor.tag_lower('current'); self.redraw_gutter()
    def redraw_gutter(self):
        if not hasattr(self,'editor'): return
        self.gutter.delete('all'); index=self.editor.index('@0,0'); active=self.editor.index('insert').split('.')[0]
        for _ in range(200):
            info=self.editor.dlineinfo(index)
            if info is None: break
            number=index.split('.')[0]
            self.gutter.create_text(36,info[1]+info[3]/2,text=number,anchor='e',font=('Consolas',self.font_size-1),fill=C['accent'] if number==active else C['subtle'])
            following=self.editor.index(f'{index}+1line')
            if following==index: break
            index=following
    def select_all(self,event=None): self.editor.tag_add('sel','1.0','end-1c'); return 'break'
    def indent(self,event=None): self.editor.insert('insert','    '); return 'break'
    def newline(self,event=None):
        before=self.editor.get('insert linestart','insert')
        self.editor.insert('insert','\n'+before[:len(before)-len(before.lstrip())]); return 'break'
    def resize_font(self,delta):
        self.font_size=max(10,min(20,self.font_size+delta)); self.editor.configure(font=('Consolas',self.font_size)); self.redraw_gutter(); return 'break'
    def toggle_sidebar(self):
        self.sidebar_visible=not self.sidebar_visible
        start=self.sidebar.winfo_width() if self.sidebar.winfo_manager() else 1
        target=205 if self.sidebar_visible else 1
        if self.sidebar_visible: self.sidebar.pack(side='left',fill='y',before=self.main)
        def animate(t):
            self.sidebar.configure(width=round(start+(target-start)*t))
            if t==1 and not self.sidebar_visible: self.sidebar.pack_forget()
        self.motion.tween('sidebar',animate,200)
        return 'break'
    def toggle_motion(self):
        self.motion.enabled=not self.motion.enabled
        if not self.motion.enabled:
            self.motion.close()
            self.sidebar.configure(width=205)
            if not self.sidebar_visible: self.sidebar.pack_forget()
            self.indicator.configure(bg=C['border'])
        self.motion_button.set_text('Animaciones: '+('sí' if self.motion.enabled else 'no'))
    def set_console(self,text):
        self.output.configure(state='normal'); self.output.delete('1.0','end'); self.output.insert('1.0',text); self.output.configure(state='disabled')

    def run(self):
        if self.highlight_job: self.root.after_cancel(self.highlight_job); self.highlight_job=None
        self.highlight(); start=perf_counter()
        report=analyze(self.editor.get('1.0','end-1c')); elapsed=(perf_counter()-start)*1000
        self.report=report; self.editor.edit_modified(False); self.editor.tag_remove('error','1.0','end')
        problems=[r for r in report['results'] if not r['ok']]
        for r in problems: self.editor.tag_add('error',f"{r['line']}.0",f"{r['line']}.end")
        self.status.configure(text='●  '+('Sin errores' if report['ok'] else f'{len(problems)} '+('problema' if len(problems)==1 else 'problemas') if problems else 'Sin instrucciones'),fg=C['accent'] if report['ok'] else C['red'])
        count=len(report['symbols'])
        self.summary.configure(text=f'{count} '+('símbolo' if count==1 else 'símbolos')+f'  ·  {elapsed:.1f} ms',fg=C['muted'])
        self.set_console(format_report(report))
        for item in self.symbols.get_children(): self.symbols.delete(item)
        for name,s in report['symbols'].items(): self.symbols.insert('','end',values=(name,s['type'],'Sí' if s['initialized'] else 'No',s['line']))
        self.render_diagnostics(report); self.show_tab('Diagnósticos')
        color=C['accent'] if report['ok'] else C['red']
        self.motion.tween('result',lambda t:self.indicator.configure(bg=blend(color,C['border'],t)),480)
        return report
    def render_diagnostics(self,report):
        self.diagnostics.clear()
        if not report['results']: self.show_empty(); return
        for result in report['results']:
            row=tk.Frame(self.diagnostics.content,bg=C['editor']); row.pack(fill='x',padx=18,pady=(12,0))
            header=tk.Frame(row,bg=C['editor']); header.pack(fill='x'); ok=result['ok']
            title=('Línea '+str(result['line'])+'  ·  '+result['type']) if ok else result['message']
            label(header,'✓' if ok else '!',11,color='accent' if ok else 'red',bold=True,width=2).pack(side='left',anchor='n')
            heading=label(header,title,10,color='text' if ok else 'red',justify='left',anchor='w',wraplength=650); heading.pack(side='left',fill='x',expand=True)
            header.bind('<Configure>',lambda e,l=heading:l.configure(wraplength=max(150,e.width-45)))
            if ok:
                for warning in result['warnings']: label(row,warning,9,color='yellow',anchor='w',justify='left',wraplength=650).pack(fill='x',padx=(26,0),pady=(4,0))
            else:
                details=tk.Frame(row,bg=C['editor']); details.pack(fill='x',padx=(26,0),pady=(6,0))
                Button(details,f"Ir a línea {result['line']}",lambda r=result:self.goto(r['line'],r['column']),self.motion,width=98,height=27,surface=C['editor']).pack(side='left')
                Button(details,'Ver ayuda',lambda r=result:self.show_hint(r),self.motion,width=88,height=27,surface=C['editor']).pack(side='left',padx=(6,0))
                label(details,result['code'],8,color='subtle').pack(side='right')
            tk.Frame(row,bg=C['border'],height=1).pack(fill='x',pady=(11,0)); self.diagnostics.bind_wheel(row)
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
    def symbol_selected(self,event=None):
        selected=self.symbols.selection()
        if selected: self.goto(self.symbols.item(selected[0],'values')[3])
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
        for item in self.symbols.get_children(): self.symbols.delete(item)
        self.set_console(''); self.show_empty(); self.highlight(); self.goto(1)
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
        if self.highlight_job: self.root.after_cancel(self.highlight_job)
        self.root.destroy()

def launch():
    root=tk.Tk(); App(root); root.mainloop()

if __name__=='__main__': launch()
