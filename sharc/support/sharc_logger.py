# -*- coding: utf-8 -*-
import csv
import os
import sys
import yaml
import logging.config
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, List

level_mapping = logging.getLevelNamesMapping()


def setup_logging(log_file=None, default_level="INFO"):
    """Setup logging configuration for the root logger.

    Run this function in the beginning of the simulation to setup the root logger.
    """

    try:
        level = level_mapping[default_level]
    except KeyError:
        raise ValueError("Invalid log level option {}".format(default_level))

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    root_logger.handlers = []

    # Stream to stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Stream to file if specified
    if log_file is not None:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


class SimulationLogger:
    """
    Logs simulation metadata to a YAML file for reproducibility.
    Also manages an optional global output directory.
    """

    _global_output_dir: Optional[Path] = None

    @classmethod
    def set_output_dir(cls, path: Path):
        """Set the global output directory for simulation logs."""
        cls._global_output_dir = path.resolve()

    @classmethod
    def get_output_dir(cls) -> Optional[Path]:
        """Return the global output directory, if set."""
        return cls._global_output_dir

    @classmethod
    def log_to_csv(
        cls,
        csv_name: str,
        vals: list
    ):
        """
        Log a list of values to a CSV file.
        Args:
            csv_name (str): The name of the CSV file (without extension).
            vals (list): A list of values to be logged to the CSV file.
        Returns:
            None
        Notes:
            - Creates a new CSV file if it doesn't exist.
            - Appends values to the file if it already exists.
            - Automatically writes a "samples" header row for new files.
            - Each value is written as a separate row in a single column.
        """
        if cls._global_output_dir is None:
            # Output directory not yet initialized, skip CSV logging
            return

        p = cls._global_output_dir / f"{csv_name}.csv"

        write_header = not p.exists()

        data = [[v] for v in vals]
        with open(p, "a", newline="") as file:
            writer = csv.writer(file)
            if write_header:
                writer.writerow(["samples"])

            writer.writerows(data)

    def __init__(self, param_file: str, log_base: str = "simulation_log"):
        self.param_file: Path = Path(param_file).resolve()
        self.param_name: str = self.param_file.stem
        self.timestamp: str = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        self.log_base: str = log_base
        self.start_time: Optional[datetime] = None

        self.output_dir: Optional[Path] = None
        self.log_path: Optional[Path] = None
        self.root_dir: Optional[Path] = self._find_root_dir("sharc")

        self.data = {
            "repo": self._get_git_info(),
            "root_dir": str(self.root_dir) if self.root_dir else "N/A",
            "run": {
                "command": self._get_invocation_command(),
                "python_version": self._get_python_version(),
                "pkgs": self._get_installed_packages(),
            },
        }

    def start(self):
        """Start the simulation timer and record start time."""
        self.start_time = datetime.now()
        self.data["run"]["started_at"] = self.start_time.isoformat()

    def end(self):
        """Stop timer, calculate duration, create output folder, and save YAML log."""
        end_time = datetime.now()
        self.data["run"]["ended_at"] = end_time.isoformat()

        if self.start_time:
            duration = end_time - self.start_time
            self.data["run"]["duration"] = str(duration)

        base_dir = self.get_output_dir() or Path.cwd() / "logs"
        self.output_dir = base_dir / f"simulation_{self.param_name}_{self.timestamp}"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.log_path = self.output_dir / f"{self.log_base}_{self.timestamp}.yaml"

        with open(self.log_path, "w") as f:
            yaml.dump(self.data, f, sort_keys=False, allow_unicode=True)

        print(f"Simulation log saved in {self.output_dir}")

    def _find_root_dir(self, folder_name: str) -> Optional[Path]:
        """Search upward for a directory containing the given folder."""
        for parent in self.param_file.parents:
            if (parent / folder_name).exists():
                return parent
        return None

    def _run_git_cmd(self, args: List[str]) -> Optional[str]:
        try:
            return (
                subprocess.check_output(["git"] + args, stderr=subprocess.DEVNULL)
                .decode()
                .strip()
            )
        except subprocess.CalledProcessError:
            return None

    def _get_git_info(self) -> dict:
        branch = self._run_git_cmd(["rev-parse", "--abbrev-ref", "HEAD"])
        commit = self._run_git_cmd(["rev-parse", "HEAD"])
        remote = (
            self._run_git_cmd(["config", f"branch.{branch}.remote"]) if branch else None
        )
        url = self._run_git_cmd(["config", f"remote.{remote}.url"]) if remote else None

        return {
            "url": url or "N/A",
            "branch": branch or "N/A",
            "commit": commit or "N/A",
        }

    def _get_invocation_command(self) -> str:
        return f"{sys.executable} {' '.join(sys.argv)}"

    def _get_python_version(self) -> str:
        return sys.version.replace("\n", " ")

    def _get_installed_packages(self) -> List[str]:
        try:
            output = subprocess.check_output(
                [sys.executable, "-m", "pip", "freeze"], stderr=subprocess.DEVNULL
            )
            return sorted(output.decode().strip().splitlines())
        except subprocess.CalledProcessError:
            return ["Could not retrieve packages"]
