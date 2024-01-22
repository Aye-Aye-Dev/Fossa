import time

from fossa.control.message import ResultsMessage


class AyeAyeProcess:
    """
    Run methods on :class:`ayeaye.Model` within an isolated :class:`multiprocess.Process`.
    """

    def __init__(self, task_id, work_queue):
        self.task_id = task_id
        self.work_queue = work_queue

    def __call__(self):
        time.sleep(3)

        result_spec = ResultsMessage(
            task_id=self.task_id,
            result={"result_set": "fake"},
        )

        self.work_queue.send(result_spec)
