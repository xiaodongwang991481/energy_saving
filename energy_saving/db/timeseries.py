import datetime
from dateutil import parser
import functools
import json
import logging
import pandas as pd
import re
import six

from energy_saving.db import database
from energy_saving.db import exception
from energy_saving.db import models


logger = logging.getLogger(__name__)
COLUMN_TYPE_CONVERTER = {
    dict: json.loads
}


def convert_column_value(value, value_type):
    try:
        if value_type in COLUMN_TYPE_CONVERTER:
            return COLUMN_TYPE_CONVERTER[value_type](value)
        return value_type(value)
    except Exception as error:
        logger.exception(error)
        logger.error(
            'failed to convert %s to %s: %s',
            value, value_type, error
        )
        raise error


def _get_attribute_dict(attribute):
    return {
        'devices': [],
        'attribute': {
            'type': attribute.type,
            'unit': attribute.unit,
            'mean': attribute.mean,
            'deviation': attribute.deviation
        }
    }


def _get_parameter_dict(parameter):
    return {
        'devices': [],
        'attribute': {
            'type': parameter.type,
            'unit': parameter.unit,
            'min': parameter.min,
            'max': parameter.max
        }
    }


def get_sensor_attributes(datacenter):
    result = {}
    for attribute in datacenter.sensor_attributes:
        result[attribute.name] = _get_attribute_dict(attribute)
        attribute_data = result[attribute.name]['devices']
        for data in attribute.attribute_data:
            attribute_data.append(data.sensor_name)
    return result


def get_controller_attributes(datacenter):
    result = {}
    for attribute in datacenter.controller_attributes:
        result[attribute.name] = _get_attribute_dict(attribute)
        attribute_data = result[attribute.name]['devices']
        for data in attribute.attribute_data:
            attribute_data.append(data.controller_name)
    return result


def get_power_supply_attributes(datacenter):
    result = {}
    for attribute in datacenter.power_supply_attributes:
        result[attribute.name] = _get_attribute_dict(attribute)
        attribute_data = result[attribute.name]['devices']
        for data in attribute.attribute_data:
            attribute_data.append(data.power_supply_name)
    return result


def get_controller_power_supply_attributes(datacenter):
    result = {}
    for attribute in datacenter.controller_power_supply_attributes:
        result[attribute.name] = _get_attribute_dict(attribute)
        attribute_data = result[attribute.name]['devices']
        for data in attribute.attribute_data:
            attribute_data.append(data.controller_power_supply_name)
    return result


def get_environment_sensor_attributes(datacenter):
    result = {}
    for attribute in datacenter.environment_sensor_attributes:
        result[attribute.name] = _get_attribute_dict(attribute)
        attribute_data = result[attribute.name]['devices']
        for data in attribute.attribute_data:
            attribute_data.append(data.environment_sensor_name)
    return result


def get_controller_parameters(datacenter):
    result = {}
    for parameter in datacenter.controller_parameters:
        result[parameter.name] = _get_parameter_dict(parameter)
        parameter_data = result[parameter.name]['devices']
        for data in parameter.parameter_data:
            parameter_data.append(data.controller_name)
    return result


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


def _get_datacenter_device_type_metadata(datacenter, device_type):
    if device_type not in DEVICE_TYPE_METADATA_GETTERS:
        raise exception.RecordNotExists(
            'device type %s does not exist' % device_type
        )
    return DEVICE_TYPE_METADATA_GETTERS[device_type](datacenter)


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


