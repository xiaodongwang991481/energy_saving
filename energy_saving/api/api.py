"""Define all the RestfulAPI entry points."""
import csv
import datetime
from dateutil import parser
import logging
import re
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
from energy_saving.models import model_type_builder_manager
from energy_saving.tasks import client as celery_client
from energy_saving.utils import logsetting
from energy_saving.utils import settings
from energy_saving.utils import util

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
    ),
    cfg.BoolOpt(
        'server_debug',
        help='flask server in debug mode',
        default=settings.DEBUG
    ),
    cfg.IntOpt(
        'timeseries_import_add_seconds_same_timestamp',
        help='adding seconds for the same timestamp record when importing',
        default=settings.DEFAULT_IMPORT_ADD_SECONDS_SAME_TIMESTAMP
    ),
    cfg.StrOpt(
        'timeseries_time_precision',
        help='timeseries time precision',
        default=settings.DEFAULT_TIME_PRECISION
    ),
    cfg.StrOpt(
        'timeseries_default_value',
        help='tiemseries default value',
        default=settings.DEFAULT_INFLUX_VALUE
    ),
    cfg.ListOpt(
        'timeseries_ignorable_values',
        help='timeseries ignorable values when import',
        default=settings.IGNORABLE_INFLUX_VALUES
    ),
    cfg.StrOpt(
        'timeseries_export_timestamp_column',
        help='timeseries export timestamp column name',
        default=settings.DEFAULT_EXPORT_TIMESTAMP_COLUMN
    ),
    cfg.StrOpt(
        'timeseries_export_device_column',
        help='timeseries export device column name',
        default=settings.DEFAULT_EXPORT_DEVICE_COLUMN
    ),
    cfg.StrOpt(
        'timeseries_export_measurement_column',
        help='timeseries export measurement column name',
        default=settings.DEFAULT_EXPORT_MEASUREMENT_COLUMN
    ),
    cfg.BoolOpt(
        'timeseries_export_timestamp_as_column',
        help='timeseries export timestamp as column name',
        default=settings.DEFAULT_EXPORT_TIMESTAMP_AS_COLUMN
    ),
    cfg.BoolOpt(
        'timeseries_export_measurement_as_column',
        help='timeseries export measurement as column name',
        default=settings.DEFAULT_EXPORT_MEASUREMENT_AS_COLUMN
    ),
    cfg.BoolOpt(
        'timeseries_export_device_as_column',
        help='timeseries export device as column name',
        default=settings.DEFAULT_EXPORT_DEVICE_AS_COLUMN
    )
]
CONF = util.CONF
CONF.register_cli_opts(opts)


logger = logging.getLogger(__name__)
model_type_manager = model_type_builder_manager.ModelTypeBuilderManager()


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
        return database.get_datacenter_device_type_metadata(
            session, datacenter_name, device_type
        )


def _get_datacenter_metadata(datacenter_name):
    with database.session() as session:
        return database.get_datacenter_metadata(session, datacenter_name)


def _get_metadata():
    with database.session() as session:
        return database.get_metadata(session)


@app.route("/metadata/timeseries/models", methods=['GET'])
def list_timeseries_models():
    logging.debug('list timeseries models')
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
    field_mapping = {
        column.name: column.type.python_type
        for column in model.__table__.columns
    }
    primary_fields = [
        column.name
        for column in model.__table__.primary_key
    ]
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
            if not fields:
                fields = row
                for field in fields:
                    assert field in field_mapping
            else:
                row = dict(zip(fields, row))
                row_data = {}
                for key, value in six.iteritems(row):
                    if value:
                        row_data[key] = database.convert_column_value(
                            value, field_mapping[key]
                        )
                data.append(row_data)
    with database.session() as session:
        for row_data in data:
            primary_data = {
                key: row_data[key] for key in primary_fields
            }
            result = session.query(
                model
            ).filter_by(**primary_data).first()
            if result:
                for key, value in six.iteritems(row_data):
                    if key not in primary_data:
                        setattr(result, key, value)
            else:
                result = model(**row_data)
                session.add(result)
        session.flush()
    return utils.make_json_response(
        200, 'OK'
    )


def _get_timestamp(timestamp_str):
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


