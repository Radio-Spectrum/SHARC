# -*- coding: utf-8 -*-
"""
Created on Mon Dec 26 17:05:49 2016

@author: edgar
"""

from sharc.support.sharc_logger import Logging
from sharc.controller import Controller
from sharc.gui.view import View
from sharc.model import Model
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))


def main():
    Logging.setup_logging()

    model = Model()
    view = View()
    controller = Controller()

    view.set_controller(controller)
    controller.set_model(model)
    model.add_observer(view)

    view.mainloop()


if __name__ == "__main__":
    main()
