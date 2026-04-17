import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import tkinter.font as tkfont
import queue
import os
import itertools
import ast
import yaml
import subprocess
import platform

# Try to use modern visual style
try:
    import ttkbootstrap as tb
    from ttkbootstrap.constants import *
    from ttkbootstrap.widgets import Meter, ToastNotification, ToolTip
    # Replace ttkbootstrap ScrolledFrame since it only supports vertical scrolling
    HAS_BOOTSTRAP = True
except ImportError:
    HAS_BOOTSTRAP = False
    tb = None
    Meter = ToastNotification = ToolTip = None
    print("CRITICAL ERROR: Install 'pip install ttkbootstrap' to see the modern visual style.")

# --- Local and Core Imports ---
from utils import build_yaml_text
from managers import RunnerManager
from core.state import AppState, get_sharc_root

# IMPORTE DO BOM E VELHO BUILDER
from core.yaml_builder import build_yaml_structure

# CRITICAL IMPORT: Import the module to access the live 'SIMULATION_STATUS' variable
from managers import ssh_runner

# Import Tabs
from ui.tabs import (
    GeneralTab, IMTTab, VictimTab,
    PreviewTab, RunnerTab, ResultsTab, SingleEarthStationTab
)

# NEW: SSH/Tunnel tab
from ui.tabs.ssh_config import SSHTunnelTab

PROJECT_ROOT = get_sharc_root()


