"""Componentes visuales y transiciones no bloqueantes para Tkinter."""
import tkinter as tk

COLORS = {'bg':'#151719','sidebar':'#191c1f','panel':'#1c2024','editor':'#181b1e',
          'raised':'#24292e','hover':'#2c3339','border':'#30373d','text':'#e4e8eb',
          'muted':'#9aa5ae','subtle':'#707d87','accent':'#a4e5c0','accent_dark':'#203c31',
          'red':'#f1a0a5','red_bg':'#38272d','blue':'#9fbce8','yellow':'#e6c88d','violet':'#c1b1e4'}

def blend(a,b,t):
    return '#'+''.join(f'{round(int(a[i:i+2],16)*(1-t)+int(b[i:i+2],16)*t):02x}' for i in (1,3,5))

class Motion:
    def __init__(self,root): self.root,self.enabled,self.jobs=root,True,{}
    def tween(self,key,callback,duration=140):
        old=self.jobs.pop(key,None)
        if old: self.root.after_cancel(old)
        if not self.enabled: callback(1); return
        import time
        start=time.perf_counter()
        def tick():
            t=min(1,(time.perf_counter()-start)*1000/duration)
            callback(1-(1-t)**3)
            if t<1: self.jobs[key]=self.root.after(16,tick)
            else: self.jobs.pop(key,None)
        tick()
    def close(self):
        for job in self.jobs.values(): self.root.after_cancel(job)
        self.jobs.clear()

class Button(tk.Canvas):
    def __init__(self,parent,text,command,motion,width=110,height=34,primary=False,surface=None,anchor='center'):
        self.surface=surface or COLORS['panel']
        super().__init__(parent,width=width,height=height,bg=self.surface,highlightthickness=0,bd=0,takefocus=True,cursor='hand2')
        self.text,self.command,self.motion=text,command,motion
        self.primary,self.anchor,self.active,self.focused=primary,anchor,False,False
        self.fill=COLORS['accent'] if primary else self.surface
        self.bind('<Configure>',lambda e:self.draw())
        self.bind('<Enter>',lambda e:self.transition(True))
        self.bind('<Leave>',lambda e:self.transition(False))
        self.bind('<ButtonRelease-1>',lambda e:self.invoke())
        self.bind('<Return>',lambda e:self.invoke()); self.bind('<space>',lambda e:self.invoke())
        self.bind('<FocusIn>',lambda e:self.focus_change(True)); self.bind('<FocusOut>',lambda e:self.focus_change(False))
    def invoke(self): self.command(); return 'break'
    def focus_change(self,value): self.focused=value; self.draw()
    def set_active(self,value): self.active=value; self.transition(False)
    def set_text(self,text): self.text=text; self.draw()
    def transition(self,hover):
        start=self.fill
        target=('#bcefd1' if hover else COLORS['accent']) if self.primary else (COLORS['hover'] if hover else COLORS['raised'] if self.active else self.surface)
        self.motion.tween(str(self),lambda t:self.paint(blend(start,target,t)))
    def paint(self,color):
        if self.winfo_exists(): self.fill=color; self.draw()
    def draw(self):
        self.delete('all'); w,h=self.winfo_width(),self.winfo_height(); r=7
        self.create_polygon(1+r,1,w-r-1,1,w-1,1,w-1,r+1,w-1,h-r-1,w-1,h-1,w-r-1,h-1,1+r,h-1,1,h-1,1,h-r-1,1,1+r,1,1,smooth=True,fill=self.fill,outline=COLORS['accent'] if self.focused else self.fill)
        if self.active and not self.primary: self.create_line(2,10,2,h-10,fill=COLORS['accent'],width=2)
        self.create_text(13 if self.anchor=='w' else w/2,h/2,text=self.text,anchor=self.anchor,fill='#17281f' if self.primary else COLORS['text'] if self.active else COLORS['muted'],font=('Segoe UI',10,'bold' if self.primary else 'normal'))

def label(parent,text,size=10,color='text',bold=False,**kwargs):
    return tk.Label(parent,text=text,font=('Segoe UI',size,'bold' if bold else 'normal'),bg=parent.cget('bg'),fg=COLORS.get(color,color),**kwargs)

class Scrollbar(tk.Canvas):
    """Barra discreta sin flechas; admite arrastre, clic en pista y rueda."""
    def __init__(self,parent,orient='vertical',command=None):
        self.orient,self.command=orient,command
        self.low,self.high=0.0,1.0; self.drag_start=None; self.over=False
        super().__init__(parent,width=9 if orient=='vertical' else 0,height=9 if orient=='horizontal' else 0,bg=COLORS['editor'],highlightthickness=0,bd=0)
        self.bind('<Configure>',lambda e:self.draw())
        self.bind('<Button-1>',self.press); self.bind('<B1-Motion>',self.drag)
        self.bind('<ButtonRelease-1>',lambda e:setattr(self,'drag_start',None))
        self.bind('<Enter>',lambda e:self.hover(True)); self.bind('<Leave>',lambda e:self.hover(False))
    def configure(self,cnf=None,**kwargs):
        if 'command' in kwargs: self.command=kwargs.pop('command')
        return super().configure(cnf,**kwargs)
    config=configure
    def set(self,low,high): self.low,self.high=float(low),float(high); self.draw()
    def hover(self,value): self.over=value; self.draw()
    def extent(self): return self.winfo_height() if self.orient=='vertical' else self.winfo_width()
    def draw(self):
        self.delete('all')
        if self.low<=0 and self.high>=1: return
        length=self.extent(); start=length*self.low; end=max(start+18,length*self.high)
        fill=COLORS['subtle'] if self.over else COLORS['border']
        if self.orient=='vertical': self.create_rectangle(2,start,7,min(end,length),fill=fill,outline='')
        else: self.create_rectangle(start,2,min(end,length),7,fill=fill,outline='')
    def press(self,event):
        position=event.y if self.orient=='vertical' else event.x
        fraction=position/max(1,self.extent())
        if not self.low<=fraction<=self.high and self.command:
            self.command('moveto',max(0,min(1,fraction-(self.high-self.low)/2)))
        self.drag_start=(position,self.low)
    def drag(self,event):
        if self.drag_start and self.command:
            position=event.y if self.orient=='vertical' else event.x
            self.command('moveto',max(0,min(1,self.drag_start[1]+(position-self.drag_start[0])/max(1,self.extent()))))

class ScrollPanel(tk.Frame):
    def __init__(self,parent,bg):
        super().__init__(parent,bg=bg)
        self.canvas=tk.Canvas(self,bg=bg,highlightthickness=0,bd=0)
        self.bar=Scrollbar(self,orient='vertical',command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.bar.pack(side='right',fill='y'); self.canvas.pack(fill='both',expand=True)
        self.content=tk.Frame(self.canvas,bg=bg)
        self.item=self.canvas.create_window(0,0,anchor='nw',window=self.content)
        self.content.bind('<Configure>',lambda e:self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>',lambda e:self.canvas.itemconfigure(self.item,width=e.width))
        self.canvas.bind('<MouseWheel>',self.wheel)
    def wheel(self,event): self.canvas.yview_scroll(-int(event.delta/120),'units'); return 'break'
    def bind_wheel(self,widget):
        widget.bind('<MouseWheel>',self.wheel)
        for child in widget.winfo_children(): self.bind_wheel(child)
    def clear(self):
        for child in self.content.winfo_children(): child.destroy()
        self.canvas.yview_moveto(0)
