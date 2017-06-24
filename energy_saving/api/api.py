"""Define all the RestfulAPI entry points."""
import datetime
import functools
import logging
import os
import os.path
import re
import requests
import simplejson as json
import six
import threading
import time

from oslo_config import cfg

from flask import request

from energy_saving.api import app
from energy_saving.api import exception_handler
from energy_saving.api import utils
from energy_saving.models import database
from energy_saving.tasks import client as celery_client
from energy_saving.utils import logsetting
from energy_saving.utils import settings
from energy_saving.utils import util


opts = [
    cfg.StrOpt('logfile',
               help='log file name',
               default=settings.WEB_LOGFILE)
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


def _wrap_response(func, response_code):
    """wrap function response to json formatted http response."""
    def wrapped_func(*args, **kwargs):
        return utils.make_json_response(
            response_code,
            func(*args, **kwargs)
        )
    return wrapped_func


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


def _parse_content_range(content_range, received_ranges=[], size=None):
    pat = re.compile(r'^(?:bytes\s+)?([0-9]+)-([0-9]+)/([0-9]+)$')
    mat = pat.match(content_range)
    if not mat:
        raise exception_handler.BadRequest(
            'invalid content-range header %s' % content_range
        )
    start = int(mat.group(1))
    end = int(mat.group(2))
    total = int(mat.group(3))
    if total == 0:
        raise exception_handler.BadRequest(
            'invalid content-range header %s, total is %s' % (
                content_range, total
            )
        )
    if start > end:
        raise exception_handler.BadRequest(
            'invalid content-range header %s: '
            'start %s is greater than end %s' % (
                content_range, start, end
            )
        )
    if end >= total:
        raise exception_handler.BadRequest(
            'invalid content-range header %s: '
            'end %s is not less than total %s' % (
                content_range, end, total
            )
        )
    if received_ranges:
        assert(size is not None)
        if size != total:
            raise exception_handler.BadRequest(
                'invalid content-range header %s: '
                'total is not equal to the expected size %s' % (
                    content_range, total, size
                )
            )
        last_end = received_ranges[-1][1]
        if last_end + 1 != start:
            raise exception_handler.BadRequest(
                'invalid content-range header %s: '
                'start %s is not continuous to previous end %s' % (
                    content_range, start, last_end
                )
            )
    else:
        if start != 0:
            raise exception_handler.BadRequest(
                'invalid content-range header %s: '
                'invalid start %s for the first package' % (
                    content_range, start
                )
            )
    return start, end, total


def init():
    logsetting.init(CONF.logfile)
    database.init()


if __name__ == '__main__':
    init()
    app.run(host='0.0.0.0')
