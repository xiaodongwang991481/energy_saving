import datetime
from dateutil import parser
import functools
import logging
import numpy as np
import pandas as pd
import re
import six
import sys

from energy_saving.db import database
from energy_saving.db import exception
from energy_saving.db import models


logger = logging.getLogger(__name__)
if sys.version_info > (3,):
    long = int
    basestring = str
    string_types = (str, bytes)
else:
    string_types = (basestring,)


def _get_attribute_dict(attribute):
    return {
        'devices': [],
        'attribute': {
            'type': attribute.type,
            'unit': attribute.unit,
            'mean': attribute.mean,
            'deviation': attribute.deviation,
            'differentiation_mean': attribute.differentiation_mean,
            'differentiation_deviation': attribute.differentiation_deviation,
            'max': attribute.max,
            'min': attribute.min,
            'differentiation_max': attribute.differentiation_max,
            'differentiation_min': attribute.differentiation_min,
            'pattern': attribute.measurement_pattern
        }
    }


def _set_attribute_dict(attribute, data):
    attribute_data = data['attribute']
    if 'mean' in attribute_data:
        attribute.mean = attribute_data['mean']
    if 'deviation' in attribute_data:
        attribute.deviation = attribute_data['deviation']
    if 'differentiation_mean' in attribute_data:
        attribute.differentiation_mean = attribute_data[
            'differentiation_mean'
        ]
    if 'differentiation_deviation' in attribute_data:
        attribute.differentiation_deviation = attribute_data[
            'differentiation_deviation'
        ]


def _get_parameter_dict(parameter):
    return {
        'devices': [],
        'attribute': {
            'type': parameter.type,
            'unit': parameter.unit,
            'min': parameter.min,
            'max': parameter.max,
            'differentiation_max': parameter.differentiation_max,
            'differentiation_min': parameter.differentiation_min,
            'mean': None,
            'deviation': None,
            'differentiation_mean': None,
            'differentiation_deviation': None,
            'pattern': None
        }
    }


def _set_parameter_dict(parameter, data):
    pass


def get_sensor_attributes(datacenter):
    result = {}
    for attribute in datacenter.sensor_attributes:
        result[attribute.name] = _get_attribute_dict(attribute)
        attribute_data = result[attribute.name]['devices']
        for data in attribute.attribute_data:
            attribute_data.append(data.sensor_name)
    return result


def set_sensor_attributes(datacenter, data):
    for attribute in datacenter.sensor_attributes:
        if attribute.name in data:
            _set_attribute_dict(attribute, data[attribute.name])


def get_controller_attributes(datacenter):
    result = {}
    for attribute in datacenter.controller_attributes:
        result[attribute.name] = _get_attribute_dict(attribute)
        attribute_data = result[attribute.name]['devices']
        for data in attribute.attribute_data:
            attribute_data.append(data.controller_name)
    return result


def set_controller_attributes(datacenter, data):
    for attribute in datacenter.controller_attributes:
        if attribute.name in data:
            _set_attribute_dict(attribute, data[attribute.name])


def get_power_supply_attributes(datacenter):
    result = {}
    for attribute in datacenter.power_supply_attributes:
        result[attribute.name] = _get_attribute_dict(attribute)
        attribute_data = result[attribute.name]['devices']
        for data in attribute.attribute_data:
            attribute_data.append(data.power_supply_name)
    return result


def set_power_supply_attributes(datacenter, data):
    for attribute in datacenter.power_supply_attributes:
        if attribute.name in data:
            _set_attribute_dict(attribute, data[attribute.name])


def get_controller_power_supply_attributes(datacenter):
    result = {}
    for attribute in datacenter.controller_power_supply_attributes:
        result[attribute.name] = _get_attribute_dict(attribute)
        attribute_data = result[attribute.name]['devices']
        for data in attribute.attribute_data:
            attribute_data.append(data.controller_power_supply_name)
    return result


def set_controller_power_supply_attributes(datacenter, data):
    for attribute in datacenter.controller_power_supply_attributes:
        if attribute.name in data:
            _set_attribute_dict(attribute, data[attribute.name])


def get_environment_sensor_attributes(datacenter):
    result = {}
    for attribute in datacenter.environment_sensor_attributes:
        result[attribute.name] = _get_attribute_dict(attribute)
        attribute_data = result[attribute.name]['devices']
        for data in attribute.attribute_data:
            attribute_data.append(data.environment_sensor_name)
    return result


def set_environment_sensor_attributes(datacenter, data):
    for attribute in datacenter.environment_sensor_attributes:
        if attribute.name in data:
            _set_attribute_dict(attribute, data[attribute.name])


