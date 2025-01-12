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
isd = 450
for key in reference.keys():
    if key in CONST_KEYS or key in IGNORE_KEYS:
        continue
    for link in [
        "ul",
        "dl"
    ]:
        for d in [4, 5, 6, 7, 8, 9, 10]:
            inps.append({
                "definition": {
                    "single_earth_station": {
                        **reference[key],
                        "param_p452": {
                            **reference[key]["param_p452"],
                            "Hte": base["imt"]["bs"]["height"] if link == "dl" else base["imt"]["ue"]["height"]
                        }
                    },
                    "imt": {
                        **base["imt"],
                        "spurious_emissions": base["imt"]["spurious_emissions"] if link == "dl" else -25,
                        "frequency": reference[key]["frequency"]
                    },
                    "general": {
                        **base["general"],
                        "imt_link": "DOWNLINK" if link == "dl" else "UPLINK",
                        "adjacent_antenna_model": "BEAMFORMING" if link == "dl" else "SINGLE_ELEMENT",
                        "output_dir_prefix":
                            base["general"]["output_dir_prefix"].replace(
                                "<subs>", f"{key}_{int(d)}km"
                            ),
                            "output_dir": base["general"]["output_dir"].replace(
                                "/output/", f"/output_{link}/"
                            )
                    },
                },
                "key": f"{key}_{int(d)}km_{link}",
                "bs_x": d * 1000
            })

path_to_inputs = path_to_scripts / ".." / "input"

try:
    os.makedirs(path_to_inputs)
except FileExistsError:
    pass

for inp in inps:
    inp["definition"]["single_earth_station"]["geometry"]["location"]["fixed"]["x"] = inp["bs_x"]
    with open(path_to_inputs / ("parameter_" + inp["key"] + ".yaml"), "w") as f:
        yaml.dump(inp["definition"], f)
    