def _get_where(data):
    wheres = []
    starttime = data.get('starttime')
    starttime = _get_timestamp(starttime)
    endtime = data.get('endtime')
    endtime = _get_timestamp(endtime)
    for key in ['datacenter', 'device_type', 'device']:
        if not data.get(key):
            continue
        value = data[key]
        if isinstance(value, list):
            if not value:
                continue
            sub_wheres = []
            for item in value:
                sub_wheres.append("%s = '%s'" % (key, item))
            wheres.append('(%s)' % ' or '.join(sub_wheres))
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
    if isinstance(order_by, list):
        return ', '.join(order_by)
    else:
        return order_by


def _list_timeseries(
    session, measurement, data, measurement_metadata,
    data_formatter=None, extra_select_fields=None
):
    logger.debug('timeseries data: %s', data)
    response = {}
    query = data.get('query')
    where = data.get('where')
    group_by = data.get('group_by') or []
    order_by = data.get('order_by') or []
    fill = data.get('fill')
    aggregation = data.get('aggregation')
    limit = data.get('limit')
    offset = data.get('offset')
    time_precision = data.get(
        'time_precision'
    ) or CONF.timeseries_time_precision
    if not time_precision:
        time_converter = parser.parse
        time_formatter = str
    else:
        time_converter = long
        time_formatter = long
    if not query:
        if not where:
            where = _get_where(data)
        if where:
            where_clause = ' where %s' % where
        else:
            where_clause = ''
        if aggregation:
            value = '%s(value) as value' % aggregation
        else:
            value = 'value'
        if extra_select_fields:
            group_by = group_by + extra_select_fields
        select = value
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
            select, measurement, where_clause,
            group_by_clause, order_by_clause, fill_clause,
            limit_clause, offset_clause
        )
    logger.debug(
        'timeseries %s precision %s query: %s',
        measurement, time_precision, query
    )
    response = []
    result = session.query(query, epoch=time_precision)
    for key, value in result.items():
        _, group_tags = key
        for item in value:
            if item['value'] is None:
                continue
            if not time_precision:
                item['time'] = time_converter(item['time'])
            if group_tags:
                item.update(group_tags)
            assert item['device'] in measurement_metadata['devices']
            item['value'] = database.format_timeseries_value(
                item['value'], measurement_metadata['attribute']['type']
            )
            response.append(item)
    if data_formatter:
        response = data_formatter(response, time_formatter)
    return response


def timeseries_device_type_formatter(data, time_formatter=str):
    result = {}
    for item in data:
        timestamp = time_formatter(item['time'])
        timestamp_result = result.setdefault(timestamp, {})
        timestamp_result[item['device']] = item['value']
    return result


def timeseries_device_formatter(data, time_formatter=str):
    result = {}
    for item in data:
        timestamp = time_formatter(item['time'])
        result[timestamp] = item['value']
    return result


