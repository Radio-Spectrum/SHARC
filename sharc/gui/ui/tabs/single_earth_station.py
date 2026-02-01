import tkinter as tk
from tkinter import ttk

from ui.tabs.assets.ses_tab.ses_sections import SESBasicSection, SESGeometrySection, SESAntennaSection, SESChannelSection
from ui.tabs.assets.ses_tab.ses_persistence import SESPersistence


class SingleEarthStationTab:
    """
    Manages the 'Single Earth Station' configuration tab.
    Acts as a coordinator for specialized UI sections.
    """

    def __init__(self, app, parent_frame):
        self.app = app
        self.frame = parent_frame

        # Section Controllers
        self.geom_section = None
        self.ant_section = None
        self.chan_section = None

        self._build_ui()
        self._setup_sync_logic()

    def _build_ui(self):
        # Top Bar
        topbar = ttk.Frame(self.frame)
        topbar.pack(fill="x", pady=(0, 6), side="top")
        actions = ttk.Frame(topbar)
        actions.pack(side="right")

        ttk.Button(actions, text="Save Config", command=lambda: SESPersistence.save_to_file(
            self.app)).pack(side="left", padx=(0, 6))
        ttk.Button(actions, text="Load Config",
                   command=self._load_config_wrapper).pack(side="left")

        # Scroll Area
        self._setup_scroll_area()

        # Build Sections
        SESBasicSection.build(self.scrollable_frame, self.app)
        self.geom_section = SESGeometrySection(self.scrollable_frame, self.app)
        self.ant_section = SESAntennaSection(self.scrollable_frame, self.app)
        self.chan_section = SESChannelSection(self.scrollable_frame, self.app)

        # Bottom Padding
        ttk.Frame(self.scrollable_frame, height=30).pack(fill="x")

        # Init Visibility
        self.geom_section.refresh_all()
        self.ant_section.refresh()
        self.chan_section.refresh()

    def _setup_scroll_area(self):
        canvas_frame = ttk.Frame(self.frame)
        canvas_frame.pack(fill="both", expand=True, side="top")

        self.canvas = tk.Canvas(canvas_frame)
        scrollbar = ttk.Scrollbar(
            canvas_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.scrollable_frame, anchor="nw")

        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(
            self.canvas_window, width=e.width))
        self.canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self._bind_mouse_scroll(self.canvas)
        self._bind_mouse_scroll(self.scrollable_frame)

    def _bind_mouse_scroll(self, widget):
        widget.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(
            int(-1*(e.delta/120)), "units") if e.delta else None)
        widget.bind(
            "<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        widget.bind(
            "<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))

    def _setup_sync_logic(self):
        """Syncs heights between main parameters and channel model variables."""
        def _sync(*_):
            self.app.p452_Hre.set(self.app.se_height.get())
            # Try to grab other heights if they exist in the app
            if hasattr(self.app, 'bs_height') and hasattr(self.app, 'ue_height') and hasattr(self.app, 'var_imt_link'):
                if self.app.var_imt_link.get() == "DOWNLINK":
                    self.app.p452_Hte.set(self.app.bs_height.get())
                else:
                    self.app.p452_Hte.set(self.app.ue_height.get())

        self.app.se_height.trace_add("write", _sync)
        _sync()

    def _load_config_wrapper(self):
        """Callback to refresh UI sections after loading data."""
        def refresh_all():
            self.geom_section.refresh_all()
            self.ant_section.refresh()
            self.chan_section.refresh()

        SESPersistence.load_from_file(self.app, refresh_callback=refresh_all)
