import multiprocessing

from fossa.control.broker import AbstractMycorrhiza
from fossa.control.message import TerminateMessage
from fossa.tools.logging import AbstractExternalLogger

from tests.base import BaseTest


class QueueLogger(AbstractExternalLogger):
    def __init__(self, log_queue):
        self.log_queue = log_queue

    def write(self, msg, level="INFO"):
        self.log_queue.put(f"{level} {msg}")
        return True


class FakeSideCar(AbstractMycorrhiza):
    def run_forever(self, work_queue_submit, available_processing_capacity):
        self.log("This is the fake sidecar")


class TestLogging(BaseTest):
    def test_external_logger_is_passed(self):
        """
        The logging setup should be passed to every object that subclasses LoggingMixin when the
        object is joined to the governor. This test just checks one sidecar.
        """
        log_queue = multiprocessing.Queue()
        fake_logger = QueueLogger(log_queue=log_queue)

        self.governor.attach_sidecar(FakeSideCar())
        self.governor.attach_external_logger(fake_logger)
        self.governor.log_to_stdout = False

        proc = self.governor.start_internal_processes()

        # instruct the governor to stop
        self.governor._task_queue_submit.put(TerminateMessage())

        # wait for it to terminate
        proc.join()

        all_the_logs = []
        while not log_queue.empty():
            log_msg = log_queue.get()
            all_the_logs.append(log_msg)

        self.assertIn("INFO This is the fake sidecar", all_the_logs)
