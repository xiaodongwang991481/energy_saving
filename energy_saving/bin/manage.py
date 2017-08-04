#!/usr/bin/env python
#
"""utility binary to manage database."""
import csv
import os
import os.path
import StringIO
import six
import sys


current_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(current_dir)


from flask_script import Manager

from energy_saving.api import api


app_manager = Manager(api.app, usage="Perform database operations")


@app_manager.command
def list_config():
    "List the commands."
    for key, value in app.config.items():
        print key, value


@app_manager.command
def generate_controller(datacenter):
    controller_prefix = 'CRAC'
    csv_header = ["location", "datacenter_name", "name", "properties"]
    string_buffer = StringIO.StringIO()
    writer = csv.writer(string_buffer)
    output = [csv_header]
    for i in range(1, 29):
        output.append([
            '{}', datacenter, '%s%d' % (controller_prefix, i), '{}'
        ])
    writer.writerows(output)
    print string_buffer.getvalue()


@app_manager.command
def generate_sensor(datacenter):
    sensor_prefix = 'TH'
    csv_header = ["location", "datacenter_name", "name", "properties"]
    string_buffer = StringIO.StringIO()
    writer = csv.writer(string_buffer)
    output = [csv_header]
    for i in range(1, 41):
        output.append([
            '{}', datacenter,
            '%s%s' % (sensor_prefix, format(i, '02d')), '{}'
        ])
    writer.writerows(output)
    print string_buffer.getvalue()


@app_manager.command
def generate_power_supply(datacenter):
    power_supply_prefix = 'PDF'
    csv_header = ["location", "datacenter_name", "name", "properties"]
    string_buffer = StringIO.StringIO()
    writer = csv.writer(string_buffer)
    output = [csv_header]
    for i in range(1, 21):
        output.append([
            '{}', datacenter,
            '%s%d' % (power_supply_prefix, i),
            '{}'
        ])
    writer.writerows(output)
    print string_buffer.getvalue()


@app_manager.command
def generate_controller_power_supply(datacenter):
    power_supply_prefix = '2AK'
    power_supply_suffix = '-B'
    csv_header = ["location", "datacenter_name", "name", "properties"]
    string_buffer = StringIO.StringIO()
    writer = csv.writer(string_buffer)
    output = [csv_header]
    for i in range(1, 4):
        output.append([
            '{}', datacenter,
            '%s%d%s' % (power_supply_prefix, i, power_supply_suffix),
            '{}'
        ])
    writer.writerows(output)
    print string_buffer.getvalue()


def _get_field_values(filename, field_name):
    header = []
    values = []
    with open(filename, 'r') as csv_file:
        reader = csv.reader(csv_file)
        for row in reader:
            if not row:
                continue
            if not header:
                header = row
            else:
                row_data = dict(zip(header, row))
                values.append(row_data[field_name])
    return values


@app_manager.command
def generate_controller_attribute_data(
    datacenter, controller_filename, controller_attribute_filename
):
    csv_header = ["datacenter_name", "controller_name", "name"]
    string_buffer = StringIO.StringIO()
    writer = csv.writer(string_buffer)
    output = [csv_header]
    controller_names = _get_field_values(controller_filename, 'name')
    controller_attribute_names = _get_field_values(
        controller_attribute_filename, 'name'
    )
    for controller_name in controller_names:
        for controller_attribute_name in controller_attribute_names:
            output.append([
                datacenter, controller_name, controller_attribute_name
            ])
    writer.writerows(output)
    print string_buffer.getvalue()


@app_manager.command
def generate_controller_parameter_data(
    datacenter, controller_filename, controller_parameter_filename
):
    csv_header = ["datacenter_name", "controller_name", "name"]
    string_buffer = StringIO.StringIO()
    writer = csv.writer(string_buffer)
    output = [csv_header]
    controller_names = _get_field_values(controller_filename, 'name')
    controller_parameter_names = _get_field_values(
        controller_parameter_filename, 'name'
    )
    for controller_name in controller_names:
        for controller_parameter_name in controller_parameter_names:
            output.append([
                datacenter, controller_name, controller_parameter_name
            ])
    writer.writerows(output)
    print string_buffer.getvalue()


@app_manager.command
def generate_sensor_attribute_data(
    datacenter, sensor_filename, sensor_attribute_filename
):
    csv_header = ["datacenter_name", "sensor_name", "name"]
    string_buffer = StringIO.StringIO()
    writer = csv.writer(string_buffer)
    output = [csv_header]
    sensor_names = _get_field_values(sensor_filename, 'name')
    sensor_attribute_names = _get_field_values(
        sensor_attribute_filename, 'name'
    )
    for sensor_name in sensor_names:
        for sensor_attribute_name in sensor_attribute_names:
            output.append([
                datacenter, sensor_name, sensor_attribute_name
            ])
    writer.writerows(output)
    print string_buffer.getvalue()


@app_manager.command
def generate_power_supply_attribute_data(
    datacenter, power_supply_filename, power_supply_attribute_filename
):
    csv_header = ["datacenter_name", "power_supply_name", "name"]
    string_buffer = StringIO.StringIO()
    writer = csv.writer(string_buffer)
    output = [csv_header]
    power_supply_names = _get_field_values(power_supply_filename, 'name')
    power_supply_attribute_names = _get_field_values(
        power_supply_attribute_filename, 'name'
    )
    for power_supply_name in power_supply_names:
        for power_supply_attribute_name in power_supply_attribute_names:
            output.append([
                datacenter, power_supply_name, power_supply_attribute_name
            ])
    writer.writerows(output)
    print string_buffer.getvalue()


@app_manager.command
def generate_controller_power_supply_attribute_data(
    datacenter, controller_power_supply_filename,
    controller_power_supply_attribute_filename
):
    csv_header = ["datacenter_name", "power_supply_name", "name"]
    string_buffer = StringIO.StringIO()
    writer = csv.writer(string_buffer)
    output = [csv_header]
    controller_power_supply_names = _get_field_values(
        controller_power_supply_filename, 'name'
    )
    controller_power_supply_attribute_names = _get_field_values(
        controller_power_supply_attribute_filename, 'name'
    )
    for controller_power_supply_name in controller_power_supply_names:
        for controller_power_supply_attribute_name in (
            controller_power_supply_attribute_names
        ):
            output.append([
                datacenter, controller_power_supply_name,
                controller_power_supply_attribute_name
            ])
    writer.writerows(output)
    print string_buffer.getvalue()


def main():
    app_manager.run()


if __name__ == "__main__":
    main()
