"""Utils for API usage."""
import logging
import mimetypes
import os.path

from flask import make_response
import simplejson as json


logger = logging.getLogger(__name__)


def make_json_response(status_code, data):
    """Wrap json format to the reponse object."""

    result = json.dumps(
        data, ensure_ascii=False, indent=4
    ).encode('utf-8') + '\r\n'
    resp = make_response(result, status_code)
    resp.headers['Content-type'] = 'application/json;charset=utf-8'
    return resp


def make_csv_response(status_code, csv_data, fname):
    """Wrap CSV format to the reponse object."""
    fname = '.'.join((fname, 'csv'))
    resp = make_response(csv_data, status_code)
    resp.mimetype = 'text/csv'
    resp.headers['Content-Disposition'] = 'attachment; filename="%s"' % fname
    return resp


def make_file_response(status_code, pathname):
    filename = os.path.basename(pathname)
    mime_type, encoding = mimetypes.guess_type(filename)
    with open(pathname) as resp_file:
        resp = make_response(resp_file.read(), status_code)
    if mime_type:
        resp.mimetype = mime_type
    if encoding:
        resp.headers['Content-Encoding'] = encoding
    return resp
