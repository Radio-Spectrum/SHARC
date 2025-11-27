from tkinter import ttk

def add_row_three(parent, r, items):
    """
    items: lista de tuplas (label_text, widget) com até 3 pares.
    Cada par ocupa ~1/3 da linha: [label][widget] * 3
    """
    col = 0
    for (txt, w) in items:
        lbl = ttk.Label(parent, text=txt)
        lbl.grid(row=r, column=col, sticky="e", padx=(0,6), pady=2)
        w.grid(row=r, column=col+1, sticky="we", pady=2)
        parent.grid_columnconfigure(col+1, weight=1)
        col += 2
    while col < 6:
        parent.grid_columnconfigure(col, weight=1)
        col += 1

def pair_entries(parent, var1, var2, w=6):
    f = ttk.Frame(parent)
    e1 = ttk.Entry(f, textvariable=var1, width=w); e1.pack(side="left")
    ttk.Label(f, text=" / ").pack(side="left")
    e2 = ttk.Entry(f, textvariable=var2, width=w); e2.pack(side="left")
    return f