def get_device_type_meatadata_from_datacenter_meatadata(
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


TIMESERIES_VALUE_CONVERTERS = {
    'binary': bool,
    'continuous': float,
    'integer': int
}


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


TIMESERIES_VALUE_FORMATTERS = {
    'continuous': lambda x: round(x, 2),
}


def format_timeseries_value(
    value, value_type, raise_exception=False, default_value=None
):
    if value is None:
        return None
    try:
        if value_type in TIMESERIES_VALUE_FORMATTERS:
            return TIMESERIES_VALUE_FORMATTERS[value_type](value)
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
    if isinstance(group_by, list):
        return ', '.join(group_by)
    else:
        return group_by


def _get_order_by(order_by):
    if isinstance(order_by, list):
        return ', '.join(order_by)
    else:
        return order_by


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
        return pd.Timestamp
    if not time_precision:
        return str
    else:
        return long


def get_query_from_data(measurement, data):
    query = data.get('query')
    where = data.get('where')
    group_by = data.get('group_by')
    order_by = data.get('order_by')
    fill = data.get('fill')
    aggregation = data.get('aggregation')
    limit = data.get('limit')
    offset = data.get('offset')
    if not query:
        query = get_query(
            measurement, where=where,
            group_by=group_by, order_by=order_by,
            fill=fill, aggregation=aggregation, limit=limit,
            offset=offset
        )
    logger.debug(
        'timeseries %s query: %s',
        measurement, query
    )
    return query


def list_timeseries(
    session, data, device_type_types={},
    time_precision=None
):
    dataframe = database.is_dataframe_session(session)
    logger.debug('timeseries data: %s', data)
    logger.debug(
        'device_type_types %s time_precision %s dataframe %s',
        device_type_types, time_precision, dataframe
    )
    measurements = data.get('measurement')
    assert measurements
    measurement = '/^%s$/' % '|'.join(measurements)
    query = get_query_from_data(
        measurement, data
    )
    timestamp_formatter = get_timestamp_formatter(
        time_precision, dataframe
    )
    if dataframe:
        result = session.query(query)
    else:
        result = session.query(query, epoch=time_precision)
    return timeseries_device_type_formatter(
        result, device_type_types,
        timestamp_formatter,
        dataframe=dataframe
    )


def list_measurement_timeseries(
    session, measurement, data, measurement_type=None,
    time_precision=None
):
    dataframe = database.is_dataframe_session(session)
    logger.debug('timeseries %s data: %s', measurement, data)
    logger.debug(
        'measurement_type %s time_precision %s dataframe %s',
        measurement_type, time_precision, dataframe
    )
    query = get_query_from_data(
        measurement, data
    )
    timestamp_formatter = get_timestamp_formatter(
        time_precision, dataframe
    )
    if dataframe:
        result = session.query(query)
    else:
        result = session.query(query, epoch=time_precision)
    return timeseries_measurement_formatter(
        result, measurement_type,
        timestamp_formatter,
        dataframe=dataframe
    )


def list_device_timeseries(
    session, measurement, data, measurement_type=None,
    time_precision=None
):
    dataframe = database.is_dataframe_session(session)
    logger.debug('timeseries %s data: %s', measurement, data)
    logger.debug(
        'measurement_type %s time_precision %s dataframe %s',
        measurement_type, time_precision, dataframe
    )
    query = get_query_from_data(
        measurement, data
    )
    timestamp_formatter = get_timestamp_formatter(
        time_precision, dataframe
    )
    if dataframe:
        result = session.query(query)
    else:
        result = session.query(query, epoch=time_precision)
    return timeseries_device_formatter(
        result, measurement_type,
        timestamp_formatter,
        dataframe=dataframe
    )


def timeseries_device_type_formatter(
    result, device_type_types, timestamp_formatter,
    dataframe=False
):
    response = {}
    for key, values in result.items():
        measurement, group_tags = key
        group_tags = dict(group_tags)
        device = group_tags['device']
        device_response = {}
        measurement_type = device_type_types.get(measurement)
        if dataframe:
            response[(measurement, device)] = device_response
            for timestamp, value in six.iteritems(dict(values['value'])):
                timestamp = timestamp_formatter(timestamp)
                device_response[timestamp] = format_timeseries_value(
                    value, measurement_type
                )
        else:
            measurement_response = response.setdefault(
                measurement, device_response
            )
            response[device] = measurement_response
            for item in values:
                timestamp = timestamp_formatter(
                    item['time']
                )
                device_response[timestamp] = format_timeseries_value(
                    item['value'], measurement_type
                )
    if dataframe:
        return pd.DataFrame(response)
    else:
        return response


def timeseries_measurement_formatter(
    result, measurement_type, timestamp_formatter,
    dataframe=False
):
    response = {}
    for key, values in result.items():
        _, group_tags = key
        group_tags = dict(group_tags)
        device = group_tags['device']
        device_response = {}
        response[device] = device_response
        if dataframe:
            for timestamp, value in six.iteritems(dict(values['value'])):
                timestamp = timestamp_formatter(timestamp)
                device_response[timestamp] = format_timeseries_value(
                    value, measurement_type
                )
        else:
            for item in values:
                timestamp = timestamp_formatter(item['time'])
                device_response[timestamp] = format_timeseries_value(
                    item['value'], measurement_type
                )
    if dataframe:
        return pd.DataFrame(response)
    else:
        return response


def timeseries_device_formatter(
    result, measurement_type, timestamp_converter, timestamp_formatter,
    dataframe=False
):
    response = {}
    for key, values in result.items():
        if dataframe:
            for timestamp, value in six.iteritems(dict(values['value'])):
                timestamp = timestamp_formatter(
                    timestamp
                )
                response[timestamp] = format_timeseries_value(
                    value, measurement_type
                )
        else:
            for item in values:
                timestamp = timestamp_formatter(item['time'])
                response[timestamp] = format_timeseries_value(
                    item['value'], measurement_type
                )
    if dataframe:
        return pd.DataFrame({'value': response})
    else:
        return response


def generate_device_type_timeseries(
    data, tags, device_type_types, timestamp_converter,
    dataframe=False
):
    for key, device_data in six.iteritems(data):
        measurement, device = key
        generated = {}
        generated_tags = dict(tags)
        for timestamp, value in six.iteritems(device_data):
            timestamp = timestamp_converter(timestamp)
            value = convert_timeseries_value(
                value, device_type_types.get(measurement),
                False
            )
            if value is not None:
                generated[timestamp] = value
        generated_tags['measurement'] = measurement
        generated_tags['device'] = device
        yield generated_tags, generated


def generate_measurement_timeseries(
    data, tags, measurement_type, timestamp_converter,
    dataframe=False
):
    for device, device_data in six.iteritems(data):
        generated = {}
        generated_tags = dict(tags)
        for timestamp, value in six.iteritems(device_data):
            timestamp = timestamp_converter(timestamp)
            value = convert_timeseries_value(
                value, measurement_type,
                False
            )
            if value is not None:
                generated[timestamp] = value
        generated_tags['device'] = device
        yield generated_tags, generated


def generate_device_timeseries(
    data, tags, measurement_type, timestamp_converter,
    dataframe=False
):
    generated = {}
    for timestamp, value in six.iteritems(data):
        timestamp = timestamp_converter(timestamp)
        value = convert_timeseries_value(
            value, measurement_type,
            False
        )
        if value is not None:
            generated[timestamp] = value
    yield tags, generated


def write_points(
    session, measurement, timeseries, tags={}, time_precision=None,
    dataframe=False
):
    if dataframe:
        return session.write_points(
            pd.DataFrame({'value': timeseries}).dropna(), measurement,
            time_precision=time_precision, tags=tags
        )
    else:
        points = []
        for timestamp, value in six.iteritems(timeseries):
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


def create_timeseries(
    session, data, device_types_type={},
    tags={}, time_precision=None
):
    dataframe = database.is_dataframe_session(session)
    logger.debug('create timeseries tags: %s', tags)
    logger.debug(
        'device_types_type %s time_precision %s dataframe %s',
        device_types_type, time_precision, dataframe
    )
    status = True
    timestamp_converter = get_timestamp_converter(
        time_precision, dataframe
    )
    for generated_tags, tag_data in generate_device_type_timeseries(
        data, tags, device_types_type, timestamp_converter,
        dataframe=dataframe
    ):
        measurement = generated_tags.pop('measurement')
        status &= write_points(
            session, measurement, tag_data,
            generated_tags, time_precision,
            dataframe=dataframe
        )
    logger.debug(
        'create timeseries status: %s', status
    )
    return status


def create_measurement_timeseries(
    session, measurement, data, measurement_type=None,
    tags={}, time_precision=None
):
    dataframe = database.is_dataframe_session(session)
    logger.debug(
        'create measurement timeseries %s tags: %s', measurement, tags
    )
    logger.debug(
        'measurement_type %s time_precision %s dataframe %s',
        measurement_type, time_precision, dataframe
    )
    status = True
    timestamp_converter = get_timestamp_converter(
        time_precision, dataframe
    )
    for generated_tags, tag_data in generate_measurement_timeseries(
        data, tags, measurement_type, timestamp_converter,
        dataframe=dataframe
    ):
        status &= write_points(
            session, measurement, tag_data,
            tags, time_precision, dataframe=dataframe
        )
    logger.debug(
        'create measurement timeseries %s status: %s',
        measurement, status
    )
    return status


def create_device_timeseries(
    session, measurement, data, measurement_type=None,
    tags={}, time_precision=None
):
    dataframe = database.is_dataframe_session(session)
    logger.debug('create device timeseries %s tags: %s', measurement, tags)
    logger.debug(
        'measurement_type %s time_precision %s dataframe %s',
        measurement_type, time_precision, dataframe
    )
    status = True
    timestamp_converter = get_timestamp_converter(
        time_precision, dataframe
    )
    for generated_tags, tag_data in generate_device_timeseries(
        data, tags, measurement_type, timestamp_converter,
        dataframe=dataframe
    ):
        status &= write_points(
            session, measurement, tag_data,
            generated_tags, time_precision,
            dataframe=dataframe
        )
    logger.debug(
        'create device timeseries tags %s status: %s',
        measurement, status
    )
    return status


def delete_timeseries(session, measurement, tags):
    session.delete_series(measurement=measurement, tags=tags)


TIMEDELTA_MAP = {
    'h': lambda t: t / 3600,
    'm': lambda t: t / 60,
    's': lambda t: t,
    'ms': lambda t: t * 1000,
    'u': lambda t: long(t * 1e6),
    'ns': lambda t: long(t * 1e9)
}


def get_timedelta(time_precision, seconds):
    if not time_precision:
        return datetime.timedelta(0, seconds)
    return TIMEDELTA_MAP[time_precision](seconds)
