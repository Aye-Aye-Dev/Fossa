import time

from fossa.control.message import TaskMessage


class AbstractMycorrhiza:
    """
    A separate 'sidecar' process that is attached to the :class:`Governor` primarily to inject
    work tasks.
    """

    def __init__(self):
        self.work_queue_submit = None
        self.available_processing_capacity = None

    def run_forever(self, work_queue_submit, available_processing_capacity):
        """
        Method to run in a separate process for the duration of Fossa.

        The arguments passed are for multiprocessing syncronisation. The Queue can't
        be passed as an argument to the constructor (sharedctype could) so keep them
        both together.

        These syncronisation variables are so subclasses of `AbstractMycorrhiza` can be partially
        attached to the governor.

        The entire governor object can't be passed as it contains weakrefs (multiprocessing Manger)
        so it can't be serialised.

        @param work_queue_submit: (Queue) end to send task into
        @param available_processing_capacity: sharedctypes int
        """
        raise NotImplementedError("Must be implemented by subclasses")

    @classmethod
    def submit_task(cls, task_spec, work_queue_submit, available_processing_capacity):
        """
        Wait for processing capacity in the governor then submit task for processing.

        @param task_spec: (TaskMessage)
        @return: None
        """
        if not isinstance(task_spec, TaskMessage):
            raise ValueError("task_spec must be of type TaskMessage")

        # TODO - proper sync primative in the governor
        while available_processing_capacity.value < 1:
            time.sleep(2)

        work_queue_submit.put(task_spec)