def get_controller_parameters(datacenter):
    result = {}
    for parameter in datacenter.controller_parameters:
        result[parameter.name] = _get_parameter_dict(parameter)
        parameter_data = result[parameter.name]['devices']
        for data in parameter.parameter_data:
            parameter_data.append(data.controller_name)
    return result


def set_controller_parameters(datacenter, data):
    for parameter in datacenter.controller_parameters:
        if parameter.name in data:
            _set_parameter_dict(parameter, data[parameter.name])


DEVICE_TYPE_METADATA_GETTERS = {
    'sensor_attribute': get_sensor_attributes,
    'controller_attribute': get_controller_attributes,
    'controller_parameter': get_controller_parameters,
    'power_supply_attribute': get_power_supply_attributes,
    'controller_power_supply_attribute': (
        get_controller_power_supply_attributes
    ),
    'environment_sensor_attribute': get_environment_sensor_attributes
}


DEVICE_TYPE_METADATA_SETTERS = {
    'sensor_attribute': set_sensor_attributes,
    'controller_attribute': set_controller_attributes,
    'controller_parameter': set_controller_parameters,
    'power_supply_attribute': set_power_supply_attributes,
    'controller_power_supply_attribute': (
        set_controller_power_supply_attributes
    ),
    'environment_sensor_attribute': set_environment_sensor_attributes
}


def _get_datacenter_device_type_metadata(datacenter, device_type):
    if device_type not in DEVICE_TYPE_METADATA_GETTERS:
        raise exception.RecordNotExists(
            'device type %s does not exist' % device_type
        )
    return DEVICE_TYPE_METADATA_GETTERS[device_type](datacenter)


def _set_datacenter_device_type_metadata(datacenter, device_type, data):
    if device_type not in DEVICE_TYPE_METADATA_SETTERS:
        raise exception.RecordNotExists(
            'device type %s does not exist' % device_type
        )
    DEVICE_TYPE_METADATA_SETTERS[device_type](datacenter, data)


def get_datacenter_device_type_metadata(
    session, datacenter_name, device_type
):
    datacenter = session.query(
        models.Datacenter
    ).filter_by(name=datacenter_name).first()
    if not datacenter:
        raise exception.RecordNotExists(
            'datacener %s does not exist' % datacenter_name
        )
    device_type_metadata = _get_datacenter_device_type_metadata(
        datacenter, device_type
    )
    logger.debug(
        'datacenter %s device type %s metadata: %s',
        datacenter_name, device_type, device_type_metadata
    )
    return device_type_metadata


def set_datacenter_device_type_metadata(
    session, datacenter_name, device_type, data
):
    logger.debug(
        'datacenter %s device type %s metadata: %s',
        datacenter_name, device_type, data
    )
    datacenter = session.query(
        models.Datacenter
    ).filter_by(name=datacenter_name).first()
    if not datacenter:
        raise exception.RecordNotExists(
            'datacener %s does not exist' % datacenter_name
        )
    _set_datacenter_device_type_metadata(
        datacenter, device_type, data
    )


def get_device_type_metadata_from_datacenter_metadata(
    datacenter_metadata, device_type
):
    return datacenter_metadata['device_types'][device_type]


def _get_datacenter_metadata(datacenter):
    result = {}
    for key, value in six.iteritems(DEVICE_TYPE_METADATA_GETTERS):
        result[key] = value(datacenter)
    return {
        'time_interval': datacenter.time_interval,
        'models': datacenter.models,
        'properties': datacenter.properties,
        'device_types': result
    }


def _set_datacenter_metadata(datacenter, data):
    device_type_data = data['device_types']
    for key, value in six.iteritems(DEVICE_TYPE_METADATA_SETTERS):
        if key in device_type_data:
            value(datacenter, device_type_data[key])


def get_datacenter_metadata(session, datacenter_name):
    datacenter = session.query(
        models.Datacenter
    ).filter_by(name=datacenter_name).first()
    if not datacenter:
        raise exception.RecordNotExists(
            'datacener %s does not exist' % datacenter_name
        )
    datacenter_metadata = _get_datacenter_metadata(datacenter)
    logger.debug(
        'datacenter %s metadata: %s',
        datacenter_name, datacenter_metadata
    )
    return datacenter_metadata


def set_datacenter_metadata(session, datacenter_name, data):
    logger.debug(
        'datacenter %s metadata: %s',
        datacenter_name, data
    )
    datacenter = session.query(
        models.Datacenter
    ).filter_by(name=datacenter_name).first()
    if not datacenter:
        raise exception.RecordNotExists(
            'datacener %s does not exist' % datacenter_name
        )
    _set_datacenter_metadata(datacenter, data)


