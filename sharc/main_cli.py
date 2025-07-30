# -*- coding: utf-8 -*-
"""
Created on Fri Aug 11 13:17:14 2017

@author: edgar
"""

import os
import sys
import getopt

from sharc.support.sharc_logger import Logging, SimulationLogger
from sharc.controller import Controller
from sharc.gui.view_cli import ViewCli
from sharc.model import Model


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

    param_file = ""

    try:
        opts, _ = getopt.getopt(argv, "hp:")
    except getopt.GetoptError:
        print("usage: main_cli.py -p <param_file>")
        sys.exit(2)

    if not opts:
        param_file = os.path.join(os.getcwd(), "input", "parameters.yaml")
    else:
        for opt, arg in opts:
            if opt == "-h":
                print("usage: main_cli.py -p <param_file>")
                sys.exit()
            elif opt == "-p":
                param_file = os.path.join(os.getcwd(), arg)

    # Logger setup start
    sim_logger = SimulationLogger(param_file)
    sim_logger.start()

    Logging.setup_logging()

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
