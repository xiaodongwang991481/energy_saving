"""Define all the RestfulAPI entry points."""
import csv
from dateutil import parser
import logging
import simplejson as json
import six
import StringIO

from oslo_config import cfg

from flask import request

from energy_saving.api import admin_api
from energy_saving.api import app
from energy_saving.api import exception_handler
from energy_saving.api import utils
from energy_saving.db import database
from energy_saving.db import models
from energy_saving.tasks import client as celery_client
from energy_saving.utils import logsetting
from energy_saving.utils import settings


opts = [
    cfg.StrOpt(
        'logfile',
        help='log file name',
        default=settings.WEB_LOGFILE
    ),
    cfg.IntOpt(
        'server_port',
        help='flask server port',
        default=settings.SERVER_PORT
    )
]
CONF = cfg.CONF
CONF.register_opts(opts)


logger = logging.getLogger(__name__)


def _clean_data(data, keys):
    """remove keys from dict."""
    for key in keys:
        if key in data:
            del data[key]


def _replace_data(data, key_mapping):
    """replace key names in dict."""
    for key, replaced_key in key_mapping.items():
        if key in data:
            data[replaced_key] = data[key]
            del data[key]


def _get_data(data, key):
    """get key's value from request arg dict.

    When the value is list, return the element in the list
    if the list size is one. If the list size is greater than one,
    raise exception_handler.BadRequest.
    Example: data = {'a': ['b'], 'b': 5, 'c': ['d', 'e'], 'd': []}
             _get_data(data, 'a') == 'b'
             _get_data(data, 'b') == 5
             _get_data(data, 'c') raises exception_handler.BadRequest
             _get_data(data, 'd') == None
             _get_data(data, 'e') == None
    Usage: Used to parse the key-value pair in request.args to expected types.
           Depends on the different flask plugins and what kind of parameters
           passed in, the request.args format may be as below:
           {'a': 'b'} or {'a': ['b']}. _get_data forces translate the
           request.args to the format {'a': 'b'}. It raises exception when some
           parameter declares multiple times.
    """
    if key in data:
        if isinstance(data[key], list):
            if data[key]:
                if len(data[key]) == 1:
                    return data[key][0]
                else:
                    raise exception_handler.BadRequest(
                        '%s declared multi times %s in request' % (
                            key, data[key]
                        )
                    )
            else:
                return None
        else:
            return data[key]
    else:
        return None


def _get_request_data():
    """Convert reqeust data from string to python dict.

    If the request data is not json formatted, raises
    exception_handler.BadRequest.
    If the request data is not json formatted dict, raises
    exception_handler.BadRequest
    If the request data is empty, return default as empty dict.
    Usage: It is used to add or update a single resource.
    """
    if request.form:
        logging.debug('get data from form')
        data = request.form.to_dict()
        # for key in data:
        #     data[key] = data[key].encode('utf-8')
        return data
    else:
        logging.debug('get data from payload')
        raw_data = request.data
        if raw_data:
            try:
                data = json.loads(raw_data)
            except Exception as error:
                logging.exception(error)
                raise exception_handler.BadRequest(
                    'request data is not json formatted: %r' % raw_data
                )
            return data
        else:
            return {}


def _bool_converter(value):
    """Convert string value to bool.

    This function is used to convert value in requeset args to expected type.
    If the key exists in request args but the value is not set, it means the
    value should be true.
    Examples:
       /<request_path>?is_admin parsed to {'is_admin', None} and it should
       be converted to {'is_admin': True}.
       /<request_path>?is_admin=0 parsed and converted to {'is_admin': False}.
       /<request_path>?is_admin=1 parsed and converted to {'is_admin': True}.
    """
    if not value:
        return True
    if value in ['False', 'false', '0']:
        return False
    if value in ['True', 'true', '1']:
        return True
    raise exception_handler.BadRequest(
        '%r type is not bool' % value
    )


def _int_converter(value):
    """Convert string value to int.

    We do not use the int converter default exception since we want to make
    sure the exact http response code.
    Raises: exception_handler.BadRequest if value can not be parsed to int.
    Examples:
       /<request_path>?count=10 parsed to {'count': '10'} and it should be
       converted to {'count': 10}.
    """
    try:
        return int(value)
    except Exception:
        raise exception_handler.BadRequest(
            '%r type is not int' % value
        )


