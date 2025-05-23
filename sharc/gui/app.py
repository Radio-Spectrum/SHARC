import os
import streamlit as st
from ui.sidebar_folders import sidebar_style
from ui.terminal_component import render_notebook_terminal
from ui.explorer import render_file_explorer  


st.set_page_config(page_title="SHARC", layout="wide")

favicon_path = os.path.join(os.path.dirname(__file__), 'ui', 'img', 'sharc_logo_1.0.png')


if os.path.exists(favicon_path):
    st.markdown(
        f'<link rel="icon" href="file://{favicon_path}" type="image/png">',
        unsafe_allow_html=True
    )
else:
    st.error("Favicon image not found!")


st.markdown("""
    <style>
    div.stButton > button {
        background-color: #202030;
        color: white;
        border-radius: 8px;
        padding: 0.5em 1.5em;
        font-size: 1rem;
        font-weight: 500;
        white-space: nowrap;
        border: 1px solid #444;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        transition: 0.2s ease;
    }

    div.stButton > button:hover {
        background-color: #2a2a3d;
        transform: scale(1.01);
        cursor: pointer;
    }
    </style>
""", unsafe_allow_html=True)

selected_page = sidebar_style()
st.title(f"{selected_page.capitalize()}")

docs_path = os.path.join(os.path.dirname(__file__), "docs", f"{selected_page}.md")
try:
    with open(docs_path, "r") as f:
        st.markdown(f.read())
except FileNotFoundError:
    st.warning(f"This module {selected_page} doesn't have documentation yet.")

if selected_page != "home":

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    folder_path = os.path.join(project_root, selected_page)

    if "show_explorer" not in st.session_state:
        st.session_state.show_explorer = False

    if st.button("Explorer"):
        st.session_state.show_explorer = not st.session_state.show_explorer

    if st.session_state.show_explorer:
        if os.path.isdir(folder_path):
            render_file_explorer(folder_path)
        else:
            st.info(f"No files found in folder `{folder_path}`.")
    
    script_files = [f for f in os.listdir(folder_path) if f.endswith(".py")]
    
    for script in script_files:
        script_path = os.path.join(folder_path, script)

    render_notebook_terminal()