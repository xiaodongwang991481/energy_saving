"""Custom exception"""
import functools
import traceback


class DatabaseException(Exception):
    """Base class for all database exceptions."""
    def __init__(self, message):
        super(DatabaseException, self).__init__(message)
        self.traceback = traceback.format_exc()
        self.status_code = 400

    def to_dict(self):
        return {'message': str(self)}


class RecordNotExists(DatabaseException):
    """Define the exception for referring non-existing object in DB."""
    def __init__(self, message):
        super(RecordNotExists, self).__init__(message)
        self.status_code = 404


class DuplicatedRecord(DatabaseException):
    """Define the exception for trying to insert an existing object in DB."""
    def __init__(self, message):
        super(DuplicatedRecord, self).__init__(message)
        self.status_code = 409


class Unauthorized(DatabaseException):
    """Define the exception for invalid user login."""
    def __init__(self, message):
        super(Unauthorized, self).__init__(message)
        self.status_code = 401


class UserDisabled(DatabaseException):
    """Define the exception that a disabled user tries to do some operations.

    """
    def __init__(self, message):
        super(UserDisabled, self).__init__(message)
        self.status_code = 403


class Forbidden(DatabaseException):
    """Define the exception that a user is trying to make some action

    without the right permission.

    """
    def __init__(self, message):
        super(Forbidden, self).__init__(message)
        self.status_code = 403


class NotAcceptable(DatabaseException):
    """The data is not acceptable."""
    def __init__(self, message):
        super(NotAcceptable, self).__init__(message)
        self.status_code = 406


class InvalidParameter(DatabaseException):
    """Define the exception that the request has invalid or missing parameters.

    """
    def __init__(self, message):
        super(InvalidParameter, self).__init__(message)
        self.status_code = 400


class InvalidResponse(DatabaseException):
    """Define the exception that the response is invalid.

    """
    def __init__(self, message):
        super(InvalidResponse, self).__init__(message)
        self.status_code = 400


class MultiDatabaseException(DatabaseException):
    """Define the exception composites with multi exceptions."""
    def __init__(self, exceptions):
        super(MultiDatabaseException, self).__init__('multi exceptions')
        self.exceptions = exceptions
        self.status_code = 400

    @property
    def traceback(self):
        tracebacks = []
        for exception in self.exceptions:
            tracebacks.append(exception.trackback)

    def to_dict(self):
        dict_info = super(MultiDatabaseException, self).to_dict()
        dict_info.update({
            'exceptions': [
                exception.to_dict() for exception in self.exceptions
            ]
        })
        return dict_info


def raise_exception(exception_class, message='unknown exception'):
    raise exception_class(message)


def raise_exception_callback(exception_class, message='unknown exception'):
    return functools.partial(raise_exception, exception_class, message)
