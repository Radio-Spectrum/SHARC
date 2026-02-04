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
        Sets up the scrollable canvas infrastructure.
        Ensures the tab can hold more content than fits on the screen.
        """
        canvas_frame = ttk.Frame(self.frame)
        canvas_frame.pack(fill="both", expand=True, side="top")

        self.canvas = tk.Canvas(canvas_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(
            canvas_frame, orient="vertical", command=self.canvas.yview)

        self.scrollable_frame = ttk.Frame(self.canvas)

        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.scrollable_frame, anchor="nw")

        # Configure Scroll Events
        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))

        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(
            self.canvas_window, width=e.width))

        self.canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        # Mousewheel bindings
        self._bind_mouse_scroll(self.canvas)
        self._bind_mouse_scroll(self.scrollable_frame)

    def _bind_mouse_scroll(self, widget):
        """Binds mousewheel events for cross-platform scrolling."""
        # Windows / MacOS
        widget.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(
            int(-1*(e.delta/120)), "units") if e.delta else None)
        # Linux
        widget.bind(
            "<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        widget.bind(
            "<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))

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
            self.app.p452_Hre.set(self.app.se_height.get())

            # Sync Tx Height based on Link Direction (Downlink vs Uplink)
            if hasattr(self.app, 'bs_height') and hasattr(self.app, 'ue_height') and hasattr(self.app, 'var_imt_link'):
                if self.app.var_imt_link.get() == "DOWNLINK":
                    self.app.p452_Hte.set(self.app.bs_height.get())
                else:
                    self.app.p452_Hte.set(self.app.ue_height.get())

        # Trace the earth station height variable
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
                self.app.se_height.set(self.app.se_height.get())

            SESPersistence.load_from_file(
                self.app, refresh_callback=on_load_complete)

        except Exception as e:
            messagebox.showerror(
                "Error", f"Failed to load SES configuration:\n{e}")