def get_datacenter_metadata_from_metadata(metadata, datacenter_name):
    return metadata[datacenter_name]


def get_metadata(session):
    result = {}
    datacenters = session.query(models.Datacenter)
    for datacenter in datacenters:
        result[datacenter.name] = (
            _get_datacenter_metadata(datacenter)
        )
    return result


def set_metadata(session, data):
    datacenters = session.query(models.Datacenter)
    for datacenter in datacenters:
        if datacenter.name in data:
            _set_datacenter_metadata(datacenter, data[datacenter.name])


TIMESERIES_VALUE_CONVERTERS = {
    'binary': bool,
    'continuous': float,
    'integer': int
}


def update_timeseries_metadata(
    session, datacenter,
    starttime, endtime,
    device_type_units={}
):
    with database.session() as db_session:
        datacenter_metadata = get_datacenter_metadata(
            db_session, datacenter
        )
    logger.debug(
        'update_timeseries_metadata original metadata: %s',
        datacenter_metadata
    )
    time_interval = datacenter_metadata['time_interval']
    for device_type, device_type_metadata in six.iteritems(
        datacenter_metadata['device_types']
    ):
        for measurement, measurement_metadata in six.iteritems(
            device_type_metadata
        ):
            response = list_timeseries(
                session, {
                    'where': {
                        'starttime': starttime,
                        'endtime': endtime
                    },
                    'group_by': ['time(%ss)' % time_interval],
                    'order_by': ['time'],
                    'aggregation': 'mean',
                    'datacenter': datacenter,
                    'device_type': {
                        device_type: {
                            measurement: []
                        }
                    }
                },
                time_precision=None,
                convert_timestamp=True, format_timestamp=False,
                device_type_units=device_type_units,
                result_as_dataframe=True
            )
            response = response.dropna()
            result = response.values
            mean = result.mean()
            deviation = result.std()
            assert not np.isnan(mean)
            assert not np.isnan(deviation)
            time_offset = datetime.timedelta(seconds=time_interval)
            differentiation_response = (
                response.shift(-1, time_offset) - response
            )
            differentiation_response = differentiation_response.dropna()
            differentiation_result = differentiation_response.values
            differentiation_mean = differentiation_result.mean()
            differentiation_deviation = differentiation_result.std()
            assert not np.isnan(differentiation_mean)
            assert not np.isnan(differentiation_deviation)
            measurement_metadata['attribute']['mean'] = mean
            measurement_metadata['attribute']['deviation'] = deviation
            measurement_metadata['attribute']['differentiation_mean'] = (
                differentiation_mean
            )
            measurement_metadata['attribute']['differentiation_deviation'] = (
                differentiation_deviation
            )
    logger.debug('updated datacenter metadata: %s', datacenter_metadata)
    with database.session() as db_session:
        set_datacenter_metadata(db_session, datacenter, datacenter_metadata)


def convert_timeseries_value(
    value, value_type, raise_exception=False, default_value=None
):
    try:
        if value_type in TIMESERIES_VALUE_CONVERTERS:
            return TIMESERIES_VALUE_CONVERTERS[value_type](value)
        else:
            return value
    except Exception as error:
        logger.exception(error)
        logger.error(
            'failed to convert %r to %s: %s',
            value, value_type, error
        )
        if raise_exception:
            raise error
        else:
            return default_value


def continuous_format(value, base_value):
    return round(value, 2) + (base_value or 0)


def binary_format(value, base_value):
    return value


def int_format(value, base_value):
    return value + (base_value or 0)


TIMESERIES_VALUE_FORMATTERS = {
    'binary': binary_format,
    'integer': int_format,
    'continuous': continuous_format,
}


def format_timeseries_value(
    value, value_type, raise_exception=False, default_value=None,
    base_value=0
):
    if value is None:
        return None
    try:
        if value_type in TIMESERIES_VALUE_FORMATTERS:
            return TIMESERIES_VALUE_FORMATTERS[value_type](value, base_value)
        return value
    except Exception as error:
        logger.exception(error)
        logger.error(
            'failed to format %s in %s: %s',
            value, value_type, error
        )
        if raise_exception:
            raise error
        else:
            return default_value


def get_timestamp(timestamp_str):
    if not timestamp_str:
        return None
    if timestamp_str[0] in ['+', '-']:
        timestamp_str = 'now()' + timestamp_str
    if re.match(
        r'^(now\(\))?\s*[+-]?\s*\d+(u|ms|s|m|h|d|w)'
        r'(\s*[+-]\s*\d+(u|ms|s|m|h|d|w))*$',
        timestamp_str
    ):
        timestamp_str = re.sub(r'\s*?([+-])\s*?', r' \1 ', timestamp_str)
    else:
        timestamp_str = "'%s'" % parser.parse(timestamp_str)
    return timestamp_str