def _get_request_args(as_list={}, **kwargs):
    """Get request args as dict.

    The value in the dict is converted to expected type.
    Args:
       kwargs: for each key, the value is the type converter.
    """
    args = request.args.to_dict(flat=False)
    for key, value in args.items():
        is_list = as_list.get(key, False)
        logger.debug('request arg %s is list? %s', key, is_list)
        if not is_list:
            value = value[-1]
            args[key] = value
        if key in kwargs:
            converter = kwargs[key]
            if isinstance(value, list):
                args[key] = [converter(item) for item in value]
            else:
                args[key] = converter(value)
    return args


@app.route("/info", methods=['GET'])
def status():
    return utils.make_json_response(
        200, 'OK'
    )


@app.route("/health", methods=['GET'])
def health():
    return utils.make_json_response(
        200, 'OK'
    )


@app.route("/metadata/database/models", methods=['GET'])
def list_database_models():
    models = {}
    for model_name, model in six.iteritems(admin_api.MODELS):
        models[model_name] = model.__mapper__.columns.keys()
    return utils.make_json_response(
        200, models
    )


@app.route("/metadata/database/models/<model_name>", methods=['GET'])
def list_database_model_fields(model_name):
    model = admin_api.MODELS[model_name]
    columns = {}
    for column_name, column in six.iteritems(model.__mapper__.columns):
        columns[model_name] = repr(column)
    return utils.make_json_response(
        200, columns
    )


def _get_device_type_metadata(datacenter_name, device_type):
    with database.session() as session:
        datacenter = session.query(
            models.Datacenter
        ).filter_by(name=datacenter_name).first()
        if not datacenter:
            raise exception_handler.ItemNotFound(
                'datacener %s does not exist' % datacenter_name
            )
        device_type_metadata = database.get_datacenter_device_type_metadata(
            datacenter, device_type
        )
        logger.debug(
            'datacenter %s device type %s metadata: %s',
            datacenter_name, device_type, device_type_metadata
        )
        return device_type_metadata


def _get_datacenter_metadata(datacenter_name):
    with database.session() as session:
        datacenter = session.query(
            models.Datacenter
        ).filter_by(name=datacenter_name).first()
        if not datacenter:
            raise exception_handler.ItemNotFound(
                'datacener %s does not exist' % datacenter_name
            )
        return database.get_datacenter_metadata(datacenter)


def _get_metadata():
    result = {}
    with database.session() as session:
        datacenters = session.query(models.Datacenter)
        for datacenter in datacenters:
            result[datacenter.name] = (
                database.get_datacenter_metadata(datacenter)
            )
    return result


@app.route("/metadata/timeseries/models", methods=['GET'])
def list_timeseries_models():
    result = _get_metadata()
    return utils.make_json_response(
        200, result
    )


@app.route("/import/database/<model_name>", methods=['POST'])
def upload_model(model_name):
    logger.debug('upload model %s', model_name)
    if model_name not in admin_api.MODELS:
        raise exception_handler.ItemNotFound(
            'model %s is not found' % model_name
        )
    model = admin_api.MODELS[model_name]
    data = []
    request_files = request.files.items(multi=True)
    if not request_files:
            raise exception_handler.NotAcceptable(
                'no csv file to upload'
            )
    logger.debug('upload csv files: %s', request_files)
    for filename, upload in request_files:
        fields = None
        reader = csv.reader(upload)
        for row in reader:
            if not row:
                continue
            logger.debug('read row %s', row)
            if not fields:
                fields = row
            else:
                row = dict(zip(fields, row))
                row_data = {}
                for key, value in six.iteritems(row):
                    if value:
                        row_data[key] = value
                data.append(row_data)
    with database.session() as session:
        session.bulk_insert_mappings(model, data, True)
    return utils.make_json_response(
        200, 'OK'
    )


