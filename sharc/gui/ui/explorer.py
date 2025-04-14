import os
import streamlit as st
import subprocess

def run_python_script(script_path):
    if not os.path.exists(script_path):
        return f"❌ Error: The script '{script_path}' was not found."
    
    try:
        result = subprocess.run(
            ["python", script_path], capture_output=True, text=True, check=True
        )
        return result.stdout  
    except subprocess.CalledProcessError as e:
        return f"❌ Error in executing the script:\n{e.stderr}"

def render_run_script_button(script_path):
    unique_key = f"run_button_{script_path}"
    
    if st.button(f"Run `{os.path.basename(script_path)}`", key=unique_key):
        with st.spinner("Running script..."):
            result = run_python_script(script_path)
            st.markdown(f"### Output for `{os.path.basename(script_path)}`")
            if result:
                st.code(result, language="python")
            else:
                st.error("❌ No output or an unknown error occurred.")

def render_file_explorer(folder_path: str):
    if not os.path.isdir(folder_path):
        st.error(f"Folder {folder_path} not found.")
        return

    for root, dirs, files in os.walk(folder_path):
        level = root.replace(folder_path, '').count(os.sep)
        indent = " " * level

        folder_name = os.path.basename(root)
        if level == 0:
            st.markdown(f"###")
        else:
            st.markdown(f"{indent} {folder_name}")

        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, start=os.getcwd())

            file_display = f"{indent} 📄 {file}"
            with st.expander(file_display, expanded=False):
                file_ext = os.path.splitext(file)[1].lower()

                if file_ext == '.py':
                    render_run_script_button(file_path)

                # Files visualization
                if file_ext in ['.py', '.txt', '.csv', '.md', '.yaml', '.yml', '.json']:
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            st.code(content, language=file_ext.strip('.'))
                    except Exception as e:
                        st.warning(f"Error reading {file}: {e}")
                elif file_ext in ['.png', '.jpg', '.jpeg', '.gif']:
                    st.image(file_path)
                else:
                    st.download_button("📥 Download", data=open(file_path, "rb"), file_name=file, mime="application/octet-stream")
