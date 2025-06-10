
# Create a Simulation Campaign

---

## 1. Setup the Environment

### Step 1: Create the Campaign Folder
Choose a descriptive name for your campaign folder based on the simulation parameters.  
- **Example:** `imt_hibs_ras_2600_MHz`

---

### Step 2: Structure the Campaign Folder
Create the following subfolders to organize your files:

- **`input` Folder:**  
  Stores all input configuration files.  
  - **Path:** `campaigns/imt_hibs_ras_2600_MHz/input/`  
  - **Contents:** `.yaml` files with simulation parameters.

- **`output` Folder:**  
  SHARC saves all simulation results here.  
  - **Path:** `campaigns/imt_hibs_ras_2600_MHz/output/`  
  - **Contents:** Simulation data and visualizations.

- **`scripts` Folder:**  
  Contains scripts for running simulations and analyzing results.  
  - **Path:** `campaigns/imt_hibs_ras_2600_MHz/scripts/`  
  - **Contents:** Python scripts for running or plotting results from campaigns.

---

## 2. Configuring Your Simulation  

### Step 3: Create a Parameter File
Define your simulation parameters in a `.yaml` file.  
- **Example File:** `parameters_hibs_ras_2600_MHz_0km.yaml`  
- **Location:** `campaigns/imt_hibs_ras_2600_MHz/input/`

---

### Step 4: Define Simulation Parameters in the `.yaml` File
Customize your simulation settings in the `.yaml` file. Key sections include:

```yaml
general:
    ###########################################################################
    # Number of simulation snapshots
    num_snapshots: 1000
    ###########################################################################
    # IMT link that will be simulated (DOWNLINK or UPLINK)
    imt_link: DOWNLINK
    ###########################################################################
    # The chosen system for sharing study
    # EESS_PASSIVE, FSS_SS, FSS_ES, FS, RAS,
    system: RAS
    ###########################################################################
**(example)**
```

---

### Step 5: Create Multiple Simulation Configurations
To study different scenarios, create additional `.yaml` files in the `input` folder.  
- **Examples:**  
  - `parameters_hibs_ras_2600_MHz_10km.yaml`  
  - `parameters_hibs_ras_2600_MHz_20km.yaml`  

---

## 3. Running Simulations  

### Step 6: Run the Simulations
In the `scripts` folder, create Python scripts to automate simulation execution.

#### Multi-threaded Simulation
Run multiple simulations in parallel for efficiency.  
- **Script:** `start_simulations_multi_thread.py`  

```python
from sharc.run_multiple_campaigns_mut_thread import run_campaign

# Set the campaign name
# The name of the campaign to run. This should match the name of the campaign directory.
name_campaign = "imt_mss_ras_2600_MHz"

# Run the campaigns
# This function will execute the campaign with the given name.
# It will look for the campaign directory under the specified name and start the necessary processes.
run_campaign(name_campaign)
**(example)**
```

#### Single-threaded Simulation
Run a single simulation for testing purposes.  
- **Script:** `start_simulations_single_thread.py`  

```python
from sharc.run_multiple_campaigns import run_campaign

# Set the campaign name
# The name of the campaign to run. This should match the name of the campaign directory.
name_campaign = "imt_mss_ras_2600_MHz"

# Run the campaign in single-thread mode
# This function will execute the campaign with the given name in a single-threaded manner.
# It will look for the campaign directory under the specified name and start the necessary processes.
run_campaign(name_campaign)
**(example)**
```

---

## 4. Post-processing and Analyzing Results  

### Step 7: Post-process and Analyze Results
Create scripts to read the output data and generate visualizations.

#### Example Plot Script: `plot_results.py`  
This script reads simulation data and generates plots.

---
