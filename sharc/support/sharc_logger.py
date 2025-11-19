# -*- coding: utf-8 -*-
import os
import sys
import yaml
import logging
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional


class Logging:
    """Logging utility class for configuring application logging."""

    @staticmethod
    def setup_logging(
        default_path="support/logging.yaml",
        default_level=logging.INFO,
        env_key="LOG_CFG",
    ):
        """Set up logging configuration for the application."""
        path = default_path
        value = os.getenv(env_key, None)
        if value:
            path = value
        if os.path.exists(path):
            with open(path, "rt") as f:
                config = yaml.safe_load(f.read())
            config['root']['level'] = logging.getLevelName(default_level)
            logging.config.dictConfig(config)
        else:
            logging.basicConfig(level=default_level)


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

    def _run_git_cmd(self, args: list[str]) -> Optional[str]:
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

    def _get_installed_packages(self) -> list[str]:
        try:
            output = subprocess.check_output(
                [sys.executable, "-m", "pip", "freeze"], stderr=subprocess.DEVNULL
            )
            return sorted(output.decode().strip().splitlines())
        except subprocess.CalledProcessError:
            return ["Could not retrieve packages"]
