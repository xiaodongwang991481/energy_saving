"""Define all the RestfulAPI entry points."""
import csv
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
from energy_saving.db import timeseries
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


@app.route("/metadata/timeseries/models", methods=['GET'])
def list_timeseries_models():
    logging.debug('list timeseries models')
    with database.session() as session:
        result = timeseries.get_metadata(session)
    return utils.make_json_response(
        200, result
    )


@app.route("/metadata/timeseries/models/<datacenter>", methods=['GET'])
def list_datacenter_timeseries_models(datacenter):
    logging.debug('list datacenter %s timeseries models', datacenter)
    with database.session() as session:
        result = timeseries.get_datacenter_metadata(session, datacenter)
    return utils.make_json_response(
        200, result
    )


@app.route(
    "/metadata/timeseries/models/<datacenter>/<device_type>",
    methods=['GET']
)
def list_device_type_timeseries_models(datacenter, device_type):
    logging.debug(
        'list datacenter %s device type %s timeseries models',
        datacenter, device_type
    )
    with database.session() as session:
        result = timeseries.get_datacenter_device_type_metadata(
            session, datacenter, device_type
        )
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


@app.route("/timeseries/<datacenter>/<device_type>", methods=['GET'])
def list_device_type_timeseries(datacenter, device_type):
    data = _get_request_args(as_list={
        'group_by': True,
        'order_by': True,
        'measurement': True,
        'device': True
    })
    time_precision = (
        data.get('time_precision') or
        CONF.timeseries_time_precision
    )
    with database.session() as session:
        device_type_metadata = timeseries.get_datacenter_device_type_metadata(
            session, datacenter, device_type
        )
    measurements = data.get('measurement') or device_type_metadata.keys()
    for measurement in measurements:
        assert measurement in device_type_metadata
    response = {}
    with database.influx_session() as session:
        response = timeseries.list_timeseries(
            session, {
                'where': {
                    'datacenter': datacenter,
                    'device_type': device_type,
                    'device': data.get('device'),
                    'starttime': data.get('starttime'),
                    'endtime': data.get('endtime')
                },
                'group_by': (data.get('group_by') or []) + ['device'],
                'order_by': data.get('order_by') or [],
                'fill': data.get('fill'),
                'aggregation': data.get('aggregation'),
                'limit': data.get('limit'),
                'offset': data.get('offset'),
                'measurement': measurements
            }, {
                measurement: measurement_metadata['attribute']['type']
                for measurement, measurement_metadata in six.iteritems(
                    device_type_metadata
                )
            },
            timeseries.timeseries_device_type_formatter,
            time_precision
        )
        for measurement, measurement_response in six.iteritems(response):
            for device in measurement_response:
                assert device in device_type_metadata[measurement]['devices']
    return utils.make_json_response(
        200, response
    )


