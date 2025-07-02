# -*- coding: utf-8 -*-
"""
Created on Fri Aug 11 13:17:14 2017

@author: edgar
"""

from sharc.support.sharc_logger import Logging
from sharc.controller import Controller
from sharc.gui.view_cli import ViewCli
from sharc.model import Model
import sys
import getopt
import os
import argparse
import logging
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))


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

    param_file = ''

    parser = argparse.ArgumentParser(description="Run the SHARC command-line interface.")
    parser.add_argument(
        "-p", "--param_file",
        type=str,
        required=True,
        help="Path to the parameter file (required)"
    )
    parser.add_argument(
        "-l", "--log_level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the logging level (default: INFO)"
    )
    args = parser.parse_args(argv)
    param_file = os.path.abspath(args.param_file)

    log_level = getattr(logging, args.log_level.upper(), logging.INFO)
    Logging.setup_logging(default_level=log_level)

    model = Model()
    view_cli = ViewCli()
    controller = Controller()

    view_cli.set_controller(controller)
    controller.set_model(model)
    model.add_observer(view_cli)

    view_cli.initialize(param_file)


if __name__ == "__main__":
    main(sys.argv[1:])
