"""Entry point of the installed (PyInstaller) SHARC build.

SHARC.exe          -> opens the GUI
SHARC.exe --sharc-cli -p <yaml>  -> runs one simulation (used by the GUI runner)
"""
import multiprocessing
import os
import sys


def _link_data(workspace, data_dir):
    """Make `<workspace>/sharc` a junction to the installed data.

    The engine resolves data files as `Path.cwd() / "sharc" / ...`; running from the
    workspace keeps those reads working while logs and outputs stay writable.
    """
    link = os.path.join(workspace, "sharc")
    try:
        if os.path.lexists(link):
            if os.path.realpath(link) == os.path.realpath(data_dir):
                return
            os.rmdir(link)  # stale junction (reinstall in another folder)
        import _winapi
        _winapi.CreateJunction(data_dir, link)
    except OSError:
        pass  # data stays reachable through sys.path; only cwd-relative lookups degrade


def _prepare_environment():
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    workspace = os.path.join(os.path.expanduser("~"), "Documents", "SHARC")
    os.makedirs(workspace, exist_ok=True)
    _link_data(workspace, os.path.join(base, "sharc"))
    os.chdir(workspace)
    # The GUI imports its own packages (ui, core, managers) by top-level name.
    for path in (base, os.path.join(base, "sharc"), os.path.join(base, "sharc", "gui")):
        if path not in sys.path:
            sys.path.insert(0, path)


def main():
    multiprocessing.freeze_support()
    _prepare_environment()
    if len(sys.argv) >= 3 and sys.argv[1] == "-m":
        # `sys.executable -m <module>` is this exe when frozen: behave like the interpreter.
        import runpy
        module = sys.argv[2]
        sys.argv = [module] + sys.argv[3:]
        runpy.run_module(module, run_name="__main__", alter_sys=True)
        return 0
    if "--sharc-cli" in sys.argv:
        args = [a for a in sys.argv[1:] if a != "--sharc-cli"]
        for stream in (sys.stdout, sys.stderr):
            if stream is not None:  # live progress for the GUI runner reading our pipe
                stream.reconfigure(line_buffering=True)
        from sharc.main_cli import main as cli_main
        cli_main(args)
        return 0
    from sharc.gui import main as sharc_gui
    sharc_gui.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
