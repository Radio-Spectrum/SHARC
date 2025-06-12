# Run the Simulator Using the Main Client Interface

---

The SHARC simulator can be executed via the main client interface script, `main_cli.py`. This guide walks you through the steps to run the SHARC simulator using this command-line interface (CLI).

## 1. Prerequisites

Before running the simulator, make sure you have:

- Python installed (preferably Python 3.12 or higher).
- All required dependencies installed. If not, use the following command to install them:
  ```bash
  pip install -r requirements.txt
  ```
- A valid configuration file (`parameters.yaml`) containing the necessary simulation parameters.

## 2. Directory Structure

Ensure that your directory structure is set up as follows:

```
sharc/
    ├── controller/
    ├── gui/
    ├── model/
    ├── parameters/
    ├── support/
    └── main_cli.py       # Main client interface script
```

- Place the `parameters.yaml` file inside the `input/` folder or specify it through the command line.

## 3. Command-Line Arguments

To run the simulator, use the following command:

```bash
python main_cli.py -p <param_file>
```

Where:
- `-p <param_file>`: Specifies the path to the configuration parameter file (e.g., `parameters.yaml`). If not specified, it defaults to `input/parameters.yaml`.

For additional help on usage, run:

```bash
python main_cli.py -h
```

This will show usage instructions:

```
usage: main_cli.py -p <param_file>
```

## 4. Running the Simulator

### Steps to Run

1. **Navigate to the SHARC directory:**
   Change to the directory where the SHARC project is located:
   ```bash
   cd /path/SHARC/sharc
   ```

2. **Run the simulator:**
   To run the simulator with a specific parameters file, use:
   ```bash
   python main_cli.py -p /path/to/parameters.yaml
   ```

   If you don't specify a parameters file, it will default to `input/parameters.yaml`:
   ```bash
   python main_cli.py
   ```

3. **View Logs:**
   The simulation will start, and logs will be displayed in the terminal. You can monitor these logs for progress and results. Logging is automatically set up via the `Logging.setup_logging()` function.

## 5. Parameters File

The configuration file (`parameters.yaml`) should define the simulation parameters.


### Example `parameters.yaml`

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

These parameters will be used by the simulator during execution, and you can modify them as needed.

## 6. Simulator Components

- **Model**: Handles the core logic and processes the simulation data.
- **ViewCli**: Provides the command-line interface to show progress and results.
- **Controller**: Manages the interaction between the Model and View.
- **Logging**: Captures logs for tracking the simulation's progress and any issues.

## 8. Handling Errors

If there is an issue with the parameters file or setup, the simulator will print an error message, such as:

```
ERROR: Could not find the configuration file /path/to/parameters.yaml
```

Ensure that the file path is correct and that the configuration file is formatted properly.

---