def _get_where(data):
    wheres = []
    starttime = data.pop('starttime', None)
    if starttime and starttime[0] in ['-', '+']:
        starttime = 'now() %s %s' % (
            starttime[0], starttime[1:]
        )
    endtime = data.pop('endtime', None)
    if endtime and endtime[0] in ['-', '+']:
        endtime = 'now() %s %s' % (
            endtime[0], endtime[1:]
        )
    for key, value in six.iteritems(data):
        if isinstance(value, list):
            if not value:
                continue
            sub_wheres = []
            for item in value:
                sub_wheres.append("%s = '%s'" % (key, item))
            wheres.append(' or '.join(sub_wheres))
        else:
            wheres.append("%s = '%s'" % (key, value))
    if starttime:
        wheres.append('time > %s' % starttime)
    if endtime:
        wheres.append('time < %s' % endtime)
    if wheres:
        return ' and '.join(wheres)
    else:
        return ''


def _get_group_by(group_by):
    if isinstance(group_by, list):
        return ', '.join(group_by)
    else:
        return group_by


def _get_order_by(order_by):
    if isinstance(order_by):
        return ', '.join(order_by)
    else:
        return order_by


def _list_timeseries(
    measurement, data, data_formatter=None, extra_select_fields=None
):
    logger.debug('timeseries data: %s', data)
    response = {}
    query = data.pop('query', None)
    where = data.pop('where', None)
    group_by = data.pop('group_by', [])
    order_by = data.pop('order_by', [])
    aggregation = data.pop('aggregation', None)
    time_precision = data.pop(
        'time_precision', settings.DEFAULT_TIME_PRECISION
    )
    if not query:
        if not where:
            where = _get_where(data)
        if where:
            where_clause = ' where %s' % where
        else:
            where_clause = ''
        if aggregation:
            value = '%s(value)' % aggregation
            group_by = group_by + extra_select_fields
        else:
            value = ', '.join(['value'] + (extra_select_fields or []))
        select = value
        if group_by:
            group_by_clause = ' group by %s' % _get_group_by(group_by)
        else:
            group_by_clause = ''
        if order_by:
            order_by_clause = 'order by %s' % _get_order_by(order_by)
        else:
            order_by_clause = ''
        query = 'select %s from %s%s%s%s' % (
            select, measurement, where_clause,
            group_by_clause, order_by_clause
        )
    logger.debug('timeseries %s query: %s', measurement, query)
    response = []
    with database.influx_session() as session:
        result = session.query(query, epoch=time_precision)
        for key, value in result.items():
            logger.debug('iterate result %s', key)
            _, group_tags = key
            if aggregation:
                for item in value:
                    logger.debug('iterate record %s', item)
                    if group_tags:
                        item.update(group_tags)
                    item['value'] = item.pop(aggregation)
                    response.append(item)
            else:
                response.extend(list(value))
    logger.debug('timeseries %s response: %s', measurement, response)
    if data_formatter:
        response = data_formatter(response)
    logger.debug(
        'timeseries %s formatted response: %s', measurement, response
    )
    return response


def timeseries_device_type_formatter(data):
    result = {}
    for item in data:
        timestamp_result = result.setdefault(item['time'], {})
        timestamp_result[item['device']] = item['value']
    return result


def timeseries_device_formatter(data):
    result = {}
    for item in data:
        result[item['time']] = item['value']
    return result


@app.route("/timeseries/<datacenter>/<device_type>", methods=['GET'])
def list_device_type_all_timeseries(datacenter, device_type):
    data = _get_request_args(as_list={
        'group_by': True,
        'order_by': True,
        'device': True
    })
    data.update({
        'datacenter': datacenter,
        'device_type': device_type
    })
    device_type_metadata = _get_device_type_metadata(
        datacenter, device_type
    )
    response = {}
    for measurement, _ in six.iteritems(device_type_metadata):
        response[measurement] = _list_timeseries(
            measurement, dict(data), timeseries_device_type_formatter,
            extra_select_fields=['device']
        )
    return utils.make_json_response(
        200, response
    )


@app.route(
    "/timeseries/<datacenter>/<device_type>/<measurement>",
    methods=['GET']
)
def list_device_type_timeseries(datacenter, device_type, measurement):
    data = _get_request_args(as_list={
        'group_by': True,
        'order_by': True,
        'device': True
    })
    data.update({
        'datacenter': datacenter,
        'device_type': device_type
    })
    response = _list_timeseries(
        measurement, data, timeseries_device_type_formatter,
        extra_select_fields=['device']
    )
    return utils.make_json_response(
        200, response
    )


