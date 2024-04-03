from fossa.settings.global_config import BaseConfig
from examples.example_etl import NothingEtl


class Config(BaseConfig):
    """
    Example config. Copy and paste this as per the README
    """

    DEBUG = False
    PREFERRED_URL_SCHEME = "http"
    ACCEPTED_MODEL_CLASSES = [NothingEtl]
