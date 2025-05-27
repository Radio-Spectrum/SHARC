import streamlit as st
from ui.explorer import run_python_script

'''
def start_simulation():

def edit_campaigns():

def create_capaign():
'''

def render_campaign_buttons():
    # Use columns to have two side-by-side smaller buttons
    col1, col2 = st.columns(2)

    # Green "Start Simulation" button
    with col1:
        start_sim = st.button("Start Simulation", key="start_sim")
        st.markdown("""
            <style>
            div.stButton > button[key="start_sim"] {
                background-color: #28a745 !important;  /* Green */
                color: white !important;
                height: 40px !important;
                width: 100% !important;
                font-weight: 600 !important;
            }
            </style>
            """, unsafe_allow_html=True)

    # Yellow "Edit Campaigns" button
    with col2:
        edit_camp = st.button("Edit Campaigns", key="edit_camp")
        st.markdown("""
            <style>
            div.stButton > button[key="edit_camp"] {
                background-color: #ffc107 !important;  /* Yellow */
                color: black !important;
                height: 40px !important;
                width: 100% !important;
                font-weight: 600 !important;
            }
            </style>
            """, unsafe_allow_html=True)

    # Big blue button below spanning full width (2 columns)
    create_camp = st.button("Create Campaign", key="create_camp")
    st.markdown("""
        <style>
        div.stButton > button[key="create_camp"] {
            background-color: #007bff !important; /* Blue */
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