@app.route(
    "/timeseries/<datacenter>/<device_type>/<device>/<measurement>",
    methods=['GET']
)
def list_device_timeseries(datacenter, device_type, device, measurement):
    data = _get_request_args(as_list={
        'group_by': True,
        'order_by': True
    })
    data.update({
        'datacenter': datacenter,
        'device_type': device_type,
        'device': device
    })
    response = _list_timeseries(
        measurement, data, timeseries_device_formatter
    )
    return utils.make_json_response(
        200, response
    )


@app.route(
    "/export/timeseries/<datacenter>/<device_type>",
    methods=['GET']
)
def export_timeseries(datacenter, device_type):
    args = _get_request_args(as_list={
        'measurement': True,
        'device': True
    })
    device_type_metadata = _get_device_type_metadata(
        datacenter, device_type
    )
    measurements = args.get('measurement')
    if not measurements:
        measurements = device_type_metadata.keys()
    measurements = set(measurements)
    devices = args.get('device')
    if not devices:
        devices = set()
        for measurement, metadata in six.iteritems(
            device_type_metadata
        ):
            devices = devices.union(metadata['devices'])
    else:
        devices = set(devices)
    logger.debug(
        'download timeseries datacenter=%s device_type=%s '
        'measurements=%s devices=%s',
        datacenter, device_type, measurements, devices
    )
    timestamp_column = args.get(
        'timestamp_column', settings.DEFAULT_EXPORT_TIMESTAMP_COLUMN
    )
    device_column = args.get(
        'device_column', settings.DEFAULT_EXPORT_DEVICE_COLUMN
    )
    measurement_column = args.get(
        'measurement_column', settings.DEFAULT_EXPORT_MEASUREMENT_COLUMN
    )
    logger.debug('timestamp_column: %s', timestamp_column)
    logger.debug('device_column: %s', device_column)
    logger.debug('measurement_column: %s', measurement_column)
    column_name_map = {
        'time': timestamp_column,
        'device': device_column,
        'measurement': measurement_column
    }
    assert any([timestamp_column, device_column, measurement_column])
    assert not all([timestamp_column, device_column, measurement_column])
    column_name_as_timestamp = bool(
        args.get(
            'column_name_as_timestamp',
            settings.DEFAULT_EXPORT_TIMESTAMP_AS_COLUMN
        )
    )
    column_name_as_measurement = bool(
        args.get(
            'column_name_as_measurement',
            settings.DEFAULT_EXPORT_MEASUREMENT_AS_COLUMN
        ) and not column_name_as_timestamp
    )
    column_name_as_device = bool(
        args.get(
            'column_name_as_device',
            settings.DEFAULT_EXPORT_DEVICE_AS_COLUMN
        ) and not (
            column_name_as_timestamp or column_name_as_measurement
        )
    )
    logger.debug('column_name_as_timestamp: %s', column_name_as_timestamp)
    logger.debug('column_name_as_measurement: %s', column_name_as_measurement)
    logger.debug('column_name_as_device: %s', column_name_as_device)
    assert sum([
        column_name_as_timestamp,
        column_name_as_device,
        column_name_as_measurement
    ]) == 1
    assert not (column_name_as_timestamp and timestamp_column)
    assert not (column_name_as_device and device_column)
    assert not (column_name_as_measurement and measurement_column)
    time_precision = args.get(
        'time_precision', settings.DEFAULT_TIME_PRECISION
    )
    logger.debug('time precision: %s', time_precision)
    timestamps = set()
    data = []
    with database.influx_session() as session:
        for measurement in measurements:
            query = (
                "select value, device from %s where datacenter='%s' "
                "and device_type='%s' order by time" % (
                    measurement, datacenter, device_type
                )
            )
            logger.debug(
                'timeseries %s query: %s', measurement, query
            )
            result = session.query(
                query, epoch=time_precision
            )
            for item in result.get_points():
                if item['device'] in devices:
                    timestamp = item['time']
                    timestamps.add(timestamp)
                    item['measurement'] = measurement
                    data.append(item)
    logger.debug('influx query response: %s', data)
    measurements = list(measurements)
    measurements = sorted(measurements)
    devices = list(devices)
    devices = sorted(devices)
    timestamps = list(timestamps)
    timestamps = sorted(timestamps)
    if time_precision:
        timestamps = sorted(timestamps)
    else:
        timestamps = sorted(
            timestamps, key=lambda timestamp: parser.parse(timestamp)
        )
    logger.debug('timestamps: %s', timestamps)
    column_names = []
    row_keys = []
    column_key = None
    if timestamp_column:
        column_names.append(timestamp_column)
        row_keys.append('time')
    if measurement_column:
        column_names.append(measurement_column)
        row_keys.append('measurement')
    if device_column:
        column_names.append(device_column)
        row_keys.append('device')
    if column_name_as_timestamp:
        column_names.extend(timestamps)
        column_key = 'time'
    if column_name_as_measurement:
        column_names.extend(measurements)
        column_key = 'measurement'
    if column_name_as_device:
        column_names.extend(devices)
        column_key = 'device'
    logger.debug('column names: %s', column_names)
    logger.debug('row_keys: %s', row_keys)
    logger.debug('column_key: %s', column_key)
    columns = len(column_names)
    column_index = {}
    for i, column_name in enumerate(column_names):
        column_index[column_name] = i
    logger.debug('column_index: %s', column_index)
    output = []
    output.append(column_names)
    rows = {}
    for item in data:
        keys = []
        key_map = {}
        for key in row_keys:
            keys.append(item[key])
            key_map[key] = item[key]
        key = '.'.join(keys)
        _, row = rows.setdefault(key, (key_map, []))
        row.append(item)
    rows = rows.values()
    rows = sorted(rows)
    for key_map, row in rows:
        line = columns * [settings.DEFAULT_INFLUX_VALUE]
        for key, value in six.iteritems(key_map):
            line[column_index[column_name_map[key]]] = value
        for item in row:
            line[column_index[item[column_key]]] = item['value']
        output.append(line)
    string_buffer = StringIO.StringIO()
    writer = csv.writer(string_buffer)
    writer.writerows(output)
    return utils.make_csv_response(
        200, string_buffer.getvalue(),
        '%s-%s.csv' % (datacenter, device_type)
    )


