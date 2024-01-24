class BaseConfig:
    DEBUG = False
    APP_TITLE = "Fossa"
    PREFERRED_URL_SCHEME = "https"
    SECRET_KEY = ""
    HTTP_PORT = 2345
    ACCEPTED_MODEL_CLASSES = []  # iterable of classes that the node is authorised to run
