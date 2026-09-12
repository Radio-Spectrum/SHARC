import subprocess
import os
import sys
import re
from concurrent.futures import ThreadPoolExecutor

# Máximo de simulações em paralelo (padrão). Limita o uso de CPU para evitar
# saturar todos os núcleos e superaquecer a máquina. Pode ser sobrescrito pela
# variável de ambiente SHARC_MAX_PARALLEL ou pelo argumento max_parallel.
MAX_PARALLEL_SIMS = 18


def run_command(param_file, main_cli_path):
    """
    Run the main_cli.py script with the specified parameter file.

    Args:
        param_file (str): Path to the parameter file.
        main_cli_path (str): Path to the main_cli.py script.
    """
    command = [sys.executable, main_cli_path, "-p", param_file]
    subprocess.run(command)


def run_campaign(campaign_name, max_parallel=None, param_name_regex=None):
    """
    Run a campaign by executing main_cli.py for each parameter file in the
    campaign's input directory, several at a time.

    Args:
        campaign_name (str): Name of the campaign (directory under campaigns/).
        max_parallel (int, optional): Maximum number of simultaneous
            simulations. Defaults to the SHARC_MAX_PARALLEL environment
            variable, or MAX_PARALLEL_SIMS when it is not set.
        param_name_regex (str, optional): Only run the .yaml files whose name
            matches this regular expression (re.match). Defaults to all.
    """
    # Path to the working directory
    workfolder = os.path.dirname(os.path.abspath(__file__))
    main_cli_path = os.path.join(workfolder, "main_cli.py")

    # Campaign directory
    campaign_folder = os.path.join(
        workfolder, "campaigns", campaign_name, "input",
    )

    # List of parameter files
    pat = re.compile(param_name_regex) if param_name_regex else None
    parameter_files = sorted(
        os.path.join(campaign_folder, f) for f in os.listdir(campaign_folder)
        if f.endswith('.yaml') and (pat is None or pat.match(f))
    )

    if len(parameter_files) == 0:
        raise ValueError(
            f"No parameter files were found in {campaign_folder}"
            + (f" matching {param_name_regex!r}" if param_name_regex else "")
        )

    if max_parallel is None:
        max_parallel = int(os.environ.get("SHARC_MAX_PARALLEL", MAX_PARALLEL_SIMS))

    # Number of threads: limitado por max_parallel para não usar todos os CPUs.
    num_threads = min(len(parameter_files), os.cpu_count(), max_parallel)
    print(f"{len(parameter_files)} simulacoes, {num_threads} em paralelo")

    # Run the commands in parallel
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        executor.map(
            run_command, parameter_files, [
                main_cli_path,
            ] * len(parameter_files),
        )


def run_campaign_re(campaign_name, param_name_regex, max_parallel=None):
    """
    Run a campaign for parameter files matching a given regular expression.
    Kept for backwards compatibility; same as run_campaign(..., param_name_regex=...).
    """
    run_campaign(campaign_name, max_parallel=max_parallel,
                 param_name_regex=param_name_regex)


if __name__ == "__main__":
    # Example usage
    run_campaign("imt_hibs_ras_2600_MHz")
