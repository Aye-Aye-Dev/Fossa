from flask import current_app, jsonify
from werkzeug.exceptions import HTTPException


class JsonException(Exception):
    """
    An exception that can be used over streams that accept Json
    """

    status_code = 400

    def __init__(self, message, status_code=None, system_message=None):
        """
        Constructor

        @param status_code: integer
            The status code of the exception
        @param system_message: string
            The message describing the error
        """
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code

        if self.status_code >= 500:
            current_app.logger.error(message)

        if self.status_code >= 400 and self.status_code != 404:
            if system_message:
                current_app.logger.warning("Client error: " + system_message)
            else:
                current_app.logger.warning("Client error: " + message)

    def to_dict(self):
        """
        Close enough to Google Errors.
        """
        return_value = {"error": {"message": self.message}}
        return return_value


def handle_json_exception(error):
    """
    Process a given Json exception

    @param error: JsonException
        The error to process

    @return: string, integer (optional)
        A json string of the error with an option error code of the message
    """
    if hasattr(error, "to_dict") and hasattr(error, "status_code"):
        response = jsonify(error.to_dict())
        response.status_code = error.status_code
        return response
    if hasattr(error, "message"):
        response = jsonify({"msg": error.message})
        return response, 500

    if isinstance(error, HTTPException):
        response = jsonify({"msg": error.name})
        return response, error.code

    current_app.logger.exception(str(error))
    response = jsonify({"msg": "Unknown error"})
    return response, 500
