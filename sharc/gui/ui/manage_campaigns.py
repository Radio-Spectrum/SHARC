import streamlit as st
from pathlib import Path
from ui.explorer import run_python_script
from ui.explorer import stop_script
from core.text_editor import yaml_editor 

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
# Stop simulation
# ===============================

@st.dialog("Stop Simulation")
def stop_simulation():
    st.write("⚠️ Are you sure you want to stop the simulation?")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Yes, stop it"):
            success, msg = stop_script()
            st.success(msg) if success else st.error(msg)
    with col2:
        if st.button("❌ Cancel"):
            st.info("Simulation was not stopped.")
            st.rerun()



# ===============================
# Placeholder for Editing
# ===============================


def edit_campaigns():
    if not check_campaign_dir():
        return
    
    list_campaigns = [f.name for f in CAMPAIGN_DIR.iterdir() if f.is_dir()]
    select_campaign = st.selectbox("Select a campaign:", list_campaigns, index=None)

    if select_campaign:
        input_dir = CAMPAIGN_DIR / select_campaign / "input"
        if input_dir.exists():
            list_files = [f.name for f in input_dir.glob("*.yaml") if f.is_file()]
            selected_file = st.selectbox("Select a YAML file:", list_files, index=None)

            if selected_file:
                edit_campaign_page([select_campaign, selected_file])
        else:
            st.warning(f"No input folder found for campaign '{select_campaign}'.")


def edit_campaign_page(select_var = None):
    if len(select_var) < 1:
        st.error("Failed to select file to edit.")
        return

    campaign = select_var[0]
    file = select_var[1]

    if not campaign or not file:
        st.warning("No file selected for editing.")
        return

    st.header(f"📝 Editing {str(file).split("/")[-1]}")

    tabs = st.tabs(["📁 File Info", "📝 Edit YAML"])

    with tabs[0]:
        path = CAMPAIGN_DIR / campaign / "input" / file
        st.markdown(f"""
            **Campaign:** {campaign}  
            **File:** {file}  
            **Path:** {path}
        """)

    with tabs[1]:
        yaml_editor(campaign, file)


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
    col1, col2, col3 = st.columns(3)

    with col1:
        start_sim = st.button("Start Simulation", key="start_sim")
        apply_button_style("start_sim", "#28a745")  # green

    with col2:
        stop_sim = st.button("Stop Simulation", key="stop_sim")
        apply_button_style("stop_sim", "#dc3545")  # red

    with col3:
        edit_camp = st.button("Edit Campaigns", key="edit_camp")
        apply_button_style("edit_camp", "#ffc107", "black")  # yellow

    create_camp = st.button("Create Campaign", key="create_camp")
    apply_button_style("create_camp", "#007bff", "white", "50px", "1.1rem")  # blue

    return start_sim, stop_sim, edit_camp, create_camp 
