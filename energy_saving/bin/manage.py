#!/usr/bin/env python
#
"""utility binary to manage database."""
import os
import os.path
import sys


current_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(current_dir)


from flask_script import Manager


app_manager = Manager(app, usage="Perform database operations")


@app_manager.command
def list_config():
    "List the commands."
    for key, value in app.config.items():
        print key, value


def main():
    app_manager.run()


if __name__ == "__main__":
    main()
