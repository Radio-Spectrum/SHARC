import json
import os
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, 
    QLabel, QLineEdit, QPushButton, QCheckBox, QPlainTextEdit, 
    QFileDialog, QMessageBox, QFrame, QScrollArea
)
from PySide6.QtCore import Qt, QTimer, Slot

def _safe_read_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}

def _safe_write_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

class SSHTunnelTab(QWidget):
    """
    SSH / Tunnel configuration tab in PySide6.

    - Uses app.runner_manager as backend component (RunnerManager from ssh_runner.py).
    - Save/Load config via JSON chosen by the user.
    - Does NOT store password.
    - Shows a live log box by tee-ing RunnerManager.log_callback (thread-safe via QTimer).
    """

    def __init__(self, app, parent_frame=None):
        super().__init__(parent_frame)

        self.app = app
        self.runner = getattr(app, "runner_manager", None)
        if self.runner is None:
            raise RuntimeError("SSHTunnelTab: app.runner_manager not found.")

        # Keep last opened/saved config file path
        self._config_file_path = ""

        # --- log box state ---
        self._orig_log_callback = None

        self._build_ui()
        self._install_logger_tee()
        self._refresh_status_labels()

    # ==========================================================
    # UI
    # ==========================================================
    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        # Header row
        top_layout = QHBoxLayout()
        lbl_title = QLabel("SSH / Tunnel")
        lbl_title.setStyleSheet("font-size: 14pt; font-weight: bold;")
        top_layout.addWidget(lbl_title)
        top_layout.addStretch()

        btn_load = QPushButton("Load Config (.json)")
        btn_load.clicked.connect(self._on_load_clicked)
        btn_save = QPushButton("Save Config (.json)")
        btn_save.clicked.connect(self._on_save_clicked)
        
        top_layout.addWidget(btn_load)
        top_layout.addWidget(btn_save)
        main_layout.addLayout(top_layout)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(line)

        # Config path display
        path_layout = QHBoxLayout()
        lbl_cfg = QLabel("Config file:")
        lbl_cfg.setStyleSheet("font-weight: bold;")
        self.lbl_cfg_path = QLabel("")
        self.lbl_cfg_path.setStyleSheet("font-family: Consolas;")
        
        path_layout.addWidget(lbl_cfg)
        path_layout.addWidget(self.lbl_cfg_path)
        path_layout.addStretch()
        main_layout.addLayout(path_layout)

        # Status row
        status_layout = QHBoxLayout()
        self.lbl_ssh = QLabel("SSH: --")
        self.lbl_ssh.setStyleSheet("font-family: Consolas;")
        self.lbl_tun = QLabel("Tunnel: --")
        self.lbl_tun.setStyleSheet("font-family: Consolas;")
        
        status_layout.addWidget(self.lbl_ssh)
        status_layout.addWidget(self.lbl_tun)
        status_layout.addStretch()
        main_layout.addLayout(status_layout)

        # Scrollable Content Area (to avoid layout crushing on small screens)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        # SSH frame
        ssh_box = QGroupBox("SSH Connection (direct or via tunnel)")
        ssh_grid = QGridLayout(ssh_box)

        ssh_grid.addWidget(QLabel("Host"), 0, 0)
        self.e_ssh_host = QLineEdit()
        ssh_grid.addWidget(self.e_ssh_host, 0, 1)

        ssh_grid.addWidget(QLabel("Port"), 0, 2)
        self.e_ssh_port = QLineEdit("22")
        self.e_ssh_port.setFixedWidth(60)
        ssh_grid.addWidget(self.e_ssh_port, 0, 3)

        ssh_grid.addWidget(QLabel("User"), 1, 0)
        self.e_ssh_user = QLineEdit()
        ssh_grid.addWidget(self.e_ssh_user, 1, 1)

        ssh_grid.addWidget(QLabel("Password"), 1, 2)
        self.e_ssh_password = QLineEdit()
        self.e_ssh_password.setEchoMode(QLineEdit.Password)
        ssh_grid.addWidget(self.e_ssh_password, 1, 3)

        ssh_grid.addWidget(QLabel("SSH Key"), 2, 0)
        self.e_ssh_key = QLineEdit()
        ssh_grid.addWidget(self.e_ssh_key, 2, 1, 1, 2)
        
        btn_pick_ssh = QPushButton("Browse")
        btn_pick_ssh.clicked.connect(self._pick_ssh_key)
        ssh_grid.addWidget(btn_pick_ssh, 2, 3)

        ssh_actions = QHBoxLayout()
        btn_conn_pass = QPushButton("Connect (Password)")
        btn_conn_pass.clicked.connect(self._connect_password)
        btn_conn_key = QPushButton("Connect (Key)")
        btn_conn_key.clicked.connect(self._connect_key)
        btn_disc = QPushButton("Disconnect")
        btn_disc.clicked.connect(self._disconnect)
        
        ssh_actions.addWidget(btn_conn_pass)
        ssh_actions.addWidget(btn_conn_key)
        ssh_actions.addWidget(btn_disc)
        ssh_actions.addStretch()
        ssh_grid.addLayout(ssh_actions, 3, 0, 1, 4)

        scroll_layout.addWidget(ssh_box)

        # Tunnel frame
        tun_box = QGroupBox("SSH Tunnel (Local Port Forward)")
        tun_grid = QGridLayout(tun_box)

        tun_grid.addWidget(QLabel("Bastion Host"), 0, 0)
        self.e_bastion_host = QLineEdit()
        tun_grid.addWidget(self.e_bastion_host, 0, 1)

        tun_grid.addWidget(QLabel("User"), 0, 2)
        self.e_bastion_user = QLineEdit()
        tun_grid.addWidget(self.e_bastion_user, 0, 3)

        tun_grid.addWidget(QLabel("Port"), 0, 4)
        self.e_bastion_port = QLineEdit("22")
        self.e_bastion_port.setFixedWidth(60)
        tun_grid.addWidget(self.e_bastion_port, 0, 5)

        tun_grid.addWidget(QLabel("Internal IP"), 1, 0)
        self.e_internal_ip = QLineEdit()
        tun_grid.addWidget(self.e_internal_ip, 1, 1)

        tun_grid.addWidget(QLabel("Internal Port"), 1, 2)
        self.e_internal_port = QLineEdit("22")
        self.e_internal_port.setFixedWidth(60)
        tun_grid.addWidget(self.e_internal_port, 1, 3)

        tun_grid.addWidget(QLabel("Local Port"), 1, 4)
        self.e_local_port = QLineEdit("2222")
        self.e_local_port.setFixedWidth(60)
        tun_grid.addWidget(self.e_local_port, 1, 5)

        tun_grid.addWidget(QLabel("Tunnel SSH Key"), 2, 0)
        self.e_tunnel_key = QLineEdit()
        tun_grid.addWidget(self.e_tunnel_key, 2, 1, 1, 4)
        
        btn_pick_tun = QPushButton("Browse")
        btn_pick_tun.clicked.connect(self._pick_tunnel_key)
        tun_grid.addWidget(btn_pick_tun, 2, 5)

        tun_actions = QHBoxLayout()
        btn_open_tun = QPushButton("Open Tunnel")
        btn_open_tun.clicked.connect(self._open_tunnel)
        btn_close_tun = QPushButton("Close Tunnel")
        btn_close_tun.clicked.connect(self._close_tunnel)
        
        tun_actions.addWidget(btn_open_tun)
        tun_actions.addWidget(btn_close_tun)
        tun_actions.addStretch()
        tun_grid.addLayout(tun_actions, 3, 0, 1, 6)

        scroll_layout.addWidget(tun_box)

        # ======================================================
        # LOG BOX
        # ======================================================
        log_box = QGroupBox("System Logs (ssh_runner)")
        log_layout = QVBoxLayout(log_box)

        log_controls = QHBoxLayout()
        btn_clear_log = QPushButton("Clear")
        btn_clear_log.clicked.connect(self._clear_log_box)
        self.cb_autoscroll = QCheckBox("Auto-scroll")
        self.cb_autoscroll.setChecked(True)
        
        log_controls.addWidget(btn_clear_log)
        log_controls.addWidget(self.cb_autoscroll)
        log_controls.addStretch()
        log_layout.addLayout(log_controls)

        self.txt_log = QPlainTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setStyleSheet("font-family: Consolas; font-size: 9pt;")
        log_layout.addWidget(self.txt_log)

        scroll_layout.addWidget(log_box)
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

    # ==========================================================
    # Logger tee (RunnerManager.log_callback)
    # ==========================================================
    def _install_logger_tee(self):
        if self._orig_log_callback is not None:
            return

        orig = getattr(self.runner, "log_callback", None)
        if not callable(orig):
            orig = getattr(self.app, "_safe_log", None)

        self._orig_log_callback = orig

        def _tee(msg: str):
            # 1) keep original behavior
            try:
                if callable(self._orig_log_callback):
                    self._orig_log_callback(msg)
            except Exception:
                pass

            # 2) mirror into this tab
            self._append_log_box(msg)

        self.runner.log_callback = _tee
        self._append_log_box("[LOG] SSH tab logger attached.\n")

    def _restore_logger(self):
        if self._orig_log_callback is not None:
            try:
                self.runner.log_callback = self._orig_log_callback
            except Exception:
                pass
            self._orig_log_callback = None

    def closeEvent(self, event):
        self._restore_logger()
        super().closeEvent(event)

    def _append_log_box(self, msg: str):
        if not hasattr(self, "txt_log") or self.txt_log is None:
            return
        if msg is None:
            return
        s = str(msg).rstrip()

        def _ui_write():
            try:
                self.txt_log.appendPlainText(s)
                if self.cb_autoscroll.isChecked():
                    sb = self.txt_log.verticalScrollBar()
                    sb.setValue(sb.maximum())
            except Exception:
                pass

        QTimer.singleShot(0, _ui_write)

    def _clear_log_box(self):
        if not hasattr(self, "txt_log") or self.txt_log is None:
            return
        try:
            self.txt_log.clear()
        except Exception:
            pass

    # ==========================================================
    # JSON Config (ask user where to save / which file to open)
    # ==========================================================
    def _collect_config_dict(self) -> dict:
        def safe_int(v, default):
            try: return int(v)
            except (ValueError, TypeError): return default
            
        return {
            "ssh": {
                "host": self.e_ssh_host.text().strip(),
                "port": safe_int(self.e_ssh_port.text(), 22),
                "user": self.e_ssh_user.text().strip(),
                "key_path": self.e_ssh_key.text().strip(),
            },
            "tunnel": {
                "bastion_host": self.e_bastion_host.text().strip(),
                "bastion_user": self.e_bastion_user.text().strip(),
                "bastion_port": safe_int(self.e_bastion_port.text(), 22),
                "internal_ip": self.e_internal_ip.text().strip(),
                "internal_port": safe_int(self.e_internal_port.text(), 22),
                "local_port": safe_int(self.e_local_port.text(), 2222),
                "key_path": self.e_tunnel_key.text().strip(),
            }
        }

    def _apply_config_dict(self, cfg: dict):
        ssh = cfg.get("ssh", {}) if isinstance(cfg, dict) else {}
        tun = cfg.get("tunnel", {}) if isinstance(cfg, dict) else {}

        self.e_ssh_host.setText(str(ssh.get("host", "")))
        self.e_ssh_port.setText(str(ssh.get("port", "22")))
        self.e_ssh_user.setText(str(ssh.get("user", "")))
        self.e_ssh_key.setText(str(ssh.get("key_path", "")))

        self.e_bastion_host.setText(str(tun.get("bastion_host", "")))
        self.e_bastion_user.setText(str(tun.get("bastion_user", "")))
        self.e_bastion_port.setText(str(tun.get("bastion_port", "22")))
        self.e_internal_ip.setText(str(tun.get("internal_ip", "")))
        self.e_internal_port.setText(str(tun.get("internal_port", "22")))
        self.e_local_port.setText(str(tun.get("local_port", "2222")))
        self.e_tunnel_key.setText(str(tun.get("key_path", "")))

    def _on_save_clicked(self):
        initdir = self._config_file_path if self._config_file_path else ""
        path, _ = QFileDialog.getSaveFileName(
            self, "Save SSH/Tunnel config", initdir or "ssh_config.json", "JSON Files (*.json);;All Files (*)"
        )
        if not path:
            return

        try:
            data = self._collect_config_dict()
            _safe_write_json(path, data)
            self._config_file_path = path
            self.lbl_cfg_path.setText(path)
            self._append_log_box(f"[CFG] Saved JSON config: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def _on_load_clicked(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load SSH/Tunnel config", "", "JSON Files (*.json);;All Files (*)"
        )
        if not path:
            return

        try:
            cfg = _safe_read_json(path)
            self._apply_config_dict(cfg)
            self._config_file_path = path
            self.lbl_cfg_path.setText(path)
            self._append_log_box(f"[CFG] Loaded JSON config: {path}")
            self._refresh_status_labels()
        except Exception as e:
            QMessageBox.critical(self, "Load Error", str(e))

    # ==========================================================
    # Pickers
    # ==========================================================
    def _pick_ssh_key(self):
        p, _ = QFileDialog.getOpenFileName(self, "Select SSH Private Key")
        if p:
            self.e_ssh_key.setText(p)

    def _pick_tunnel_key(self):
        p, _ = QFileDialog.getOpenFileName(self, "Select Tunnel SSH Private Key")
        if p:
            self.e_tunnel_key.setText(p)

    # ==========================================================
    # Actions (use RunnerManager from ssh_runner.py)
    # ==========================================================
    def _connect_password(self):
        try:
            self.runner.connect_ssh_password(
                host=self.e_ssh_host.text().strip(),
                user=self.e_ssh_user.text().strip(),
                port=int(self.e_ssh_port.text() or 22),
                password=self.e_ssh_password.text(),
            )
            self._refresh_status_labels()
        except Exception as e:
            QMessageBox.critical(self, "SSH Error", str(e))
            self._refresh_status_labels()

    def _connect_key(self):
        try:
            key_path = self.e_ssh_key.text().strip()
            if not key_path:
                QMessageBox.warning(self, "Missing key", "Select an SSH key file first.")
                return

            self.runner.connect_ssh_key(
                host=self.e_ssh_host.text().strip(),
                user=self.e_ssh_user.text().strip(),
                port=int(self.e_ssh_port.text() or 22),
                key_path=key_path,
            )
            self._refresh_status_labels()
        except Exception as e:
            QMessageBox.critical(self, "SSH Error", str(e))
            self._refresh_status_labels()

    def _disconnect(self):
        try:
            self.runner.disconnect_ssh()
        except Exception:
            pass
        self._refresh_status_labels()

    def _open_tunnel(self):
        try:
            key_path = self.e_tunnel_key.text().strip()
            if not key_path:
                QMessageBox.warning(self, "Missing key", "Select a tunnel SSH key file first.")
                return

            self.runner.create_tunnel(
                bastion_host=self.e_bastion_host.text().strip(),
                bastion_user=self.e_bastion_user.text().strip(),
                bastion_port=int(self.e_bastion_port.text() or 22),
                int_ip=self.e_internal_ip.text().strip(),
                int_port=int(self.e_internal_port.text() or 22),
                loc_port=int(self.e_local_port.text() or 2222),
                key_path=key_path,
            )
            self._refresh_status_labels()
        except Exception as e:
            QMessageBox.critical(self, "Tunnel Error", str(e))
            self._refresh_status_labels()

    def _close_tunnel(self):
        try:
            self.runner.close_tunnel()
        except Exception:
            pass
        self._refresh_status_labels()

    # ==========================================================
    # Status integration
    # ==========================================================
    def _refresh_status_labels(self):
        ssh_ok = bool(getattr(self.runner, "ssh_connected", False))
        tun_ok = bool(getattr(self.runner, "tunnel_process", None))

        ssh_txt = "SSH: Connected" if ssh_ok else "SSH: Disconnected"
        tun_txt = "Tunnel: Active" if tun_ok else "Tunnel: Closed"

        try:
            self.lbl_ssh.setText(ssh_txt)
            self.lbl_tun.setText(tun_txt)
        except Exception:
            pass

        if hasattr(self.app, "ssh_status"):
            try:
                # Se app.ssh_status for SharcVar (ou similar que possui set())
                self.app.ssh_status.set(ssh_txt)
            except AttributeError:
                self.app.ssh_status = ssh_txt
                
        if hasattr(self.app, "tunnel_status"):
            try:
                self.app.tunnel_status.set(tun_txt)
            except AttributeError:
                self.app.tunnel_status = tun_txt