def _get_group_by(group_by):
    return ', '.join(group_by)


def _get_order_by(order_by):
    return ', '.join(order_by)


def get_where(
    starttime=None, endtime=None, **kwargs
):
    wheres = []
    if starttime:
        starttime = get_timestamp(starttime)
        wheres.append('time >= %s' % starttime)
    if endtime:
        endtime = get_timestamp(endtime)
        wheres.append('time < %s' % endtime)
    for key, value in six.iteritems(kwargs):
        if value is None:
            continue
        if isinstance(value, list):
            if not value:
                continue
            sub_wheres = []
            for item in value:
                sub_wheres.append("%s = '%s'" % (key, item))
            wheres.append('(%s)' % ' or '.join(sub_wheres))
        else:
            wheres.append("%s = '%s'" % (key, value))
    if wheres:
        return ' and '.join(wheres)
    else:
        return ''


def get_query(
    measurement, where=None, group_by=None, order_by=None,
    fill=None, aggregation=None, limit=None, offset=None
):
    if where:
        where = get_where(**where)
    if where:
        where_clause = ' where %s' % where
    else:
        where_clause = ''
    if aggregation:
        value = '%s(value) as value' % aggregation
    else:
        value = 'value'
    if group_by:
        group_by_clause = ' group by %s' % _get_group_by(group_by)
    else:
        group_by_clause = ''
    if order_by:
        order_by_clause = ' order by %s' % _get_order_by(order_by)
    else:
        order_by_clause = ''
    if fill:
        fill_clause = ' fill(%s)' % fill
    else:
        fill_clause = ''
    if limit:
        limit_clause = ' limit %s' % limit
    else:
        limit_clause = ''
    if offset:
        offset_clause = ' offset %s' % offset
    else:
        offset_clause = ''
    query = 'select %s from %s%s%s%s%s%s%s' % (
        value, measurement, where_clause,
        group_by_clause, order_by_clause, fill_clause,
        limit_clause, offset_clause
    )
    logger.debug('get query: %s', query)
    return query


def get_timestamp_converter(time_precision, dataframe=False):
    if dataframe:
        if not time_precision:
            return pd.Timestamp
        else:
            return functools.partial(pd.Timestamp, unit=time_precision)
    if not time_precision:
        return parser.parse
    else:
        return long


def get_timestamp_formatter(time_precision, dataframe=False):
    if dataframe:
        return str
    if not time_precision:
        return str
    else:
        return long


def get_query_from_data(
    datacenter, device_type, measurement, data
):
    query = data.get('query')
    where = data.get('where') or {}
    where['device_type'] = device_type
    where['datacenter'] = datacenter
    group_by = data.get('group_by') or []
    if isinstance(group_by, string_types):
        group_by = [group_by]
    if 'device' not in group_by:
        group_by = group_by + ['device']
    order_by = data.get('order_by') or []
    if isinstance(order_by, string_types):
        order_by = [order_by]
    fill = data.get('fill')
    aggregation = data.get('aggregation')
    limit = data.get('limit')
    if limit:
        limit = int(limit)
    offset = data.get('offset')
    if offset:
        offset = int(offset)
    if not query:
        query = get_query(
            measurement, where=where,
            group_by=group_by, order_by=order_by,
            fill=fill, aggregation=aggregation, limit=limit,
            offset=offset
        )
    logger.debug(
        'timeseries %s %s query: %s',
        device_type, measurement, query
    )
    return query