@app.route("/timeseries/<datacenter>/<device_type>", methods=['GET'])
def list_device_type_all_timeseries(datacenter, device_type):
    data = _get_request_args(as_list={
        'group_by': True,
        'order_by': True,
        'measurement': True,
        'device': True
    })
    data.update({
        'datacenter': datacenter,
        'device_type': device_type
    })
    device_type_metadata = _get_device_type_metadata(
        datacenter, device_type
    )
    measurements = data.get('measurement') or device_type_metadata.keys()
    for measurement in measurements:
        assert measurement in device_type_metadata
    response = {}
    with database.influx_session() as session:
        for measurement in measurements:
            measurment_metadata = device_type_metadata[measurement]
            response[measurement] = _list_timeseries(
                session, measurement, data,
                measurment_metadata,
                timeseries_device_type_formatter,
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
    response = {}
    device_type_metadata = _get_device_type_metadata(
        datacenter, device_type
    )
    assert measurement in device_type_metadata
    measurement_metadata = device_type_metadata[measurement]
    with database.influx_session() as session:
        response = _list_timeseries(
            session, measurement, data,
            measurement_metadata,
            timeseries_device_type_formatter,
            extra_select_fields=['device']
        )
    return utils.make_json_response(
        200, response
    )


@app.route(
    "/timeseries/<datacenter>/<device_type>/<measurement>/<device>",
    methods=['GET']
)
def list_device_timeseries(datacenter, device_type, measurement, device):
    data = _get_request_args(as_list={
        'group_by': True,
        'order_by': True
    })
    data.update({
        'datacenter': datacenter,
        'device_type': device_type,
        'device': device
    })
    response = {}
    device_type_metadata = _get_device_type_metadata(
        datacenter, device_type
    )
    assert measurement in device_type_metadata
    measurement_metadata = device_type_metadata[measurement]
    assert device in measurement_metadata['devices']
    with database.influx_session() as session:
        response = _list_timeseries(
            session, measurement, data,
            measurement_metadata,
            timeseries_device_formatter,
            extra_select_fields=['device']
        )
    return utils.make_json_response(
        200, response
    )


def _get_key_function(item_funcs):
    def get_key(items):
        keys = tuple(
            item_func(item) for item_func, item in zip(item_funcs, items)
        )
        return keys
    return get_key


@app.route(
    "/export/timeseries/<datacenter>/<device_type>",
    methods=['GET']
)
def export_timeseries(datacenter, device_type):
    args = _get_request_args(as_list={
        'measurement': True,
        'device': True,
        'group_by': True,
        'order_by': True
    })
    device_type_metadata = _get_device_type_metadata(
        datacenter, device_type
    )
    measurements = args.get('measurement') or device_type_metadata.keys()
    all_devices = set()
    for measurement in measurements:
        assert measurement in device_type_metadata
        all_devices = all_devices.union(
            device_type_metadata[measurement]['devices']
        )
    measurements = set(measurements)
    devices = args.get('device')
    if not devices:
        devices = set()
    else:
        for device in devices:
            assert device in all_devices
        devices = set(devices)
    logger.debug(
        'download timeseries datacenter=%s device_type=%s '
        'measurements=%s devices=%s',
        datacenter, device_type, measurements, devices
    )
    timestamp_column = args.get(
        'timestamp_column'
    ) or CONF.timeseries_export_timestamp_column
    device_column = args.get(
        'device_column'
    ) or CONF.timeseries_export_device_column
    measurement_column = args.get(
        'measurement_column'
    ) or CONF.timeseries_export_measurement_column
    logger.debug('timestamp_column: %s', timestamp_column)
    logger.debug('device_column: %s', device_column)
    logger.debug('measurement_column: %s', measurement_column)
    assert any([timestamp_column, device_column, measurement_column])
    assert not all([timestamp_column, device_column, measurement_column])
    column_name_as_timestamp = bool(
        args.get(
            'column_name_as_timestamp',
            CONF.timeseries_export_timestamp_as_column
        )
    )
    column_name_as_measurement = bool(
        args.get(
            'column_name_as_measurement',
            CONF.timeseries_export_measurement_as_column
        )
    )
    column_name_as_device = bool(
        args.get(
            'column_name_as_device',
            CONF.timeseries_export_device_as_column
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
    timestamps = set()
    data = []
    with database.influx_session() as session:
        for measurement in measurements:
            tags = {
                'datacenter': datacenter,
                'device_type': device_type,
                'device': args.get('device'),
                'time_precision': args.get('time_precision'),
                'starttime': args.get('starttime'),
                'endtime': args.get('endtime'),
                'group_by': args.get('group_by'),
                'order_by': args.get('order_by'),
                'aggregation': args.get('aggregation'),
                'fill': args.get('fill'),
                'limit': args.get('limit'),
                'offset': args.get('offset')
            }
            measurement_metadata = device_type_metadata[measurement]
            response = _list_timeseries(
                session, measurement, tags,
                measurement_metadata,
                timeseries_device_type_formatter,
                extra_select_fields=['device']
            )
            for timestamp, device_data in six.iteritems(response):
                for device, value in six.iteritems(device_data):
                    timestamps.add(timestamp)
                    data.append({
                        'measurement': measurement,
                        'device': device,
                        'time': timestamp,
                        'value': value
                    })
    measurements = list(measurements)
    measurements = sorted(measurements)
    devices = list(devices)
    devices = sorted(devices)
    timestamps = list(timestamps)
    timestamps = sorted(timestamps)
    logger.debug('timestamps: %s', timestamps)
    column_names = []
    row_keys = []
    column_key = None
    if device_column:
        column_names.append(device_column)
        row_keys.append('device')
    if timestamp_column:
        column_names.append(timestamp_column)
        row_keys.append('time')
    if measurement_column:
        column_names.append(measurement_column)
        row_keys.append('measurement')
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
        for key in row_keys:
            keys.append(item[key])
        row = rows.setdefault(tuple(keys), [])
        row.append(item)
    export_keys = rows.keys()
    export_keys = sorted(export_keys)
    for keys in export_keys:
        row = rows[keys]
        line = columns * [CONF.timeseries_default_value]
        for i, key in enumerate(keys):
            line[i] = key
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


def generate_device_type_timeseries(
    data, tags, measurement_metadata, timestamp_converter
):
    for timestamp, timestamp_data in six.iteritems(data):
        timestamp = timestamp_converter(timestamp)
        for device, value in six.iteritems(timestamp_data):
            value = _convert_timeseries_value(
                value, measurement_metadata['attribute']['type'],
                False
            )
            if value is not None:
                yield {timestamp: value}, device


def generate_device_timeseries(
    data, tags, measurement_metadata, timestamp_converter
):
    device = tags['device']
    for timestamp, value in six.iteritems(data):
        timestamp = timestamp_converter(timestamp)
        value = _convert_timeseries_value(
            value, measurement_metadata['attribute']['type'],
            False
        )
        if value is not None:
            yield {timestamp: value}, device


def _create_timeseries(
    measurement, data, measurement_metadata,
    timeseries_generator, tags={}, time_precision=None
):
    status = True
    uniq_tags = {}
    if not time_precision:
        timestamp_converter = parser.parse
    else:
        timestamp_converter = long
    for device_data, device in timeseries_generator(
        data, tags, measurement_metadata, timestamp_converter
    ):
        uniq_tag = uniq_tags.setdefault(device, {})
        uniq_tag.update(device_data)
    with database.influx_session() as session:
        for device, device_data in six.iteritems(uniq_tags):
            tags['device'] = device
            status &= _write_points(
                session, measurement, device_data,
                tags, time_precision
            )
    logger.debug(
        'create timeseries %s status: %s',
        measurement, status
    )
    if not status:
        raise exception_handler.NotAccept(
            'measurement %s data is not acceptable' % (
                measurement
            )
        )


def _convert_timeseries_value(value, value_type, raise_exception=False):
    return database.convert_timeseries_value(
        value, value_type, raise_exception=raise_exception
    )


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
    import_add_seconds_same_timestamp = args.get(
        'import_add_seconds_same_timestamp'
    ) or CONF.timeseries_import_add_seconds_same_timestamp
    if import_add_seconds_same_timestamp:
        import_add_seconds_same_timestamp = int(
            import_add_seconds_same_timestamp
        )
    default_measurement = args.get('measurement')
    default_device = args.get('device')
    default_timestamp = args.get('timestamp')
    timestamp_column = args.get(
        'timestamp_column'
    ) or CONF.timeseries_export_timestamp_column
    device_column = args.get(
        'device_column'
    ) or CONF.timeseries_export_device_column
    measurement_column = args.get(
        'measurement_column'
    ) or CONF.timeseries_export_measurement_column
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
        args.get(
            'column_name_as_timestamp',
            CONF.timeseries_export_timestamp_as_column
        )
    )
    column_name_as_measurement = bool(
        args.get(
            'column_name_as_measurement',
            CONF.timeseries_export_measurement_as_column
        )
    )
    column_name_as_device = bool(
        args.get(
            'column_name_as_device',
            CONF.timeseries_export_device_as_column
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
    assert not all([column_name_as_timestamp, timestamp_column])
    assert not all([column_name_as_device, device_column])
    assert not all([column_name_as_measurement, measurement_column])
    assert any([
        column_name_as_timestamp, timestamp_column, default_timestamp
    ])
    assert any([
        column_name_as_device, device_column, default_device
    ])
    assert any([
        column_name_as_measurement, measurement_column, default_measurement
    ])
    time_precision = args.get(
        'time_precision'
    ) or CONF.timeseries_time_precision
    if not time_precision:
        timestamp_converter = parser.parse
    else:
        timestamp_converter = long
    import_add_seconds_same_timestamp = get_timedelta(
        time_precision, import_add_seconds_same_timestamp
    )
    logger.debug('time precision: %s', time_precision)
    column_key = None
    if column_name_as_timestamp:
        column_key = 'time'
    if column_name_as_measurement:
        column_key = 'measurement'
    if column_name_as_device:
        column_key = 'device'
    logger.debug('column_key: %s', column_key)
    request_files = request.files.items(multi=True)
    if not request_files:
        raise exception_handler.NotAcceptable(
            'no csv file to upload'
        )
    logger.debug('upload csv files: %s', request_files)
    data = []
    column_names = set()
    uniq_tags = {}
    logger.debug('read csv files')
    for filename, upload in request_files:
        logger.debug('read csv file %s', filename)
        fields = None
        reader = csv.reader(upload)
        for row in reader:
            if not row:
                continue
            if not fields:
                fields = row
                for field in fields:
                    if field not in column_name_map:
                        column_names.add(field)
            else:
                data.append(dict(zip(fields, row)))
    logger.debug('data is loaded from csv files')
    device_type_metadata = _get_device_type_metadata(datacenter, device_type)
    logger.debug('generate influx data')
    logger.debug('ignorable values: %s', CONF.timeseries_ignorable_values)
    for item in data:
        tags = {}
        for key, value in six.iteritems(column_name_map):
            tag_value = item.pop(
                key, CONF.timeseries_default_value
            )
            if tag_value not in CONF.timeseries_ignorable_values:
                tags[value] = tag_value
            # else:
                # logger.debug('ignore column %s value %r', value, tag_value) 
        for key, value in six.iteritems(item):
            tags[column_key] = key
            measurement = tags.get('measurement', default_measurement)
            timestamp = tags.get('time', default_timestamp)
            device = tags.get('device', default_device)
            if not measurement or not timestamp or not device:
                logger.debug('%s tag missing in processing %s', tags, item)
                continue
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
            timestamp = timestamp_converter(timestamp)
            uniq_tag = (measurement, device)
            tag_timestamps = uniq_tags.setdefault(uniq_tag, {})
            if value in CONF.timeseries_ignorable_values:
                # logger.debug('ignore value %s', value)
                continue
            value = _convert_timeseries_value(
                value, measurement_metadata['attribute']['type'],
                False
            )
            if value is not None:
                if import_add_seconds_same_timestamp:
                    while timestamp in tag_timestamps:
                        # logger.debug(
                        #     'increase %s timestamp %s', uniq_tag, timestamp
                        # )
                        timestamp += import_add_seconds_same_timestamp
                tag_timestamps[timestamp] = value
    logger.debug('influx data is generated')
    status = True
    logger.debug('write data to influx')
    with database.influx_session() as session:
        tags = {
            'datacenter': datacenter,
            'device_type': device_type
        }
        for uniq_tags, timeseries_data in six.iteritems(uniq_tags):
            measurement, device = uniq_tags
            tags['device'] = device
            status &= _write_points(
                session, measurement,
                timeseries_data, tags,
                time_precision
            )
    logger.debug('influx data is written')
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
        'time_precision'
    ) or CONF.timeseries_time_precision
    tags = data.pop('tags') or {}
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
        'time_precision'
    ) or CONF.timeseries_time_precision
    tags = data.pop('tags') or {}
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
        'time_precision'
    ) or CONF.timeseries_time_precision
    tags = data.pop('tags') or {}
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


def _create_test_result(datacenter_name):
    with database.session() as session:
        datacenter = session.query(
            models.Datacenter
        ).filter_by(name=datacenter_name).first()
        test_result = models.TestResult()
        datacenter.test_results.append(test_result)
        session.flush()
        return test_result.name


@app.route("/models/<datacenter_name>", methods=['GET'])
def list_model_types(datacenter_name):
    model_types = model_type_manager.model_type_builders.keys()
    model_types = sorted(model_types)
    return utils.make_json_response(
        200, model_types
    )


@app.route("/models/<datacenter_name>/<model_type>", methods=['GET'])
def show_model_type(datacenter_name, model_type):
    model_type = model_type_manager.model_type_builders.get_model_type_builder(
        model_type
    ).get_model_type(datacenter_name)
    return utils.make_json_response(
        200, model_type.config
    )


@app.route("/models/<datacenter_name>/<model_type>/build", methods=['POST'])
def build_model(datacenter_name, model_type):
    data = _get_request_data()
    logger.debug(
        'build model params: data=%s',
        data
    )
    try:
        celery_client.celery.send_task(
            'energy_saving.tasks.build_model', (
                datacenter_name, model_type
            ), {
                'data': data
            }
        )
    except Exception as error:
        logging.exception(error)
        raise exception_handler.Forbidden(
            'failed to send build_model to celery'
        )
    return utils.make_json_response(
        200, {'status': True}
    )


@app.route("/models/<datacenter_name>/<model_type>/train", methods=['POST'])
def train_model(datacenter_name, model_type):
    data = _get_request_data()
    starttime = _get_timestamp(data.get('starttime'))
    endtime = _get_timestamp(data.get('endtime'))
    train_data = data.get('data')
    logger.debug(
        'train model params: starttime=%s, endtime=%s data=%s',
        starttime, endtime, train_data
    )
    if not train_data:
        assert starttime is not None
        assert endtime is not None
    try:
        celery_client.celery.send_task(
            'energy_saving.tasks.train_model', (
                datacenter_name, model_type
            ), {
                'starttime': starttime,
                'endtime': endtime,
                'data': train_data
            }
        )
    except Exception as error:
        logging.exception(error)
        raise exception_handler.Forbidden(
            'failed to send train_model to celery'
        )
    return utils.make_json_response(
        200, {'status': True}
    )


@app.route("/models/<datacenter_name>/<model_type>/test", methods=['POST'])
def test_model(datacenter_name, model_type):
    data = _get_request_data()
    starttime = _get_timestamp(data.get('starttime'))
    endtime = _get_timestamp(data.get('endtime'))
    test_data = data.get('data')
    logger.debug(
        'test model params: starttime=%s, endtime=%s data=%s',
        starttime, endtime, test_data
    )
    if not test_data:
        assert starttime is not None
        assert endtime is not None
    test_result = _create_test_result(datacenter_name)
    try:
        celery_client.celery.send_task(
            'energy_saving.tasks.test_model', (
                datacenter_name, model_type, test_result
            ), {
                'starttime': starttime,
                'endtime': endtime,
                'data': test_data
            }
        )
    except Exception as error:
        logging.exception(error)
        raise exception_handler.Forbidden(
            'failed to send test_model to celery'
        )
    return utils.make_json_response(
        200, {'status': status, 'test_result': test_result}
    )


@app.route("/models/<datacenter_name>/<model_type>/apply", methods=['POST'])
def apply_model(datacenter_name, model_type):
    data = _get_request_data()
    starttime = _get_timestamp(data.get('starttime'))
    endtime = _get_timestamp(data.get('endtime'))
    apply_data = data.get('data')
    logger.debug(
        'apply model params: starttime=%s, endtime=%s data=%s',
        starttime, endtime, apply_data
    )
    if not apply_data:
        assert starttime is not None
        assert endtime is not None
    prediction = _create_prediction(datacenter_name)
    logger.debug(
        'datacenter %s model %s prediction %s',
        datacenter_name, model_type, prediction
    )
    try:
        celery_client.celery.send_task(
            'energy_saving.tasks.apply_model', (
                datacenter_name, model_type, prediction
            ), {
                'starttime': starttime,
                'endtime': endtime,
                'data': apply_data
            }
        )
    except Exception as error:
        logging.exception(error)
        raise exception_handler.Forbidden(
            'failed to send apply_model to celery'
        )
    return utils.make_json_response(
        200, {'status': status, 'prediction': prediction}
    )


def init(argv=None):
    util.init(argv)
    logsetting.init(CONF.logfile)
    database.init()
    admin_api.init()
    app.debug = CONF.server_debug
    return app


def run_server():
    app.run(
        host='0.0.0.0', port=CONF.server_port,
        debug=CONF.server_debug
    )


if __name__ == '__main__':
    init()
    run_server()
