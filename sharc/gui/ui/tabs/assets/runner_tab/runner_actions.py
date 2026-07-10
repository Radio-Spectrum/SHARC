"""
runner_actions.py
-----------------
Standalone action helpers for RunnerTab.

Each function receives the RunnerTab instance as ``tab`` and re-implements
the logic previously embedded as private methods in RunnerTab.  The original
methods in runner.py can delegate to these helpers or be replaced by them.

Functions
---------
scan_yaml_files(tab)
    Re-implements ``RunnerTab._scan_yaml_files``.

insert_job_row(tab, iid, yaml_name, status, snap, pct, eta, branch, location, host)
    Re-implements ``RunnerTab._insert_job_row``.

run_selected(tab)
    Re-implements ``RunnerTab._run_selected_ui``.

stop_selected(tab)
    Re-implements ``RunnerTab._stop_selected_ui``.
"""

import os
from datetime import datetime
from tkinter import messagebox


# ---------------------------------------------------------------------------
# scan_yaml_files
# ---------------------------------------------------------------------------

def scan_yaml_files(tab) -> None:
    """
    Scan YAML files (local folder or remote SSH directory) and populate
    ``tab.tree``.

    Mirrors ``RunnerTab._scan_yaml_files``.
    """
    # Clear tree but keep _jobs (schedule history).
    try:
        tab.tree.delete(*tab.tree.get_children())
    except Exception:
        pass

    mode = tab.app.var_run_mode.get()
    tab._append_log(f"[SCAN] Scanning files in mode: {mode}...")

    if mode == "LOCAL":
        folder = tab.app.run_folder.get()
        if os.path.isdir(folder):
            files = [
                f
                for f in os.listdir(folder)
                if f.lower().endswith((".yaml", ".yml"))
            ]
            files.sort()
            for f in files:
                full_path = os.path.join(folder, f)
                insert_job_row(
                    tab,
                    iid=full_path,
                    yaml_name=f,
                    status="Ready",
                    snap="0/--",
                    pct="0",
                    eta="--",
                    branch="(local)",
                    location=folder,
                    host="local",
                )
        else:
            tab._append_log(f"[ERR] Local folder not found: {folder}")

    elif mode == "SSH":
        if tab.manager and getattr(tab.manager, "ssh_connected", False):
            remote_dir = tab.app.ssh_remote_dir.get().strip()
            try:
                files = tab.manager.list_remote_files(remote_dir)
                for f in files:
                    fname = os.path.basename(f)
                    insert_job_row(
                        tab,
                        iid=f,
                        yaml_name=fname,
                        status="Ready",
                        snap="0/--",
                        pct="0",
                        eta="--",
                        branch=tab.app.var_git_branch.get() or "",
                        location=remote_dir,
                        host=tab._current_host_label(),
                    )
            except Exception as e:
                tab._append_log(f"[ERR] Error listing remote files: {e}")
        else:
            tab._append_log("[SSH] Not connected. Connect via SSH tab first.")


# ---------------------------------------------------------------------------
# insert_job_row
# ---------------------------------------------------------------------------

def insert_job_row(
    tab,
    iid: str,
    yaml_name: str,
    status: str,
    snap: str,
    pct: str,
    eta: str,
    branch: str,
    location: str,
    host: str,
) -> None:
    """
    Register a job in ``tab._jobs`` and insert (or update) a row in
    ``tab.tree``.

    Mirrors ``RunnerTab._insert_job_row``.
    """
    # Register in internal schedule.
    tab._jobs[iid] = {
        "yaml": yaml_name,
        "status": status,
        "snap": snap,
        "pct": pct,
        "eta": eta,
        "branch": branch,
        "location": location,
        "host": host,
        "seen_at": datetime.now().isoformat(timespec="seconds"),
    }

    try:
        tab.tree.insert(
            "",
            "end",
            iid=iid,
            values=(yaml_name, status, snap, pct, eta, branch, location, host),
        )
    except Exception:
        # Duplicate iid – attempt update instead.
        try:
            if tab.tree.exists(iid):
                tab.tree.item(
                    iid,
                    values=(yaml_name, status, snap, pct, eta, branch, location, host),
                )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# run_selected
# ---------------------------------------------------------------------------

def run_selected(tab) -> None:
    """
    Start running the selected YAML files (local or SSH).

    Mirrors ``RunnerTab._run_selected_ui``.
    """
    if not tab.manager:
        messagebox.showerror("Runner", "runner_manager not found.")
        return

    sel = tab.tree.selection()
    if not sel:
        messagebox.showwarning("Runner", "Select files to run.")
        return

    mode = tab.app.var_run_mode.get()
    workers = int(tab.app.var_max_workers.get())
    files = list(sel)

    tab._append_log(
        f"[RUN] Starting {len(files)} simulation(s) in {mode} mode "
        f"(workers={workers})..."
    )

    # Mark as queued in the schedule.
    for iid in files:
        try:
            tab.tree.set(iid, "status", "Queued")
            branch = tab.app.var_git_branch.get() or tab.tree.set(iid, "branch")
            tab.tree.set(iid, "branch", branch)
            tab.tree.set(iid, "host", tab._current_host_label())
            job = tab._jobs.get(iid, {})
            job.update(
                {
                    "status": "Queued",
                    "branch": branch,
                    "host": tab._current_host_label(),
                }
            )
            tab._jobs[iid] = job
        except Exception:
            pass

    if mode == "SSH":
        tab.manager.run_remote_parallel(files, workers)
    else:
        tab.manager.run_local_parallel(files, workers)


# ---------------------------------------------------------------------------
# stop_selected
# ---------------------------------------------------------------------------

def stop_selected(tab) -> None:
    """
    Stop the selected running simulations.

    Mirrors ``RunnerTab._stop_selected_ui``.
    """
    if not tab.manager:
        return
    sel = tab.tree.selection()
    if not sel:
        return
    tab._append_log(f"[STOP] Stopping {len(sel)} process(es)...")
    tab.manager.stop_simulations(list(sel))

    for iid in sel:
        try:
            tab.tree.set(iid, "status", "Stopped")
        except Exception:
            pass