def get_device_type_mapping(
    device_types,
    datacenter_metadata,
    raise_exception=True
):
    logger.debug(
        'get_device_type_mapping device_types %s '
        'datacenter_metadata %s raise exception %s',
        device_types, datacenter_metadata,
        raise_exception
    )
    device_type_mapping = {}
    device_type_measurements = {}
    if not device_types:
        for device_type, device_type_metadata in six.iteritems(
            datacenter_metadata['device_types']
        ):
            device_type_measurements[device_type] = {}
    elif isinstance(device_types, string_types):
        device_type_measurements[device_types] = {}
    elif isinstance(device_types, list):
        for device_type in device_types:
            device_type_measurements[device_type] = {}
    else:
        device_type_measurements = device_types
    for device_type, measurements in six.iteritems(device_type_measurements):
        if device_type not in datacenter_metadata['device_types']:
            logger.debug('unknown device_type %s', device_type)
            if raise_exception:
                raise Exception('unknown device_type %s' % device_type)
            continue
        measurement_mapping = device_type_mapping.setdefault(
            device_type, {}
        )
        device_type_metadata = datacenter_metadata[
            'device_types'
        ][device_type]
        measurement_devices = {}
        if not measurements:
            for measurement, measurement_metadata in six.iteritems(
                device_type_metadata
            ):
                measurement_devices[measurement] = []
        elif isinstance(measurements, string_types):
            measurement_devices[measurements] = []
        elif isinstance(measurements, list):
            for measurement in measurements:
                measurement_devices[measurement] = []
        else:
            measurement_devices = measurements
        for measurement, devices in six.iteritems(measurement_devices):
            if measurement not in device_type_metadata:
                logger.debug(
                    'unknown device_type %s measurement %s',
                    device_type, measurement
                )
                if raise_exception:
                    raise Exception(
                        'unknown device_type %s measurement %s' % (
                            device_type, measurement
                        )
                    )
                continue
            measurement_metadata = device_type_metadata[measurement]
            if not devices:
                devices = measurement_metadata['devices']
            elif isinstance(devices, string_types):
                devices = [devices]
            real_devices = []
            for device in devices:
                if device not in measurement_metadata['devices']:
                    logger.debug(
                        'unknown device_type %s '
                        'measurement %s device %s',
                        device_type, measurement, device
                    )
                    if raise_exception:
                        raise Exception(
                            'unknown device_type %s '
                            'measurement %s device %s' % (
                                device_type, measurement, device
                            )
                        )
                    continue
                real_devices.append(device)
            measurement_mapping[measurement] = real_devices
    return device_type_mapping


def get_device_type_infos(
    session, datacenter, device_types,
    device_type_units={},
    raise_exception=True
):
    datacenter_metadata = get_datacenter_metadata(session, datacenter)
    device_type_mapping = get_device_type_mapping(
        device_types, datacenter_metadata, raise_exception=raise_exception
    )
    device_type_types = {}
    device_type_patterns = {}
    device_type_unit_converters = {}
    for device_type, measurement_mapping in six.iteritems(
        device_type_mapping
    ):
        device_type_metadata = datacenter_metadata[
            'device_types'
        ][device_type]
        measurement_types = device_type_types.setdefault(device_type, {})
        measurement_patterns = device_type_patterns.setdefault(
            device_type, {}
        )
        measurement_units = {}
        if device_type_units:
            measurement_units = device_type_units.get(device_type) or {}
        measurement_unit_converters = (
            device_type_unit_converters.setdefault(device_type, {})
        )
        for measurement in six.iterkeys(measurement_mapping):
            measurement_metadata = device_type_metadata[measurement]
            measurement_types[measurement] = measurement_metadata[
                'attribute'
            ]['type']
            measurement_pattern = measurement_metadata[
                'attribute'
            ]['pattern']
            if measurement_pattern:
                measurement_patterns[measurement] = measurement_pattern
            if measurement_units and measurement in measurement_units:
                measurement_unit = measurement_units[measurement]
                if measurement_unit:
                    measurement_unit_converters[measurement] = (
                        measurement_unit,
                        measurement_metadata['attribute']['unit']
                    )
    return (
        device_type_mapping, device_type_types,
        device_type_patterns, device_type_unit_converters
    )


def list_timeseries_internal(
    session, data, datacenter,
    time_precision=None,
    convert_timestamp=False, format_timestamp=True,
    device_type_mapping={}, device_type_types={},
    device_type_patterns={}, device_type_unit_converters={},
    result_as_dataframe=None,
    measurement_callback=None,
    data_callback=None
):
    dataframe = database.is_dataframe_session(session)
    if result_as_dataframe is None:
        result_as_dataframe = dataframe
    if convert_timestamp:
        timestamp_converter = get_timestamp_converter(
            time_precision, dataframe
        )
    else:
        timestamp_converter = None
    if format_timestamp:
        timestamp_formatter = get_timestamp_formatter(
            time_precision, dataframe
        )
    else:
        timestamp_formatter = None
    responses = []
    for device_type, measurements in six.iteritems(device_type_mapping):
        measurement_types = device_type_types.get(device_type) or {}
        measurement_patterns = device_type_patterns.get(device_type) or {}
        measurement_unit_converters = device_type_unit_converters.get(
            device_type
        ) or {}
        for measurement, devices in six.iteritems(measurements):
            measurement_type = measurement_types.get(measurement)
            measurement_pattern = measurement_patterns.get(measurement)
            measurement_unit_converter = measurement_unit_converters.get(
                measurement
            )
            if measurement_pattern:
                pattern = r'/^%s$/' % measurement_pattern
            else:
                pattern = measurement
            if measurement_callback:
                if callable(measurement_callback):
                    pattern = measurement_callback(pattern)
                else:
                    pattern = measurement_callback
            if data_callback:
                if callable(data_callback):
                    data = data_callback(measurement, data)
                else:
                    data = data_callback
            query = get_query_from_data(
                datacenter, device_type, pattern, data
            )
            if dataframe:
                result = session.query(query)
            else:
                result = session.query(query, epoch=time_precision)
            response = timeseries_formatter(
                result, device_type, measurement, devices,
                measurement_type=measurement_type,
                timestamp_converter=timestamp_converter,
                timestamp_formatter=timestamp_formatter,
                dataframe=dataframe,
                measurement_pattern=measurement_pattern,
                measurement_unit_converter=measurement_unit_converter,
                result_as_dataframe=result_as_dataframe
            )
            responses.append(response)
    if result_as_dataframe:
        if responses:
            return pd.concat(responses, axis=1)
        else:
            return pd.DataFrame()
    else:
        total_response = {}
        for response in responses:
            total_response.update(response)
        return total_response


