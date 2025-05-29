import streamlit as st
from pathlib import Path
from ui.explorer import run_python_script

# ===============================
# Utils
# ===============================
def find_project_root(folder_name="sharc") -> Path | None:
    current_path = Path(__file__).resolve()
    return next((p for p in current_path.parents if (p / folder_name).exists()), None)

def get_campaign_dir() -> Path | None:
    root = find_project_root("sharc")
    return root / "sharc" / "campaigns" if root else None

CAMPAIGN_DIR = get_campaign_dir()

# ===============================
# Validation
# ===============================
def check_campaign_dir() -> bool:
    """Check if the campaigns directory exists and is a valid directory."""
    if CAMPAIGN_DIR is None:
        st.error("Could not find the 'sharc' folder in the directory hierarchy. Please check your project structure.")
        return False
    if not CAMPAIGN_DIR.exists():
        st.error(f"The directory '{CAMPAIGN_DIR}' does not exist. Please create it manually.")
        return False
    if not CAMPAIGN_DIR.is_dir():
        st.error(f"'{CAMPAIGN_DIR}' exists but is not a directory.")
        return False
    return True

# ===============================
# Campaign Creation
# ===============================
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
            campaign_path.mkdir(parents=True, exist_ok=False)
            script_path.mkdir(exist_ok=False)
            input_path.mkdir(exist_ok=False)

            st.session_state.campaign = campaign_name
            st.success(f"Campaign '{campaign_name}' created successfully with subfolders 'script' and 'input'!")
            st.session_state.logs = st.session_state.get("logs", [])
            st.session_state.logs.append(f"Created: {campaign_path} with 'script' and 'input' subfolders")

# ===============================
# Campaign Simulation
# ===============================
@st.dialog("Start Simulation")
def start_simulation():
    if not check_campaign_dir():
        return

    list_campaigns = [f.name for f in CAMPAIGN_DIR.iterdir() if f.is_dir()]
    select_campaign = st.selectbox("Select a campaign to simulate:", list_campaigns, index=None, placeholder="Select an option")

    script_type = st.radio("Choose simulation type:", ["Multi-thread", "Single-thread"], horizontal=True)
    script_file = "start_simulations_multi_thread.py" if script_type == "Multi-thread" else "start_simulations_single_thread.py"

    if st.button("Start Simulation"):
        simulate_script = CAMPAIGN_DIR / select_campaign / "scripts" / script_file
        if simulate_script.exists():
            run_python_script(str(simulate_script))
            st.success("Simulation started in terminal instance!")
        else:
            st.error(f"Simulation script '{script_file}' not found in the selected campaign.")

# ===============================
# Placeholder for Editing
# ===============================
def edit_campaigns():
    st.info("Edit campaigns feature coming soon.")

# ===============================
# Campaign Button Renderer
# ===============================
def apply_button_style(key: str, color: str, text_color: str = "white", height="40px", font_size="1rem"):
    st.markdown(f"""
        <style>
        div.stButton > button[key=\"{key}\"] {{
            background-color: {color} !important;
            color: {text_color} !important;
            height: {height} !important;
            width: 100% !important;
            font-weight: 600 !important;
            font-size: {font_size} !important;
            border-radius: 8px !important;
        }}
        </style>
    """, unsafe_allow_html=True)

def render_campaign_buttons():
    col1, col2 = st.columns(2)

    with col1:
        start_sim = st.button("Start Simulation", key="start_sim")
        apply_button_style("start_sim", "#28a745")

    with col2:
        edit_camp = st.button("Edit Campaigns", key="edit_camp")
        apply_button_style("edit_camp", "#ffc107", "black")

    create_camp = st.button("Create Campaign", key="create_camp")
    apply_button_style("create_camp", "#007bff", "white", "50px", "1.1rem")

    return start_sim, edit_camp, create_camp
