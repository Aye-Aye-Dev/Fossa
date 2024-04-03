"""
Run Fossa in a productions environment.
"""
import atexit
from multiprocessing.util import _exit_function
import os
import signal

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


def disable_worker_atexit(worker):
    """
    Disable multiprocessing's atexit hook for gunicorn request handling workers.

    This is needed because there are non-gunicorn Processes that are children of
    the main gunicorn process.

    When a gunicorn worker terminates the atexist registered function is called and that inspects
    the non-gunicorn processes. The gunicorn workers don't need further cleaning up.

    Should be called within the worker process after it has started running.
    """
    atexit.register(_exit_function)
    atexit.unregister(_exit_function)
    worker.log.info(f"worker post_worker_init done, (pid: {worker.pid})")


def run_fossa(deployment_config):
    """
    Run Fossa through gunicorn.

    @param deployment_config: (str or class or anything accepted by Flask's `app.config.from_object`)
        Used to choose the settings file. i.e. 'prod' uses .....settings.prod_config.Config
    """
    app = single_config_initialise(deployment_config)

    def stop_governor(_signum, _frame):
        """
        Use a signal to shutdown the governor before gunicorn's shutdown.

        Gunicorn's "on_exit" runs after workers are shutdown.

        Using this signal as it's simpler not to use a signal the gunicor already uses.
        See https://docs.gunicorn.org/en/stable/signals.html

        signal.SIGABRT
        Abort signal from abort(3).
        """
        app.fossa_governor.shutdown(None)

    signal.signal(signal.SIGABRT, stop_governor)

    options = {
        "bind": "%s:%s" % ("0.0.0.0", app.config["HTTP_PORT"]),
        "workers": 4,
        "syslog": True,
        "timeout": 80,
        # "post_worker_init": disable_worker_atexit, # this isn't working
        # "capture_output": True,
        "on_exit": app.fossa_governor.shutdown,
    }

    StandaloneApplication(app, options).run()


if __name__ == "__main__":
    deployment_label = os.environ["DEPLOYMENT_ENVIRONMENT"]
    config_package = f"fossa.settings.{deployment_label}_config.Config"
    run_fossa(config_package)
