import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *

# --- Project Imports ---
from ui.tabs.assets.ses_tab.ses_sections import (
    SESBasicSection,
    SESGeometrySection,
    SESAntennaSection,
    SESChannelSection
)
from ui.tabs.assets.ses_tab.ses_persistence import SESPersistence


class SingleEarthStationTab:
    """
    Manages the 'Single Earth Station' (SES) configuration tab.

    Features:
    - High-visibility top toolbar for Save/Load presets.
    - Scrollable layout for handling multiple configuration sections.
    - Synchronization logic for P.452 heights.
    - Integration with SESPersistence for data management.
    """

    def __init__(self, app, parent_frame):
        """
        Initialize the SES Tab.

        :param app: The main application controller.
        :param parent_frame: The parent widget where this tab is displayed.
        """
        self.app = app
        self.frame = parent_frame

        # =====================================================================
        # [CRITICAL FIX] GARANTIR VARIÁVEIS STRING PARA SES (Global State)
        # =====================================================================
        # Como o SES usa variáveis globais (self.app), varremos o app procurando
        # variáveis de prefixo 'se_' ou 'p452_' e convertemos para StringVar
        # caso ainda sejam numéricas estritas.
        for attr_name in dir(self.app):
            if attr_name.startswith(("se_", "p452_")):
                val = getattr(self.app, attr_name)
                if isinstance(val, (tk.DoubleVar, tk.IntVar)):
                    current_val = val.get()
                    # Substitui a variável no AppState por uma StringVar
                    setattr(self.app, attr_name, tk.StringVar(
                        value=str(current_val)))
        # =====================================================================

        # Section Controllers
        self.geom_section = None
        self.ant_section = None
        self.chan_section = None

        # Build Interface
        self._build_top_toolbar()
        self._setup_scroll_area()
        self._build_content()
        self._setup_sync_logic()

    # =========================================================================
    # UI CONSTRUCTION
    # =========================================================================

    def _build_top_toolbar(self):
        """
        Creates a high-visibility top toolbar containing File Operations.
        Uses a 'primary' colored Menubutton to stand out.
        """
        toolbar_frame = ttk.Frame(self.frame)
        toolbar_frame.pack(side="top", fill="x", padx=5, pady=(10, 10))

        # File Menu Button (Cascade Style)
        # bootstyle='primary' gives it a solid accent color
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
            label="💾 Save SES Config",
            command=self.save_config
        )
        self.menu_files.add_command(
            label="📂 Load SES Config",
            command=self.load_config
        )

        # Visual Separator
        ttk.Separator(self.frame, orient="horizontal").pack(
            fill="x", pady=(0, 5))

    def _setup_scroll_area(self):
        """
        No longer needs dedicated canvas as main.py provides ScrolledFrame.
        """
        self.scrollable_frame = ttk.Frame(self.frame)
        self.scrollable_frame.pack(fill="both", expand=True)

    def _build_content(self):
        """
        Constructs the main sections of the form inside the scrollable area.
        """
        # 1. Basic Parameters
        SESBasicSection.build(self.scrollable_frame, self.app)

        # 2. Geometry Section
        self.geom_section = SESGeometrySection(self.scrollable_frame, self.app)

        # 3. Antenna Section
        self.ant_section = SESAntennaSection(self.scrollable_frame, self.app)

        # 4. Channel Section
        self.chan_section = SESChannelSection(self.scrollable_frame, self.app)

        # Bottom Padding for aesthetics
        ttk.Frame(self.scrollable_frame, height=30).pack(fill="x")

        # Initial Refresh
        self._refresh_sections()

    def _refresh_sections(self):
        """Updates all subsections with current variable values."""
        if self.geom_section:
            self.geom_section.refresh_all()
        if self.ant_section:
            self.ant_section.refresh()
        if self.chan_section:
            self.chan_section.refresh()

    def _setup_sync_logic(self):
        """
        Syncs heights between main parameters and channel model variables.
        Ensures P.452 input fields match the basic geometry inputs.
        """
        def _sync(*_):
            # Sync Earth Station Height
            if hasattr(self.app, 'p452_Hre') and hasattr(self.app, 'se_height'):
                self.app.p452_Hre.set(self.app.se_height.get())

            # Sync Tx Height based on Link Direction (Downlink vs Uplink)
            if hasattr(self.app, 'bs_height') and hasattr(self.app, 'ue_height') and hasattr(self.app, 'var_imt_link') and hasattr(self.app, 'p452_Hte'):
                if self.app.var_imt_link.get() == "DOWNLINK":
                    self.app.p452_Hte.set(self.app.bs_height.get())
                else:
                    self.app.p452_Hte.set(self.app.ue_height.get())

        # Trace the earth station height variable
        if hasattr(self.app, 'se_height'):
            self.app.se_height.trace_add("write", _sync)
            # Trigger immediately
            _sync()

    # =========================================================================
    # PRESET LOGIC (SAVE / LOAD)
    # =========================================================================

    def save_config(self):
        """
        Triggers the Save logic via SESPersistence.
        """
        try:
            # We delegate to the Persistence class as it handles specific SES variable mapping
            SESPersistence.save_to_file(self.app)
        except Exception as e:
            messagebox.showerror(
                "Error", f"Failed to save SES configuration:\n{e}")

    def load_config(self):
        """
        Triggers the Load logic via SESPersistence and refreshes the UI.
        """
        try:
            # Callback to refresh UI after data is loaded into variables
            def on_load_complete():
                self._refresh_sections()
                # Optional: Re-trigger sync logic
                if hasattr(self.app, 'se_height'):
                    self.app.se_height.set(self.app.se_height.get())

            SESPersistence.load_from_file(
                self.app, refresh_callback=on_load_complete)

        except Exception as e:
            messagebox.showerror(
                "Error", f"Failed to load SES configuration:\n{e}")