class ResponsiveTabFrame(ttk.Frame):
    """
    A professional full-axis scrollable container.
    Fixes the Tkinter infinite layout loop that occurred previously 
    by persisting elegant scrollbars, accommodating any resolution safely.
    """
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        
        bg_color = "SystemButtonFace"
        if HAS_BOOTSTRAP:
            try:
                bg_color = tb.Style().colors.bg
            except:
                pass
                
        # Persistent scrollbars prevent infinite layout thrashing
        self.v_scroll = ttk.Scrollbar(self, orient="vertical")
        self.v_scroll.pack(side="right", fill="y")
        
        self.h_scroll = ttk.Scrollbar(self, orient="horizontal")
        self.h_scroll.pack(side="bottom", fill="x")
        
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0, bg=bg_color)
        self.canvas.pack(side="left", fill="both", expand=True)
        
        self.canvas.configure(yscrollcommand=self.v_scroll.set, xscrollcommand=self.h_scroll.set)
        self.v_scroll.configure(command=self.canvas.yview)
        self.h_scroll.configure(command=self.canvas.xview)
        
        self.container = ttk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.container, anchor="nw")
        
        self.container.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        
        self.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_frame_configure(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        req_width = self.container.winfo_reqwidth()
        req_height = self.container.winfo_reqheight()
        
        w = max(req_width, event.width)
        h = max(req_height, event.height)
        self.canvas.itemconfig(self.canvas_window, width=w, height=h)

    def _on_mousewheel(self, event):
        try:
            x, y = self.winfo_pointerxy()
            widget = self.winfo_containing(x, y)
            is_child = False
            cur = widget
            while cur:
                if cur == self:
                    is_child = True
                    break
                cur = cur.master
            
            if is_child:
                if event.delta > 0:
                    self.canvas.yview_scroll(-1, "units")
                elif event.delta < 0:
                    self.canvas.yview_scroll(1, "units")
        except:
            pass


class App(tb.Window if HAS_BOOTSTRAP else tk.Tk):
    """
    SHARC GUI:
    - Preserves original functionality (tabs, YAML build/snapshot, batch generation, preview, runner, HUD monitoring)
    - Visual upgrades: consistent sidebar/HUD backgrounds (no white boxes), professional HUD card, toolbar,
      macOS menubar support, Settings menu (theme + resolution).
    """

    def __init__(self, defer_ui_init: bool = False):
        # 1. Theme Configuration
        self._theme_name = "cosmo"
        if HAS_BOOTSTRAP:
            super().__init__(themename=self._theme_name)  # keep the "blue" feel
        else:
            super().__init__()

        self.title("SHARC – SHARing and Compatibility")
        
        # 1.1 Resolution Adaptation: Adjust initial size based on screen dimensions
        try:
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            
            # Initial size: 85% of screen
            target_w = int(sw * 0.85)
            target_h = int(sh * 0.85)
            
            # Cap maximum initial size
            target_w = min(1440, max(800, target_w))
            target_h = min(900, max(600, target_h))
            
            # If screen is very small, use most of it
            if sw <= 1024 or sh <= 768:
                target_w = int(sw * 0.95)
                target_h = int(sh * 0.90)
                
            self.geometry(f"{target_w}x{target_h}")
        except Exception:
            self.geometry("1024x768")

        # Dynamically set minsize based on screen (prevent clipping on small screens natively)
        try:
            min_w = min(800, self.winfo_screenwidth() - 50)
            min_h = min(600, self.winfo_screenheight() - 50)
            self.minsize(min_w, min_h)
        except:
            self.minsize(800, 600)

        # 2. Initialize State Variables
        self.state_model = AppState()
        # Inject state model attributes into App (self) so SES tab can access app.var_x
        self.__dict__.update(self.state_model.__dict__)

        # Set default system if empty
        if not self.var_system.get():
            self.var_system.set("SINGLE_EARTH_STATION")

        self.main_cli_path = tk.StringVar(
            value=os.path.join(PROJECT_ROOT / "main_cli.py"))

        # 3. Backend and Queues
        self.line_q = queue.Queue()
        self.runner_manager = RunnerManager(
            log_callback=self._safe_log,
            update_row_callback=self._safe_update_row
        )

        # Page Control
        self.current_key = None
        self.current_frame = None
        self.frames = {}
        self.nav_buttons = {}

        self.pages_config = [
            ("general", "General", GeneralTab, "⚙"),
            ("imt", "IMT", IMTTab, "📡"),
            ("victim", "Single Space Station", VictimTab, "🛰"),
            ("station", "Single Earth Station", SingleEarthStationTab, "🛰"),
            ("preview", "Preview", PreviewTab, "👁"),
            ("ssh", "SSH Connection", SSHTunnelTab, "🔐"),
            ("runner", "Execution Runner", RunnerTab, "🚀"),
            ("results", "Results", ResultsTab, "📊"),
        ]

        # UX flags
        self._sidebar_visible = True
        self._theme_is_dark = False

        # Settings vars (menubar radio entries)
        self._theme_var = tk.StringVar(value=self._theme_name)
        self._size_var = tk.StringVar(value="800x600")

        self._ui_initialized = False
        if not defer_ui_init:
            self.initialize_ui()

    def initialize_ui(self):
        """Build the full interface once the root window is ready."""
        if self._ui_initialized:
            return

        # 4. Interface Construction
        self._setup_custom_styles()
        self._build_menubar()     # ✅ macOS-safe menubar (goes to top bar on mac)
        self._build_layout()

        # Initialize pages and establish Data Connections (Crucial for General Tab)
        self._init_pages()

        # 5. Logic: Observe changes in System Type
        self.var_system.trace_add("write", self._on_system_changed)

        # 6. Start Loop for Logs
        self.after(100, self._drain_log_queue)

        # 7. Start Loop for Simulation Status (HUD)
        self.monitor_simulation_status()

        # Force initial sidebar refresh
        self._refresh_sidebar_items()

        # Select initial page
        self._switch_page("general")

        # Show welcome toast
        self.after(800, self._show_welcome_toast)

        self.after(1000, self._disable_strict_validation)
        self._ui_initialized = True

    def _setup_custom_styles(self):
        """Define styles for the theme (visual upgrades, preserving behavior)."""
        if not HAS_BOOTSTRAP:
            return

        style = tb.Style()
        colors = style.colors

        # Base fonts (keep original, but nicer defaults)
        base_font = ("Segoe UI", 10)
        header_font = ("Segoe UI", 22, "bold")
        style.configure(".", font=base_font)

        # Nav button style
        self._theme_is_dark = self._theme_name in ("darkly", "cyborg", "superhero", "solar")
        brand_color = colors.light if self._theme_is_dark else "#2C3E50"

        # Initialize missing theme color attributes
        self._sidebar_bg = colors.bg
        self._card_bg = colors.bg
        self._muted = colors.secondary

        # "Blue" brand label (as in original)
        style.configure("Brand.TLabel", font=header_font, foreground=brand_color, background=self._sidebar_bg)
        style.configure("SubBrand.TLabel", font=("Segoe UI", 9, "bold"), foreground=self._muted, background=self._sidebar_bg)
        style.configure(
            "Nav.TButton",
            font=("Segoe UI", 11),
            anchor="w",
            padding=(20, 12)
        )
        # Softer hover (optional)
        try:
            style.map("Nav.TButton", background=[
                      ("active", "#e9ecef"), ("pressed", "#dee2de")])
        except Exception:
            pass

        # HUD Card: consistent background to avoid "white boxes" feeling
        style.configure("HudCard.TFrame",
                        background=self._card_bg, relief="flat")
        style.configure(
            "HudTitle.TLabel",
            font=("Segoe UI", 9, "bold"),
            background=self._card_bg,
            foreground=self._muted
        )
        style.configure(
            "HudValue.TLabel",
            font=("Consolas", 10, "bold"),
            background=self._card_bg,
            foreground="#2C3E50"
        )
        style.configure(
            "HudLabel.TLabel",
            font=("Segoe UI", 8),
            background=self._card_bg,
            foreground="#7F8C8D"
        )

        # Toolbar (header quick actions)
        style.configure("Toolbar.TFrame", background=colors.bg)
        style.configure("Toolbar.TButton", padding=(
            10, 6), font=("Segoe UI", 10))

    # ==========================================================
    # MENUBAR (macOS-safe) + Settings
    # ==========================================================
    def _build_menubar(self):
        # Create ALWAYS (do not depend on ttkbootstrap)
        menubar = tk.Menu(self)

        # macOS integration: Apple menu and Cmd+Q
        try:
            if self.tk.call("tk", "windowingsystem") == "aqua":
                appmenu = tk.Menu(menubar, name="apple", tearoff=0)
                menubar.add_cascade(menu=appmenu)
                appmenu.add_command(label="About SHARC",
                                    command=self._about_dialog)
                appmenu.add_separator()
                appmenu.add_command(label="Quit SHARC",
                                    command=self.destroy, accelerator="⌘Q")
                try:
                    self.createcommand("tk::mac::Quit", self.destroy)
                except Exception:
                    pass
                self.bind_all("<Command-q>", lambda e: self.destroy())
        except Exception:
            pass

        # File
        m_file = tk.Menu(menubar, tearoff=0)
        m_file.add_command(label="Save Snapshot (Current State)...",
                           command=self.save_yaml_dialog_multicombos)
        m_file.add_command(label="Batch Generate (from Table)",
                           command=self._proxy_batch_generate)
        m_file.add_separator()
        m_file.add_command(label="Export Current YAML As...",
                           command=self._export_current_yaml_as)
        m_file.add_command(label="Copy Current YAML to Clipboard",
                           command=self._copy_current_yaml_to_clipboard)
        m_file.add_separator()
        m_file.add_command(label="Open YAML Folder",
                           command=self._open_yaml_folder)
        m_file.add_command(label="Open Results Folder",
                           command=self._open_results_folder)
        m_file.add_separator()
        m_file.add_command(label="Exit", command=self.destroy)
        menubar.add_cascade(label="File", menu=m_file)

        # Edit
        m_edit = tk.Menu(menubar, tearoff=0)
        m_edit.add_command(label="Clear Runner Log",
                           command=self._clear_runner_log)
        m_edit.add_separator()
        m_edit.add_command(label="Refresh Preview",
                           command=self._refresh_preview)
        menubar.add_cascade(label="Edit", menu=m_edit)

        # View
        m_view = tk.Menu(menubar, tearoff=0)
        m_view.add_command(label="Toggle Theme (Light/Dark)",
                           command=self._toggle_theme_safely)
        m_view.add_separator()
        m_view.add_command(label="Toggle Sidebar",
                           command=self._toggle_sidebar)
        m_view.add_command(label="Toggle Simulation Tray",
                           command=self._toggle_simulation_tray)
        menubar.add_cascade(label="View", menu=m_view)

        # Settings (NEW): Theme + Resolution
        m_settings = tk.Menu(menubar, tearoff=0)

        # Theme submenu
        m_theme = tk.Menu(m_settings, tearoff=0)
        # Keep the list small and reliable across ttkbootstrap versions
        themes = [
            ("Cosmo (Blue)", "cosmo"),
            ("Flatly", "flatly"),
            ("Minty", "minty"),
            ("Litera", "litera")
        ]

        for label, theme_name in themes:
            m_theme.add_radiobutton(
                label=label,
                variable=self._theme_var,
                value=theme_name,
                command=self._apply_theme_from_settings
            )
        m_settings.add_cascade(label="Theme", menu=m_theme)

        # Resolution submenu
        m_res = tk.Menu(m_settings, tearoff=0)
        sizes = [
            "800x600",
            "1024x768",
            "1280x720",
            "1366x768",
            "1440x900",
            "1600x900",
            "1920x1080",
        ]
        for s in sizes:
            m_res.add_radiobutton(
                label=s,
                variable=self._size_var,
                value=s,
                command=self._apply_resolution_from_settings
            )
        m_res.add_separator()
        m_res.add_command(
            label="Custom…", command=self._open_custom_resolution_dialog)
        m_settings.add_cascade(label="Resolution", menu=m_res)

        menubar.add_cascade(label="Settings", menu=m_settings)

        # Window (dynamic)
        self._m_window = tk.Menu(
            menubar, tearoff=0, postcommand=self._rebuild_window_menu)
        menubar.add_cascade(label="Window", menu=self._m_window)

        # Help
        m_help = tk.Menu(menubar, tearoff=0)
        m_help.add_command(label="About SHARC", command=self._about_dialog)
        menubar.add_cascade(label="Help", menu=m_help)

        # Attach
        self.config(menu=menubar)
        self._menubar = menubar

    def _rebuild_window_menu(self):
        if not hasattr(self, "_m_window"):
            return
        self._m_window.delete(0, "end")
        visible = self._get_visible_page_keys()
        for key, label, _, _ in self.pages_config:
            if key in visible:
                self._m_window.add_command(
                    label=label,
                    command=lambda k=key, l=label: self._switch_page(k, l)
                )

    def _apply_theme_from_settings(self):
        if not HAS_BOOTSTRAP:
            return
        theme = self._theme_var.get().strip() or "cosmo"
        self._set_theme(theme)

    def _toggle_theme_safely(self):
        """Toggle theme without destroying widgets/tabs (safe)."""
        if not HAS_BOOTSTRAP:
            return
        # Just toggle between cosmo and darkly for predictability
        if self._theme_name != "darkly":
            self._set_theme("darkly")
            self._theme_var.set("darkly")
        else:
            self._set_theme("cosmo")
            self._theme_var.set("cosmo")

    def _set_theme(self, theme_name: str):
        """Apply a ttkbootstrap theme safely."""
        if not HAS_BOOTSTRAP:
            return
        try:
            style = tb.Style()
            style.theme_use(theme_name)
            self._theme_name = theme_name
            self._theme_is_dark = theme_name in (
                "darkly", "cyborg", "superhero", "solar")
            self._setup_custom_styles()
        except Exception as e:
            # Fall back to cosmo if theme not found
            try:
                style = tb.Style()
                style.theme_use("cosmo")
                self._theme_name = "cosmo"
                self._theme_var.set("cosmo")
                self._setup_custom_styles()
            except Exception:
                pass

    def _apply_resolution_from_settings(self):
        s = (self._size_var.get() or "").strip().lower()
        if "x" not in s:
            return
        try:
            w_str, h_str = s.split("x", 1)
            w = int(w_str.strip())
            h = int(h_str.strip())
            self._set_resolution(w, h)
        except Exception:
            return

    def _set_resolution(self, w: int, h: int):
        """Set window geometry. Keeps original minsize(800x600) to preserve layout guarantees."""
        try:
            # If user selects smaller than minsize, Tk will clamp to minsize.
            self.geometry(f"{w}x{h}")
        except Exception:
            pass

    def _open_custom_resolution_dialog(self):
        """Simple custom resolution dialog (Width x Height)."""
        win = tk.Toplevel(self)
        win.title("Custom Resolution")
        win.resizable(False, False)

        # mac-friendly: keep on top, and place near main window
        try:
            win.transient(self)
            win.grab_set()
        except Exception:
            pass

        frm = ttk.Frame(win, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Width").grid(row=0, column=0, sticky="w")
        ent_w = ttk.Entry(frm, width=10)
        ent_w.grid(row=0, column=1, padx=(8, 0))
        ttk.Label(frm, text="Height").grid(
            row=1, column=0, sticky="w", pady=(8, 0))
        ent_h = ttk.Entry(frm, width=10)
        ent_h.grid(row=1, column=1, padx=(8, 0), pady=(8, 0))

        # Prefill from current geometry
        try:
            geo = self.winfo_geometry()  # e.g. "800x600+10+10"
            size = geo.split("+", 1)[0]
            cw, ch = size.split("x")
            ent_w.insert(0, cw)
            ent_h.insert(0, ch)
        except Exception:
            ent_w.insert(0, "1280")
            ent_h.insert(0, "720")

        def apply():
            try:
                w = int(ent_w.get().strip())
                h = int(ent_h.get().strip())
                if w < 200 or h < 200:
                    messagebox.showwarning(
                        "Invalid size", "Please choose a larger size.")
                    return
                self._set_resolution(w, h)
                self._size_var.set(f"{w}x{h}")
                win.destroy()
            except Exception:
                messagebox.showerror(
                    "Invalid input", "Width/Height must be integers.")

        btns = ttk.Frame(frm)
        btns.grid(row=2, column=0, columnspan=2, pady=(12, 0), sticky="e")
        ttk.Button(btns, text="Cancel", command=win.destroy).pack(side="right")
        ttk.Button(btns, text="Apply", command=apply).pack(
            side="right", padx=(0, 8))

    def _build_layout(self):
        """Layout: Sidebar (Left) + Content (Right)."""
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- A. Sidebar (Left) ---
        self.sidebar = (tb.Frame(self, bootstyle="bg")
                        if HAS_BOOTSTRAP else ttk.Frame(self))
        self.sidebar.grid(row=0, column=0, rowspan=3, sticky="nsew")
        self._build_sidebar_header()

        # Try to use ScrolledFrame from ttkbootstrap for the sidebar if it exists
        try:
            from ttkbootstrap.scrolled import ScrolledFrame
            self.menu_frame = ScrolledFrame(self.sidebar, bootstyle="bg", autohide=True)
        except Exception:
            self.menu_frame = ttk.Frame(self.sidebar)
            
        self.menu_frame.pack(fill="both", expand=True, pady=10)

        # Monitor/HUD at the bottom of the sidebar
        self._build_system_monitor()

        # --- B. Header Bar (Top Right) ---
        self.header = (tb.Frame(self, bootstyle="bg-white", height=70)
                       if HAS_BOOTSTRAP else ttk.Frame(self, height=70))
        self.header.grid(row=0, column=1, sticky="ew")
        self._build_header_content()
        if HAS_BOOTSTRAP:
            tb.Separator(self.header, orient="horizontal",
                         bootstyle="secondary").pack(side="bottom", fill="x")
        else:
            ttk.Separator(self.header, orient="horizontal").pack(
                side="bottom", fill="x")

        # --- C. Content Area (Center Right) ---
        self.content_area = (tb.Frame(self, padding=25)
                             if HAS_BOOTSTRAP else ttk.Frame(self, padding=25))
        self.content_area.grid(row=1, column=1, sticky="nsew")

        # --- D. Status Bar (Bottom Right) ---
        self.status_bar = (tb.Frame(self, bootstyle="primary")
                           if HAS_BOOTSTRAP else ttk.Frame(self))
        self.status_bar.grid(row=2, column=1, sticky="ew")
        self._build_footer_content()

    def _toggle_sidebar(self):
        if not hasattr(self, "sidebar"):
            return
        if self._sidebar_visible:
            self.sidebar.grid_forget()
            self._sidebar_visible = False
        else:
            self.sidebar.grid(row=0, column=0, rowspan=3, sticky="nsew")
            self._sidebar_visible = True

    def _build_sidebar_header(self):
        if not HAS_BOOTSTRAP:
            frame = ttk.Frame(self.sidebar)
            frame.pack(fill="x", pady=(30, 10), padx=20)
            ttk.Label(frame, text="SHARC").pack(anchor="w")
            ttk.Label(frame, text="SIMULATION MANAGER").pack(anchor="w")
            ttk.Separator(self.sidebar, orient="horizontal").pack(
                fill="x", padx=20, pady=15)
            return

        frame = tb.Frame(self.sidebar, bootstyle="bg")
        frame.pack(fill="x", pady=(30, 10), padx=20)

        lbl = tb.Label(frame, text="SHARC", style="Brand.TLabel")
        lbl.pack(anchor="w")

        sub = tb.Label(
            frame,
            text="SIMULATION MANAGER",
            style="SubBrand.TLabel"
        )
        sub.pack(anchor="w")

        tb.Separator(self.sidebar, bootstyle="secondary").pack(
            fill="x", padx=20, pady=15)

    def _build_system_monitor(self):
        """Builds the Circular Meter, the Status HUD, and the Retractable Tray (professional card)."""
        if not HAS_BOOTSTRAP:
            monitor_frame = ttk.Frame(self.sidebar, padding=15)
            monitor_frame.pack(side="bottom", fill="x", pady=10)
            ttk.Label(monitor_frame, text="Global Progress").pack(
                anchor="center")
            return

        monitor_frame = tb.Frame(self.sidebar, bootstyle="bg", padding=12)
        monitor_frame.pack(side="bottom", fill="x", pady=10)

        # HUD CARD (key fix for background artifacts)
        card = tb.Frame(monitor_frame, style="HudCard.TFrame",
                        padding=10, relief="flat", borderwidth=0)
        card.pack(fill="x")

        tb.Label(card, text="Global Progress", style="HudTitle.TLabel").pack(
            anchor="center", pady=(0, 5))

        # --- Retractable Tray for Active Threads ---
        self.tray_button = tb.Button(
            card,
            text="▼ Active Simulations ▼",
            bootstyle="secondary-link",
            command=self._toggle_simulation_tray
        )
        self.tray_button.pack(anchor="center", pady=(0, 5))

        # Tray container (starts hidden)
        self.tray_frame = tb.Frame(card, style="HudCard.TFrame")
        self.tray_visible = False
        self.thread_widgets = {}  # Dictionary to manage individual widgets

        # 1. Circular Meter
        self.sys_meter = Meter(
            card,
            metersize=130,
            padding=10,
            amountused=0,
            metertype="full",
            subtext="0.0%",
            textright="",
            textfont=("Segoe UI", 12, "bold"),
            subtextfont=("Segoe UI", 8),
            showtext=False,
            interactive=False,
            bootstyle="success",
            stripethickness=4
        )
        self.sys_meter.pack(anchor="center", pady=(5, 10))

        # FIX: Force Meter to draw with the sidebar background instead of default TFrame (white box fix)
        _orig_draw = getattr(self.sys_meter, "_draw_meter", None) or getattr(self.sys_meter, "draw_meter", None)
        if _orig_draw:
            def _patched_draw(*args, **kwargs):
                style = tb.Style()
                orig_bg = style.lookup("TFrame", "background")
                style.configure("TFrame", background=self._card_bg)
                try:
                    _orig_draw(*args, **kwargs)
                    # Ensure the internal canvas also uses the exact color
                    if hasattr(self.sys_meter, "indicator"):
                        self.sys_meter.indicator.configure(background=self._card_bg)
                finally:
                    style.configure("TFrame", background=orig_bg)
            
            if hasattr(self.sys_meter, "_draw_meter"):
                self.sys_meter._draw_meter = _patched_draw
                self.after(50, self.sys_meter._draw_meter)  # apply initial draw override
            else:
                self.sys_meter.draw_meter = _patched_draw
                self.after(50, self.sys_meter.draw_meter)

        # 2. HUD Container (Snapshots and ETA)
        self.hud_frame = tb.Frame(card, style="HudCard.TFrame")
        self.hud_frame.pack(fill="x", pady=5)

        self.hud_frame.columnconfigure(0, weight=1)
        self.hud_frame.columnconfigure(1, weight=1)
        self.hud_frame.columnconfigure(2, weight=1)

        f_snaps = tb.Frame(self.hud_frame, style="HudCard.TFrame")
        f_snaps.grid(row=0, column=0, sticky="ew")
        tb.Label(f_snaps, text="SNAPSHOTS",
                 style="HudLabel.TLabel").pack(anchor="center")
        self.lbl_hud_snaps = tb.Label(
            f_snaps, text="0 / 0", style="HudValue.TLabel")
        self.lbl_hud_snaps.pack(anchor="center")

        ttk.Separator(self.hud_frame, orient="vertical").grid(
            row=0, column=1, sticky="ns", padx=8)

        f_eta = tb.Frame(self.hud_frame, style="HudCard.TFrame")
        f_eta.grid(row=0, column=2, sticky="ew")
        tb.Label(f_eta, text="ETA", style="HudLabel.TLabel").pack(
            anchor="center")
        self.lbl_hud_eta = tb.Label(
            f_eta, text="--:--:--", style="HudValue.TLabel")
        self.lbl_hud_eta.pack(anchor="center")

    def _toggle_simulation_tray(self):
        """Shows or hides the ongoing simulations tray."""
        if not HAS_BOOTSTRAP:
            return
        if self.tray_visible:
            self.tray_frame.pack_forget()
            self.tray_button.configure(text="▼ Active Simulations ▼")
            self.tray_visible = False
        else:
            self.tray_frame.pack(before=self.sys_meter, fill="x", pady=(0, 10))
            self.tray_button.configure(text="▲ Hide Simulations ▲")
            self.tray_visible = True

    def _build_header_content(self):
        """Header with Title + Toolbar + Global Generate button (original preserved)."""
        if not HAS_BOOTSTRAP:
            self.lbl_page_title = ttk.Label(self.header, text="Dashboard")
            self.lbl_page_title.pack(side="left", padx=30, pady=20)
            return

        # Left title
        self.lbl_page_title = tb.Label(self.header, text="Dashboard",
                                       font=("Segoe UI", 18), foreground="#2C3E50")
        self.lbl_page_title.pack(side="left", padx=(30, 10), pady=20)

        # Toolbar (requested): quick actions, doesn't replace original generate menu
        self._build_toolbar()

        # Global Generate Button (Cascade Style) - original behavior
        self.btn_gen_main = tb.Menubutton(
            self.header,
            text="⚡ GENERATE",
            bootstyle="success",
            width=20
        )
        self.btn_gen_main.pack(side="right", padx=30)

        self.menu_gen_main = tk.Menu(self.btn_gen_main, tearoff=0)
        self.btn_gen_main.configure(menu=self.menu_gen_main)

        self.menu_gen_main.add_command(
            label="🚀 Batch Generate (from Table)",
            command=self._proxy_batch_generate
        )
        self.menu_gen_main.add_separator()
        self.menu_gen_main.add_command(
            label="💾 Save Current State (Snapshot)",
            command=self.save_yaml_dialog_multicombos
        )

        ToolTip(self.btn_gen_main,
                text="Generate YAML configuration files (Batch or Single Snapshot).")

    def _build_toolbar(self):
        """Compact toolbar in header. Pure UI shortcuts to existing features."""
        if not HAS_BOOTSTRAP:
            return

        bar = tb.Frame(self.header, style="Toolbar.TFrame")
        bar.pack(side="right", padx=(0, 10), pady=16)

    def _build_footer_content(self):
        if not HAS_BOOTSTRAP:
            ttk.Label(self.status_bar, text="Ready.").pack(
                side="left", padx=20)
            return

        # SSH Status
        f_ssh = tb.Frame(self.status_bar, bootstyle="primary", padding=(15, 5))
        f_ssh.pack(side="right", fill="y")
        tb.Label(f_ssh, textvariable=self.ssh_status, font=("Consolas", 9, "bold"),
                 bootstyle="inverse-primary").pack()

        tb.Label(self.status_bar, text="|",
                 bootstyle="inverse-primary").pack(side="right")

        # Tunnel Status
        f_tun = tb.Frame(self.status_bar, bootstyle="primary", padding=(15, 5))
        f_tun.pack(side="right", fill="y")
        tb.Label(f_tun, textvariable=self.tunnel_status, font=("Consolas", 9),
                 bootstyle="inverse-primary").pack()

        # Log Message
        self.lbl_status_msg = tb.Label(self.status_bar, text="Ready.", font=("Segoe UI", 9),
                                       bootstyle="inverse-primary")
        self.lbl_status_msg.pack(side="left", padx=20)

    def _refresh_preview(self):
        logic = getattr(self, "tab_preview", None)
        if logic:
            if hasattr(logic, "refresh"):
                logic.refresh()
            elif hasattr(logic, "update_plot"):
                logic.update_plot()

    def _about_dialog(self):
        messagebox.showinfo(
            "About SHARC",
            "SHARC – SHARing and Compatibility\nGUI Manager\n\n© ANATEL / Project Contributors"
        )

    def _open_folder_crossplatform(self, folder: str):
        try:
            if not folder or not os.path.isdir(folder):
                messagebox.showwarning(
                    "Folder not found", f"Folder does not exist:\n{folder}")
                return
            system = platform.system().lower()
            if "windows" in system:
                os.startfile(folder)  # noqa
            elif "darwin" in system:
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open folder:\n{e}")

    def _open_yaml_folder(self):
        folder = self.var_yaml_dir.get() or os.getcwd()
        self._open_folder_crossplatform(folder)

    def _open_results_folder(self):
        guess = str(PROJECT_ROOT / "results")
        if not os.path.isdir(guess):
            guess = os.getcwd()
        self._open_folder_crossplatform(guess)

    def _export_current_yaml_as(self):
        init = self.var_yaml_dir.get() or os.getcwd()
        path = filedialog.asksaveasfilename(
            title="Export Current YAML",
            defaultextension=".yaml",
            initialdir=init,
            initialfile=(self.var_prefix.get() or "snapshot") + ".yaml"
        )
        if not path:
            return
        try:
            data = self.current_yaml_dict()
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False,
                          sort_keys=False, allow_unicode=True)
            self.var_yaml_dir.set(os.path.dirname(path))
            self._show_success_toast("Exported YAML successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export YAML:\n{e}")

    def _copy_current_yaml_to_clipboard(self):
        try:
            data = self.current_yaml_dict()
            yaml_text = yaml.dump(
                data, default_flow_style=False, sort_keys=False, allow_unicode=True)
            self.clipboard_clear()
            self.clipboard_append(yaml_text)
            self._show_success_toast("YAML copied to clipboard.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy YAML:\n{e}")

    def _clear_runner_log(self):
        try:
            if hasattr(self, "tab_runner") and hasattr(self.tab_runner, "txt_log"):
                w = self.tab_runner.txt_log
                w.configure(state="normal")
                w.delete("1.0", "end")
                w.configure(state="disabled")
            if hasattr(self, "lbl_status_msg"):
                self.lbl_status_msg.config(text="Runner log cleared.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to clear log:\n{e}")

    def _show_welcome_toast(self):
        if not HAS_BOOTSTRAP:
            return
        ToastNotification(
            title="SHARC", message="System Ready.\nTheme: Cosmo Light",
            duration=3000, bootstyle="light", position=(40, 60, "ne")
        ).show_toast()

    def _show_success_toast(self, msg):
        if not HAS_BOOTSTRAP:
            return
        ToastNotification(
            title="Success", message=msg, duration=3000,
            bootstyle="success", position=(40, 60, "ne")
        ).show_toast()

    def _safe_log(self, msg): self.line_q.put(("log", msg))
    def _safe_update_row(self, data): self.line_q.put(("row", data))

    def _drain_log_queue(self):
        try:
            for _ in range(50):
                item = self.line_q.get_nowait()
                msg, payload = item
                if msg == "log":
                    clean = payload.strip()
                    if clean:
                        self.lbl_status_msg.config(text=clean[:120])
                    if hasattr(self.tab_runner, 'txt_log'):
                        w = self.tab_runner.txt_log
                        w.configure(state="normal")
                        w.insert("end", payload +
                                 ("\n" if not payload.endswith("\n") else ""))
                        w.see("end")
                        w.configure(state="disabled")
                elif msg == "row":
                    if hasattr(self.tab_runner, 'tree'):
                        tree = self.tab_runner.tree
                        iid = payload.get("iid")
                        if iid and tree.exists(iid):
                            cur = list(tree.item(iid, "values"))
                            if payload["status"] is not None:
                                cur[1] = payload["status"]
                            if payload["pct"] is not None:
                                cur[3] = payload["pct"]
                            tree.item(iid, values=cur)
        except:
            pass
        self.after(100, self._drain_log_queue)

    def monitor_simulation_status(self):
        """Monitors global simulation progress via ssh_runner module."""
        try:
            raw_data = getattr(ssh_runner, "SIMULATION_STATUS", {})

            if not raw_data or not isinstance(raw_data, dict):
                if HAS_BOOTSTRAP and hasattr(self, "sys_meter"):
                    self.sys_meter.configure(amountused=0, subtext="0.0%")
                if hasattr(self, "lbl_hud_snaps"):
                    self.lbl_hud_snaps.configure(text="0 / 0")
                if hasattr(self, "lbl_hud_eta"):
                    self.lbl_hud_eta.configure(text="--:--:--")
                if hasattr(self, "thread_widgets"):
                    for t, w in list(self.thread_widgets.items()):
                        try:
                            w['row'].destroy()
                        except Exception:
                            pass
                    self.thread_widgets.clear()
                self.after(5000, self.monitor_simulation_status)
                return

            percentages = []
            total_done_snaps = 0
            total_max_snaps = 0
            etas = []
            current_threads = set(raw_data.keys())
            existing_threads = set(self.thread_widgets.keys())

            for t in existing_threads - current_threads:
                self.thread_widgets[t]['row'].destroy()
                del self.thread_widgets[t]

            for key, val in raw_data.items():
                if isinstance(val, dict):
                    pct_str = val.get('pct', '0%')
                    try:
                        clean_pct = float(pct_str.replace('%', '').strip())
                    except:
                        clean_pct = 0.0
                    percentages.append(clean_pct)

                    snap_str = val.get('snap', '0/0')
                    if '/' in snap_str:
                        try:
                            done, total = snap_str.split('/')
                            total_done_snaps += int(done)
                            total_max_snaps += int(total)
                        except:
                            pass

                    eta_str = val.get('eta', '')
                    if eta_str and ':' in eta_str:
                        etas.append(eta_str)

                    if key not in self.thread_widgets:
                        row = tb.Frame(self.tray_frame, style="HudCard.TFrame")
                        row.pack(fill="x", pady=4)
                        header_frame = tb.Frame(row, style="HudCard.TFrame")
                        header_frame.pack(fill="x")

                        short_name = str(key).split("/")[-1]
                        lbl_name = tb.Label(
                            header_frame,
                            text=short_name[:20],
                            font=("Segoe UI", 8, "bold"),
                            style="HudValue.TLabel"
                        )
                        lbl_name.pack(side="left")

                        lbl_eta = tb.Label(
                            header_frame,
                            text=eta_str or "--:--",
                            font=("Consolas", 8),
                            style="HudLabel.TLabel"
                        )
                        lbl_eta.pack(side="right")

                        pb = tb.Progressbar(
                            row, bootstyle="success-striped", maximum=100)
                        pb.pack(fill="x", pady=(2, 0))

                        self.thread_widgets[key] = {
                            'row': row, 'lbl_eta': lbl_eta, 'pb': pb, 'lbl_name': lbl_name
                        }
                    else:
                        w = self.thread_widgets[key]
                        w['lbl_eta'].configure(text=eta_str or "--:--")
                        w['pb']['value'] = clean_pct

            avg_pct = sum(percentages) / len(percentages) if percentages else 0
            snaps_text = f"{total_done_snaps} / {total_max_snaps}" if total_max_snaps > 0 else "0 / 0"
            final_eta = max(etas) if etas else "--:--:--"

            self.sys_meter.configure(amountused=int(
                avg_pct) if avg_pct > 0 else 0, subtext=f"{avg_pct:.1f}%")
            self.lbl_hud_snaps.configure(text=snaps_text)
            self.lbl_hud_eta.configure(text=final_eta)

        except Exception as e:
            print(f"HUD Update Error: {e}")

        self.after(5000, self.monitor_simulation_status)

    def _init_pages(self):
        """Initializes all tabs and establishes data connections."""
        # Get the actual frame to place buttons (if ScrolledFrame is used)
        btn_parent = getattr(self.menu_frame, "container", self.menu_frame)

        for key, label, Cls, icon in self.pages_config:
            btn = tb.Button(
                btn_parent,
                text=f"  {icon}   {label}",
                style="Nav.TButton",
                bootstyle="secondary-link",
                command=lambda k=key, l=label: self._switch_page(k, l)
            )
            self.nav_buttons[key] = btn
            
            # The 'results' and 'preview' tabs contain interactive dynamic Plots 
            # and PanedWindows that MUST natively shrink/expand to the window bounds.
            # Wrapping them in a Canvas (ResponsiveTabFrame) causes them to indefinitely 
            # overflow the screen horizontally and hide sidebars (PanedWindow sash issues).
            if key in ["results", "preview"]:
                container = ttk.Frame(self.content_area)
                content_parent = container
            else:
                if HAS_BOOTSTRAP:
                    container = ResponsiveTabFrame(self.content_area)
                    content_parent = container.container
                else:
                    container = ttk.Frame(self.content_area)
                    content_parent = container

            self.frames[key] = container
            instance = Cls(self, content_parent)
            setattr(self, f"tab_{key}", instance)

        if hasattr(self, 'tab_general'):

            def get_imt_live_data():
                data = {}
                if hasattr(self, 'tab_imt'):
                    if hasattr(self.tab_imt, 'state') and hasattr(self.tab_imt.state, 'vars'):
                        for k, v in self.tab_imt.state.vars.items():
                            try:
                                data[k] = v.get()
                            except:
                                pass
                    if hasattr(self.tab_imt, 'topo_section') and self.tab_imt.topo_section:
                        if hasattr(self.tab_imt.topo_section, 'get_countries_text'):
                            data['countries_text'] = self.tab_imt.topo_section.get_countries_text(
                            )
                return data

            def get_system_live_data():
                data = {}
                sys_mode = self.var_system.get()
                objs_to_scan = [self]

                if sys_mode in self._space_ui_systems():
                    if hasattr(self, 'tab_victim'):
                        objs_to_scan.append(self.tab_victim)
                elif sys_mode in self._earth_ui_systems():
                    if hasattr(self, 'tab_station'):
                        objs_to_scan.append(self.tab_station)

                for target_obj in objs_to_scan:
                    if not target_obj:
                        continue

                    sources = [
                        getattr(target_obj, 'vars', {}),
                        getattr(getattr(target_obj, 'state', None), 'vars', {})
                    ]
                    for src in sources:
                        if isinstance(src, dict):
                            for k, v in src.items():
                                try:
                                    data[k] = v.get()
                                except:
                                    data[k] = v

                    for attr_name in dir(target_obj):
                        if attr_name.startswith("_"):
                            continue
                        if attr_name.startswith(("imt_", "topo_", "bs_", "ue_", "ul_", "dl_", "ch_", "shadowing")):
                            continue

                        try:
                            val = getattr(target_obj, attr_name)
                            if isinstance(val, (tk.StringVar, tk.DoubleVar, tk.IntVar, tk.BooleanVar)):
                                data[attr_name] = val.get()
                            elif isinstance(val, (list, dict, int, float, str, bool)):
                                if not callable(val):
                                    data[attr_name] = val
                        except:
                            pass

                return data

            self.tab_general.register_data_collector(get_imt_live_data)
            self.tab_general.register_data_collector(get_system_live_data)

    def _space_ui_systems(self):
        return {
            "SINGLE_SPACE_STATION",
            "HAPS",
            "MSS_SS",
            "MSS_D2D",
            "FSS_SS",
            "EESS_SS",
            "METSAT_SS",
            "RNS",
        }

    def _earth_ui_systems(self):
        return {
            "SINGLE_EARTH_STATION",
            "FS",
            "FSS_ES",
            "RAS",
        }

    def _on_system_changed(self, *args):
        self._refresh_sidebar_items()

    def _get_visible_page_keys(self):
        sys_type = self.var_system.get()
        visible = set()
        for key, label, _, _ in self.pages_config:
            should_show = True
            if sys_type in self._earth_ui_systems():
                if key == "victim":
                    should_show = False
                if key == "station":
                    should_show = True
            elif sys_type in self._space_ui_systems():
                if key == "station":
                    should_show = False
                if key == "victim":
                    should_show = True
            else:
                if key == "victim":
                    should_show = False
            if should_show:
                visible.add(key)
        return visible

    def _refresh_sidebar_items(self):
        sys_type = self.var_system.get()
        for btn in self.nav_buttons.values():
            btn.pack_forget()

        for key, label, _, _ in self.pages_config:
            should_show = True
            if sys_type in self._earth_ui_systems():
                if key == "victim":
                    should_show = False
                if key == "station":
                    should_show = True
            elif sys_type in self._space_ui_systems():
                if key == "station":
                    should_show = False
                if key == "victim":
                    should_show = True
            else:
                if key == "victim":
                    should_show = False

            if should_show:
                self.nav_buttons[key].pack(fill="x", pady=2, padx=10)

        if self.current_key and not self.nav_buttons[self.current_key].winfo_ismapped():
            self._switch_page("general")

    def _switch_page(self, key, label_text=None):
        if hasattr(self, 'tab_imt') and hasattr(self.tab_imt, 'txt_countries'):
            try:
                raw_txt = self.tab_imt.txt_countries.get("1.0", "end").strip()
                if raw_txt and hasattr(self, 'topo_countries'):
                    self.topo_countries.set(raw_txt)
            except:
                pass

        if label_text:
            self.lbl_page_title.config(text=label_text)
        elif key == "general":
            self.lbl_page_title.config(text="General Settings")

        if self.current_frame:
            self.current_frame.pack_forget()

        for k, btn in self.nav_buttons.items():
            btn.configure(bootstyle="primary" if k ==
                          key else "secondary-link")

        self.current_frame = self.frames[key]
        self.current_frame.pack(fill="both", expand=True)
        self.current_key = key

        if key == "preview":
            logic = getattr(self, f"tab_{key}", None)
            if logic:
                if hasattr(logic, "refresh"):
                    logic.refresh()
                elif hasattr(logic, "update_plot"):
                    logic.update_plot()

    def current_yaml_dict(self) -> dict:
        """
        Generates the current configuration dictionary (Snapshot).
        Required by PreviewTab to display the YAML.
        Uses the live GeneralTab builder so preview and batch generation stay aligned.
        """
        if hasattr(self, "tab_general") and hasattr(self.tab_general, "build_current_structure"):
            try:
                return self.tab_general.build_current_structure()
            except Exception:
                pass
        return build_yaml_structure(self)

    def _proxy_batch_generate(self):
        """Calls batch generation (from variable table) on GeneralTab."""
        if hasattr(self, 'tab_general'):
            self.tab_general.save_yaml_to_yamldir()
        else:
            messagebox.showerror("Error", "General Tab not available.")

    def save_yaml_dialog_multicombos(self):
        """
        SNAPSHOT: Uses build_yaml_structure (old robust method) to save single state.
        """
        init = self.var_yaml_dir.get() or os.getcwd()
        path = filedialog.asksaveasfilename(
            title="Save Snapshot",
            defaultextension=".yaml",
            initialdir=init,
            initialfile=(self.var_prefix.get() or "snapshot") + ".yaml"
        )
        if path:
            try:
                if hasattr(self, "tab_general") and hasattr(self.tab_general, "build_current_structure"):
                    data = self.tab_general.build_current_structure()
                else:
                    data = build_yaml_structure(self)
                with open(path, 'w', encoding='utf-8') as f:
                    yaml.dump(data, f, default_flow_style=False,
                              sort_keys=False)
                self.var_yaml_dir.set(os.path.dirname(path))
                messagebox.showinfo("Success", f"Snapshot saved to:\n{path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save snapshot:\n{e}")

    def _deep_format(self, obj, combo):
        """Helper for string formatting, kept for compatibility."""
        if isinstance(obj, dict):
            return {k: self._deep_format(v, combo) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._deep_format(v, combo) for v in obj]
        if isinstance(obj, str):
            try:
                return obj.format(**combo)
            except:
                return obj
        return obj

    def _disable_strict_validation(self):
        def _recursive_clean(widget):
            try:
                if isinstance(widget, (tk.Entry, ttk.Entry)):
                    widget.configure(validate="none")
            except Exception:
                pass
            for child in widget.winfo_children():
                _recursive_clean(child)

        _recursive_clean(self)
        print(">> UI Ready: SHARC ready!")


if __name__ == "__main__":
    app = App()
    app.mainloop()
