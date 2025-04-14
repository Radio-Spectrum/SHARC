import streamlit as st
from PIL import Image 
import os

def sidebar_style():
    folders = [
        "home", "antenna", "campaigns", "mask", 
        "parameters", "propagation", "topology"
    ]

    icons = {
        "home": "",
        "antenna": "",
        "campaigns": "",
        "input": "",
        "mask": "",
        "parameters": "",
        "plots": "",
        "propagation": "",
        "topology": ""
    }

    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');

    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Inter', sans-serif;
        background: linear-gradient(to bottom, #f3f4f6, #e5e7eb);
        color: #1c1c1e;
    }
                

    [data-testid="stSidebar"] {
        background: rgba(255, 255, 255, 0.75);
        backdrop-filter: blur(18px);
        -webkit-backdrop-filter: blur(18px);
        border-right: 1px solid rgba(0, 0, 0, 0.05);
        width: 240px;
        padding: 1.5rem 1.5rem 2rem 1.5rem;
        box-shadow: 2px 0 15px rgba(0, 0, 0, 0.05);
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }

    .block-container {
        padding: 1rem 2rem;
    }
                
    .header {
        font-size: 24px;
        font-weight: 600;
        margin: 0.3rem 0 0.5rem 0;
        padding-left: 0.1rem;
        color: #00a7da;
    }

    .sidebar-logo {
        display: flex;
        justify-content: center;
        margin-bottom: 1.2rem;
    }

    .sidebar-logo img {
        max-width: 120px;
        height: auto;
        border-radius: 6px;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05);
        animation: floatPulse 3s ease-in-out infinite;
    }

    @keyframes floatPulse {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-4px); }
    }

    .custom-title {
        font-size: 17px;
        font-weight: 600;
        margin: 0.5rem 0 0.8rem 0;
        padding-left: 0.2rem;
        color: #444;
    }

    .search-box {
        position: relative;
        margin-bottom: 1rem;
    }

    .search-box input {
        width: 100%;
        padding: 9px 12px 9px 34px;
        border-radius: 10px;
        background-color: rgba(245, 245, 250, 0.9);
        color: #1c1c1e;
        border: 1px solid #ddd;
        font-size: 14px;
        box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.04);
    }

    .search-box input:focus {
        border-color: #007aff;
        box-shadow: 0 0 0 2px rgba(0, 122, 255, 0.2);
        outline: none;
    }

    button[kind="secondary"] {
        background-color: transparent !important;
        color: #1c1c1e !important;
        border: none !important;
        width: 100% !important;
        text-align: left !important;
        padding: 0.6rem 1rem !important;
        border-radius: 12px !important;
        font-size: 15px !important;
        font-weight: 500;
        margin-bottom: 6px;
        transition: background 0.25s ease, transform 0.25s ease;
    }

    button[kind="secondary"]:hover {
        background-color: #e5e5ea !important;
        transform: scale(1.01);
    }

    button.selected {
        background-color: #007aff !important;
        color: white !important;
        font-weight: 600;
        box-shadow: 0 0 0 1.5px rgba(0, 122, 255, 0.5);
    }

    .bottom-footer {
        font-size: 13px;
        color: #666;
        margin-top: 2rem;
        padding-top: 1rem;
        border-top: 1px solid #ddd;
    }

    </style>
    """, unsafe_allow_html=True)

    st.sidebar.markdown('<div class="header">Radio-Spectrum SHARC</div>', unsafe_allow_html=True)

    icon = os.path.join(os.path.dirname(__file__), "img", "sharc_logo_1.0.png")
    image = Image.open(icon)
    st.sidebar.markdown('<div class="sidebar-logo">', unsafe_allow_html=True)
    st.sidebar.image(image, use_column_width=False, width=120)
    st.sidebar.markdown('</div>', unsafe_allow_html=True)

    st.sidebar.markdown('<div class="custom-title">Navigation</div>', unsafe_allow_html=True)

    st.sidebar.markdown('<div class="search-box">', unsafe_allow_html=True)
    search_query = st.sidebar.text_input("", "", key="sidebar_search", placeholder="Search...").lower()
    st.sidebar.markdown('</div>', unsafe_allow_html=True)

    if "selected_folder" not in st.session_state:
        st.session_state.selected_folder = "home"

    filtered_folders = [f for f in folders if search_query in f.lower()]
    for folder in filtered_folders:
        label = f"{icons.get(folder, '')} {folder.capitalize()}"
        button_key = f"btn_{folder}"
        clicked = st.sidebar.button(label, key=button_key)
        selected = (st.session_state.selected_folder == folder)

        # Add selected class dynamically via JS after button is rendered
        if clicked:
            st.session_state.selected_folder = folder

        if selected:
            st.markdown(f"""
            <style>
            button[data-testid="{button_key}"] {{
                background-color: #007aff !important;
                color: white !important;
                font-weight: 600 !important;
                box-shadow: 0 0 0 1.5px rgba(0, 122, 255, 0.5) !important;
            }}
            </style>
            """, unsafe_allow_html=True)

    st.sidebar.markdown(f'[**Documentation**](https://projectsharc.vercel.app/)', unsafe_allow_html=True)
    st.sidebar.markdown(f'[**ITU-Resolutions**](www.itu.int/en/about/Pages/default.aspx)', unsafe_allow_html=True)
    st.sidebar.markdown('<div class="bottom-footer">Copyright © 2025<br>Radio-Spectrum SHARC</div>', unsafe_allow_html=True)

    return st.session_state.selected_folder
