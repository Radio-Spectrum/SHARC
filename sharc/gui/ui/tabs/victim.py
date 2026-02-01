import tkinter as tk
from tkinter import ttk

# Import manager
from ui.tabs.assets.victim_tab.victim_state import VictimStateManager
from ui.tabs.assets.victim_tab.victim_sections import VictimBasicSection, VictimP619Section, VictimGeometrySection, VictimAntennaSection


class VictimTab:
    """
    Manages the 'Victim' configuration tab.
    Orchestrates the UI sections and delegates state management.
    """

    def __init__(self, app, parent_frame):
        self.app = app
        self.frame = parent_frame

        self.state = VictimStateManager()
        self.ant_section = None  # Reference needed for callbacks

        self._build_ui()

    def _build_ui(self):
        """Constructs the user interface elements."""

        # --- Topbar ---
        topbar = ttk.Frame(self.frame)
        topbar.pack(fill="x", pady=(0, 6))

        ttk.Button(topbar, text="Save Config (.json)",
                   command=self.state.save_to_file).pack(side="left")

        # Load needs to refresh the Antenna UI after setting variables
        ttk.Button(topbar, text="Load Config (.json)",
                   command=self._load_config_wrapper).pack(side="left", padx=(6, 0))

        # --- Sections ---
        VictimBasicSection.build(self.frame, self.state)
        VictimP619Section.build(self.frame, self.state)
        VictimGeometrySection.build(self.frame, self.state)

        # Antenna Section (stored in self to access its refresh method)
        self.ant_section = VictimAntennaSection(self.frame, self.state)

    def _load_config_wrapper(self):
        """Loads config and triggers UI refresh."""
        self.state.load_from_file(callback_after_load=self.ant_section.refresh)