def _write_points(
    session, measurement, timeseries, tags={}, time_precision=None
):
    points = []
    for timestamp, value in six.iteritems(timeseries):
        if time_precision:
            timestamp = long(timestamp)
        points.append({
            'measurement': measurement,
            'time': timestamp,
            'fields': {
                'value': value
            }
        })
    logger.debug('timeseries %s points: %s', measurement, points)
    logger.debug('timeseries %s tags: %s', measurement, tags)
    return session.write_points(
        points, time_precision=time_precision, tags=tags
    )


def generate_device_type_timeseries(data, tags, measurement_metadata):
    for timestamp, timestamp_data in six.iteritems(data):
        for device, value in six.iteritems(timestamp_data):
            generated_tags = dict(tags)
            generated_tags.update({
                'device': device
            })
            value = _convert_timeseries_value(
                value, measurement_metadata['attribute']['type']
            )
            yield {timestamp: value}, generated_tags


def generate_device_timeseries(data, tags, measurement_metadata):
    generated_tags = dict(tags)
    for timestamp, value in six.iteritems(data):
        value = _convert_timeseries_value(
            value, measurement_metadata['attribute']['type']
        )
        yield {timestamp: value}, generated_tags


def _create_timeseries(
    measurement, data, measurement_metadata,
    timeseries_generator, tags={}, time_precision=None
):
    status = True
    outputs = []
    for device_data, generated_tags in timeseries_generator(
        data, tags, measurement_metadata
    ):
        outputs.append((measurement, device_data, generated_tags))
    with database.influx_session() as session:
        for measurement, device_data, generated_tags in outputs:
            status &= _write_points(
                session, measurement, device_data,
                generated_tags, time_precision
            )
    logger.debug(
        'create timeseries %s %s status: %s',
        measurement, data, status
    )
    if not status:
        raise exception_handler.NotAccept(
            'measurement %s with data %s is not acceptable' % (
                measurement, data
            )
        )


def _convert_timeseries_value(value, value_type):
    return database.convert_timeseries_value(value, value_type)


