import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import tkinter.font as tkfont
import queue
import os
import itertools
import ast
import yaml 

# Try to use modern visual style
try:
    import ttkbootstrap as tb
    from ttkbootstrap.constants import *
    from ttkbootstrap.widgets import Meter, ToastNotification, ToolTip
    HAS_BOOTSTRAP = True
except ImportError:
    HAS_BOOTSTRAP = False
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
PROJECT_ROOT = get_sharc_root()


class App(tb.Window if HAS_BOOTSTRAP else tk.Tk):
    def __init__(self):
        # 1. Theme Configuration
        if HAS_BOOTSTRAP:
            super().__init__(themename="cosmo")
        else:
            super().__init__()

        self.title("SHARC – SHARing and Compatibility")
        self.geometry("800x600")
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
            ("runner", "Execution Runner", RunnerTab, "🚀"),
            ("results", "Results", ResultsTab, "📊"),
        ]

        # 4. Interface Construction
        self._setup_custom_styles()
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

    def _setup_custom_styles(self):
        """Define styles for the theme."""
        style = tb.Style()
        base_font = ("Segoe UI", 10)
        header_font = ("Segoe UI", 22, "bold")

        style.configure(".", font=base_font)
        style.configure("Brand.TLabel", font=header_font, foreground="#2C3E50")
        style.configure("Nav.TButton", font=("Segoe UI", 11),
                        anchor="w", padding=(20, 12))
        style.configure("Card.TFrame", background="#ffffff", relief="flat")

        # Specific styles for the HUD
        style.configure("HudValue.TLabel", font=(
            "Consolas", 10, "bold"), foreground="#2C3E50")
        style.configure("HudLabel.TLabel", font=(
            "Segoe UI", 8), foreground="#7F8C8D")

    def _build_layout(self):
        """Layout: Sidebar (Left) + Content (Right)."""
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- A. Sidebar (Left) ---
        self.sidebar = tb.Frame(self, bootstyle="light")
        self.sidebar.grid(row=0, column=0, rowspan=3, sticky="nsew")
        self._build_sidebar_header()

        self.menu_frame = tb.Frame(self.sidebar, bootstyle="light")
        self.menu_frame.pack(fill="both", expand=True, pady=10)

        # Monitor/HUD at the bottom of the sidebar
        self._build_system_monitor()

        # --- B. Header Bar (Top Right) ---
        self.header = tb.Frame(self, bootstyle="bg-white", height=70)
        self.header.grid(row=0, column=1, sticky="ew")
        self._build_header_content()
        tb.Separator(self.header, orient="horizontal",
                     bootstyle="secondary").pack(side="bottom", fill="x")

        # --- C. Content Area (Center Right) ---
        self.content_area = tb.Frame(self, padding=25)
        self.content_area.grid(row=1, column=1, sticky="nsew")

        # --- D. Status Bar (Bottom Right) ---
        self.status_bar = tb.Frame(self, bootstyle="primary")
        self.status_bar.grid(row=2, column=1, sticky="ew")
        self._build_footer_content()

    def _build_sidebar_header(self):
        frame = tb.Frame(self.sidebar, bootstyle="light")
        frame.pack(fill="x", pady=(30, 10), padx=20)

        lbl = tb.Label(frame, text="SHARC", style="Brand.TLabel",
                       bootstyle="inverse-light")
        lbl.pack(anchor="w")

        sub = tb.Label(frame, text="SIMULATION MANAGER", font=("Segoe UI", 9, "bold"),
                       foreground="#7F8C8D", bootstyle="inverse-light")
        sub.pack(anchor="w")

        tb.Separator(self.sidebar, bootstyle="secondary").pack(
            fill="x", padx=20, pady=15)

    def _build_system_monitor(self):
        """Builds the Circular Meter, the Status HUD, and the Retractable Tray."""
        monitor_frame = tb.Frame(self.sidebar, bootstyle="light", padding=15)
        monitor_frame.pack(side="bottom", fill="x", pady=10)

        # Title
        tb.Label(monitor_frame, text="Global Progress", foreground="#7F8C8D",
                 font=("Segoe UI", 9, "bold"), bootstyle="inverse-light").pack(anchor="center", pady=(0, 5))

        # --- Retractable Tray for Active Threads ---
        self.tray_button = tb.Button(
            monitor_frame,
            text="▼ Active Simulations ▼",
            bootstyle="secondary-link",
            command=self._toggle_simulation_tray
        )
        self.tray_button.pack(anchor="center", pady=(0, 5))

        # Tray container (starts hidden)
        self.tray_frame = tb.Frame(monitor_frame, bootstyle="light")
        self.tray_visible = False
        self.thread_widgets = {}  # Dictionary to manage individual widgets

        # 1. Circular Meter
        self.sys_meter = Meter(
            monitor_frame,
            metersize=140,
            padding=5,
            amountused=0,
            metertype="full",
            subtext="0.0%",
            textright="",
            showtext=False,
            interactive=False,
            bootstyle="primary",
            stripethickness=10
        )
        self.sys_meter.pack(anchor="center", pady=(0, 15))

        # 2. HUD Container (Snapshots and ETA)
        self.hud_frame = tb.Frame(monitor_frame, bootstyle="light")
        self.hud_frame.pack(fill="x", pady=5)

        # -- HUD Grid --
        self.hud_frame.columnconfigure(0, weight=1)
        self.hud_frame.columnconfigure(1, weight=1)
        self.hud_frame.columnconfigure(2, weight=1)

        # Snapshots Section
        f_snaps = tb.Frame(self.hud_frame, bootstyle="light")
        f_snaps.grid(row=0, column=0, sticky="ew")
        tb.Label(f_snaps, text="SNAPSHOTS", style="HudLabel.TLabel",
                 bootstyle="inverse-light").pack(anchor="center")
        self.lbl_hud_snaps = tb.Label(
            f_snaps, text="0 / 0", style="HudValue.TLabel", bootstyle="inverse-light")
        self.lbl_hud_snaps.pack(anchor="center")

        # Vertical Separator
        ttk.Separator(self.hud_frame, orient="vertical").grid(
            row=0, column=1, sticky="ns", padx=5)

        # ETA Section
        f_eta = tb.Frame(self.hud_frame, bootstyle="light")
        f_eta.grid(row=0, column=2, sticky="ew")
        tb.Label(f_eta, text="ETA", style="HudLabel.TLabel",
                 bootstyle="inverse-light").pack(anchor="center")
        self.lbl_hud_eta = tb.Label(
            f_eta, text="--:--:--", style="HudValue.TLabel", bootstyle="inverse-light")
        self.lbl_hud_eta.pack(anchor="center")

    def _toggle_simulation_tray(self):
        """Shows or hides the ongoing simulations tray."""
        if self.tray_visible:
            self.tray_frame.pack_forget()
            self.tray_button.configure(text="▼ Active Simulations ▼")
            self.tray_visible = False
        else:
            self.tray_frame.pack(before=self.sys_meter, fill="x", pady=(0, 10))
            self.tray_button.configure(text="▲ Hide Simulations ▲")
            self.tray_visible = True

    def _build_header_content(self):
        """Header with Title and Global Save/Generate Button (Cascade)."""
        self.lbl_page_title = tb.Label(self.header, text="Dashboard",
                                       font=("Segoe UI", 18), foreground="#2C3E50")
        self.lbl_page_title.pack(side="left", padx=30, pady=20)

        # Global Generate Button (Cascade Style)
        # Substitui o botão único antigo por um Menubutton
        self.btn_gen_main = tb.Menubutton(
            self.header, 
            text="⚡ GENERATE", 
            bootstyle="success",
            width=20
        )
        self.btn_gen_main.pack(side="right", padx=30)

        self.menu_gen_main = tk.Menu(self.btn_gen_main, tearoff=0)
        self.btn_gen_main.configure(menu=self.menu_gen_main)

        # Opção 1: Geração em Lote (Proxy para General Tab - Nova lógica robusta)
        self.menu_gen_main.add_command(
            label="🚀 Batch Generate (from Table)", 
            command=self._proxy_batch_generate
        )
        self.menu_gen_main.add_separator()
        
        # Opção 2: Snapshot Único (Usa o BOM E VELHO BUILDER)
        self.menu_gen_main.add_command(
            label="💾 Save Current State (Snapshot)", 
            command=self.save_yaml_dialog_multicombos
        )

        ToolTip(self.btn_gen_main, text="Generate YAML configuration files (Batch or Single Snapshot).")

    def _build_footer_content(self):
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

    # --- MONITOR ---
    def monitor_simulation_status(self):
        """Monitors global simulation progress via ssh_runner module."""
        try:
            raw_data = getattr(ssh_runner, "SIMULATION_STATUS", {})

            if not raw_data or not isinstance(raw_data, dict):
                self.sys_meter.configure(amountused=0, subtext="0.0%")
                self.lbl_hud_snaps.configure(text="0 / 0")
                self.lbl_hud_eta.configure(text="--:--:--")
                for t, w in self.thread_widgets.items():
                    w['row'].destroy()
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
                    try: clean_pct = float(pct_str.replace('%', '').strip())
                    except: clean_pct = 0.0
                    percentages.append(clean_pct)

                    snap_str = val.get('snap', '0/0')
                    if '/' in snap_str:
                        try:
                            done, total = snap_str.split('/')
                            total_done_snaps += int(done)
                            total_max_snaps += int(total)
                        except: pass

                    eta_str = val.get('eta', '')
                    if eta_str and ':' in eta_str: etas.append(eta_str)

                    if key not in self.thread_widgets:
                        row = tb.Frame(self.tray_frame, bootstyle="light")
                        row.pack(fill="x", pady=4)
                        header_frame = tb.Frame(row, bootstyle="light")
                        header_frame.pack(fill="x")
                        
                        short_name = str(key).split("/")[-1]
                        lbl_name = tb.Label(header_frame, text=short_name[:20], font=("Segoe UI", 8, "bold"), bootstyle="inverse-light")
                        lbl_name.pack(side="left")
                        
                        lbl_eta = tb.Label(header_frame, text=eta_str or "--:--", font=("Consolas", 8), bootstyle="inverse-light")
                        lbl_eta.pack(side="right")
                        
                        pb = tb.Progressbar(row, bootstyle="success-striped", maximum=100)
                        pb.pack(fill="x", pady=(2, 0))
                        
                        self.thread_widgets[key] = {'row': row, 'lbl_eta': lbl_eta, 'pb': pb, 'lbl_name': lbl_name}
                    else:
                        w = self.thread_widgets[key]
                        w['lbl_eta'].configure(text=eta_str or "--:--")
                        w['pb']['value'] = clean_pct

            avg_pct = sum(percentages) / len(percentages) if percentages else 0
            snaps_text = f"{total_done_snaps} / {total_max_snaps}" if total_max_snaps > 0 else "0 / 0"
            final_eta = max(etas) if etas else "--:--:--"

            self.sys_meter.configure(amountused=int(avg_pct) if avg_pct > 0 else 0, subtext=f"{avg_pct:.1f}%")
            self.lbl_hud_snaps.configure(text=snaps_text)
            self.lbl_hud_eta.configure(text=final_eta)

        except Exception as e:
            print(f"HUD Update Error: {e}")

        self.after(5000, self.monitor_simulation_status)

    def _init_pages(self):
        """Initializes all tabs and establishes data connections."""
        for key, label, Cls, icon in self.pages_config:
            btn = tb.Button(
                self.menu_frame,
                text=f"  {icon}   {label}",
                style="Nav.TButton",
                bootstyle="secondary-link",
                command=lambda k=key, l=label: self._switch_page(k, l)
            )
            self.nav_buttons[key] = btn
            container = tb.Frame(self.content_area)
            self.frames[key] = container
            instance = Cls(self, container)
            setattr(self, f"tab_{key}", instance)

        # =====================================================================
        # [NEW] DATA CONNECTION BRIDGE (ROBUST UNIVERSAL VERSION)
        # =====================================================================
        if hasattr(self, 'tab_general'):
            
            # 1. IMT Data Collector (Specific to IMT logic)
            def get_imt_live_data():
                data = {}
                if hasattr(self, 'tab_imt'):
                    # Vars from state manager
                    if hasattr(self.tab_imt, 'state') and hasattr(self.tab_imt.state, 'vars'):
                        for k, v in self.tab_imt.state.vars.items():
                            try: data[k] = v.get()
                            except: pass
                    # Topology text
                    if hasattr(self.tab_imt, 'topo_section') and self.tab_imt.topo_section:
                        if hasattr(self.tab_imt.topo_section, 'get_countries_text'):
                            data['countries_text'] = self.tab_imt.topo_section.get_countries_text()
                return data

            # 2. System (SES/Victim) Universal Data Collector
            # This function scans BOTH the App (self) and the active Tab for variables.
            # It ensures variables are caught whether they are global (SES) or local (SSS).
            def get_system_live_data():
                data = {}
                sys_mode = self.var_system.get()

                # Define list of objects to scan (The Vacuum Cleaner Approach)
                # We ALWAYS scan 'self' because global vars (like SES vars) might be there.
                objs_to_scan = [self]

                # Add specific tab based on mode
                if sys_mode == "SINGLE_SPACE_STATION":
                    if hasattr(self, 'tab_victim'):
                        objs_to_scan.append(self.tab_victim)
                elif sys_mode == "SINGLE_EARTH_STATION":
                    if hasattr(self, 'tab_station'):
                        objs_to_scan.append(self.tab_station)

                # Iterate through all targets (Self + Tab)
                for target_obj in objs_to_scan:
                    if not target_obj: continue

                    # A. Explicit Dictionaries (for organized tabs)
                    sources = [
                        getattr(target_obj, 'vars', {}),
                        getattr(getattr(target_obj, 'state', None), 'vars', {})
                    ]
                    for src in sources:
                        if isinstance(src, dict):
                            for k, v in src.items():
                                try: data[k] = v.get()
                                except: data[k] = v

                    # B. Attribute Scanning (The catch-all)
                    # Scans for loose variables (Tkinter vars or simple types)
                    for attr_name in dir(target_obj):
                        if attr_name.startswith("_"): continue # Skip private attrs
                        
                        try:
                            val = getattr(target_obj, attr_name)
                            
                            # 1. Tkinter Variables
                            if isinstance(val, (tk.StringVar, tk.DoubleVar, tk.IntVar, tk.BooleanVar)):
                                data[attr_name] = val.get()
                            
                            # 2. Simple Types (Configs/Lists/Dicts)
                            elif isinstance(val, (list, dict, int, float, str, bool)):
                                # Filter out methods/callables to avoid noise
                                if not callable(val):
                                    data[attr_name] = val
                        except:
                            pass

                return data

            # Register Data Collectors
            self.tab_general.register_data_collector(get_imt_live_data)
            self.tab_general.register_data_collector(get_system_live_data)

    def _on_system_changed(self, *args):
        self._refresh_sidebar_items()

    def _refresh_sidebar_items(self):
        sys_type = self.var_system.get()
        for btn in self.nav_buttons.values():
            btn.pack_forget()

        for key, label, _, _ in self.pages_config:
            should_show = True
            if sys_type == "SINGLE_EARTH_STATION":
                if key == "victim": should_show = False
                if key == "station": should_show = True
            elif sys_type == "SINGLE_SPACE_STATION":
                if key == "station": should_show = False
                if key == "victim": should_show = True
            else:
                if key == "victim": should_show = False

            if should_show:
                self.nav_buttons[key].pack(fill="x", pady=2, padx=10)

        if self.current_key and not self.nav_buttons[self.current_key].winfo_ismapped():
            self._switch_page("general")

    def _switch_page(self, key, label_text=None):
        # Auto-save countries text if switching away from IMT (Optional sync)
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

    def _show_welcome_toast(self):
        ToastNotification(
            title="SHARC", message="System Ready.\nTheme: Cosmo Light",
            duration=3000, bootstyle="light", position=(40, 60, "ne")
        ).show_toast()

    def _show_success_toast(self, msg):
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

    # =========================================================================
    # COMPATIBILITY METHODS & PROXIES (LINKING MAIN BUTTON TO GENERAL TAB)
    # =========================================================================

    def current_yaml_dict(self) -> dict:
        """
        Generates the current configuration dictionary (Snapshot).
        Required by PreviewTab to display the YAML.
        
        USES THE GOOD OLD BUILDER: build_yaml_structure
        """
        if hasattr(self, 'tab_imt') and hasattr(self.tab_imt, 'txt_countries'):
            try:
                self.topo_countries.set(
                    self.tab_imt.txt_countries.get("1.0", "end"))
            except:
                pass
        
        # Aqui usamos o builder robusto diretamente
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
                # 1. Generate Data using the Good Old Builder
                data = build_yaml_structure(self)
                
                # 2. Save File
                with open(path, 'w', encoding='utf-8') as f:
                    yaml.dump(data, f, default_flow_style=False, sort_keys=False)
                
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
            try: return obj.format(**combo)
            except: return obj
        return obj


if __name__ == "__main__":
    app = App()
    app.mainloop()