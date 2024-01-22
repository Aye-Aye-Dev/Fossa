"""
Web app for API and html views of Fossa
"""
from flask import Flask

from fossa.control.governor import Governor
from fossa.utils import JsonException, handle_json_exception
from fossa.views.api import api_views
from fossa.views.web import web_views

api_base_url = "/api/0.01/"


def create_app(settings_class, governor):
    """
    Create a Flask app that can be run as a server

    @param settings_class: (str) or Config class
        to settings. See Flask docs.

    @param governor: (:class:`` obj) - The Governor connects the web frontend; message brokers and
        task execution. It runs it's own :class:`multiprocessing.Process`es, and sets up shared
        memory.

    @return: Flask
        The flask app for Fossa
    """
    app = Flask(__name__)
    app.config.from_object(settings_class)

    app.fossa_governor = governor

    app.register_error_handler(JsonException, handle_json_exception)
    app.register_error_handler(Exception, handle_json_exception)
    app.register_error_handler(500, handle_json_exception)

    app.register_blueprint(api_views, url_prefix=api_base_url)
    app.register_blueprint(web_views, url_prefix="/")

    return app


def run_local_app():
    """
    Run app locally just for development, don't use this in production.
    """
    governor = Governor()
    governor.start_internal_process()

    settings = "fossa.settings.local_config.Config"
    app = create_app(settings, governor)
    app.run(
        debug=app.config["DEBUG"],
        host="0.0.0.0",
        port=app.config["HTTP_PORT"],
    )


if __name__ == "__main__":
    run_local_app()