@app.route(
    "/import/timeseries/<datacenter>/<device_type>",
    methods=['POST']
)
def import_timeseries(datacenter, device_type):
    args = _get_request_args()
    logger.debug(
        'upload timeseries datacenter=%s device_type=%s',
        datacenter, device_type
    )
    timestamp_column = args.get('timestamp_column', 'time')
    device_column = args.get('device_column')
    measurement_column = args.get('measurement_column')
    logger.debug('timestamp_column: %s', timestamp_column)
    logger.debug('device_column: %s', device_column)
    logger.debug('measurement_column: %s', measurement_column)
    column_name_map = {}
    if timestamp_column:
        column_name_map[timestamp_column] = 'time'
    if device_column:
        column_name_map[device_column] = 'device'
    if measurement_column:
        column_name_map[measurement_column] = 'measurement'
    logger.debug('column_name_map: %s', column_name_map)
    assert any([timestamp_column, device_column, measurement_column])
    assert not all([timestamp_column, device_column, measurement_column])
    column_name_as_timestamp = bool(
        args.get('column_name_as_timestamp', False)
    )
    column_name_as_measurement = bool(
        args.get('column_name_as_measurement', False)
    )
    column_name_as_device = bool(
        args.get(
            'column_name_as_device',
            not (
                column_name_as_timestamp or column_name_as_measurement
            )
        )
    )
    logger.debug('column_name_as_timestamp: %s', column_name_as_timestamp)
    logger.debug('column_name_as_measurement: %s', column_name_as_measurement)
    logger.debug('column_name_as_device: %s', column_name_as_device)
    assert sum([
        column_name_as_timestamp,
        column_name_as_device,
        column_name_as_measurement
    ]) == 1
    assert not (column_name_as_timestamp and timestamp_column)
    assert not (column_name_as_device and device_column)
    assert not (column_name_as_measurement and measurement_column)
    time_precision = args.get(
        'time_precisin', settings.DEFAULT_TIME_PRECISION
    )
    logger.debug('time precision: %s', time_precision)
    device_type_metadata = _get_device_type_metadata(
        datacenter, device_type
    )
    column_key = None
    if column_name_as_timestamp:
        column_key = 'time'
    if column_name_as_measurement:
        column_key = 'measurement'
    if column_name_as_device:
        column_key = 'device'
    logger.debug('column_key: %s', column_key)
    device_type_metadata = _get_device_type_metadata(datacenter, device_type)
    request_files = request.files.items(multi=True)
    if not request_files:
            raise exception_handler.NotAcceptable(
                'no csv file to upload'
            )
    logger.debug('upload csv files: %s', request_files)
    data = []
    column_names = set()
    for filename, upload in request_files:
        fields = None
        reader = csv.reader(upload)
        for row in reader:
            if not row:
                continue
            logger.debug('read row %s', row)
            if not fields:
                fields = row
                for field in fields:
                    if field not in column_name_map:
                        column_names.add(field)
            else:
                data.append(dict(zip(fields, row)))
    outputs = []
    for item in data:
        extra_tags = {}
        for key, value in six.iteritems(column_name_map):
            extra_tags[value] = item.pop(
                key, settings.DEFAULT_INFLUX_VALUE
            )
        for key, value in six.iteritems(item):
            extra_tags[column_key] = key
            tags = {
                'datacenter': datacenter,
                'device_type': device_type
            }
            tags.update(extra_tags)
            measurement = tags.pop('measurement')
            timestamp = tags.pop('time')
            if measurement not in device_type_metadata:
                raise exception_handler.ItemNotFound(
                    'measurement %s does not found '
                    'in datacenter %s device type %s' % (
                        measurement, datacenter, device_type
                    )
                )
            measurement_metadata = device_type_metadata[measurement]
            if 'device' in tags:
                device = tags['device']
                if device not in measurement_metadata['devices']:
                    raise exception_handler.ItemNotFound(
                        'device %s does not found '
                        'in datacenter %s device type %s measurement %s' % (
                            device, datacenter, device_type, measurement
                        )
                    )
            if time_precision:
                timestamp = long(timestamp)
            value = _convert_timeseries_value(
                value, measurement_metadata['attribute']['type']
            )
            outputs.append((measurement, {timestamp: value}, tags))
    status = True
    with database.influx_session() as session:
        for measurement, timeseries_data, tags in outputs:
            status &= _write_points(
                session, measurement,
                timeseries_data, tags,
                time_precision
            )
    if not status:
        raise exception_handler.NotAccept(
            'data import for datacenter %s device type %s '
            'is not acceptable' % (
                datacenter, device_type
            )
        )
    return utils.make_json_response(
        200, {'status': True}
    )


