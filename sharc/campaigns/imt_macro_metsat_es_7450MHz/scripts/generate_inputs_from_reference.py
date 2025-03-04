import yaml
from pathlib import Path
import os

path_to_scripts = Path(__file__).parent

with open((path_to_scripts / "reference_input.yaml"), "r") as f:
    reference = yaml.full_load(f)

base = {}

CONST_KEYS = ["imt", "general"]
IGNORE_KEYS = ["generic"]

for key in CONST_KEYS:
    base[key] = reference[key]

inps = []

isd = 3 * 400 / 2
border = 2.5 * isd

for key in reference.keys():
    if key in CONST_KEYS or key in IGNORE_KEYS:
        continue
    for link in [
        # "ul",
        "dl"
    ]:
        for load in [0.2, 0.5]:
            for d in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]:
                from copy import deepcopy
                new_dic = {
                    "definition": {
                        "imt": deepcopy(reference["imt"]),
                        "general": deepcopy(reference["general"]),
                        "single_earth_station": deepcopy(reference[key]),
                    },
                    "key": f"{key}_{load}load_{d}km"
                }

                new_dic["definition"]["single_earth_station"]["param_p452"]["Hte"] = base["imt"]["bs"]["height"] if link == "dl" else base["imt"]["ue"]["height"]
                new_dic["definition"]["single_earth_station"]["geometry"]["location"]["fixed"]["x"] = border + d * 1000
                new_dic["definition"]["imt"]["frequency"] = reference[key]["frequency"]
                new_dic["definition"]["imt"]["bs"]["load_probability"] = load
                new_dic["definition"]["general"]["imt_link"] = "DOWNLINK" if link == "dl" else "UPLINK"
                new_dic["definition"]["general"]["adjacent_antenna_model"] = "BEAMFORMING" if link == "dl" else "SINGLE_ELEMENT"
                new_dic["definition"]["general"]["output_dir_prefix"] = base["general"]["output_dir_prefix"].replace(
                    "<subs>", f"{key}_{load}load_{d}km"
                )
                new_dic["definition"]["general"]["output_dir"] = base["general"]["output_dir"].replace(
                    "/output/", f"/output_{link}/"
                )

                inps.append(new_dic)

path_to_inputs = path_to_scripts / ".." / "input"

try:
    os.makedirs(path_to_inputs)
except FileExistsError:
    pass

for inp in inps:
    with open(path_to_inputs / ("parameter_" + inp["key"] + ".yaml"), "w") as f:
        yaml.dump(inp["definition"], f)
    