def list_test_result_timeseries(
    session, data, measurement_key,
    time_precision=None,
    convert_timestamp=False, format_timestamp=True,
    result_as_dataframe=None,
    device_type_mapping={}, device_type_types={}
):
    def generate_test_result_tags(measurement, data):
        where = data.setdefault('where', {})
        where['measurement_name'] = measurement
        return data

    logger.debug(
        'list test result timeseries data %s '
        'measurement key %s' % (
            data, measurement_key
        )
    )
    datacenter = data.pop('datacenter')
    return list_timeseries_internal(
        session, data, datacenter,
        time_precision=time_precision,
        convert_timestamp=convert_timestamp,
        format_timestamp=format_timestamp,
        device_type_mapping=device_type_mapping,
        device_type_types=device_type_types,
        result_as_dataframe=result_as_dataframe,
        measurement_callback=measurement_key,
        data_callback=generate_test_result_tags
    )


def list_timeseries(
    session, data,
    time_precision=None,
    convert_timestamp=False, format_timestamp=True,
    device_type_units={},
    result_as_dataframe=None,
    measurement_callback=None,
    data_callback=None
):
    logger.debug('timeseries data: %s', data)
    datacenter = data.pop('datacenter')
    device_types = data.pop('device_type', {})
    with database.session() as db_session:
        (
            device_type_mapping, device_type_types,
            device_type_patterns, device_type_unit_converters
        ) = get_device_type_infos(
            db_session, datacenter, device_types, device_type_units
        )
    logger.debug(
        'device_type_mapping %s device_type_types %s '
        'time_precision %s device_type_unit_converters %s'
        'device_type_patterns %s convert_timestamp %s format_timestamp %s'
        'result_as_dataframe %s',
        device_type_mapping, device_type_types, time_precision,
        device_type_unit_converters, device_type_patterns,
        convert_timestamp, format_timestamp, result_as_dataframe
    )
    return list_timeseries_internal(
        session, data, datacenter,
        time_precision=time_precision,
        convert_timestamp=convert_timestamp,
        format_timestamp=format_timestamp,
        device_type_mapping=device_type_mapping,
        device_type_types=device_type_types,
        device_type_patterns=device_type_patterns,
        device_type_unit_converters=device_type_unit_converters,
        result_as_dataframe=result_as_dataframe,
        measurement_callback=measurement_callback,
        data_callback=data_callback
    )


