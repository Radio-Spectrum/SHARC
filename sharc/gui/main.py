import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import tkinter.font as tkfont
import queue
import os
import itertools
import ast

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
from core.yaml_builder import build_yaml_structure

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
        self.__dict__.update(self.state_model.__dict__)

        # Set default system if empty to prevent empty sidebar on startup
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
        self.current_key = None  # Tracks which tab key is currently open
        self.current_frame = None
        self.frames = {}
        self.nav_buttons = {}

        # Page Configuration: (key, label, Class, icon)
        # We define this list here to maintain order and iterate easily
        self.pages_config = [
            ("general", "General", GeneralTab, "⚙"),
            ("imt", "IMT", IMTTab, "📡"),
            ("victim", "Victim", VictimTab, "🛰"),            # Exclusive to SINGLE_SPACE_STATION
            ("station", "Single Earth Station", SingleEarthStationTab, "🛰"), # Exclusive to SINGLE_EARTH_STATION
            ("preview", "Preview", PreviewTab, "👁"),
            ("runner", "Execution Runner", RunnerTab, "🚀"),
            ("results", "Results", ResultsTab, "📊"),
        ]

        # 4. Interface Construction
        self._setup_custom_styles()
        self._build_layout()
        self._init_pages()

        # 5. Logic: Observe changes in System Type to update Sidebar
        self.var_system.trace_add("write", self._on_system_changed)

        # 6. Start Loop
        self.after(100, self._drain_log_queue)

        # Force initial sidebar refresh based on default value
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
        style.configure("Nav.TButton", font=("Segoe UI", 11), anchor="w", padding=(20, 12))
        style.configure("Card.TFrame", background="#ffffff", relief="flat")

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
        self._build_system_monitor()

        # --- B. Header Bar (Top Right) ---
        self.header = tb.Frame(self, bootstyle="bg-white", height=70)
        self.header.grid(row=0, column=1, sticky="ew")
        self._build_header_content()
        tb.Separator(self.header, orient="horizontal", bootstyle="secondary").pack(side="bottom", fill="x")

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

        lbl = tb.Label(frame, text="SHARC", style="Brand.TLabel", bootstyle="inverse-light")
        lbl.pack(anchor="w")

        sub = tb.Label(frame, text="SIMULATION MANAGER", font=("Segoe UI", 9, "bold"),
                       foreground="#7F8C8D", bootstyle="inverse-light")
        sub.pack(anchor="w")

        tb.Separator(self.sidebar, bootstyle="secondary").pack(fill="x", padx=20, pady=15)

    def _build_system_monitor(self):
        monitor_frame = tb.Frame(self.sidebar, bootstyle="light", padding=15)
        monitor_frame.pack(side="bottom", fill="x", pady=10)

        tb.Label(monitor_frame, text="Global Progress", foreground="#7F8C8D",
                 font=("Segoe UI", 9, "bold"), bootstyle="inverse-light").pack(anchor="center", pady=5)

        self.sys_meter = Meter(
            monitor_frame,
            metersize=140,
            padding=5,
            amountused=0,
            metertype="full",
            subtext="Idle",
            interactive=False,
            bootstyle="primary",
            stripethickness=10
        )
        self.sys_meter.pack(anchor="center")

    def _build_header_content(self):
        self.lbl_page_title = tb.Label(self.header, text="Dashboard",
                                       font=("Segoe UI", 18), foreground="#2C3E50")
        self.lbl_page_title.pack(side="left", padx=30, pady=20)

        btn_save = tb.Button(self.header, text="Save Configuration", bootstyle="success",
                             command=self.save_yaml_dialog_multicombos)
        btn_save.pack(side="right", padx=30)
        ToolTip(btn_save, text="Generate and save YAML files with current configuration.")

    def _build_footer_content(self):
        # SSH Status
        f_ssh = tb.Frame(self.status_bar, bootstyle="primary", padding=(15, 5))
        f_ssh.pack(side="right", fill="y")
        tb.Label(f_ssh, textvariable=self.ssh_status, font=("Consolas", 9, "bold"),
                 bootstyle="inverse-primary").pack()

        tb.Label(self.status_bar, text="|", bootstyle="inverse-primary").pack(side="right")

        # Tunnel Status
        f_tun = tb.Frame(self.status_bar, bootstyle="primary", padding=(15, 5))
        f_tun.pack(side="right", fill="y")
        tb.Label(f_tun, textvariable=self.tunnel_status, font=("Consolas", 9),
                 bootstyle="inverse-primary").pack()

        # Log Message
        self.lbl_status_msg = tb.Label(self.status_bar, text="Ready.", font=("Segoe UI", 9),
                                       bootstyle="inverse-primary")
        self.lbl_status_msg.pack(side="left", padx=20)

    def _init_pages(self):
        """Initializes pages logic and buttons, but does NOT pack them yet."""

        for key, label, Cls, icon in self.pages_config:
            # 1. Create Menu Button (stored, but not packed)
            btn = tb.Button(
                self.menu_frame,
                text=f"  {icon}   {label}",
                style="Nav.TButton",
                bootstyle="secondary-link",
                command=lambda k=key, l=label: self._switch_page(k, l)
            )
            self.nav_buttons[key] = btn

            # 2. Visual Container
            container = tb.Frame(self.content_area)
            self.frames[key] = container

            # 3. Logic Instance
            instance = Cls(self, container)
            setattr(self, f"tab_{key}", instance)

    # --- Dynamic Visibility Logic ---

    def _on_system_changed(self, *args):
        """Callback triggered when var_system changes."""
        self._refresh_sidebar_items()

    def _refresh_sidebar_items(self):
        """Reorganizes sidebar items based on the selected system mode."""
        sys_type = self.var_system.get()

        # Unpack all buttons first
        for btn in self.nav_buttons.values():
            btn.pack_forget()

        # Re-pack buttons based on logic
        for key, label, _, _ in self.pages_config:
            should_show = True

            # Mutual exclusion logic (UPDATED MAPPING)
            if sys_type == "SINGLE_EARTH_STATION":
                if key == "victim": should_show = False   # Hide Victim (Space Station)
                if key == "station": should_show = True   # Show Station (Earth Station)

            elif sys_type == "SINGLE_SPACE_STATION":
                if key == "station": should_show = False  # Hide Station (Earth Station)
                if key == "victim": should_show = True    # Show Victim (Space Station)

            else:
                # Fallback behavior if empty or invalid
                if key == "victim": should_show = False   # Hide Victim by default

            if should_show:
                self.nav_buttons[key].pack(fill="x", pady=2, padx=10)

        # Safety: If the user is on a tab that just got hidden, switch to General
        if self.current_key:
            # Check if the current page's button is mapped (visible)
            if not self.nav_buttons[self.current_key].winfo_ismapped():
                self._switch_page("general")

    def _switch_page(self, key, label_text=None):
        """Switches the visible page."""

        # Sync IMT data (required for 3D visualization)
        if hasattr(self, 'tab_imt') and hasattr(self.tab_imt, 'txt_countries'):
            try:
                raw_txt = self.tab_imt.txt_countries.get("1.0", "end").strip()
                if raw_txt:
                    self.topo_countries.set(raw_txt)
            except Exception:
                pass

        # Update Title
        if label_text:
            self.lbl_page_title.config(text=label_text)
        elif key == "general":
            self.lbl_page_title.config(text="General Settings")

        # Hide current container
        if self.current_frame:
            self.current_frame.pack_forget()

        # Update button styles (Highlight active)
        for k, btn in self.nav_buttons.items():
            if k == key:
                btn.configure(bootstyle="primary")
            else:
                btn.configure(bootstyle="secondary-link")

        # Show new container
        self.current_frame = self.frames[key]
        self.current_frame.pack(fill="both", expand=True)
        self.current_key = key

        # Trigger Refresh (e.g., for Maps)
        if key == "preview":
            logic_instance = getattr(self, f"tab_{key}", None)
            if logic_instance:
                if hasattr(logic_instance, "refresh"):
                    logic_instance.refresh()
                elif hasattr(logic_instance, "update_plot"):
                    logic_instance.update_plot()

    def _show_welcome_toast(self):
        toast = ToastNotification(
            title="SHARC",
            message="System Ready.\nTheme: Cosmo Light",
            duration=3000,
            bootstyle="light",
            position=(40, 60, "ne")
        )
        toast.show_toast()

    def _show_success_toast(self, msg):
        toast = ToastNotification(
            title="Success",
            message=msg,
            duration=3000,
            bootstyle="success",
            position=(40, 60, "ne")
        )
        toast.show_toast()

    # --- Backend Logic & Logs ---

    def _safe_log(self, msg):
        self.line_q.put(("log", msg))

    def _safe_update_row(self, data):
        self.line_q.put(("row", data))

    def _drain_log_queue(self):
        try:
            for _ in range(50):
                item = self.line_q.get_nowait()
                msg_type, payload = item

                if msg_type == "log":
                    clean_msg = payload.strip()
                    if clean_msg:
                        self.lbl_status_msg.config(text=clean_msg[:120])

                    if hasattr(self.tab_runner, 'txt_log'):
                        w = self.tab_runner.txt_log
                        w.configure(state="normal")
                        w.insert("end", payload +
                                 ("\n" if not payload.endswith("\n") else ""))
                        w.see("end")
                        w.configure(state="disabled")

                elif msg_type == "row":
                    if hasattr(self.tab_runner, 'tree'):
                        tree = self.tab_runner.tree
                        iid = payload.get("iid")
                        if iid and tree.exists(iid):
                            cur = list(tree.item(iid, "values"))
                            if payload["status"] is not None:
                                cur[1] = payload["status"]
                            if payload["pct"] is not None:
                                cur[3] = payload["pct"]
                                try:
                                    pct_float = float(
                                        payload["pct"].strip('%'))
                                    self.sys_meter.configure(
                                        amountused=int(pct_float), subtext="Running")
                                except:
                                    pass
                            tree.item(iid, values=cur)
        except queue.Empty:
            pass
        except Exception:
            pass

        self.after(100, self._drain_log_queue)

    # --- YAML Generation ---

    def current_yaml_dict(self) -> dict:
        if hasattr(self, 'tab_imt') and hasattr(self.tab_imt, 'txt_countries'):
            try:
                txt = self.tab_imt.txt_countries.get("1.0", "end")
                self.topo_countries.set(txt)
            except:
                pass
        return build_yaml_structure(self)

    def _deep_format(self, obj, combo):
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

    def save_yaml_to_yamldir(self):
        self._generate_and_save_yaml(self.var_yaml_dir.get())

    def save_yaml_dialog_multicombos(self):
        initdir = self.var_yaml_dir.get() or os.getcwd()
        path = filedialog.asksaveasfilename(
            title="Choose base filename",
            defaultextension=".yaml",
            initialdir=initdir,
            initialfile=(self.var_prefix.get() or "scenario") + ".yaml"
        )
        if path:
            outdir = os.path.dirname(path)
            count = self._generate_and_save_yaml(outdir)
            self.var_yaml_dir.set(outdir)

    def _generate_and_save_yaml(self, outdir):
        if not outdir:
            return 0
        os.makedirs(outdir, exist_ok=True)

        tree = self.tab_general.var_table
        names, lists = [], []
        for iid in tree.get_children():
            name, vals = tree.item(iid, "values")
            try:
                vlist = ast.literal_eval(vals)
                names.append(str(name))
                lists.append(list(vlist))
            except:
                messagebox.showwarning(
                    "Error", f"Invalid values for variable {name}")
                return 0

        combos = [dict(zip(names, p))
                  for p in itertools.product(*lists)] if names else [{}]
        root = self.current_yaml_dict()
        base_prefix = root["general"]["output_dir_prefix"] or "scenario"

        count = 0
        for combo in combos:
            prefix = base_prefix
            try:
                prefix = prefix.format(**combo)
            except:
                pass

            root_fmt = self._deep_format(root, combo)
            text = build_yaml_text(root_fmt)
            fname = os.path.join(outdir, f"{prefix}.yaml")
            with open(fname, "w", encoding="utf-8") as f:
                f.write(text)
            count += 1

        self._show_success_toast(f"{count} scenarios generated in:\n{outdir}")
        return count


if __name__ == "__main__":
    app = App()
    app.mainloop()