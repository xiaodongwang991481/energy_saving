"""Define all the RestfulAPI entry points."""
import csv
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


def _get_request_args(**kwargs):
    """Get request args as dict.

    The value in the dict is converted to expected type.
    Args:
       kwargs: for each key, the value is the type converter.
    """
    args = request.args.to_dict(flat=False)
    for key, value in args.items():
        if key in kwargs:
            converter = kwargs[key]
            if isinstance(value, list):
                args[key] = [converter(item) for item in value]
            else:
                args[key] = converter(value)
        if isinstance(args[key], list):
            if len(args[key]) == 1:
                args[key] = args[key][0]
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
    models = {}
    with database.session() as session:
        datacenters = session.query(models.Datacenter)
        for datacenter in datacenters:
            models[datacenter.name] = {
                'sensor_attribute': {},
                'controller_attribute': {},
                'controller_parameter': {},
                'power_supply_attribute': {},
                'controller_power_supply_attribute': {},
                'environment_sensor_attribute': {}
            }
            attributes = models[datacenter.name]['sensor_attribute']
            for attribute in datacenter.sensor_attibutes:
                attributes[attribute.name] = []
                attribute_data = attributes[
                    attribute.name
                ]
                for data in attribute.attribute_data:
                    attribute_data.append(data.sensor_name)
            attributes = models[datacenter.name][
                'environment_sensor_attribute'
            ]
            for attribute in (
                datacenter.environment_sensor_attributes
            ):
                attributes[attribute.name] = []
                attribute_data = attributes[
                    attribute.name
                ]
                for data in attribute.attribute_data:
                    attribute_data.append(data.environment_sensor_name)
            attributes = models[datacenter.name][
                'controller_attribute'
            ]
            for attribute in (
                datacenter.controller_attributes
            ):
                attributes[attribute.name] = []
                attribute_data = attributes[
                    attribute.name
                ]
                for data in attribute.attribute_data:
                    attribute_data.append(data.controller_name)
            attributes = models[datacenter.name][
                'controller_parameter'
            ]
            for attribute in (
                datacenter.controller_parameters
            ):
                attributes[attribute.name] = []
                attribute_data = attributes[
                    attribute.name
                ]
                for data in attribute.parameter_data:
                    attribute_data.append(data.controller_name)
            attributes = models[datacenter.name][
                'power_supply_attribute'
            ]
            for attribute in (
                datacenter.power_supply_attributes
            ):
                attributes[attribute.name] = []
                attribute_data = attributes[
                    attribute.name
                ]
                for data in attribute.parameter_data:
                    attribute_data.append(data.power_supply_name)
            attributes = models[datacenter.name][
                'controller_power_supply_attribute'
            ]
            for attribute in (
                datacenter.controller_power_supply_attributes
            ):
                attributes[attribute.name] = []
                attribute_data = attributes[
                    attribute.name
                ]
                for data in attribute.parameter_data:
                    attribute_data.append(data.controller_power_supply_name)
    return utils.make_json_response(
        200, models
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
                data.append(dict(zip(fields, row)))
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


def _list_timeseries(measurement, data):
    logger.debug('timeseries data: %s', data)
    response = {}
    query = data.pop('query', None)
    where = data.pop('where', None)
    group_by = data.pop('group_by', None)
    order_by = data.pop('order_by', None)
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
        if group_by:
            group_by_clause = ' group by %s' % group_by
        else:
            group_by_clause = ''
        if order_by:
            order_by_clause = 'order by %s' % order_by
        else:
            order_by_clause = ''
        query = 'select * from %s%s%s%s' % (
            measurement, where_clause, group_by_clause, order_by_clause
        )
    logger.debug('timeseries %s query: %s', measurement, query)
    response = []
    with database.influx_session() as session:
        result = session.query(query, epoch=time_precision)
        response = list(result.get_points())
    logger.debug('timeseries %s response: %s', measurement, response)
    return utils.make_json_response(
        200, response
    )


@app.route("/timeseries", methods=['GET'])
def list_all_timeseries():
    data = _get_request_args()
    return _list_timeseries('/.*/', data)


@app.route("/timeseries/<measurement>", methods=['GET'])
def list_timeseries(measurement):
    data = _get_request_args()
    return _list_timeseries(measurement, data)


@app.route("/timeseries/<datacenter>/<measurement>", methods=['GET'])
def list_datacenter_timeseries(datacenter, measurement):
    data = _get_request_args()
    data.update({
        'datacenter': datacenter
    })
    return _list_timeseries(measurement, data)


@app.route(
    "/timeseries/<datacenter>/<device_type>/<measurement>",
    methods=['GET']
)
def list_device_type_timeseries(datacenter, device_type, measurement):
    data = _get_request_args()
    data.update({
        'datacenter': datacenter,
        'device_type': device_type
    })
    return _list_timeseries(measurement, data)


@app.route(
    "/timeseries/<datacenter>/<device_type>/<device>/<measurement>",
    methods=['GET']
)
def list_device_timeseries(datacenter, device_type, device, measurement):
    data = _get_request_args()
    data.update({
        'datacenter': datacenter,
        'device_type': device_type,
        'device': device
    })
    return _list_timeseries(measurement, data)


@app.route(
    "/export/timeseries/<datacenter>/<device_type>/<measurement>",
    methods=['GET']
)
def export_timeseries(datacenter, device_type, measurement):
    logger.debug(
        'download timeseries datacenter=%s %s %s',
        datacenter, device_type, measurement
    )
    query = (
        "select value, device from %s where datacenter='%s' "
        "and device_type='%s' order by time"
    ) % (
        measurement, datacenter, device_type
    )
    logger.debug('timeseries %s query: %s', measurement, query)
    response = []
    with database.influx_session() as session:
        result = session.query(query, epoch=settings.DEFAULT_TIME_PRECISION)
        response = list(result.get_points())
    logger.debug('influx query response: %s', response)
    data_by_device = {}
    devices = set()
    for item in response:
        device = item['device']
        timestamp = item['time']
        value = item['value']
        devices.add(device)
        device_data = data_by_device.setdefault(timestamp, {})
        device_data[device] = value
    devices = list(devices)
    devices = sorted(devices)
    data_by_timestamp = {}
    for timestamp, device_data in six.iteritems(data_by_device):
        timestamp_data = []
        for device in devices:
            timestamp_data.append(device_data.get(device, ''))
        data_by_timestamp[timestamp] = timestamp_data
    timestamps = data_by_device.keys()
    if settings.DEFAULT_TIME_PRECISION:
        timestamps = sorted(timestamps)
    else:
        timestamps = sorted(
            timestamps, key=lambda timestamp: parser.parse(timestamp)
        )
    data = []
    data.append(['time'] + devices)
    for timestamp in timestamps:
        data.append([timestamp] + data_by_timestamp[timestamp])
    string_buffer = StringIO.StringIO()
    writer = csv.writer(string_buffer)
    writer.writerows(data)
    return utils.make_csv_response(
        200, string_buffer.getvalue(),
        '%s-%s-%s.csv' % (measurement, datacenter, device_type)
    )


def _write_points(
    session, measurement, device_data, tags={}, time_precision=None
):
    points = []
    for timestamp, value in six.iteritems(device_data):
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


def generate_timeseries(data, tags):
    generated_tags = dict(tags)
    for datacenter, datacenter_data in six.iteritems(data):
        for device_type, device_type_data in six.iteritems(datacenter_data):
            for device, device_data in six.iteritems(device_type_data):
                generated_tags.update({
                    'datacenter': datacenter,
                    'device_type': device_type,
                    'device': device
                })
                yield device_data, generated_tags


def generate_datacenter_timeseries(data, tags):
    generated_tags = dict(tags)
    for device_type, device_type_data in six.iteritems(data):
        for device, device_data in six.iteritems(device_type_data):
            generated_tags.update({
                'device_type': device_type,
                'device': device
            })
            yield device_data, generated_tags


def generate_device_type_timeseries(data, tags):
    generated_tags = dict(tags)
    for device, device_data in six.iteritems(data):
        generated_tags.update({
            'device': device
        })
        yield device_data, generated_tags


def generate_device_timeseries(data, tags):
    generated_tags = dict(tags)
    yield data, generated_tags


def _create_timeseries(
    measurement, data,
    timeseries_generator, tags={}, time_precision=None
):
    status = True
    with database.influx_session() as session:
        for device_data, generated_tags in timeseries_generator(data, tags):
            status = all([
                status,
                _write_points(
                    session, measurement, device_data,
                    generated_tags, time_precision
                )
            ])
    logger.debug('timeseries %s status: %s', measurement, status)
    if status:
        return utils.make_json_response(
            200, {'status': status}
        )
    else:
        raise exception_handler.NotAcceptable(
            'timeseries %s data not acceptable' % measurement
        )


@app.route("/timeseries/<measurement>", methods=['POST'])
def create_timeseries(measurement):
    data = _get_request_data()
    logger.debug('timeseries data for %s: %s', measurement, data)
    time_precision = data.pop(
        'time_precision', settings.DEFAULT_TIME_PRECISION
    )
    tags = data.pop('tags', {})
    return _create_timeseries(
        measurement, data, generate_timeseries, tags, time_precision
    )


TYPE_CONVERTERS = [(
    re.compile(r'^true|false|True|False$'), bool
), (
    re.compile(r'^[+-]?\d+$'), long
), (
    re.compile(r'^[+-]?\d+(.\d+)?([e|E][+-]?\d+)$'), float
)]


def _convert_timeseries_value(value):
    for pattern, converter in TYPE_CONVERTERS:
        if pattern.match(value):
            return converter(value)
    return value


@app.route(
    "/import/timeseries/<datacenter>/<device_type>/<measurement>",
    methods=['POST']
)
def import_timeseries(datacenter, device_type, measurement):
    logger.debug(
        'upload timeseries datacenter=%s %s %s',
        datacenter, device_type, measurement
    )
    data_by_device = {}
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
                fields = row[1:]
                for field in fields:
                    data_by_device.setdefault(field, {})
            else:
                timestamp = row[0]
                row = row[1:]
                data = dict(zip(fields, row))
                for field, value in six.iteritems(data):
                    if value:
                        data_by_device[
                            field
                        ][timestamp] = _convert_timeseries_value(
                            value
                        )
    status = True
    with database.influx_session() as session:
        for device, device_data in six.iteritems(data_by_device):
            tags = {
                'datacenter': datacenter,
                'device_type': device_type,
                'device':  device
            }
            status = all([
                status,
                _write_points(
                    session, measurement, device_data, tags,
                    settings.DEFAULT_TIME_PRECISION
                )
            ])
    if status:
        return utils.make_json_response(
            200, {'status': status}
        )
    else:
        raise exception_handler.NotAcceptable(
            'timeseries %s csv file does not acceptable' % measurement
        )


@app.route("/timeseries/<datacenter>/<measurement>", methods=['POST'])
def create_datacenter_timeseries(datacenter, measurement):
    data = _get_request_data()
    logger.debug('timeseries data for %s: %s', measurement, data)
    time_precision = data.pop(
        'time_precision', settings.DEFAULT_TIME_PRECISION
    )
    tags = data.pop('tags', {})
    tags.update({'datacenter': datacenter})
    return _create_timeseries(
        measurement, data, generate_datacenter_timeseries,
        tags, time_precision
    )


@app.route(
    "/timeseries/<datacenter>/<device_type>/<measurement>",
    methods=['POST']
)
def create_device_type_timeseries(datacenter, device_type, measurement):
    data = _get_request_data()
    logger.debug('timeseries data for %s: %s', measurement, data)
    time_precision = data.pop(
        'time_precision', settings.DEFAULT_TIME_PRECISION
    )
    tags = data.pop('tags', {})
    tags.update({
        'datacenter': datacenter,
        'device_type': device_type
    })
    return _create_timeseries(
        measurement, data, generate_device_type_timeseries,
        tags, time_precision
    )


@app.route(
    "/timeseries/<datacenter>/<device_type>/<device>/<measurement>",
    methods=['POST']
)
def create_device_timeseries(datacenter, device_type, device, measurement):
    data = _get_request_data()
    logger.debug('timeseries data for %s: %s', measurement, data)
    time_precision = data.pop(
        'time_precision', settings.DEFAULT_TIME_PRECISION
    )
    tags = data.pop('tags', {})
    tags.update({
        'datacenter': datacenter,
        'device_type': device_type,
        'device': device
    })
    return _create_timeseries(
        measurement, data, generate_device_timeseries, tags, time_precision
    )


def _delete_timeseries(measurement, tags):
    logger.debug('timeseries data for %s: %s', measurement, tags)
    with database.influx_session() as session:
        session.delete_series(measurement=measurement, tags=tags)
    return utils.make_json_response(
        200, {'status': True}
    )


@app.route("/timeseries/<measurement>", methods=['DELETE'])
def delete_timeseries(measurement):
    data = _get_request_data()
    return _delete_timeseries(measurement, data)


@app.route("/timeseries/<datacenter>/<measurement>", methods=['DELETE'])
def delete_datacenter_timeseries(datacenter, measurement):
    data = _get_request_data()
    data.update({'datacenter': datacenter})
    return _delete_timeseries(measurement, data)


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
    return _delete_timeseries(measurement, data)


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
    return _delete_timeseries(measurement, data)


@app.route("/", methods=['GET'])
def index():
    return utils.make_template_response(200, {}, 'index.html')


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
    try:
        celery_client.celery.send_task(
            'energy_saving.tasks.apply_model', (
                datacenter, model_type
            )
        )
    except Exception as error:
        logging.exception(error)
        raise exception_handler.Forbidden(
            'failed to send apply_model to celery'
        )
    return utils.make_json_response(
        200, {}
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
