#!/usr/bin/env python
#
"""energy saving wsgi module."""
import os
import sys


current_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(current_dir)


from energy_saving.api import api


def initialize_application():
    api.init()
    application = api.app
    return application