def timeseries_formatter(
    result, device_type, measurement, devices, measurement_type=None,
    timestamp_converter=None, timestamp_formatter=None,
    dataframe=False, measurement_pattern=None,
    measurement_unit_converter=None,
    result_as_dataframe=False
):
    logger.debug(
        'format timeseries device_type %s '
        'measurement %s devices %s measurement_type %s '
        'dataframe %s measurement_pattern %s '
        'measurement_unit_converter %s result_as_dataframe %s',
        device_type, measurement, devices,
        measurement_type, dataframe, measurement_pattern,
        measurement_unit_converter, result_as_dataframe
    )
    response = {}
    unit_converter = None
    if measurement_unit_converter:
        unit_converter = tuple(reversed(measurement_unit_converter))
        unit_converter = get_unit_converter(unit_converter)
    logger.debug('unit converter: %s', unit_converter)
    for key, values in result.items():
        _, group_tags = key
        group_tags = dict(group_tags)
        device = group_tags['device']
        if devices and device not in devices:
            logger.debug('ignore device %s', device)
            continue
        device_response = {}
        response.setdefault(
            (device_type, measurement, device),
            device_response
        )
        if dataframe:
            for timestamp, value in six.iteritems(dict(values['value'])):
                if timestamp_formatter:
                    timestamp = timestamp_formatter(
                        timestamp
                    )
                if value is not None:
                    if unit_converter:
                        value = unit_converter(value)
                    device_response[timestamp] = format_timeseries_value(
                        value, measurement_type,
                        base_value=device_response.get(timestamp)
                    )
        else:
            for item in values:
                timestamp = item['time']
                if timestamp_converter:
                    timestamp = timestamp_converter(
                        timestamp
                    )
                if timestamp_formatter:
                    timestamp = timestamp_formatter(
                        timestamp
                    )
                value = item['value']
                if value is not None:
                    if unit_converter:
                        value = unit_converter(value)
                    device_response[timestamp] = format_timeseries_value(
                        value, measurement_type,
                        base_value=device_response.get(timestamp)
                    )
    if result_as_dataframe:
        return pd.DataFrame(response)
    else:
        return response


def generate_device_type_timeseries(
    data, device_type_mapping,
    device_type_types={},
    timestamp_converter=None,
    dataframe=False, device_type_patterns={},
    device_type_unit_converters={}
):
    for key, device_data in six.iteritems(data):
        device_type, measurement, device = key
        if device_type not in device_type_mapping:
            logger.debug('ignore device type %s', device_type)
            continue
        measurement_mapping = device_type_mapping[device_type]
        measurement_types = None
        if device_type_types:
            measurement_types = device_type_types.get(device_type)
        measurement_patterns = None
        if device_type_patterns:
            measurement_patterns = device_type_patterns.get(device_type)
        measurement_unit_converters = None
        if device_type_unit_converters:
            measurement_unit_converters = device_type_unit_converters.get(
                device_type
            )
        real_measurement = measurement
        if measurement_patterns:
            for try_measurement, pattern in six.iteritems(
                measurement_patterns
            ):
                if re.match(r'^%s$' % pattern, measurement):
                    real_measurement = try_measurement
                    break
        if real_measurement not in measurement_mapping:
            logger.debug('ignore measurement %s', real_measurement)
            continue
        devices = measurement_mapping[real_measurement]
        if device not in devices:
            logger.debug('ignore device %s', device)
            continue
        measurement_type = None
        if measurement_types:
            measurement_type = measurement_types.get(real_measurement)
        unit_converter = None
        if measurement_unit_converters:
            unit_converter = measurement_unit_converters.get(real_measurement)
        if unit_converter:
            unit_converter = get_unit_converter(unit_converter)
        generated = {}
        for timestamp, value in six.iteritems(device_data):
            if timestamp_converter:
                timestamp = timestamp_converter(timestamp)
            if value is not None:
                value = convert_timeseries_value(
                    value, measurement_type,
                    False
                )
            if value is not None:
                if unit_converter:
                    value = unit_converter(value)
                generated[timestamp] = value
        yield (device_type, measurement, device), generated


def write_points(
    session, measurement, timeseries, tags={}, time_precision=None,
    dataframe=False
):
    logger.debug('wirte %s points tags %s', measurement, tags)
    if dataframe:
        return session.write_points(
            pd.DataFrame({'value': timeseries}).dropna(), measurement,
            time_precision=time_precision, tags=tags
        )
    else:
        points = []
        for timestamp, value in six.iteritems(timeseries):
            if value is not None:
                points.append({
                    'measurement': measurement,
                    'time': timestamp,
                    'fields': {
                        'value': value
                    }
                })
        return session.write_points(
            points, time_precision=time_precision, tags=tags
        )


def create_timeseries_internal(
    session, data, datacenter, extra_tags,
    time_precision=None,
    convert_timestamp=True,
    device_type_mapping={}, device_type_types={},
    device_type_patterns={}, device_type_unit_converters={},
    measurement_callback=None,
    tags_callback=None
):
    dataframe = database.is_dataframe_session(session)
    status = True
    if convert_timestamp:
        timestamp_converter = get_timestamp_converter(
            time_precision, dataframe
        )
    else:
        timestamp_converter = None
    if dataframe:
        columns = data.columns
    else:
        columns = data.keys()
    logger.debug(
        'create timeseries %s tags %s data: %s',
        datacenter, extra_tags, columns
    )
    for generated_tags, tag_data in generate_device_type_timeseries(
        data, device_type_mapping,
        device_type_types=device_type_types,
        timestamp_converter=timestamp_converter,
        dataframe=dataframe, device_type_patterns=device_type_patterns,
        device_type_unit_converters=device_type_unit_converters
    ):
        device_type, measurement, device = generated_tags
        tags = {
            'datacenter': datacenter,
            'device_type': device_type,
            'device': device
        }
        tags.update(extra_tags)
        if tags_callback:
            if callable(tags_callback):
                tags = tags_callback(measurement, tags)
            else:
                tags = tags_callback
        if measurement_callback:
            if callable(measurement_callback):
                measurement = measurement_callback(measurement)
            else:
                measurement = measurement_callback
        status &= write_points(
            session, measurement, tag_data,
            tags, time_precision,
            dataframe=dataframe
        )
    logger.debug(
        'create timeseries status: %s', status
    )
    return status


