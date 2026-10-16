import os
import json
import tempfile
import webbrowser
from ui.tabs.assets.preview_tab.webgl_globe_template import HTML_TEMPLATE

def generate_webgl_preview_from_json(json_data, open_in_browser=True):
    """
    Inject JSON data into the HTML template and open it in the default browser.
    """
    html_content = HTML_TEMPLATE.replace("__SCENARIO_DATA_PLACEHOLDER__", json.dumps(json_data))
    
    fd, path = tempfile.mkstemp(prefix="sharc_webgl_preview_", suffix=".html")
    os.close(fd)
    
    with open(path, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    if open_in_browser:
        webbrowser.open('file://' + path.replace('\\', '/'))
        
    return path