@app.route(
    "/timeseries/<datacenter>/<device_type>/<measurement>",
    methods=['GET']
)
def list_measurement_timeseries(datacenter, device_type, measurement):
    data = _get_request_args(as_list={
        'group_by': True,
        'order_by': True,
        'device': True
    })
    time_precision = (
        data.get('time_precision') or
        CONF.timeseries_time_precision
    )
    response = {}
    with database.session() as session:
        device_type_metadata = timeseries.get_datacenter_device_type_metadata(
            session, datacenter, device_type
        )
    assert measurement in device_type_metadata
    measurement_metadata = device_type_metadata[measurement]
    with database.influx_session() as session:
        response = timeseries.list_measurement_timeseries(
            session, measurement, {
                'where': {
                    'datacenter': datacenter,
                    'device_type': device_type,
                    'device': data.get('device'),
                    'starttime': data.get('starttime'),
                    'endtime': data.get('endtime')
                },
                'group_by': (data.get('group_by') or []) + ['device'],
                'order_by': data.get('order_by') or [],
                'fill': data.get('fill'),
                'aggregation': data.get('aggregation'),
                'limit': data.get('limit'),
                'offset': data.get('offset')
            },
            measurement_metadata['attribute']['type'],
            time_precision
        )
        for device in response:
            assert device in measurement_metadata['devices']
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
    time_precision = (
        data.get('time_precision') or
        CONF.timeseries_time_precision
    )
    response = {}
    with database.session() as session:
        device_type_metadata = timeseries.get_datacenter_device_type_metadata(
            session, datacenter, device_type
        )
    assert measurement in device_type_metadata
    measurement_metadata = device_type_metadata[measurement]
    assert device in measurement_metadata['devices']
    with database.influx_session() as session:
        response = timeseries.list_device_timeseries(
            session, measurement, {
                'where': {
                    'datacenter': datacenter,
                    'device_type': device_type,
                    'device': device,
                    'starttime': data.get('starttime'),
                    'endtime': data.get('endtime')
                },
                'group_by': (data.get('group_by') or []) + ['device'],
                'order_by': data.get('order_by') or [],
                'fill': data.get('fill'),
                'aggregation': data.get('aggregation'),
                'limit': data.get('limit'),
                'offset': data.get('offset')
            },
            measurement_metadata['attribute']['type'],
            time_precision
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
        'device': True,
        'group_by': True,
        'order_by': True
    })
    with database.session() as session:
        device_type_metadata = timeseries.get_datacenter_device_type_metadata(
            session, datacenter, device_type
        )
    measurements = args.get('measurement') or device_type_metadata.keys()
    measurements = list(measurements)
    measurements = sorted(measurements)
    all_devices = set()
    for measurement in measurements:
        assert measurement in device_type_metadata
        all_devices = all_devices.union(
            device_type_metadata[measurement]['devices']
        )
    measurements = set(measurements)
    devices = args.get('device')
    if not devices:
        devices = all_devices
    else:
        for device in devices:
            assert device in all_devices
        devices = set(devices)
    devices = list(devices)
    devices = sorted(devices)
    logger.debug(
        'download timeseries datacenter=%s device_type=%s '
        'measurements=%s devices=%s',
        datacenter, device_type, measurements, devices
    )
    timestamp_column = args.get(
        'timestamp_column'
    ) or CONF.timeseries_export_timestamp_column
    assert timestamp_column
    device_column = args.get(
        'device_column'
    ) or CONF.timeseries_export_device_column
    measurement_column = args.get(
        'measurement_column'
    ) or CONF.timeseries_export_measurement_column
    logger.debug('timestamp_column: %s', timestamp_column)
    logger.debug('device_column: %s', device_column)
    logger.debug('measurement_column: %s', measurement_column)
    assert any([device_column, measurement_column])
    assert not all([device_column, measurement_column])
    column_names = []
    column_names.append(timestamp_column)
    if device_column:
        column_names.append(device_column)
        column_names.extend(measurements)
    if measurement_column:
        column_names.append(measurement_column)
        column_names.extend(devices)
    logger.debug('column names: %s', column_names)
    columns = len(column_names)
    column_index = {}
    for i, column_name in enumerate(column_names):
        column_index[column_name] = i
    logger.debug('column_index: %s', column_index)
    timestamps = set()
    data = {}
    time_precision = (
        args.get('time_precision') or
        CONF.timeseries_time_precision
    )
    with database.influx_session() as session:
        response = timeseries.list_timeseries(
            session, {
                'where': {
                    'datacenter': datacenter,
                    'device_type': device_type,
                    'device': args.get('device'),
                    'starttime': args.get('starttime'),
                    'endtime': args.get('endtime')
                },
                'group_by': (args.get('group_by') or []) + ['device'],
                'order_by': args.get('order_by') or [],
                'fill': args.get('fill'),
                'aggregation': args.get('aggregation'),
                'limit': args.get('limit'),
                'offset': args.get('offset'),
                'measurement': measurements
            }, {
                measurement: measurement_metadata['attribute']['type']
                for measurement, measurement_metadata in six.iteritems(
                    device_type_metadata
                )
            },
            time_precision
        )
        for measurement, measurement_data in six.iteritems(response):
            for device, device_data in six.iteritems(measurement_data):
                assert device in device_type_metadata[measurement]['devices']
                data[(measurement, device)] = device_data
                for timestamp, value in six.iteritems(device_data):
                    timestamps.add(timestamp)
    timestamps = list(timestamps)
    timestamps = sorted(timestamps)
    logger.debug('timestamps: %s', timestamps)
    rows = {}
    default_row = columns * [CONF.timeseries_default_value]
    for key, values in six.iteritems(data):
        measurement, device = key
        column_name = None
        row_name = None
        if device_column:
            column_name = device
            row_name = measurement
        else:
            column_name = measurement
            row_name = device
        for timestamp, value in six.iteritems(values):
            row = rows.setdefault(
                (timestamp, row_name),
                default_row[:]
            )
            row[0] = timestamp
            row[1] = column_name
            row[column_index[row_name]] = value
    export_keys = rows.keys()
    export_keys = sorted(export_keys)
    output = []
    output.append(column_names)
    for keys in export_keys:
        row = rows[keys]
        output.append(row)
    string_buffer = StringIO.StringIO()
    writer = csv.writer(string_buffer)
    writer.writerows(output)
    return utils.make_csv_response(
        200, string_buffer.getvalue(),
        '%s-%s.csv' % (datacenter, device_type)
    )


