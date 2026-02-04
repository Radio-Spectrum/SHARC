import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from pathlib import Path
import json

# --- Project Imports ---
from ui.tabs.assets.victim_tab.victim_state import VictimStateManager
from ui.tabs.assets.victim_tab.victim_sections import (
    VictimBasicSection,
    VictimP619Section,
    VictimGeometrySection,
    VictimAntennaSection
)


class VictimTab:
    """
    Manages the 'Victim' configuration tab.

    Features:
    - High-visibility top toolbar for Save/Load presets.
    - Scrollable layout to handle multiple configuration sections.
    - Integration with VictimStateManager for variable tracking.
    """

    def __init__(self, app, parent_frame):
        """
        Initialize the Victim Tab.

        :param app: The main application controller.
        :param parent_frame: The parent widget where this tab is displayed.
        """
        self.app = app
        self.frame = parent_frame

        self.state = VictimStateManager()
        self.ant_section = None  # Reference needed for callbacks
        self.scrollable_frame = None

        # Build Interface
        self._build_top_toolbar()
        self._setup_scroll_area()
        self._build_content()

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
            label="💾 Save Victim Preset (.json)",
            command=self.save_config
        )
        self.menu_files.add_command(
            label="📂 Load Victim Preset (.json)",
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
        container = ttk.Frame(self.frame)
        container.pack(fill="both", expand=True, side="top")

        self.canvas = tk.Canvas(container, highlightthickness=0)
        vsb = ttk.Scrollbar(container, orient="vertical",
                            command=self.canvas.yview)

        self.scrollable_frame = ttk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.scrollable_frame, anchor="nw")

        # Configure Scroll Events
        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))

        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(
            self.canvas_window, width=e.width))

        self.canvas.configure(yscrollcommand=vsb.set)

        vsb.pack(side="right", fill="y")
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
        Constructs the user interface elements inside the scrollable frame.
        """
        # Pass self.scrollable_frame instead of self.frame to ensure scrolling
        VictimBasicSection.build(self.scrollable_frame, self.state)
        VictimP619Section.build(self.scrollable_frame, self.state)
        VictimGeometrySection.build(self.scrollable_frame, self.state)

        # Antenna Section (Store ref for refresh callback)
        self.ant_section = VictimAntennaSection(
            self.scrollable_frame, self.state)

        # Bottom Padding
        ttk.Frame(self.scrollable_frame, height=30).pack(fill="x")

    # =========================================================================
    # PRESET LOGIC (SAVE / LOAD)
    # =========================================================================

    def save_config(self):
        """
        Collects all UI states and saves them to a JSON file.
        Iterates over the VictimStateManager variables.
        """
        data = {}

        # 1. Collect Variables
        if hasattr(self.state, 'vars') and isinstance(self.state.vars, dict):
            for key, var in self.state.vars.items():
                try:
                    data[key] = var.get()
                except Exception:
                    pass

        # 2. Write to File
        fpath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("Victim Configuration", "*.json")],
            title="Save Victim Preset"
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
        Loads a JSON file, updates State Manager, and triggers UI refresh.
        """
        fpath = filedialog.askopenfilename(
            filetypes=[("Victim Configuration", "*.json")],
            title="Load Victim Preset"
        )
        if not fpath:
            return

        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 1. Restore Variables
            if hasattr(self.state, 'vars') and isinstance(self.state.vars, dict):
                for key, value in data.items():
                    if key in self.state.vars:
                        try:
                            self.state.vars[key].set(value)
                        except Exception as e:
                            print(
                                f"Warning: Could not set variable '{key}': {e}")

            # 2. Refresh UI (Antenna section often requires redraw based on mode)
            if self.ant_section:
                self.ant_section.refresh()

            messagebox.showinfo(
                "Success", "Configuration loaded successfully!")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load preset:\n{e}")
