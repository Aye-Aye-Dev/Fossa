from fossa.settings.global_config import BaseConfig
from tests.example_etl import SimpleExampleEtl


class Config(BaseConfig):
    """
    Example config. Copy and paste this as per the README
    """

    DEBUG = True
    PREFERRED_URL_SCHEME = "http"
    ACCEPTED_MODEL_CLASSES = [SimpleExampleEtl]
