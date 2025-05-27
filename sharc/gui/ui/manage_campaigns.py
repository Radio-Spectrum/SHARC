import streamlit as st
from pathlib import Path
from ui.explorer import run_python_script

def find_project_root(folder_name="sharc") -> Path | None:
    current_path = Path(__file__).resolve()
    for parent in current_path.parents:
        if (parent / folder_name).exists():
            return parent
    return None

PROJECT_ROOT = find_project_root("sharc")

if PROJECT_ROOT is None:
    st.error("Could not find the 'sharc' folder in the directory hierarchy. Please check your project structure.")
    CAMPAIGN_DIR = None
else:
    CAMPAIGN_DIR = PROJECT_ROOT / "sharc" / "campaigns"

def check_campaign_dir():
    """Checks if the 'sharc/campaigns' folder exists, without creating it."""
    if CAMPAIGN_DIR is None:
        return False
    if not CAMPAIGN_DIR.exists():
        st.error(f"The directory '{CAMPAIGN_DIR}' does not exist. Please create it manually.")
        return False
    if not CAMPAIGN_DIR.is_dir():
        st.error(f"'{CAMPAIGN_DIR}' exists but is not a directory.")
        return False
    return True

@st.dialog("Create New Campaign")
def create_campaign():
    if not check_campaign_dir():
        return

    campaign_name = st.text_input("Campaign Name")
    
    if st.button("Create"):
        campaign_name = campaign_name.strip()
        campaign_path = CAMPAIGN_DIR / campaign_name
        script_path = campaign_path / "script"
        input_path = campaign_path / "input"

        if not campaign_name:
            st.warning("Campaign name cannot be empty.")
        elif campaign_path.exists():
            st.error("A campaign with this name already exists.")
        else:
            # Cria a pasta principal da campanha
            campaign_path.mkdir(parents=True, exist_ok=False)
            # Cria as subpastas script e input
            script_path.mkdir(exist_ok=False)
            input_path.mkdir(exist_ok=False)

            st.session_state.campaign = campaign_name
            st.success(f"Campaign '{campaign_name}' created successfully with subfolders 'script' and 'input'!")
            if "logs" not in st.session_state:
                st.session_state.logs = []
            st.session_state.logs.append(f"Created: {campaign_path} with 'script' and 'input' subfolders")

def edit_campaigns():
    st.info("Edit campaigns feature coming soon.")

def start_simulation():
    st.info("Simulation started!")  

def render_campaign_buttons():
    col1, col2 = st.columns(2)

    with col1:
        start_sim = st.button("Start Simulation", key="start_sim")
        st.markdown("""
            <style>
            div.stButton > button[key="start_sim"] {
                background-color: #28a745 !important;
                color: white !important;
                height: 40px !important;
                width: 100% !important;
                font-weight: 600 !important;
            }
            </style>
            """, unsafe_allow_html=True)

    with col2:
        edit_camp = st.button("Edit Campaigns", key="edit_camp")
        st.markdown("""
            <style>
            div.stButton > button[key="edit_camp"] {
                background-color: #ffc107 !important;
                color: black !important;
                height: 40px !important;
                width: 100% !important;
                font-weight: 600 !important;
            }
            </style>
            """, unsafe_allow_html=True)

    create_camp = st.button("Create Campaign", key="create_camp")
    st.markdown("""
        <style>
        div.stButton > button[key="create_camp"] {
            background-color: #007bff !important;
            color: white !important;
            height: 50px !important;
            width: 100% !important;
            font-weight: 700 !important;
            font-size: 1.1rem !important;
            margin-top: 12px !important;
            border-radius: 8px !important;
        }
        </style>
        """, unsafe_allow_html=True)

    return start_sim, edit_camp, create_camp
