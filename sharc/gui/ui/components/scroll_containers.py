import tkinter as tk
import ttkbootstrap as ttk

class ScrollableContainer(ttk.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.v_scroll = ttk.Scrollbar(self, orient="vertical")
        self.v_scroll.pack(side="right", fill="y")
        
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.configure(yscrollcommand=self.v_scroll.set)
        self.v_scroll.configure(command=self.canvas.yview)
        
        self.container = ttk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.container, anchor="nw")
        
        self.container.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width))
        self.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_mousewheel(self, event):
        try:
            widget = self.winfo_containing(*self.winfo_pointerxy())
            cur = widget
            while cur:
                if cur == self:
                    if event.delta > 0: self.canvas.yview_scroll(-1, "units")
                    elif event.delta < 0: self.canvas.yview_scroll(1, "units")
                    break
                cur = cur.master
        except: pass
