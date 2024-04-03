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

    @param settings_class: (str) or Config class or (dict)
        to settings. See Flask docs.

    @param governor: (:class:`` obj) - The Governor connects the web frontend; message brokers and
        task execution. It runs it's own :class:`multiprocessing.Process`es, and sets up shared
        memory.

    @return: Flask
        The flask app for Fossa
    """
    app = Flask(__name__)

    if isinstance(settings_class, dict):
        app.config.from_mapping(settings_class)
    else:
        app.config.from_object(settings_class)

    app.fossa_governor = governor

    app.register_error_handler(JsonException, handle_json_exception)
    app.register_error_handler(Exception, handle_json_exception)
    app.register_error_handler(500, handle_json_exception)

    app.register_blueprint(api_views, url_prefix=api_base_url)
    app.register_blueprint(web_views, url_prefix="/")

    return app


def single_config_initialise(flask_config):
    """
    A convenient layout is for Fossa and Flask settings to stored in a single shared python class.

    There is a connection between the :class:`Governor` and Flask which must be setup correctly in
    order for the governor and flask requests to communicate. There are a number of ways to achieve
    this including this simple function that is used by the gunicorn runner and local (developer's)
    run mode.

    @param flask_config: (anything accepted by Flask's `app.config.from_object`)
    @return: Flask app
    """
    governor = Governor()
    app = create_app(flask_config, governor)

    governor.log_to_stdout = app.config["LOG_TO_STDOUT"]

    for logger in app.config.get("EXTERNAL_LOGGERS", []):
        governor.attach_external_logger(logger)

    for model_cls in app.config["ACCEPTED_MODEL_CLASSES"]:
        governor.set_accepted_class(model_cls)

    isolated_processor = app.config.get("ISOLATED_PROCESSOR")
    if isolated_processor:
        governor.isolated_processor = isolated_processor

    for callable_manager in app.config.get("MESSAGE_BROKER_MANAGERS"):
        governor.attach_sidecar(callable_manager)

    governor.start_internal_processes()

    return app


def run_local_app():
    """
    Run app locally just for development, don't use this in production.
    """
    import warnings

    settings = "fossa.settings.local_config.Config"
    app = single_config_initialise(settings)

    if app.config["DEBUG"]:
        msg = (
            "In DEBUG mode, the flask internal web server runs this module twice. This will "
            "result in two governor processes and a load of confusion."
        )
        warnings.warn(msg)

    app.run(
        debug=app.config["DEBUG"],
        host="0.0.0.0",
        port=app.config["HTTP_PORT"],
    )


if __name__ == "__main__":
    run_local_app()