def create_test_result_timeseries(
    session, data, tags, measurement_key,
    time_precision=None,
    convert_timestamp=True,
    device_type_mapping={}, device_type_types={}
):
    def generate_test_result_tags(measurement, tags):
        tags['measurement_name'] = measurement
        return tags

    logger.debug(
        'create test result timeseries tags %s '
        'measurement key %s' % (
            tags, measurement_key
        )
    )
    datacenter = tags.pop('datacenter')
    return create_timeseries_internal(
        session, data, datacenter, tags,
        time_precision=time_precision,
        convert_timestamp=convert_timestamp,
        device_type_mapping=device_type_mapping,
        device_type_types=device_type_types,
        measurement_callback=measurement_key,
        tags_callback=generate_test_result_tags
    )


def create_timeseries(
    session, data,
    tags, time_precision=None,
    convert_timestamp=True,
    device_type_units={},
    measurement_callback=None,
    tags_callback=None
):
    logger.debug('create timeseries tags: %s', tags)
    datacenter = tags.pop('datacenter')
    device_types = tags.pop('device_type', {})
    with database.session() as db_session:
        (
            device_type_mapping, device_type_types, device_type_patterns,
            device_type_unit_converters
        ) = get_device_type_infos(
            db_session, datacenter, device_types, device_type_units, False
        )
    logger.debug(
        'device_type_mapping %s device_type_types %s '
        'time_precision %s '
        'device_type_patterns %s convert_timestamp %s device_type_units %s',
        device_type_mapping, device_type_types, time_precision,
        device_type_patterns, convert_timestamp, device_type_units
    )
    return create_timeseries_internal(
        session, data, datacenter, tags, time_precision=time_precision,
        convert_timestamp=convert_timestamp,
        device_type_mapping=device_type_mapping,
        device_type_types=device_type_types,
        device_type_patterns=device_type_patterns,
        device_type_unit_converters=device_type_unit_converters,
        measurement_callback=measurement_callback,
        tags_callback=tags_callback
    )


def delete_timeseries_internal(
    session, datacenter,
    device_type_mapping={}
):
    for device_type, measurement_mapping in six.iteritems(
        device_type_mapping
    ):
        for measurement, devices in six.iteritems(measurement_mapping):
            for device in devices:
                session.delete_series(
                    measurement=measurement, tags={
                        'datacenter': datacenter,
                        'device_type': device_type,
                        'device': device
                    }
                )


def delete_timeseries(session, tags):
    logger.debug('delete timeseries tags: %s', tags)
    datacenter = tags.pop('datacenter')
    device_types = tags.pop('device_type')
    with database.session() as db_session:
        (
            device_type_mapping, device_type_types, device_type_patterns,
            device_type_unit_converters
        ) = get_device_type_infos(
            db_session, datacenter, device_types, {}, False
        )
    logger.debug(
        'device_type_mapping %s',
        device_type_mapping
    )
    delete_timeseries_internal(
        session, datacenter, device_type_mapping=device_type_mapping
    )


TIMEDELTA_MAP = {
    'h': lambda t: long(t) // 3600,
    'm': lambda t: long(t) // 60,
    's': lambda t: long(t),
    'ms': lambda t: long(t) * 1000,
    'u': lambda t: long(t) * 1e6,
    'ns': lambda t: long(t) * 1e9
}


def get_timedelta(time_precision, seconds):
    if not time_precision:
        return datetime.timedelta(0, seconds)
    return TIMEDELTA_MAP[time_precision](seconds)


UNIT_CONVERTERS = {
    ('w', 'kw'): lambda x: x / 1000,
    ('kw', 'w'): lambda x: x * 1000
}


def get_unit_converter(unit_converter):
    if unit_converter in UNIT_CONVERTERS:
        return UNIT_CONVERTERS[unit_converter]
    logger.debug('unkown unit converter %s', unit_converter)
    return None