@app.route("/timeseries/<datacenter>/<device_type>", methods=['POST'])
def create_device_type_all_timeseries(datacenter, device_type):
    data = _get_request_data()
    logger.debug(
        'timeseries data for %s %s: %s',
        datacenter, device_type, data
    )
    time_precision = data.pop(
        'time_precision', settings.DEFAULT_TIME_PRECISION
    )
    tags = data.pop('tags', {})
    tags.update({
        'datacenter': datacenter,
        'device_type': device_type
    })
    device_type_metadata = _get_device_type_metadata(
        datacenter, device_type
    )
    for measurement, measurement_metadata in six.iteritems(
        device_type_metadata
    ):
        _create_timeseries(
            measurement, data, measurement_metadata,
            generate_device_type_timeseries,
            tags, time_precision
        )
    return utils.make_json_response(
        200, {'status': True}
    )


@app.route(
    "/timeseries/<datacenter>/<device_type>/<measurement>",
    methods=['POST']
)
def create_device_type_timeseries(datacenter, device_type, measurement):
    data = _get_request_data()
    logger.debug(
        'timeseries data for %s %s %s: %s',
        datacenter, device_type, measurement, data
    )
    time_precision = data.pop(
        'time_precision', settings.DEFAULT_TIME_PRECISION
    )
    tags = data.pop('tags', {})
    tags.update({
        'datacenter': datacenter,
        'device_type': device_type
    })
    device_type_metadata = _get_device_type_metadata(
        datacenter, device_type
    )
    if measurement not in device_type_metadata:
        raise exception_handler.ItemNotFound(
            'measurement %s does not found '
            'in datacenter %s device type %s' % (
                measurement, datacenter, device_type
            )
        )
    measurement_metadata = device_type_metadata[measurement]
    _create_timeseries(
        measurement, data, measurement_metadata,
        generate_device_type_timeseries,
        tags, time_precision
    )
    return utils.make_json_response(
        200, {'status': True}
    )


@app.route(
    "/timeseries/<datacenter>/<device_type>/<device>/<measurement>",
    methods=['POST']
)
def create_device_timeseries(datacenter, device_type, device, measurement):
    data = _get_request_data()
    logger.debug(
        'timeseries data for %s %s %s %s: %s',
        datacenter, device_type, device, measurement, data
    )
    time_precision = data.pop(
        'time_precision', settings.DEFAULT_TIME_PRECISION
    )
    tags = data.pop('tags', {})
    tags.update({
        'datacenter': datacenter,
        'device_type': device_type,
        'device': device
    })
    device_type_metadata = _get_device_type_metadata(
        datacenter, device_type
    )
    if measurement not in device_type_metadata:
        raise exception_handler.ItemNotFound(
            'measurement %s does not found '
            'in datacenter %s device type %s' % (
                measurement, datacenter, device_type
            )
        )
    measurement_metadata = device_type_metadata[measurement]
    if device not in measurement_metadata['devices']:
        raise exception_handler.ItemNotFound(
            'device %s does not found '
            'in datacenter %s device type %s measurement %s' % (
                device, datacenter, device_type, measurement
            )
        )
    _create_timeseries(
        measurement, data, measurement_metadata,
        generate_device_timeseries, tags, time_precision
    )
    return utils.make_json_response(
        200, {'status': True}
    )


def _delete_timeseries(measurement, tags):
    logger.debug('timeseries data for %s: %s', measurement, tags)
    with database.influx_session() as session:
        session.delete_series(measurement=measurement, tags=tags)
    return True


@app.route(
    "/timeseries/<datacenter>/<device_type>",
    methods=['DELETE']
)
def delete_device_type_all_timeseries(
        datacenter, device_type
):
    data = _get_request_data()
    data.update({
        'datacenter': datacenter,
        'device_type': device_type
    })
    device_type_metadata = _get_device_type_metadata(
        datacenter, device_type
    )
    for measurement, _ in six.iteritems(device_type_metadata):
        _delete_timeseries(measurement, data)
    return utils.make_json_response(
        200, {'status': True}
    )


