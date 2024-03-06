"""
Run Fossa in a productions environment.
"""

import os

import gunicorn.app.base

from fossa.app import single_config_initialise


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


def run_fossa(deployment_config):
    """
    Run Fossa through gunicorn.

    @param deployment_config: (str or class or anything accepted by Flask's `app.config.from_object`)
        Used to choose the settings file. i.e. 'prod' uses .....settings.prod_config.Config
    """
    app = single_config_initialise(deployment_config)

    options = {
        "bind": "%s:%s" % ("0.0.0.0", app.config["HTTP_PORT"]),
        "workers": 4,
        "syslog": True,
        "timeout": 80,
    }

    StandaloneApplication(app, options).run()


if __name__ == "__main__":
    deployment_label = os.environ["DEPLOYMENT_ENVIRONMENT"]
    config_package = f"fossa.settings.{deployment_label}_config.Config"
    run_fossa(config_package)
