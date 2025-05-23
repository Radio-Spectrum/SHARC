import os
import streamlit as st
import platform

def find_venv_path(venv_folder_name=".venv"):
    current_path = os.path.abspath(os.path.dirname(__file__))
    while True:
        candidate = os.path.join(current_path, venv_folder_name)
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
    if platform.system() == "Windows":
        return os.path.join(venv_path, "Scripts", "python.exe")
    else:
        return os.path.join(venv_path, "bin", "python")

def run_python_script(script_path):
    if not os.path.exists(script_path):
        return f"❌ Error: The script '{script_path}' was not found."

    python_executable = get_venv_python()
    if not python_executable or not os.path.exists(python_executable):
        return f"❌ Error: Python executable not found in `.venv`: {python_executable}"

    system = platform.system()
    abs_script_path = os.path.abspath(script_path)

    try:
        if system == "Windows":
            os.system(f'start cmd /k "{python_executable} {abs_script_path}"')
        elif system == "Linux":
            os.system(f'gnome-terminal -- bash -c "{python_executable} {abs_script_path}; exec bash"')
        elif system == "Darwin":  # macOS
            os.system(f'osascript -e \'tell app "Terminal" to do script "{python_executable} {abs_script_path}"\'')
        else:
            return f"❌ Unsupported OS: {system}"
    except Exception as e:
        return f"❌ Exception occurred while launching: {e}"

    return "✅ Script launched in a new terminal."

def render_run_script_button(script_path):
    unique_key = f"run_button_{script_path}"
    if st.button(f"▶ Run `{os.path.basename(script_path)}`", key=unique_key):
        with st.spinner("Launching script..."):
            result = run_python_script(script_path)
            if result.startswith("✅"):
                st.success(result)
            else:
                st.error(result)

def render_file_explorer(folder_path: str):
    if not os.path.isdir(folder_path):
        st.error(f"❌ Folder `{folder_path}` not found.")
        return

    for root, dirs, files in os.walk(folder_path):
        level = root.replace(folder_path, '').count(os.sep)
        indent = "╚" + "═ " * (level - 1) + "> "
        folder_name = os.path.basename(root) or root
        relative_folder = os.path.relpath(root, start=folder_path)

        # Expander para cada pasta
        with st.expander(f"{indent}📁 {folder_name} (Folder level: {level})", expanded=(level == 0)):
            for file in sorted(files):
                file_path = os.path.join(root, file)
                file_ext = os.path.splitext(file)[1].lower()
                file_display = f"{(level + 1) * "-" + ">"} 📄 {file}"

                st.markdown(f"**{file_display}**")

                if file_ext == '.py':
                    render_run_script_button(file_path)

                if file_ext in ['.py', '.txt', '.csv', '.md', '.yaml', '.yml', '.json']:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            st.code(content, language=file_ext.strip('.'))
                    except Exception as e:
                        st.warning(f"⚠️ Error reading {file}: {e}")
                elif file_ext in ['.png', '.jpg', '.jpeg', '.gif']:
                    st.image(file_path)
                else:
                    try:
                        with open(file_path, "rb") as f:
                            st.download_button("📥 Download", data=f.read(), file_name=file, mime="application/octet-stream")
                    except Exception as e:
                        st.warning(f"⚠️ Error preparing download for {file}: {e}")

# Sidebar status
venv_path = find_venv_path()
if venv_path:
    st.sidebar.success(f"✅ venv found at: `{venv_path}`")
else:
    st.sidebar.error("❌ No venv found.")

# Example usage
render_file_explorer("scripts")  # Change "scripts" to your target folder
