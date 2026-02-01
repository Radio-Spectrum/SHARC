import tkinter as tk
from tkinter import ttk

# Project imports
from ui.tabs.assets.imt_tab.imt_state import IMTStateManager
from ui.tabs.assets.imt_tab.imt_sections import IMTSections
from ui.tabs.assets.imt_tab.imt_topology import IMTTopologySection


class IMTTab:
    """
    Main controller for the IMT Configuration Tab.
    Orchestrates the specialized sections and manages the scrollable canvas.
    """

    def __init__(self, app, parent_frame: tk.Widget):
        self.app = app
        self.frame = parent_frame
        self.state = IMTStateManager()

        # Component references
        self.topo_section = None

        self._setup_scroll_container()
        self._build_content()

    def _setup_scroll_container(self):
        """Sets up the scrollable canvas infrastructure."""
        container = ttk.Frame(self.frame)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, highlightthickness=0)
        vsb = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)

        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self.inner_frame = ttk.Frame(canvas)
        canvas_window = canvas.create_window(
            (0, 0), window=self.inner_frame, anchor="nw")

        def _configure_scroll(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(canvas_window, width=canvas.winfo_width())

        self.inner_frame.bind("<Configure>", _configure_scroll)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(
            canvas_window, width=e.width))

        # Mousewheel Support
        def _on_mousewheel(event):
            if self.inner_frame.winfo_exists():
                delta = int(-1 * (event.delta / 120))
                canvas.yview_scroll(delta, "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind_all(
            "<Button-4>", lambda e: canvas.yview_scroll(-1, "units"))  # Linux
        canvas.bind_all(
            "<Button-5>", lambda e: canvas.yview_scroll(1, "units"))  # Linux

    def _build_content(self):
        """Assembles the UI components."""

        # 1. Top Bar
        topbar = ttk.Frame(self.inner_frame)
        topbar.pack(fill="x", pady=(0, 6))
        ttk.Button(topbar, text="Save IMT Config (.json)",
                   command=self._save).pack(side="left")
        ttk.Button(topbar, text="Load IMT Config (.json)",
                   command=self._load).pack(side="left", padx=(6, 0))

        # 2. General Parameters
        IMTSections.build_general(self.inner_frame, self.state)

        # 3. Topology (Complex Logic managed by class)
        self.topo_section = IMTTopologySection(self.inner_frame, self.state)

        # 4. BS & UE & Channel
        IMTSections.build_bs(self.inner_frame, self.state)
        IMTSections.build_ue(self.inner_frame, self.state)
        IMTSections.build_channel(self.inner_frame, self.state)

    def _save(self):
        """Delegates save logic, gathering extra text data from components."""
        extra = {}
        # Retrieve text from the topology section if it exists
        if self.topo_section:
            extra["countries"] = self.topo_section.get_countries_text()

        self.state.save_to_file(extra)

    def _load(self):
        """Delegates load logic and refreshes components."""
        data = self.state.load_from_file(
            callback_after_load=lambda d: self._refresh_ui_after_load(d)
        )

    def _refresh_ui_after_load(self, data):
        """Updates specific UI elements that aren't auto-bound variables."""
        if self.topo_section:
            # Refresh topology switches
            self.topo_section.toggle_visibility()
            self.topo_section._toggle_raster_state()

            # Manually set text widget content
            if "countries" in data:
                self.topo_section.set_countries_text(data["countries"])
