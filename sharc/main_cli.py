# -*- coding: utf-8 -*-
"""
Created on Fri Aug 11 13:17:14 2017

@author: edgar
"""

import os
import sys
import argparse

from sharc.support.sharc_logger import setup_logging, SimulationLogger
from sharc.controller import Controller
from sharc.gui.view_cli import ViewCli
from sharc.model import Model


sys.path.append(os.path.join(os.path.dirname(__file__), ".."))


def _scenario_of_project(path):
    """A `.sharc` project holds the engine YAML: write it to a temporary file and run that (the GUI writes absolute
    paths for its data files, so the YAML does not depend on where it sits)."""
    import tempfile
    from sharc.gui.core.project_file import ProjectError, extract_scenario
    name = os.path.splitext(os.path.basename(path))[0]
    folder = tempfile.mkdtemp(prefix="sharc_project_")
    try:
        out = extract_scenario(path, os.path.join(folder, f"{name}.yaml"))
    except ProjectError as exc:
        sys.exit(f"Cannot open the project: {exc}")
    print(f"Project {path}: running its scenario ({out})\n")
    return out


def main(argv):
    """
    Run the main entry point for the SHARC command-line interface.

    Parses command-line arguments, sets up logging, initializes the Model, ViewCli, and Controller,
    connects them, and starts the simulation using the provided parameter file.

    Parameters
    ----------
    argv : list
        List of command-line arguments passed to the script.
    """
    print("Welcome to SHARC!\n")

    param_file = ""

    parser = argparse.ArgumentParser(description="SHARC - Radio Sharing and Compatiblity Monte Carlo Simulator")
    parser.add_argument("-p", "--param-file", default=os.path.join(os.getcwd(), "input", "parameters.yaml"),
                        help="Path to the parameter file: a YAML, or a .sharc project (default: input/parameters.yaml)")
    parser.add_argument("-l", "--log-file", default=None,
                        help="Path to output log file (optional)")

    args = parser.parse_args(argv)
    param_file = os.path.join(os.getcwd(), args.param_file) if not os.path.isabs(args.param_file) else args.param_file
    if param_file.lower().endswith(".sharc"):
        param_file = _scenario_of_project(param_file)

    log_file = None
    if args.log_file is not None:
        log_file = os.path.join(os.getcwd(), args.log_file) if not os.path.isabs(args.log_file) else args.log_file

    setup_logging(log_file=log_file)

    # Logger setup start
    sim_logger = SimulationLogger(param_file)
    sim_logger.start()

    model = Model()
    view_cli = ViewCli()
    controller = Controller()

    view_cli.set_controller(controller)
    controller.set_model(model)
    model.add_observer(view_cli)

    try:
        view_cli.initialize(param_file)
    finally:
        sim_logger.end()


if __name__ == "__main__":
    main(sys.argv[1:])
