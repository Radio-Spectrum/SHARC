import os
import platform
import subprocess
import threading
import time
from collections import deque

import streamlit as st
from streamlit_autorefresh import st_autorefresh

# ===============================
# Script Execution Observer (Async)
# ===============================
class ScriptObserver:
    def __init__(self, script_path, python_path):
        self.script_path = script_path
        self.python_path = python_path
        self.process = None
        self.output = deque(maxlen=500)
        self.thread = None
        self.running = False
        self.lock = threading.Lock()

    def start(self):
        if self.running or not os.path.exists(self.script_path):
            return False
        try:
            self.process = subprocess.Popen(
                [self.python_path, self.script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                universal_newlines=True,
            )
            self.running = True
            self.thread = threading.Thread(target=self._capture_output, daemon=True)
            self.thread.start()
            return True
        except Exception as e:
            print(f"Error starting script: {e}")
            return False

    def _capture_output(self):
        try:
            for line in self.process.stdout:
                with self.lock:
                    self.output.append(line)
            self.process.stdout.close()
            self.process.wait()
        except Exception as e:
            with self.lock:
                self.output.append(f"\n⚠️ Error capturing output: {e}\n")
        finally:
            self.running = False

    def read_output(self):
        with self.lock:
            return list(self.output)[-50:]

    def stop(self):
        if self.running and self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            except Exception as e:
                print(f"Error stopping process: {e}")
            self.running = False
            return True
        return False


# ===============================
# Virtual Environment Handling
# ===============================
def find_venv_path(folder_name=".venv"):
    current_path = os.path.abspath(os.path.dirname(__file__))
    while True:
        candidate = os.path.join(current_path, folder_name)
        if os.path.isdir(candidate):
            return candidate
        parent = os.path.dirname(current_path)
        if parent == current_path:
            break
        current_path = parent
    return None

def get_venv_python():
    venv_path = find_venv_path()
    if not venv_path:
        return None
    return os.path.join(
        venv_path,
        "Scripts" if platform.system() == "Windows" else "bin",
        "python.exe" if platform.system() == "Windows" else "python"
    )


# ===============================
# Script Execution With Logs
# ===============================
def run_python_script(script_path):
    if "observer" not in st.session_state:
        st.session_state.observer = None

    if st.session_state.observer and st.session_state.observer.running:
        return False, "⚠️ Another script is already running."

    if not os.path.exists(script_path):
        return False, f"❌ Script not found: {script_path}"

    python_exec = get_venv_python()
    if not python_exec or not os.path.exists(python_exec):
        return False, f"❌ Python executable not found in .venv: {python_exec}"

    observer = ScriptObserver(script_path, python_exec)
    if observer.start():
        st.session_state.observer = observer
        return True, "✅ Execution started."
    return False, "❌ Failed to start execution."


# ===============================
# External Terminal Execution
# ===============================
def run_script_externally(script_path):
    if not os.path.exists(script_path):
        return f"❌ Script not found: {script_path}"

    python_exec = get_venv_python()
    if not python_exec or not os.path.exists(python_exec):
        return f"❌ Python executable not found: {python_exec}"

    system = platform.system()
    abs_path = os.path.abspath(script_path)

    try:
        if system == "Windows":
            os.system(f'start cmd /k "{python_exec} {abs_path}"')
        elif system == "Linux":
            cmds = [
                f'gnome-terminal -- bash -c "{python_exec} {abs_path}; exec bash"',
                f'konsole -e {python_exec} {abs_path}',
                f'xterm -hold -e {python_exec} {abs_path}',
            ]
            for cmd in cmds:
                if os.system(cmd) == 0:
                    return "✅ Script launched in terminal."
            return "❌ No supported Linux terminal found."
        elif system == "Darwin":
            os.system(f'''osascript -e 'tell app "Terminal" to do script "{python_exec} {abs_path}"' ''')
        else:
            return f"❌ Unsupported OS: {system}"
    except Exception as e:
        return f"❌ Error launching script: {e}"

    return "✅ Script launched."


def render_external_run_button(script_path):
    key = f"external_run_{script_path}"
    if st.button(f"▶ Run in Terminal: {os.path.basename(script_path)}", key=key):
        with st.spinner("Launching script in terminal..."):
            result = run_script_externally(script_path)
            st.success(result) if result.startswith("✅") else st.error(result)


# ===============================
# File Explorer
# ===============================
def render_file_explorer(folder):
    if not os.path.isdir(folder):
        st.error(f"❌ Folder not found: {folder}")
        return

    if "observer" not in st.session_state:
        st.session_state.observer = None

    for root, dirs, files in os.walk(folder):
        level = root.replace(folder, "").count(os.sep)
        indent = " " * 4 * level
        folder_name = os.path.basename(root) or root

        with st.expander(f"{indent}📁 {folder_name} (Level {level})", expanded=(level == 0)):
            for file in sorted(files):
                path = os.path.join(root, file)
                ext = os.path.splitext(file)[1].lower()

                st.markdown(f"**{' ' * 4 * (level + 1)}📄 {file}**")

                if ext == ".py":
                    col1, col2 = st.columns([1, 2])
                    with col1:
                        render_external_run_button(path)
                    with col2:
                        run_key = f"run_{path}"
                        stop_key = f"stop_{path}"
                        is_running = bool(st.session_state.get("observer") and st.session_state.observer.running)

                        if st.button("🧪 Run with logs", key=run_key, disabled=is_running):
                            success, msg = run_python_script(path)
                            st.success(msg) if success else st.error(msg)

                        if st.button("🛑 Stop execution", key=stop_key):
                            if is_running and st.session_state.observer.stop():
                                st.success("🛑 Execution stopped.")
                            else:
                                st.info("ℹ️ No script running.")

                if ext in [".py", ".txt", ".csv", ".md", ".yaml", ".yml", ".json"]:
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            st.code(f.read(), language=ext.strip("."))
                    except Exception as e:
                        st.warning(f"⚠️ Error reading {file}: {e}")
                elif ext in [".png", ".jpg", ".jpeg", ".gif"]:
                    st.image(path)
                else:
                    try:
                        with open(path, "rb") as f:
                            st.download_button("📥 Download", data=f.read(), file_name=file)
                    except Exception as e:
                        st.warning(f"⚠️ Error preparing download: {e}")


# ===============================
# Real-Time Log Viewer
# ===============================
def render_script_logger():
    if "show_logs" not in st.session_state:
        st.session_state.show_logs = False

    if st.button("🧪 Toggle Real-time Logs"):
        st.session_state.show_logs = not st.session_state.show_logs

    if st.session_state.show_logs:
        if st.session_state.observer and st.session_state.observer.running:
            st.subheader(f"🧪 Real-time Logs: {os.path.basename(st.session_state.observer.script_path)}")
            st_autorefresh(interval=1000, limit=None, key="log_refresh")
            log_area = st.empty()
            output = st.session_state.observer.read_output()
            log_area.code("".join(output), language="bash")
        else:
            st.info("ℹ️ No script running.")