@app.route(
    "/timeseries/<datacenter>/<device_type>/<measurement>",
    methods=['DELETE']
)
def delete_device_type_timeseries(datacenter, device_type, measurement):
    data = _get_request_data()
    data.update({
        'datacenter': datacenter,
        'device_type': device_type
    })
    device_type_metadata = _get_device_type_metadata(
        datacenter, device_type
    )
    if measurement not in device_type_metadata:
        raise exception_handler.ItemNotFound(
            'measurement %s does not found '
            'in datacenter %s device type %s' % (
                measurement, datacenter, device_type
            )
        )
    _delete_timeseries(measurement, data)
    return utils.make_json_response(
        200, {'status': True}
    )


@app.route(
    "/timeseries/<datacenter>/<device_type>/<device>/<measurement>",
    methods=['DELETE']
)
def delete_device_timeseries(datacenter, device_type, device, measurement):
    data = _get_request_data()
    data.update({
        'datacenter': datacenter,
        'device_type': device_type,
        'device': device
    })
    device_type_metadata = _get_device_type_metadata(
        datacenter, device_type
    )
    if measurement not in device_type_metadata:
        raise exception_handler.ItemNotFound(
            'measurement %s does not found '
            'in datacenter %s device type %s' % (
                measurement, datacenter, device_type
            )
        )
    measurement_metadata = device_type_metadata[measurement]
    if device not in measurement_metadata['devices']:
        raise exception_handler.ItemNotFound(
            'device %s does not found '
            'in datacenter %s device type %s measurement %s' % (
                device, datacenter, device_type, measurement
            )
        )
    _delete_timeseries(measurement, data)
    return utils.make_json_response(
        200, {'status': True}
    )


@app.route("/", methods=['GET'])
def index():
    return utils.make_template_response(200, {}, 'index.html')


def _create_prediction(datacenter_name):
    with database.session() as session:
        datacenter = session.query(
            models.Datacenter
        ).filter_by(name=datacenter_name).first()
        prediction = models.Prediction()
        datacenter.predictions.append(prediction)
        session.flush()
        return prediction.name


@app.route("/models/<datacenter>/<model_type>/build", methods=['POST'])
def build_model(datacenter, model_type):
    try:
        celery_client.celery.send_task(
            'energy_saving.tasks.build_model', (
                datacenter, model_type
            )
        )
    except Exception as error:
        logging.exception(error)
        raise exception_handler.Forbidden(
            'failed to send build_model to celery'
        )
    return utils.make_json_response(
        200, {}
    )


@app.route("/models/<datacenter>/<model_type>/train", methods=['POST'])
def train_model(datacenter, model_type):
    try:
        celery_client.celery.send_task(
            'energy_saving.tasks.train_model', (
                datacenter, model_type
            )
        )
    except Exception as error:
        logging.exception(error)
        raise exception_handler.Forbidden(
            'failed to send train_model to celery'
        )
    return utils.make_json_response(
        200, {}
    )


@app.route("/models/<datacenter>/<model_type>/test", methods=['POST'])
def test_model(datacenter, model_type):
    try:
        celery_client.celery.send_task(
            'energy_saving.tasks.test_model', (
                datacenter, model_type
            )
        )
    except Exception as error:
        logging.exception(error)
        raise exception_handler.Forbidden(
            'failed to send test_model to celery'
        )
    return utils.make_json_response(
        200, {}
    )


@app.route("/models/<datacenter>/<model_type>/apply", methods=['POST'])
def apply_model(datacenter, model_type):
    prediction = _create_prediction(datacenter)
    logger.debug(
        'datacenter %s model %s prediction %s',
        datacenter, model_type, prediction
    )
    try:
        celery_client.celery.send_task(
            'energy_saving.tasks.apply_model', (
                datacenter, model_type, prediction
            )
        )
    except Exception as error:
        logging.exception(error)
        raise exception_handler.Forbidden(
            'failed to send apply_model to celery'
        )
    return utils.make_json_response(
        200, {'prediction': prediction}
    )


def init():
    logsetting.init(CONF.logfile)
    database.init()
    admin_api.init()


if __name__ == '__main__':
    init()
    app.run(
        host='0.0.0.0', port=CONF.server_port,
        debug=settings.DEBUG
    )
