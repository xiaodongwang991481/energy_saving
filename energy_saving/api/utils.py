"""Utils for API usage."""
import logging
import mimetypes
import os.path

from flask import make_response
from flask import render_template
import simplejson as json


logger = logging.getLogger(__name__)


def make_json_response(status_code, data, **kwags):
    """Wrap json format to the reponse object."""

    result = json.dumps(
        data, ensure_ascii=False, indent=4, encoding='utf-8'
    ) + '\r\n'
    resp = make_response(result, status_code)
    resp.headers['Content-type'] = 'application/json;charset=utf-8'
    return resp


def make_text_response(status_code, data, **kwargs):
    """Text to the reponse object."""
    resp = make_response(data, status_code)
    resp.headers['Content-type'] = 'text/plain;charset=utf-8'
    return resp


def make_csv_response(status_code, csv_data, fname=None, **kwargs):
    """Wrap CSV format to the reponse object."""
    if not fname:
        fname = 'download.csv'
    if not fname.endswith('.csv'):
        fname = '.'.join((fname, 'csv'))
    resp = make_response(csv_data, status_code)
    resp.mimetype = 'text/csv'
    resp.headers['Content-Disposition'] = 'attachment; filename="%s"' % fname
    return resp


def make_file_response(status_code, pathname, **kwargs):
    filename = os.path.basename(pathname)
    mime_type, encoding = mimetypes.guess_type(filename)
    with open(pathname) as resp_file:
        resp = make_response(resp_file.read(), status_code)
    if mime_type:
        resp.mimetype = mime_type
    if encoding:
        resp.headers['Content-Encoding'] = encoding
    return resp


def make_template_response(status_code, data, template_path, **kwargs):
    rv = render_template(template_path, data=data)
    logger.debug('make_template_response %s rv: %s', template_path, rv)
    resp = make_response(
        rv, status_code
    )
    return resp


RESPONSE_RENDER_BY_TYPE = {
    'json': make_json_response,
    'plain': make_text_response,
    'csv': make_csv_response,
    'static': make_file_response,
    'template': make_template_response
}


def make_response_by_type(status_code, data, response_type, **kwargs):
    return RESPONSE_RENDER_BY_TYPE[response_type](
        status_code, data, **kwargs
    )
