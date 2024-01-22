import multiprocessing
from multiprocessing.sharedctypes import Value
import os
import random
import string

from ayeaye.runtime.knowledge import RuntimeKnowledge


class Governor:
    """
    Connect the web frontend; message brokers and task execution.
    """

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
        self.governor_id = f"{self.process_id}_{ident}"

        # managed shared memory has more convenient typing than multiprocessing.shared_memory
        self.mp_manager = multiprocessing.Manager()
        self.process_table = self.mp_manager.dict()  # currently running processes
        self.previous_tasks = self.mp_manager.list()
        self.available_processing_capacity = Value("i", 0)

        # the link between the execution environment and the process
        self.runtime = RuntimeKnowledge()

        # override CPU based default
        self.runtime.max_concurrent_tasks = 3

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
            "work_queue": self._work_queue_receive,
            "process_table": self.process_table,
            "runtime": self.runtime,
            "available_processing_capacity": self.available_processing_capacity,
        }

        governor_proc = multiprocessing.Process(target=Governor.run_forever, kwargs=pkwargs)
        governor_proc.start()

        return governor_proc

    @staticmethod
    def run_forever(work_queue, process_table, runtime, available_processing_capacity):
        """
        The governor's own worker process. It manages running tasks and the communication with task
        queues.
        """

        while True:
            tasks_waiting_in_queue = work_queue.poll()
            processing_capacity = runtime.max_concurrent_tasks - len(process_table)

            print("processing cap:", processing_capacity, process_table)

            # maintain the capacity score-board
            if not tasks_waiting_in_queue and processing_capacity > 0:
                available_processing_capacity.value = processing_capacity
            else:
                # there are items in the queue, no idea how many, they might be tasks
                available_processing_capacity.value = 0

            task_spec = work_queue.recv()
            proc_id = Governor._generate_identifier()
            print(f"Recieved: '{task_spec}' is proc: {proc_id}")
            process_table[proc_id] = {"something": "hello task"}

    def submit_task(self):
        """
        To avoid a race condition this method doesn't check for capacity. Users of this
        method should check :meth:`has_processing_capacity`
        """
        self._work_queue_submit.send("hello")
        print(f"task recieved by {self.governor_id}")
        return self.governor_id

    @classmethod
    def _generate_identifier(self):
        """
        Util method to create a random string.

        @return: (str)
        """
        return "".join([random.choice(string.ascii_lowercase) for _ in range(5)])
