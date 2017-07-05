"""Define all the RestfulAPI entry points."""
import logging
import simplejson as json
import six

from oslo_config import cfg

from flask import request

from energy_saving.api import admin_api
from energy_saving.api import app
from energy_saving.api import exception_handler
from energy_saving.api import utils
from energy_saving.db import database
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


@app.route("/timeseries/<measurement>", methods=['GET'])
def list_timeseries(measurement):
    data = _get_request_args()
    logger.debug('timeseries data: %s', data)
    response = {}
    query = data.pop('query', None)
    where = data.pop('where', None)
    group_by = data.pop('group_by', None)
    time_precision = data.pop('time_precision', None)
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
        query = 'select * from %s%s%s' % (
            measurement, where_clause, group_by_clause
        )
    logger.debug('timeseries %s query: %s', measurement, query)
    with database.influx_session() as session:
        result = session.query(query, epoch=time_precision)
        response = list(result.get_points())
    logger.debug('timeseries %s response: %s', measurement, response)
    return utils.make_json_response(
        200, response
    )


@app.route("/timeseries/<measurement>", methods=['POST'])
def create_timeseries(measurement):
    data = _get_request_data()
    logger.debug('timeseries data for %s: %s', measurement, data)
    points = []
    tags = data.pop('tags', {})
    time_precision = data.pop('time_precision', None)
    timeseries = {}
    for key, value in six.iteritems(data):
        for timestamp, item in six.iteritems(value):
            timeseries.setdefault(timestamp, {})[key] = item
    for timestamp, items in six.iteritems(timeseries):
        if time_precision:
            timestamp = long(timestamp)
        points.append({
            'measurement': measurement,
            'time': timestamp,
            'fields': items
        })
    logger.debug('timeseries %s points: %s', measurement, points)
    logger.debug('timeseries %s tags: %s', measurement, tags)
    status = False
    with database.influx_session() as session:
        status = session.write_points(
            points, time_precision=time_precision, tags=tags
        )
    logger.debug('timeseries %s status: %s', measurement, status)
    if status:
        return utils.make_json_response(
            200, {'status': status}
        )
    else:
        raise exception_handler.NotAcceptable(
            'timeseries %s data not acceptable' % measurement
        )


@app.route("/timeseries/<measurement>", methods=['DELETE'])
def delete_timeseries(measurement):
    data = _get_request_data()
    logger.debug('timeseries data for %s: %s', measurement, data)
    with database.influx_session() as session:
        session.delete_series(measurement=measurement, tags=data)
    return utils.make_json_response(
        200, {'status': True}
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