@app.route(
    "/export/timeseries/<datacenter>/<device_type>/<measurement>",
    methods=['GET']
)
def export_measurement_timeseries(datacenter, device_type, measurement):
    args = _get_request_args(as_list={
        'device': True,
        'group_by': True,
        'order_by': True
    })
    with database.session() as session:
        device_type_metadata = timeseries.get_datacenter_device_type_metadata(
            session, datacenter, device_type
        )
    assert measurement in device_type_metadata
    measurement_metadata = device_type_metadata[measurement]
    all_devices = set(
        measurement_metadata['devices']
    )
    devices = args.get('device')
    if not devices:
        devices = all_devices
    else:
        for device in devices:
            assert device in all_devices
        devices = set(devices)
    devices = list(devices)
    devices = sorted(devices)
    logger.debug(
        'download timeseries datacenter=%s device_type=%s '
        'measurement=%s devices=%s',
        datacenter, device_type, measurement, devices
    )
    timestamp_column = args.get(
        'timestamp_column'
    ) or CONF.timeseries_export_timestamp_column
    assert timestamp_column
    logger.debug('timestamp_column: %s', timestamp_column)
    column_names = []
    column_names.append(timestamp_column)
    column_names.extend(devices)
    logger.debug('column names: %s', column_names)
    columns = len(column_names)
    column_index = {}
    for i, column_name in enumerate(column_names):
        column_index[column_name] = i
    columns = len(column_names)
    logger.debug('column_index: %s', column_index)
    timestamps = set()
    data = {}
    time_precision = (
        args.get('time_precision') or
        CONF.timeseries_time_precision
    )
    with database.influx_session() as session:
        response = timeseries.list_measurement_timeseries(
            session, measurement, {
                'where': {
                    'datacenter': datacenter,
                    'device_type': device_type,
                    'device': args.get('device'),
                    'starttime': args.get('starttime'),
                    'endtime': args.get('endtime')
                },
                'group_by': (args.get('group_by') or []) + ['device'],
                'order_by': args.get('order_by') or [],
                'fill': args.get('fill'),
                'aggregation': args.get('aggregation'),
                'limit': args.get('limit'),
                'offset': args.get('offset')
            },
            measurement_metadata['attribute']['type'],
            time_precision
        )
        for device, device_data in six.iteritems(response):
            assert device in measurement_metadata['devices']
            data[device] = device_data
            for timestamp, value in six.iteritems(device_data):
                timestamps.add(timestamp)
    timestamps = list(timestamps)
    timestamps = sorted(timestamps)
    logger.debug('timestamps: %s', timestamps)
    rows = {}
    default_row = columns * [CONF.timeseries_default_value]
    for device, values in six.iteritems(data):
        for timestamp, value in six.iteritems(values):
            row = rows.setdefault(
                timestamp,
                default_row[:]
            )
            row[0] = timestamp
            row[column_index[device]] = value
    output = []
    output.append(column_names)
    for timestamp in timestamps:
        row = rows[timestamp]
        output.append(row)
    string_buffer = StringIO.StringIO()
    writer = csv.writer(string_buffer)
    writer.writerows(output)
    return utils.make_csv_response(
        200, string_buffer.getvalue(),
        '%s-%s-%s.csv' % (datacenter, device_type, measurement)
    )


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
    timestamp_column = args.get(
        'timestamp_column'
    ) or CONF.timeseries_export_timestamp_column
    assert timestamp_column
    device_column = args.get(
        'device_column'
    ) or CONF.timeseries_export_device_column
    measurement_column = args.get(
        'measurement_column'
    ) or CONF.timeseries_export_measurement_column
    logger.debug('timestamp_column: %s', timestamp_column)
    logger.debug('device_column: %s', device_column)
    logger.debug('measurement_column: %s', measurement_column)
    assert any([device_column, measurement_column])
    assert not all([device_column, measurement_column])
    column_name_map = {}
    column_key = None
    column_name_map[timestamp_column] = 'time'
    if device_column:
        column_name_map[device_column] = 'device'
        column_key = 'measurement'
    if measurement_column:
        column_name_map[measurement_column] = 'measurement'
        column_key = 'device'
    logger.debug('column_name_map: %s', column_name_map)
    time_precision = (
        args.get('time_precision') or
        CONF.timeseries_time_precision
    )
    timestamp_converter = timeseries.get_timestamp_converter(time_precision)
    timestamp_formatter = timeseries.get_timestamp_formatter(time_precision)
    logger.debug('time precision: %s', time_precision)
    import_add_seconds_same_timestamp = timeseries.get_timedelta(
        time_precision, import_add_seconds_same_timestamp
    )
    request_files = request.files.items(multi=True)
    if not request_files:
        raise exception_handler.NotAcceptable(
            'no csv file to upload'
        )
    logger.debug('upload csv files: %s', request_files)
    logger.debug('read csv files')
    data = []
    for filename, upload in request_files:
        logger.debug('read csv file %s', filename)
        fields = None
        reader = csv.reader(upload)
        for row in reader:
            if not row:
                continue
            if not fields:
                fields = row
            else:
                data.append(dict(zip(fields, row)))
    logger.debug('data is loaded from csv files')
    with database.session() as session:
        device_type_metadata = timeseries.get_datacenter_device_type_metadata(
            session, datacenter, device_type
        )
    logger.debug('generate influx data')
    logger.debug('ignorable values: %s', CONF.timeseries_ignorable_values)
    inputs = {}
    for item in data:
        tags = {}
        for key, value in six.iteritems(column_name_map):
            tag_value = item.pop(
                key, CONF.timeseries_default_value
            )
            if tag_value not in CONF.timeseries_ignorable_values:
                tags[value] = tag_value
            else:
                continue
        for key, value in six.iteritems(item):
            if key not in CONF.timeseries_ignorable_values:
                tags[column_key] = key
            else:
                continue
            measurement = tags['measurement']
            timestamp = tags['time']
            device = tags['device']
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
            tag_timestamps = inputs.setdefault(
                measurement, {}
            ).setdefault(device, {})
            if value in CONF.timeseries_ignorable_values:
                continue
            if import_add_seconds_same_timestamp:
                while timestamp in tag_timestamps:
                    timestamp = timestamp_converter(timestamp)
                    timestamp += import_add_seconds_same_timestamp
                    timestamp = timestamp_formatter(timestamp)
            tag_timestamps[timestamp] = value
    logger.debug('influx data is generated')
    tags = {
        'datacenter': datacenter,
        'device_type': device_type
    }
    status = True
    logger.debug('write data to influx')
    with database.influx_session() as session:
        status &= timeseries.create_timeseries(
            session, inputs, {
                measurement: measurement_metadata['attribute']['type']
                for measurement, measurement_metadata in six.iteritems(
                    device_type_metadata
                )
            },
            tags,
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


@app.route(
    "/import/timeseries/<datacenter>/<device_type>/<measurement>",
    methods=['POST']
)
def import_measurement_timeseries(datacenter, device_type, measurement):
    args = _get_request_args()
    logger.debug(
        'upload timeseries datacenter=%s device_type=%s measurement=%s',
        datacenter, device_type, measurement
    )
    import_add_seconds_same_timestamp = args.get(
        'import_add_seconds_same_timestamp'
    ) or CONF.timeseries_import_add_seconds_same_timestamp
    if import_add_seconds_same_timestamp:
        import_add_seconds_same_timestamp = int(
            import_add_seconds_same_timestamp
        )
    timestamp_column = args.get(
        'timestamp_column'
    ) or CONF.timeseries_export_timestamp_column
    assert timestamp_column
    logger.debug('timestamp_column: %s', timestamp_column)
    time_precision = (
        args.get('time_precision') or
        CONF.timeseries_time_precision
    )
    timestamp_converter = timeseries.get_timestamp_converter(time_precision)
    timestamp_formatter = timeseries.get_timestamp_formatter(time_precision)
    logger.debug('time precision: %s', time_precision)
    import_add_seconds_same_timestamp = timeseries.get_timedelta(
        time_precision, import_add_seconds_same_timestamp
    )
    with database.session() as session:
        device_type_metadata = timeseries.get_datacenter_device_type_metadata(
            session, datacenter, device_type
        )
    if measurement not in device_type_metadata:
        raise exception_handler.ItemNotFound(
            'measurement %s does not found '
            'in datacenter %s device type %s' % (
                measurement, datacenter, device_type
            )
        )
    measurement_metadata = device_type_metadata[measurement]
    request_files = request.files.items(multi=True)
    if not request_files:
        raise exception_handler.NotAcceptable(
            'no csv file to upload'
        )
    logger.debug('upload csv files: %s', request_files)
    logger.debug('read csv files')
    data = []
    for filename, upload in request_files:
        logger.debug('read csv file %s', filename)
        fields = None
        reader = csv.reader(upload)
        for row in reader:
            if not row:
                continue
            if not fields:
                fields = row
            else:
                data.append(dict(zip(fields, row)))
    logger.debug('data is loaded from csv files')
    logger.debug('generate influx data')
    logger.debug('ignorable values: %s', CONF.timeseries_ignorable_values)
    inputs = {}
    for item in data:
        tag_value = item.pop(
            timestamp_column, CONF.timeseries_default_value
        )
        if tag_value not in CONF.timeseries_ignorable_values:
            timestamp = tag_value
        else:
            continue
        for device, value in six.iteritems(item):
            if device in CONF.timeseries_ignorable_values:
                continue
            if device not in measurement_metadata['devices']:
                raise exception_handler.ItemNotFound(
                    'device %s does not found '
                    'in datacenter %s device type %s measurement %s' % (
                        device, datacenter, device_type, measurement
                    )
                )
            tag_timestamps = inputs.setdefault(device, {})
            if value in CONF.timeseries_ignorable_values:
                continue
            if import_add_seconds_same_timestamp:
                while timestamp in tag_timestamps:
                    timestamp = timestamp_converter(timestamp)
                    timestamp += import_add_seconds_same_timestamp
                    timestamp = timestamp_formatter(timestamp)
            tag_timestamps[timestamp] = value
    logger.debug('influx data is generated')
    tags = {
        'datacenter': datacenter,
        'device_type': device_type,
        'measurement': measurement
    }
    status = True
    logger.debug('write data to influx')
    with database.influx_session() as session:
        status &= timeseries.create_measurement_timeseries(
            session, inputs,
            measurement_metadata['attribute']['type'],
            tags,
            time_precision
        )
    logger.debug('influx data is written')
    if not status:
        raise exception_handler.NotAccept(
            'data import for datacenter %s device type %s measurement %s'
            'is not acceptable' % (
                datacenter, device_type, measurement
            )
        )
    return utils.make_json_response(
        200, {'status': True}
    )


@app.route("/timeseries/<datacenter>/<device_type>", methods=['POST'])
def create_device_type_timeseries(datacenter, device_type):
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
    with database.session() as session:
        device_type_metadata = timeseries.get_datacenter_device_type_metadata(
            datacenter, device_type
        )
    for measurement, measurement_data in six.iteritems(data):
        assert measurement in device_type_metadata
        measurement_metadata = device_type_metadata[measurement]
        for device in measurement_data:
            assert device in measurement_metadata['devices']
    status = True
    with database.influx_session() as session:
        status &= timeseries.create_timeseries(
            session, data, {
                measurement: measurement_metadata['attribute']['type']
                for measurement, measurement_metadata in six.iteritems(
                    device_type_metadata
                )
            },
            tags, time_precision
        )
    if not status:
        raise exception_handler.NotAcceptable(
            'invalid data from device_type %s' % device_type
        )
    return utils.make_json_response(
        200, {'status': True}
    )


@app.route(
    "/timeseries/<datacenter>/<device_type>/<measurement>",
    methods=['POST']
)
def create_measurement_timeseries(datacenter, device_type, measurement):
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
    with database.session() as session:
        device_type_metadata = timeseries.get_datacenter_device_type_metadata(
            session, datacenter, device_type
        )
    assert measurement in device_type_metadata
    measurement_metadata = device_type_metadata[measurement]
    for device in data:
        assert device in measurement_metadata['devices']
    status = timeseries.create_measurement_timeseries(
        measurement, data, measurement_metadata['attribute']['type'],
        tags, time_precision
    )
    if not status:
        raise exception_handler.NotAcceptable(
            'Invalid data for device_type %s measurement %s' % (
                device_type, measurement
            )
        )
    return utils.make_json_response(
        200, {'status': True}
    )


@app.route(
    "/timeseries/<datacenter>/<device_type>/<measurement>/<device>",
    methods=['POST']
)
def create_device_timeseries(datacenter, device_type, measurement, device):
    data = _get_request_data()
    logger.debug(
        'timeseries data for %s %s %s %s: %s',
        datacenter, device_type, measurement, device, data
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
    with database.session() as session:
        device_type_metadata = timeseries.get_datacenter_device_type_metadata(
            session, datacenter, device_type
        )
    assert measurement in device_type_metadata
    measurement_metadata = device_type_metadata[measurement]
    assert device in measurement_metadata['devices']
    status = timeseries.create_device_timeseries(
        measurement, data, measurement_metadata['attribute']['type'],
        tags, time_precision
    )
    if not status:
        raise exception_handler.NotAcceptable(
            'Invalid data for device_type %s measurement %s device %s' % (
                device_type, measurement, device
            )
        )
    return utils.make_json_response(
        200, {'status': True}
    )


@app.route(
    "/timeseries/<datacenter>/<device_type>",
    methods=['DELETE']
)
def delete_device_type_timeseries(
        datacenter, device_type
):
    with database.session() as session:
        device_type_metadata = timeseries.get_datacenter_device_type_metadata(
            session, datacenter, device_type
        )
    with database.influx_session() as session:
        for measurement, measurement_metadata in six.iteritems(
            device_type_metadata
        ):
            timeseries.delete_timeseries(
                session, measurement, {
                    'datacenter': datacenter,
                    'device_type': device_type
                }
            )
    return utils.make_json_response(
        200, {'status': True}
    )


@app.route(
    "/timeseries/<datacenter>/<device_type>/<measurement>",
    methods=['DELETE']
)
def delete_measurement_timeseries(datacenter, device_type, measurement):
    with database.session() as session:
        device_type_metadata = timeseries.get_datacenter_device_type_metadata(
            session, datacenter, device_type
        )
    if measurement not in device_type_metadata:
        raise exception_handler.ItemNotFound(
            'measurement %s does not found '
            'in datacenter %s device type %s' % (
                measurement, datacenter, device_type
            )
        )
    with database.influx_session() as session:
        timeseries.delete_timeseries(
            session, measurement, {
                'datacenter': datacenter,
                'device_type': device_type
            }
        )
    return utils.make_json_response(
        200, {'status': True}
    )


@app.route(
    "/timeseries/<datacenter>/<device_type>/<device>/<measurement>",
    methods=['DELETE']
)
def delete_device_timeseries(datacenter, device_type, device, measurement):
    with database.session() as session:
        device_type_metadata = timeseries.get_datacenter_device_type_metadata(
            session, datacenter, device_type
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
    with database.influx_session() as session:
        timeseries.delete_timeseries(
            session, measurement, {
                'datacenter': datacenter,
                'device_type': device_type,
                'device': device
            }
        )
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
    starttime = timeseries.get_timestamp(data.get('starttime'))
    endtime = timeseries.get_timestamp(data.get('endtime'))
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
    starttime = timeseries.get_timestamp(data.get('starttime'))
    endtime = timeseries.get_timestamp(data.get('endtime'))
    test_data = data.get('data')
    logger.debug(
        'test model params: starttime=%s, endtime=%s data=%s',
        starttime, endtime, test_data
    )
    if not test_data:
        assert starttime is not None
        assert endtime is not None
    test_result = _create_test_result(datacenter_name)
    logger.debug(
        'datacenter %s model type %s test result: %s',
        datacenter_name, model_type, test_result
    )
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
        200, {'status': True, 'test_result': test_result}
    )


@app.route("/models/<datacenter_name>/<model_type>/apply", methods=['POST'])
def apply_model(datacenter_name, model_type):
    data = _get_request_data()
    starttime = timeseries.get_timestamp(data.get('starttime'))
    endtime = timeseries.get_timestamp(data.get('endtime'))
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
        200, {'status': True, 'prediction': prediction}
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
