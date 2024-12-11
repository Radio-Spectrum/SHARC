# -*- coding: utf-8 -*-
"""
Created on Fri Aug 11 13:17:14 2017

@author: edgar
"""

from sharc.support.logging import Logging
from sharc.controller import Controller
from sharc.gui.view_cli import ViewCli
from sharc.model import Model
import sys
import argparse
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))


def main(argv):
    print("Welcome to SHARC!\n")

    cli_parser = argparse.ArgumentParser(prog='main_cli.py')
    default_parameter_file = os.path.abspath(os.path.join(__file__, "..", "input", "parameters.yaml"))

    cli_parser.add_argument(
        "-p", "--parameter-file",
        # default value
        default=[default_parameter_file],
        nargs=1,
        help=f"Specify a parameter (.yaml) file to use for simulation. Default value: '{default_parameter_file}'"
    )

    cli_parser.add_argument(
        "-ov", "--overwrite-parameter",
        type=lambda x: tuple(x.split("=")),
        nargs='*',
        help="Specify one or more parameters to overwrite from parameter file.",
    )

    args = cli_parser.parse_args()
    param_file = args.parameter_file[0]
    overwrite_params = args.overwrite_parameter

    Logging.setup_logging()

    model = Model()
    view_cli = ViewCli()
    controller = Controller()

    view_cli.set_controller(controller)
    controller.set_model(model)
    model.add_observer(view_cli)

    view_cli.initialize(param_file, overwrite_parameters=overwrite_params)


if __name__ == "__main__":
    main(sys.argv[1:])
