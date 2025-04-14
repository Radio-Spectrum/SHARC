import streamlit as st
import subprocess
import io
import contextlib
import traceback
import os
from pathlib import Path
import sys
import platform
import datetime


def list_all_sharc_scripts(base_dir="sharc"):
    scripts = []
    for path in Path(base_dir).rglob("*.py"):
        if not path.name.startswith("__"):
            scripts.append(str(path))
    return scripts


def suggest_similar_scripts(script_path):
    all_scripts = list_all_sharc_scripts()
    partial = os.path.basename(script_path).lower()
    suggestions = [s for s in all_scripts if partial in s.lower()]
    if not suggestions:
        return "\n💡 No similar scripts found. Try `%list_scripts` to see all available scripts."
    return "\n💡 Did you mean:\n" + "\n".join(f"- `{s}`" for s in suggestions)


def sharc_run(script_path):
    script_file = Path(script_path)
    if not script_file.exists():
        return f"❌ Script '{script_path}' not found." + suggest_similar_scripts(script_path)
    try:
        with open(script_path, "r") as f:
            code = f.read()
            output_buffer = io.StringIO()
            with contextlib.redirect_stdout(output_buffer):
                exec(code, globals())
            return output_buffer.getvalue()
    except Exception:
        return f"❌ Error in script execution:\n{traceback.format_exc()}"


def get_system_info():
    return f"""
    💻 **System Info**
    OS: {platform.system()} {platform.release()}
    Python: {platform.python_version()}
    Platform: {platform.platform()}
    Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    Current Path: {os.getcwd()}
    """


def render_notebook_terminal():
    with st.expander("🧪 Jupyter Terminal / SHARC Shell", expanded=True):
        st.markdown("""
            <style>
                .terminal-box textarea {
                    font-family: 'JetBrains Mono', monospace;
                    
                    font-size: 14px;
                    background-color: #ffffff;
                    color: #ffffff;
                    border-radius: 10px;
                    padding: 12px;
                    border: none;
                }
                .stTextArea textarea {
                    background-color: #001e56 !important;
                    color: #ffffff !important;
                    font-family: 'JetBrains Mono', monospace;
                    font-size: 14px;
                    border-radius: 10px;
                }
                .stTextArea textarea::placeholder {
                    color: white !important;
                }
            </style>
        """, unsafe_allow_html=True)

        code = st.text_area("Terminal", height=200, placeholder="Type %help for help...", key="terminal_input")

        if st.button("▶️ Run", key="run_notebook_code"):
            with st.spinner("Running..."):
                output_buffer = io.StringIO()
                try:
                    code = code.strip()
                    result = ""

                    if code.startswith("%sharc_run"):
                        script_path = code.replace("%sharc_run", "").strip()
                        result = sharc_run(script_path)

                    elif code.startswith("%list_scripts"):
                        all_scripts = list_all_sharc_scripts()
                        result = "\n".join(f"- {s}" for s in all_scripts)
                        st.success("📂 Available SHARC Scripts:")

                    elif code.startswith("%sys_info"):
                        result = get_system_info()

                    elif code.startswith("%clear"):
                        st.experimental_rerun()

                    elif code.startswith("%help"):
                        result = """
📜 **Available Commands:**
- %sharc_run path/script.py — Run a SHARC Python script
- %sys_info — Show system and environment info
- %clear — Clear the terminal output
- %help — Show this help message
                        """

                    else:
                        with contextlib.redirect_stdout(output_buffer):
                            exec(code, globals())
                        result = output_buffer.getvalue()

                    if result:
                        st.code(result, language="python")

                except Exception as e:
                    st.error("❌ Error in execution:")
                    st.code(traceback.format_exc(), language="python")
