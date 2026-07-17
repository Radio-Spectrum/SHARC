"""
runner_actions.py
-----------------
Standalone action helpers for RunnerTab.
"""

import os
from datetime import datetime
from PySide6.QtWidgets import QMessageBox, QTreeWidgetItem
from PySide6.QtCore import Qt

def scan_yaml_files(tab) -> None:
    try:
        tab.tree.clear()
    except Exception:
        pass

    mode = "LOCAL" if tab.rb_local.isChecked() else "SSH"
    tab._append_log(f"[SCAN] Scanning files in mode: {mode}...")

    if mode == "LOCAL":
        folder = tab.e_run_folder.text()
        if os.path.isdir(folder):
            files = [f for f in os.listdir(folder) if f.lower().endswith((".yaml", ".yml"))]
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
            remote_dir = tab.e_remote_dir.text().strip()
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
                        branch=tab.cmb_git_branch.currentText() or "",
                        location=remote_dir,
                        host=tab._current_host_label(),
                    )
            except Exception as e:
                tab._append_log(f"[ERR] Error listing remote files: {e}")
        else:
            tab._append_log("[SSH] Not connected. Connect via SSH tab first.")


def insert_job_row(tab, iid: str, yaml_name: str, status: str, snap: str, pct: str, eta: str, branch: str, location: str, host: str) -> None:
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

    # Procura se já existe
    existing_item = None
    for i in range(tab.tree.topLevelItemCount()):
        item = tab.tree.topLevelItem(i)
        if item.data(0, Qt.UserRole) == iid:
            existing_item = item
            break

    if existing_item:
        existing_item.setText(0, yaml_name)
        existing_item.setText(1, status)
        existing_item.setText(2, snap)
        existing_item.setText(3, pct)
        existing_item.setText(4, eta)
        existing_item.setText(5, branch)
        existing_item.setText(6, location)
        existing_item.setText(7, host)
    else:
        new_item = QTreeWidgetItem([yaml_name, status, snap, pct, eta, branch, location, host])
        new_item.setData(0, Qt.UserRole, iid)
        tab.tree.addTopLevelItem(new_item)


def run_selected(tab) -> None:
    if not tab.manager:
        QMessageBox.critical(tab.frame, "Runner", "runner_manager not found.")
        return

    sel_items = tab.tree.selectedItems()
    if not sel_items:
        QMessageBox.warning(tab.frame, "Runner", "Select files to run.")
        return

    mode = "LOCAL" if tab.rb_local.isChecked() else "SSH"
    workers = tab.spin_workers.value()
    files = [item.data(0, Qt.UserRole) for item in sel_items]

    tab._append_log(f"[RUN] Starting {len(files)} simulation(s) in {mode} mode (workers={workers})...")

    global_branch = tab.cmb_git_branch.currentText().strip()
    host = tab._current_host_label()

    for item in sel_items:
        iid = item.data(0, Qt.UserRole)
        branch = global_branch or item.text(5)
        
        item.setText(1, "Queued")
        item.setText(5, branch)
        item.setText(7, host)
        
        job = tab._jobs.get(iid, {})
        job.update({
            "status": "Queued",
            "branch": branch,
            "host": host,
        })
        tab._jobs[iid] = job

    if mode == "SSH":
        tab.manager.run_remote_parallel(files, workers)
    else:
        tab.manager.run_local_parallel(files, workers)


def stop_selected(tab) -> None:
    if not tab.manager:
        return
    sel_items = tab.tree.selectedItems()
    if not sel_items:
        return
    
    files = [item.data(0, Qt.UserRole) for item in sel_items]
    tab._append_log(f"[STOP] Stopping {len(files)} process(es)...")
    tab.manager.stop_simulations(files)

    for item in sel_items:
        item.setText(1, "Stopped")
