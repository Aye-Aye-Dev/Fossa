import copy
from datetime import datetime


class AbstractExternalLogger:
    """
    External loggers can be used alongside or instead of writing log messages to STDOUT.
    """

    def write(self, msg, level="INFO"):
        """
        @param msg: (str)
        @param level: (str)
        @return: bool for success to log
        """
        raise NotImplementedError("Must be implemented by subclasses")


class LoggingMixin:
    """
    Additional methods to log system information to the stdout (i.e. print) or to external
    logging services such as CloudWatch Logs.
    """

    def __init__(self):
        # @see :meth:`attach_external_logger`
        self.external_loggers = []

        # publically settable
        self.log_to_stdout = True

    def attach_external_logger(self, logger):
        """
        @param logger (subclass of :class:`AbstractExternalLogger`):
        """
        assert isinstance(logger, AbstractExternalLogger)
        self.external_loggers.append(logger)

    def copy_logging_setup(self, logging_mixin_obj):
        """
        Take all the logging info from another subclass of :class:`LoggingMixin` and use it here.
        """
        self.log_to_stdout = logging_mixin_obj.log_to_stdout

        # pass any external loggers on
        for logger in logging_mixin_obj.external_loggers:
            # use a copy just incase there is any multiprocessing 'fun' around weak refs
            # or lack of concurrency support
            self.attach_external_logger(copy.copy(logger))

    def log(self, message, level="INFO"):
        """
        @param message: (str)
        @param level: (str) - standard POSIX levels - DEBUG, INFO, ERROR, CRITICAL etc.
        """
        if self.log_to_stdout:
            date_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            msg = "{} {}{}".format(date_str, level.ljust(10), message)
            print(msg)

        for logger in self.external_loggers:
            if not logger.write(msg=message, level=level) and self.log_to_stdout:
                date_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                msg = "{} {}External logger failed".format(date_str, level.ljust(10), message)
                print(msg)


class MiniLogger(LoggingMixin):
    """
    Standalone logger which is useful within isolated processes. Using this keeps the interface
    consistent with other classes that implement the `LoggingMixin`.
    """

    pass
