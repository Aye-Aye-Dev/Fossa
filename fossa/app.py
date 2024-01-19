"""
Web app for API and html views of Fossa
"""
from flask import Flask

from fossa.utils import JsonException, handle_json_exception
from fossa.views.api import api_views
from fossa.views.web import web_views

api_base_url = "/api/0.01/"


def create_app(settings_class):
    """
    Create a Flask app that can be run as a server

    @param settings_class: (str) or Config class
        to settings. See Flask docs.

    @return: Flask
        The flask app for Fossa
    """
    app = Flask(__name__)
    app.config.from_object(settings_class)

    app.register_error_handler(JsonException, handle_json_exception)
    app.register_error_handler(Exception, handle_json_exception)
    app.register_error_handler(500, handle_json_exception)

    app.register_blueprint(api_views, url_prefix=api_base_url)
    app.register_blueprint(web_views, url_prefix="/")

    return app


def run_app():
    """
    Local run for developers, don't use this in production.
    """
    app = create_app("fossa.settings.local_config.Config")
    app.run(
        debug=app.config["DEBUG"],
        host="0.0.0.0",
        port=2345,
    )


if __name__ == "__main__":
    run_app()
