import multiprocessing
from multiprocessing.sharedctypes import Value
import os
import random
import string

from ayeaye.runtime.knowledge import RuntimeKnowledge

from fossa.control.message import TaskMessage, ResultsMessage, TerminateMessage
from fossa.control.process import AyeAyeProcess


class Governor:
    """
    Connect the web frontend; message brokers and task execution.
    """

    print_to_stdout = True

    def __init__(self):
        # self.general_lock = multiprocessing.Lock()

        # Tasks submitted and internal tasks (e.g. process results at end of task) are put on this
        # pipe.
        self._work_queue_receive, self._work_queue_submit = multiprocessing.Pipe(duplex=False)

        # Each instance of Fossa must have a single governor. Some usages (for example
        # using Flask's debug=True and a code re-loader) will cause __main__ and therefore
        # :meth:`app.create_app` to be run twice. So create a unique identifier so these
        # can be differenticated.
        self.process_id = os.getpid()
        ident = self._generate_identifier()
        self.governor_id = f"{self.process_id}:{ident}"

        # managed shared memory has more convenient typing than multiprocessing.shared_memory
        self.mp_manager = multiprocessing.Manager()
        self.process_table = self.mp_manager.dict()  # currently running processes
        self.previous_tasks = self.mp_manager.list()
        self.available_processing_capacity = Value("i", 0)

        # the link between the execution environment and the process
        self.runtime = RuntimeKnowledge()

        # override CPU based default
        # self.runtime.max_concurrent_tasks = 1

    @property
    def has_processing_capacity(self):
        """
        A new task could be accepted.

        @return: boolean
        """
        return self.available_processing_capacity.value > 0

    def start_internal_process(self):
        """
        The internal process is a staticmethod so the weakref of `self.mp_manager` doesn't get in
        the way of serialising the instance of this class.

        This method prepares the shared objects for use by the governor's Process.

        @return: :class:`Process` - just in case the reference is need to cleanly kill the process.
        """
        pkwargs = {
            "work_queue_receive": self._work_queue_receive,
            "work_queue_submit": self._work_queue_submit,
            "process_table": self.process_table,
            "previous_tasks": self.previous_tasks,
            "runtime": self.runtime,
            "available_processing_capacity": self.available_processing_capacity,
        }

        governor_proc = multiprocessing.Process(target=Governor.run_forever, kwargs=pkwargs)
        governor_proc.start()

        return governor_proc

    @classmethod
    def log(cls, msg, level="INFO"):
        "Hook for local messages to make it easy to pipe them elsewhere."
        if cls.print_to_stdout:
            print(msg)

    @classmethod
    def run_forever(
        cls,
        work_queue_receive,
        work_queue_submit,
        process_table,
        previous_tasks,
        runtime,
        available_processing_capacity,
    ):
        """
        The governor's own worker process. It manages running tasks and the communication with task
        queues.
        """

        while True:
            tasks_waiting_in_queue = work_queue_receive.poll()
            processing_capacity = runtime.max_concurrent_tasks - len(process_table)

            # maintain the capacity score-board
            if not tasks_waiting_in_queue and processing_capacity > 0:
                available_processing_capacity.value = processing_capacity
            else:
                # there are items in the queue, no idea how many, they might be tasks
                available_processing_capacity.value = 0

            work_spec = work_queue_receive.recv()

            if isinstance(work_spec, TaskMessage):
                # this message is the specification for the execution of a task
                task_spec = work_spec

                proc_id = cls._generate_identifier()
                cls.log(f"Recieved task_spec: '{task_spec}' is proc: {proc_id}")

                # Setup a blast radius and make context available to this isolated process
                ayeaye_proc_wrapper = AyeAyeProcess(
                    task_id=proc_id,
                    work_queue=work_queue_submit,
                )

                process_table[proc_id] = {
                    "task_spec": task_spec,
                    "wrapped_process": ayeaye_proc_wrapper,
                }

                # run the process. It put's results onto the work_queue when it's done.
                ayeaye_proc = multiprocessing.Process(target=ayeaye_proc_wrapper)
                ayeaye_proc.start()

            elif isinstance(work_spec, ResultsMessage):
                # this is the result of running a task
                result_spec = work_spec

                task_id = result_spec.task_id
                process_details = process_table.get(task_id)

                if process_details is None:
                    cls.log(f"Unknown task id [{task_id}], skipping callback", level="ERROR")
                    continue

                # These are the details of the task from before processing
                task_spec = process_details["task_spec"]

                # TODO - external code - wrap in try except
                task_spec.on_completion_callback(result_spec, task_spec)

                # Remove from processing table but keep a log of finished tasks
                previous_tasks.append(process_details)
                del process_table[task_id]
            elif isinstance(work_spec, TerminateMessage):
                cls.log("Received termination message, ending now")
                return
            else:
                cls.log("Unknown message type received and ignored", level="ERROR")

    def submit_task(self, task_spec):
        """
        To avoid a race condition this method doesn't check for capacity. Users of this
        method should check :meth:`has_processing_capacity`

        @param task_spec: (TaskMessage)
        @return: (str) identifier for the governor process that accepted the task
        """
        if not isinstance(task_spec, TaskMessage):
            raise ValueError("task_spec must be of type TaskMessage")

        self._work_queue_submit.send(task_spec)
        return self.governor_id

    @classmethod
    def _generate_identifier(cls):
        """
        Util method to create a random string.

        @return: (str)
        """
        return "".join([random.choice(string.ascii_lowercase) for _ in range(5)])
