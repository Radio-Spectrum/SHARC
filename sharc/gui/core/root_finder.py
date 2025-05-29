import os
from pathlib import Path

def find_project_root(folder_name = "sharc") -> Path | None:

    current_path = Path(__file__).resolve()
    for parent in current_path.parents:
        if (parent / folder_name).exists():
            return parent
    return None

if find_project_root == None:
    print("Not found")
else:
    PROJECT_ROOT = str(find_project_root("sharc")) 
    print(PROJECT_ROOT)
    