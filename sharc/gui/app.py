#!/usr/bin/env python3
"""Launcher for the SHARC GUI with virtualenv activation and splash screen."""

from __future__ import annotations

import importlib.util
import logging
import math
import os
import shutil
import subprocess
import sys
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageTk

GUI_DIR = Path(__file__).resolve().parent
PACKAGE_ROOT = GUI_DIR.parent
REPO_ROOT = PACKAGE_ROOT.parent
MAIN_MODULE_PATH = GUI_DIR / "main.py"
APP_ICON_PATH = PACKAGE_ROOT / "img" / "app_icon.gif"
SPLASH_VIDEO_PATH = PACKAGE_ROOT / "img" / "SHARC_splash_screen.mp4"
SPLASH_POSTER_PATH = PACKAGE_ROOT / "img" / "splash_frames" / f"{SPLASH_VIDEO_PATH.name}.png"
LOG_DIR = GUI_DIR / "logs"
LOG_FILE = LOG_DIR / "gui_startup.log"
SPLASH_STATIC_MIN_DURATION_MS = 1600
SPLASH_ANIMATION_DURATION_MS = 1200
RESAMPLE_LANCZOS = getattr(Image, "Resampling", Image).LANCZOS

logger = logging.getLogger("sharc.gui.launcher")


def _venv_python_path(venv_path: Path) -> Path:
    """Return the Python executable for the given virtualenv."""
    if sys.platform.startswith("win"):
        return venv_path / "Scripts" / "python.exe"
    return venv_path / "bin" / "python"


def _is_virtualenv_dir(path: Path) -> bool:
    """Check whether a directory looks like a valid Python virtual environment."""
    return path.is_dir() and (path / "pyvenv.cfg").is_file() and _venv_python_path(path).is_file()


def find_virtualenv() -> Path | None:
    """
    Locate the most relevant virtual environment for this project.

    Preference order:
    1. Currently active ``VIRTUAL_ENV`` when valid
    2. The active interpreter's prefix when running inside a venv
    3. Common repo-local names such as ``.venv`` and ``venv``
    4. Any matching venv nested inside the repository tree
    """
    candidates: list[Path] = []
    seen: set[Path] = set()

    def add_candidate(path: Path | None) -> None:
        if path is None:
            return
        resolved = path.expanduser().resolve()
        if resolved not in seen:
            seen.add(resolved)
            candidates.append(resolved)

    active_env = os.environ.get("VIRTUAL_ENV")
    if active_env:
        add_candidate(Path(active_env))

    if getattr(sys, "base_prefix", sys.prefix) != sys.prefix:
        add_candidate(Path(sys.prefix))

    for root in (REPO_ROOT, PACKAGE_ROOT, GUI_DIR):
        for name in (".venv", "venv", "env"):
            add_candidate(root / name)

    for root in (REPO_ROOT, PACKAGE_ROOT):
        if not root.is_dir():
            continue
        for name in (".venv", "venv", "env"):
            for path in root.rglob(name):
                add_candidate(path)

    for candidate in candidates:
        if _is_virtualenv_dir(candidate):
            return candidate

    return None


def _activate_current_process_venv(venv_path: Path) -> None:
    """Populate environment variables when already running inside the target venv."""
    python_dir = str(_venv_python_path(venv_path).parent)
    current_path = os.environ.get("PATH", "")
    path_parts = current_path.split(os.pathsep) if current_path else []

    os.environ["VIRTUAL_ENV"] = str(venv_path)
    if not path_parts or path_parts[0] != python_dir:
        os.environ["PATH"] = os.pathsep.join([python_dir, *path_parts]) if path_parts else python_dir


def ensure_virtualenv() -> Path:
    """
    Re-execute this launcher inside the project virtual environment.

    The simulator is only opened after a valid virtual environment is found and
    activated.
    """
    venv_path = find_virtualenv()
    if venv_path is None:
        raise RuntimeError(
            "No Python virtual environment was found for SHARC. "
            "Create or restore a project .venv before opening the simulator."
        )

    current_python = Path(sys.executable).resolve()
    target_python = _venv_python_path(venv_path).resolve()

    if current_python == target_python:
        _activate_current_process_venv(venv_path)
        return venv_path

    env = os.environ.copy()
    bin_dir = str(target_python.parent)
    env["VIRTUAL_ENV"] = str(venv_path)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"

    argv = [str(target_python), str(Path(__file__).resolve()), *sys.argv[1:]]
    os.execve(str(target_python), argv, env)
    raise RuntimeError("Failed to re-launch SHARC inside the detected virtual environment.")


