import streamlit as st
import yaml
import ui.manage_campaigns as mng_cp

def yaml_editor(select_campaign, selected_file):
    file_path = mng_cp.CAMPAIGN_DIR / select_campaign / "input" / selected_file

    if not file_path.exists():
        st.error(f"File not found: {file_path}")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    edited_content = st.text_area(
        label="Edit YAML content:",
        value=content,
        height=400,
        key=f"editor_{select_campaign}_{selected_file}"
    )

    if st.button("💾 Save Changes", key=f"save_{select_campaign}_{selected_file}"):
        try:
            yaml.safe_load(edited_content)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(edited_content)
            st.success("✅ File saved successfully!")
        except yaml.YAMLError as e:
            st.error(f"❌ YAML syntax error:\n\n{e}")
