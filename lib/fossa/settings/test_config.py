from fossa.settings.global_config import BaseConfig


class Config(BaseConfig):
    """
    A configuration for unittests
    """

    APP_TITLE = BaseConfig.APP_TITLE + " Test"
    DEBUG = True
    TESTING = True
    PREFERRED_URL_SCHEME = "http"
    SECRET_KEY = "beefca4e"
    SERVER_NAME = "localhost.localdomain"