def configure_logging() -> None:
    """Configure launcher logging once."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    if logger.handlers:
        return

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    file_handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.propagate = False


def ensure_splash_poster() -> Path | None:
    """Return a poster image derived from the splash artwork video."""
    if SPLASH_POSTER_PATH.is_file():
        return SPLASH_POSTER_PATH

    if not SPLASH_VIDEO_PATH.is_file():
        logger.warning("Splash video not found at %s", SPLASH_VIDEO_PATH)
        return None

    qlmanage_path = shutil.which("qlmanage")
    if qlmanage_path is None:
        logger.warning("Quick Look is not available; falling back to default splash art.")
        return None

    SPLASH_POSTER_PATH.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [qlmanage_path, "-t", "-s", "1600", "-o", str(SPLASH_POSTER_PATH.parent), str(SPLASH_VIDEO_PATH)],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        details = (result.stderr or result.stdout).strip()
        logger.warning("Failed to extract splash poster from video: %s", details)
        return None

    if SPLASH_POSTER_PATH.is_file():
        return SPLASH_POSTER_PATH

    logger.warning("Quick Look finished without creating the splash poster image.")
    return None


class SplashScreen(tk.Frame):
    """Artwork-driven splash overlay shown while the GUI prepares the app."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, bg="#0A1624", highlightthickness=0, borderwidth=0)
        self.status_var = tk.StringVar(value="Preparing SHARC environment...")
        self.detail_var = tk.StringVar(value="Loading interface modules...")
        self._poster_path = ensure_splash_poster()
        self._base_image = self._load_base_image()
        self._photo_image: ImageTk.PhotoImage | None = None
        self._progress_value = 0.0
        self.window_width, self.window_height = self._base_image.size
        self._overlay_height = max(92, int(self.window_height * 0.18))
        self._progress_left = 28
        self._progress_right = self.window_width - 28
        self._progress_top = self.window_height - 24
        self._progress_bottom = self.window_height - 12

        self._build_ui()
        self._apply_frame(self._base_image)
        self.place(x=0, y=0, width=self.window_width, height=self.window_height)
        self.lift()
        self.update_idletasks()

    def _load_base_image(self) -> Image.Image:
        """Load the splash artwork and scale it to a display-friendly size."""
        self.master.update_idletasks()
        target_width = self.master.winfo_width()
        target_height = self.master.winfo_height()
        if target_width <= 1 or target_height <= 1:
            target_width = min(1440, max(800, int(self.master.winfo_screenwidth() * 0.85)))
            target_height = min(900, max(600, int(self.master.winfo_screenheight() * 0.85)))

        if self._poster_path is not None and self._poster_path.is_file():
            with Image.open(self._poster_path) as raw_image:
                image = raw_image.convert("RGBA")
        else:
            image = Image.new("RGBA", (1280, 720), "#0F1E33")
            if APP_ICON_PATH.is_file():
                try:
                    with Image.open(APP_ICON_PATH) as raw_icon:
                        icon = raw_icon.convert("RGBA")
                    icon = icon.resize((240, 240), RESAMPLE_LANCZOS)
                    dest = ((image.width - icon.width) // 2, (image.height - icon.height) // 2 - 40)
                    image.alpha_composite(icon, dest=dest)
                except Exception:
                    logger.warning("Could not load fallback app icon for splash.", exc_info=True)

        return image.resize((target_width, target_height), RESAMPLE_LANCZOS)

    def _build_ui(self) -> None:
        self.canvas = tk.Canvas(
            self,
            width=self.window_width,
            height=self.window_height,
            highlightthickness=0,
            borderwidth=0,
            bg="#0A1624",
        )
        self.canvas.pack(fill="both", expand=True)

        self.image_item = self.canvas.create_image(0, 0, anchor="nw")
        self.canvas.create_rectangle(
            0,
            self.window_height - self._overlay_height,
            self.window_width,
            self.window_height,
            fill="#071320",
            outline="",
            stipple="gray50",
        )
        self.canvas.create_text(
            28,
            self.window_height - self._overlay_height + 18,
            anchor="w",
            text="SHARC simulator",
            fill="#50D9FF",
            font=("Segoe UI", 11, "bold"),
        )
        self.status_item = self.canvas.create_text(
            28,
            self.window_height - self._overlay_height + 46,
            anchor="w",
            text=self.status_var.get(),
            fill="#F1FAFF",
            font=("Segoe UI", 18, "bold"),
        )
        self.detail_item = self.canvas.create_text(
            28,
            self.window_height - self._overlay_height + 76,
            anchor="w",
            text=self.detail_var.get(),
            fill="#B7D8EA",
            font=("Segoe UI", 11),
        )

        self.progress_track = self.canvas.create_rectangle(
            self._progress_left,
            self._progress_top,
            self._progress_right,
            self._progress_bottom,
            fill="#10273C",
            outline="",
        )
        self.progress_fill = self.canvas.create_rectangle(
            self._progress_left,
            self._progress_top,
            self._progress_left,
            self._progress_bottom,
            fill="#2DE2FF",
            outline="",
        )

    def _apply_frame(self, image: Image.Image) -> None:
        """Render an animation frame on the splash canvas."""
        self._photo_image = ImageTk.PhotoImage(image)
        self.canvas.itemconfigure(self.image_item, image=self._photo_image)

    def _zoom_frame(self, zoom_factor: float) -> Image.Image:
        """Create a centered zoom of the splash artwork."""
        if zoom_factor <= 1.0:
            return self._base_image.copy()

        scaled_width = max(self.window_width, int(self.window_width * zoom_factor))
        scaled_height = max(self.window_height, int(self.window_height * zoom_factor))
        scaled = self._base_image.resize((scaled_width, scaled_height), RESAMPLE_LANCZOS)
        left = (scaled_width - self.window_width) // 2
        top = (scaled_height - self.window_height) // 2
        return scaled.crop((left, top, left + self.window_width, top + self.window_height))

    def _compose_animation_frame(self, progress: float) -> Image.Image:
        """Generate a polished launch animation from the splash artwork (Fallback)."""
        eased = 0.5 - 0.5 * math.cos(progress * math.pi)
        frame = self._zoom_frame(1.0 + 0.045 * eased)
        frame = ImageEnhance.Brightness(frame).enhance(1.0 + 0.08 * math.sin(progress * math.pi))

        overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        band_width = max(120, int(frame.width * 0.16))
        band_center = int((frame.width + band_width * 3) * progress) - band_width
        draw.rectangle(
            [band_center - band_width, 0, band_center + band_width, frame.height],
            fill=(69, 233, 255, 56),
        )
        overlay = overlay.filter(ImageFilter.GaussianBlur(radius=max(24, frame.width // 40)))
        return Image.alpha_composite(frame, overlay)

    def set_status(self, text: str, detail: str | None = None) -> None:
        """Update the current splash screen messages."""
        self.status_var.set(text)
        self.canvas.itemconfigure(self.status_item, text=text)
        if detail is not None:
            self.detail_var.set(detail)
            self.canvas.itemconfigure(self.detail_item, text=detail)
        self.update_idletasks()

    def set_progress(self, value: float) -> None:
        """Set splash progress explicitly."""
        self._progress_value = max(0.0, min(100.0, value))
        fill_right = self._progress_left + (
            (self._progress_right - self._progress_left) * (self._progress_value / 100.0)
        )
        self.canvas.coords(
            self.progress_fill,
            self._progress_left,
            self._progress_top,
            fill_right,
            self._progress_bottom,
        )
        self.update_idletasks()

    def step_progress(self, amount: float) -> None:
        """Advance the progress bar."""
        self.set_progress(self._progress_value + amount)

    def play_launch_animation(self, on_complete=None, duration_ms: int = SPLASH_ANIMATION_DURATION_MS) -> None:
        """Animate the artwork asynchronously before handing over to the main simulator window."""
        self.canvas.itemconfigure(self.progress_track, state="hidden")
        self.canvas.itemconfigure(self.progress_fill, state="hidden")
        self.set_status("Simulator ready", "Starting SHARC...")

        # Try using OpenCV to play the actual MP4 video
        try:
            import cv2
            if SPLASH_VIDEO_PATH.is_file():
                cap = cv2.VideoCapture(str(SPLASH_VIDEO_PATH))
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_delay = max(1, int(1000 / fps)) if fps > 0 else 33

                def play_video_frame():
                    ret, frame = cap.read()
                    if not ret:
                        # Video ended
                        cap.release()
                        if on_complete:
                            on_complete()
                        return

                    # Convert frame from BGR (OpenCV) to RGB (Pillow)
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    image = Image.fromarray(frame_rgb)
                    
                    # Resize to cover the splash screen window
                    image = image.resize((self.window_width, self.window_height), RESAMPLE_LANCZOS)
                    
                    self._apply_frame(image)
                    self.update_idletasks()
                    
                    # Schedule the next frame
                    self.after(frame_delay, play_video_frame)

                play_video_frame()
                return
        except ImportError:
            logger.warning("OpenCV is not installed. Using synthetic fallback animation. Run: pip install opencv-python")
        except Exception as e:
            logger.warning(f"Error attempting to play the splash video: {e}")

        # Fallback: If OpenCV is missing or the video fails, use the original synthetic animation
        steps = max(12, duration_ms // 33)
        frame_delay = max(1, duration_ms // steps)

        def do_step(index=0):
            if index > steps:
                if on_complete:
                    on_complete()
                return
            progress = index / steps
            self._apply_frame(self._compose_animation_frame(progress))
            self.update_idletasks()
            self.after(frame_delay, do_step, index + 1)

        do_step()


def load_main_module():
    """Load ``sharc/gui/main.py`` from disk without spawning a subprocess."""
    if not MAIN_MODULE_PATH.is_file():
        raise FileNotFoundError(f"main.py not found at {MAIN_MODULE_PATH}")

    spec = importlib.util.spec_from_file_location("sharc_gui_main", MAIN_MODULE_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load spec for {MAIN_MODULE_PATH}")

    module = importlib.util.module_from_spec(spec)

    if str(GUI_DIR) not in sys.path:
        sys.path.insert(0, str(GUI_DIR))

    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    return module


def show_error_dialog(title: str, message: str) -> None:
    """Display an error dialog when the GUI cannot be started."""
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(title, message, parent=root)
        root.destroy()
    except tk.TclError:
        pass


def launch_main() -> int:
    """Show the splash screen, load the main GUI, and start the application as an async sequence."""
    start_time = time.perf_counter()
    exit_code = [0]
    app = None
    splash = None

    try:
        main_module = load_main_module()
        app = main_module.App(defer_ui_init=True)
        app.update_idletasks()
        app.lift()

        splash = SplashScreen(app)
        splash.set_status("Preparing SHARC launcher...", "Activating the simulator environment...")
        splash.set_progress(20)

        def _handle_error(exc: Exception) -> None:
            """Catch errors inside the event callbacks without crashing silently."""
            logger.exception("Failed to launch SHARC GUI: %s", exc)
            if splash is not None:
                try: splash.destroy()
                except tk.TclError: pass
            if app is not None:
                try: app.destroy()
                except tk.TclError: pass
            show_error_dialog("SHARC Launcher Error", f"Unable to start the simulator.\n\n{exc}")
            exit_code[0] = 1
            if app: app.quit()

        def phase1():
            try:
                splash.set_status("Loading interface modules...", "Applying the SHARC splash artwork...")
                splash.set_progress(40)
                app.after(100, phase2)
            except Exception as e: _handle_error(e)

        def phase2():
            try:
                splash.set_status("Building the simulator interface...", "Loading panels, meters and controls...")
                splash.set_progress(60)
                app.after(50, phase3)
            except Exception as e: _handle_error(e)

        def phase3():
            try:
                # The initializer now runs INSIDE the active mainloop,
                # fixing background thread errors in Tkinter
                app.initialize_ui()
                splash.lift()
                splash.set_progress(82)

                elapsed_ms = int((time.perf_counter() - start_time) * 1000)
                remaining_ms = max(0, SPLASH_STATIC_MIN_DURATION_MS - elapsed_ms)
                splash.set_status("Modules loaded", "Preparing the simulator window...")
                app.after(remaining_ms, phase4)
            except Exception as e: _handle_error(e)

        def phase4():
            try:
                splash.set_progress(100)
                splash.set_status("Interface ready", "Opening the simulator...")
                splash.play_launch_animation(on_complete=phase5)
            except Exception as e: _handle_error(e)

        def phase5():
            try:
                splash.destroy()
                app.update_idletasks()
                app.lift()
                try: app.focus_force()
                except tk.TclError: pass
                logger.info("SHARC GUI initialized successfully.")
            except Exception as e: _handle_error(e)

        # Starts the asynchronous sequence
        app.after(100, phase1)
        
        # Start the main loop now! This avoids thread collisions from _render_worker
        app.mainloop()
        
        logger.info("SHARC GUI closed normally.")
        return exit_code[0]

    except Exception as exc:
        logger.exception("Failed to launch SHARC GUI: %s", exc)
        if app is not None:
            try: app.destroy()
            except tk.TclError: pass
        if splash is not None:
            try: splash.destroy()
            except tk.TclError: pass
        show_error_dialog(
            "SHARC Launcher Error",
            f"Unable to start the simulator.\n\n{exc}",
        )
        return 1


def main() -> int:
    """Run the SHARC GUI launcher."""
    configure_logging()

    try:
        venv_path = ensure_virtualenv()
    except Exception as exc:
        logger.exception("Virtual environment setup failed: %s", exc)
        show_error_dialog(
            "SHARC Virtual Environment Error",
            f"Unable to activate the SHARC virtual environment.\n\n{exc}",
        )
        return 1

    logger.info("=== Launching SHARC GUI ===")
    logger.info("Launcher PID: %s", os.getpid())
    logger.info("Current interpreter: %s", sys.executable)
    logger.info("Using virtual environment at %s", venv_path)

    return launch_main()


if __name__ == "__main__":
    sys.exit(main())