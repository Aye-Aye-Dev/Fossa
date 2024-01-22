"""
Run Fossa in a productions environment.
"""

import os

import gunicorn.app.base

from fossa.app import create_app
from fossa.control.governor import Governor


class StandaloneApplication(gunicorn.app.base.BaseApplication):
    """
    Run a WSGI web-app using gunicorn.
    """

    def __init__(self, app, options=None):
        self.options = options or {}
        self.application = app
        super().__init__()

    def load_config(self):
        config = {
            key: value
            for key, value in self.options.items()
            if key in self.cfg.settings and value is not None
        }
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def load(self):
        return self.application


def run_forever(deployment_label):
    """
    Run Fossa through gunicorn.

    @param deployment_label: (str)
        Used to choose the settings file. i.e. 'prod' uses .....settings.prod_config.Config
    """
    config_package = f"fossa.settings.{deployment_label}_config.Config"

    governor = Governor()
    governor.start_internal_process()

    app = create_app(config_package, governor)

    options = {
        "bind": "%s:%s" % ("0.0.0.0", app.config["HTTP_PORT"]),
        "workers": 4,
        "syslog": True,
        "timeout": 80,
    }

    StandaloneApplication(app, options).run()


if __name__ == "__main__":
    deployment_label = os.environ["DEPLOYMENT_ENVIRONMENT"]
    run_forever(deployment_label)