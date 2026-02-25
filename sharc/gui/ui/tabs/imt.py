import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from pathlib import Path
import json

# --- Project Imports ---
# Ensure these modules exist in your project structure
from ui.tabs.assets.imt_tab.imt_state import IMTStateManager
from ui.tabs.assets.imt_tab.imt_sections import IMTSections
from ui.tabs.assets.imt_tab.imt_topology import IMTTopologySection


class IMTTab:
    """
    Main controller for the IMT Configuration Tab.

    Features:
    - High-visibility top toolbar for Save/Load presets (JSON).
    - Scrollable layout to handle complex configuration sections.
    - Integration with IMTStateManager for tracking simulation variables.
    - Orchestrates specialized sections (General, Topology, BS, UE, Channel).
    """

    def __init__(self, app, parent_frame: tk.Widget):
        """
        Initialize the IMT Tab.

        :param app: The main application controller.
        :param parent_frame: The parent widget where this tab is displayed.
        """
        self.app = app
        self.frame = parent_frame

        # State Manager: Holds the Tkinter variables for this tab
        self.state = IMTStateManager()

        # =====================================================================
        # [CRITICAL FIX] CONVERSÃO DE VARIÁVEIS PARA SUPORTAR TAGS {var}
        # =====================================================================
        # O IMTStateManager original cria DoubleVar/IntVar que impedem texto.
        # Aqui convertemos tudo para StringVar para aceitar "{teste}".
        if hasattr(self.state, 'vars'):
            new_vars = {}
            for k, v in self.state.vars.items():
                # Se for variável numérica estrita, converte para StringVar
                if isinstance(v, (tk.DoubleVar, tk.IntVar)):
                    val = v.get()
                    # Recria como string mantendo o valor atual
                    new_vars[k] = tk.StringVar(value=str(val))
                else:
                    new_vars[k] = v

            # Substitui o dicionário de variáveis pelo novo convertido
            self.state.vars = new_vars
        # =====================================================================

        # Component references
        self.topo_section = None
        self.inner_frame = None

        # Build Interface
        self._build_top_toolbar()
        self._setup_scroll_container()
        self._build_content()

    # =========================================================================
    # UI CONSTRUCTION
    # =========================================================================

    def _build_top_toolbar(self):
        """
        Creates a high-visibility top toolbar containing File Operations.
        Uses a 'primary' colored Menubutton to match the General Tab style.
        """
        toolbar_frame = ttk.Frame(self.frame)
        toolbar_frame.pack(side="top", fill="x", padx=5, pady=(10, 10))

        # File Menu Button (Cascade Style)
        # bootstyle='primary' makes it stand out (Solid Blue usually)
        self.btn_files = ttk.Menubutton(
            toolbar_frame,
            text="📁 File Operations (Presets)",
            bootstyle="primary",
            width=25
        )
        self.btn_files.pack(side="left")

        # Dropdown Menu
        self.menu_files = tk.Menu(self.btn_files, tearoff=0)
        self.btn_files.configure(menu=self.menu_files)

        self.menu_files.add_command(
            label="💾 Save IMT Preset (.json)",
            command=self.save_config
        )
        self.menu_files.add_command(
            label="📂 Load IMT Preset (.json)",
            command=self.load_config
        )

        # Visual Separator below toolbar
        ttk.Separator(self.frame, orient="horizontal").pack(
            fill="x", pady=(0, 5))

    def _setup_scroll_container(self):
        """
        Sets up the vertical scrollbar and canvas infrastructure.
        This enables the tab to hold more content than fits on the screen.
        """
        container = ttk.Frame(self.frame)
        container.pack(fill="both", expand=True)

        # Canvas Setup
        canvas = tk.Canvas(container, highlightthickness=0)
        vsb = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)

        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # Inner Frame (Content Holder)
        self.inner_frame = ttk.Frame(canvas)
        canvas_window = canvas.create_window(
            (0, 0), window=self.inner_frame, anchor="nw")

        # Events to resize scroll region dynamically
        def _configure_scroll(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(canvas_window, width=canvas.winfo_width())

        self.inner_frame.bind("<Configure>", _configure_scroll)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(
            canvas_window, width=e.width))

        # Mousewheel Support
        def _on_mousewheel(event):
            if self.inner_frame.winfo_exists():
                # Cross-platform scroll direction adjustment (Windows/MacOS)
                delta = int(-1 * (event.delta / 120))
                canvas.yview_scroll(delta, "units")

        # Binding mousewheel globally (Note: this might affect other tabs if not handled carefully,
        # but is standard for simple Tkinter scroll implementations).
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind_all(
            # Linux Up
            "<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind_all(
            # Linux Down
            "<Button-5>", lambda e: canvas.yview_scroll(1, "units"))

    def _build_content(self):
        """
        Assembles the UI components inside the scrollable frame.
        Delegates detailed UI construction to helper classes (IMTSections).
        """
        # 1. General Parameters Section
        IMTSections.build_general(self.inner_frame, self.state)

        # 2. Topology Section (Complex Logic managed by IMTTopologySection class)
        self.topo_section = IMTTopologySection(self.inner_frame, self.state)

        # 3. Technical Sections (Base Station, User Equipment, Channel Model)
        IMTSections.build_bs(self.inner_frame, self.state)
        IMTSections.build_ue(self.inner_frame, self.state)
        IMTSections.build_channel(self.inner_frame, self.state)

    # =========================================================================
    # PRESET LOGIC (SAVE / LOAD)
    # =========================================================================

    def save_config(self):
        """
        Collects all UI states (variables + text fields) and saves them to a JSON file.
        Includes error handling.
        """
        data = {"config_type": "IMT"}

        # 1. Collect Variables from State Manager
        # Iterates over the 'vars' dictionary in the state manager.
        if hasattr(self.state, 'vars') and isinstance(self.state.vars, dict):
            for key, var in self.state.vars.items():
                try:
                    # Save the value of the Tkinter variable
                    data[key] = var.get()
                except Exception:
                    # Skip items that aren't valid Tkinter variables or are empty
                    pass

        # 2. Collect Extra Data (e.g., Free Text from Topology)
        if self.topo_section:
            # We assume 'get_countries_text' returns a string from a Text widget
            data["countries_text"] = self.topo_section.get_countries_text()

        # 3. Write to File
        fpath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("IMT Configuration", "*.json")],
            title="Save IMT Preset"
        )
        if fpath:
            try:
                with open(fpath, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
                messagebox.showinfo(
                    "Success", f"Preset saved to:\n{Path(fpath).name}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save preset:\n{e}")

    def load_config(self):
        """
        Loads a JSON file, updates State Manager variables, and refreshes the UI.
        """
        fpath = filedialog.askopenfilename(
            filetypes=[("IMT Configuration", "*.json")],
            title="Load IMT Preset"
        )
        if not fpath:
            return

        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 1. Restore Variables into State Manager
            if hasattr(self.state, 'vars') and isinstance(self.state.vars, dict):
                for key, value in data.items():
                    if key in self.state.vars:
                        try:
                            self.state.vars[key].set(value)
                        except Exception as e:
                            print(
                                f"Warning: Could not set variable '{key}': {e}")

            # 2. Restore UI Specifics (Topology Text, Visibility)
            if self.topo_section:
                # Trigger internal logic updates based on loaded variables
                # (e.g., hiding/showing frames based on dropdowns)
                self.topo_section.toggle_visibility()
                self.topo_section._toggle_raster_state()

                # Restore text widget content
                if "countries_text" in data:
                    self.topo_section.set_countries_text(
                        data["countries_text"])
                # Fallback for legacy key compatibility
                elif "countries" in data:
                    self.topo_section.set_countries_text(data["countries"])

            messagebox.showinfo(
                "Success", "Configuration loaded successfully!")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load preset:\n{e}")
