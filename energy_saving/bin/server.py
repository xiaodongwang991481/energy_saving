#!/usr/bin/env python
#
"""energy saving wsgi module."""
import os
import sys


current_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(current_dir)


from energy_saving.api import api


def main():
    application = api.init()
    application.run(
        host='0.0.0.0', port=CONF.server_port
    )


if __name__ == '__main__':
    main()
