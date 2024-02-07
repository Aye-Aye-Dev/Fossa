import copy
from datetime import datetime
from inspect import isclass
import multiprocessing
from multiprocessing.sharedctypes import Value
import os
import random
import string

from ayeaye.runtime.knowledge import RuntimeKnowledge

from fossa.control.broker import AbstractMycorrhiza
from fossa.control.message import TaskMessage, ResultsMessage, TerminateMessage
from fossa.control.process import LocalAyeAyeProcessor
from fossa.tools.logging import LoggingMixin, MiniLogger


class InvalidTaskSpec(ValueError):
    pass


class Governor(LoggingMixin):
    """
    Connect the web frontend; message brokers and task execution.
    """

    def __init__(self, isolated_processor=None):
        """
        @param isolated_process (subclass of :class:`AbstractIsolatedProcessor`): instance/object
                This class has a method (`__call__`) which is run in a separate
                :class:`multiprocessing.Process`.
                The object is initiated before being passed so subclass specifics can be setup,
                e.g. a connection to a message broker.
                The :meth:`set_work_queue` will be called on `isolated_process` to connect it
                into the processing done by the governor.
                If not explicitly set through this constructor or through :attr:`isolated_processor`
                the :class:`LocalAyeAyeProcess` processor will be used.
        """
        LoggingMixin.__init__(self)

        # Tasks submitted and internal tasks (e.g. process results at end of task) are put on this
        # queue.
        self._task_queue_submit = multiprocessing.Queue()
        self._task_queue_receive = multiprocessing.Queue()

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

        # key (str) is the name of the class (e.g. cls.__name__), value is the class itself.
        # For security reasons, models not in the list aren't permitted
        self.accepted_classes = {}

        # Can be set by construction or with :meth:`isolated_processor`
        self._isolated_processor = isolated_processor

        # @see :meth:`attach_sidecar`
        self._sidecar_instances = []

        # keep track of internal processes
        self._internal_process_table = []

    @property
    def isolated_processor(self):
        """
        If not explicitly set in the constructor or the setter version of this attribute, the
        process will default to :class:`LocalAyeAyeProcessor`.

        This default processor doesn't split partitioned tasks into sub-tasks that run across
        a distributed environment. It just runs everything in the local compute node.

        @return: (subclass of :class:`AbstractIsolatedProcessor`): instance/object
        """

        if self._isolated_processor is None:
            self._isolated_processor = LocalAyeAyeProcessor()

            # connect the governor with isolated processes with a Pipe
            self._isolated_processor.set_work_queue(self._task_queue_submit)

            # copy logging setup across
            assert isinstance(self._isolated_processor, LoggingMixin)
            self._isolated_processor.copy_logging_setup(self)

        return self._isolated_processor

    @isolated_processor.setter
    def isolated_processor(self, processor):
        "See doc. string in getter version of :meth:`isolated_processor`"
        self._isolated_processor = processor
        self._isolated_processor.set_work_queue(self._task_queue_submit)

        # copy logging setup across if supported by processor
        if isinstance(self._isolated_processor, LoggingMixin):
            self._isolated_processor.copy_logging_setup(self)

    @property
    def has_processing_capacity(self):
        """
        A new task could be accepted.

        @return: boolean
        """
        return self.available_processing_capacity.value > 0

    def attach_sidecar(self, sidecar):
        """
        Add a object to be run within a separate :class:`multiprocessing.Process`.

        Sidecar processes are those used by other subsystems. For example, to connect to a
        messaging broker, read and write to it etc.

        @param sidecar (:class:`AbstractMycorrhiza`) as the base class. Enough of the governor will
        be automatically attached to the sidecar to allow it's :meth:`submit_task` to work. See
        the doc. string in :class:`AbstractMycorrhiza` for details on this.
        """
        assert isinstance(sidecar, AbstractMycorrhiza)
        self._sidecar_instances.append(sidecar)

    def start_internal_processes(self):
        """
        Run the governor's own management process along with any sidecar processes in separate
        :class:`multiprocessing.Processes.

        For sidecar processes see :meth:`attach_sidecar`.

        The internal process is a classmethod so the weakref of `self.mp_manager` doesn't get in
        the way of serialising the instance of this class. This manager and other shared objects
        are prepared here for the governor's `run_forever` Process.

        @return: :class:`Process` - just in case the reference is need to cleanly kill the process.
        """
        if len(self._internal_process_table) > 0:
            msg = "This should only be called once; There are already running processes"
            raise ValueError(msg)

        pkwargs = {
            "governor_id": self.governor_id,
            "work_queue_receive": self._task_queue_submit,
            "process_table": self.process_table,
            "previous_tasks": self.previous_tasks,
            "runtime": self.runtime,
            "available_processing_capacity": self.available_processing_capacity,
            "available_classes": self.accepted_classes,
            "isolated_processor": self.isolated_processor,
            "external_loggers": [copy.copy(logger) for logger in self.external_loggers],
            "log_to_stdout": self.log_to_stdout,
        }

        governor_proc = multiprocessing.Process(target=Governor.run_forever, kwargs=pkwargs)
        governor_proc.start()
        self._internal_process_table.append(governor_proc)

        # optional side processes
        for c in self._sidecar_instances:
            if isinstance(c, LoggingMixin):
                c.copy_logging_setup(self)

            rf_kwargs = dict(
                work_queue_submit=self._task_queue_submit,
                available_processing_capacity=self.available_processing_capacity,
            )
            proc = multiprocessing.Process(target=c.run_forever, kwargs=rf_kwargs)
            proc.start()
            self._internal_process_table.append(proc)

        return governor_proc

    @classmethod
    def run_forever(
        cls,
        governor_id,
        work_queue_receive,
        process_table,
        previous_tasks,
        runtime,
        available_processing_capacity,
        available_classes,
        isolated_processor,
        external_loggers,
        log_to_stdout,
    ):
        """
        The governor's own worker process. It manages running tasks and the communication with task
        queues.
        """

        logger = MiniLogger()
        logger.log_to_stdout = log_to_stdout
        for ext_log in external_loggers:
            logger.attach_external_logger(ext_log)

        while True:
            # Slight race condition - the window between 'Read incoming tasks' and calculating the
            # `processing_capacity` is an opportunity for many tasks to be added to the pipe. A
            # semaphore could be used alongside any operation on the process_table.
            empty_queue = work_queue_receive.empty()
            processing_capacity = runtime.max_concurrent_tasks - len(process_table)

            # maintain the capacity score-board
            if empty_queue and processing_capacity > 0:
                available_processing_capacity.value = processing_capacity
            else:
                # there are items in the queue, no idea how many, they might be tasks
                available_processing_capacity.value = 0

            # Read incoming tasks
            # This process should spend a lot of time here waiting for the next instruction
            work_spec = work_queue_receive.get()

            if isinstance(work_spec, TaskMessage):
                # this message is the specification for the execution of a task
                task_spec = work_spec

                proc_id = cls._generate_identifier()
                logger.log(f"Recieved task_spec: '{task_spec}' is proc: {proc_id}")

                # Setup a blast radius and make context available to this isolated process
                if task_spec.model_class not in available_classes:
                    # Throwing an exception seems pretty extreme for what is expected to be a long
                    # running method but it's a coding mistake for a task to be in the pipe without
                    # being sanatised by :meth:`submit_task`.
                    msg = f"Model class '{task_spec.model_class}' is not an accepted class"
                    raise InvalidTaskSpec(msg)

                TaskCls = available_classes[task_spec.model_class]

                iso_proc_kwargs = {
                    "task_id": proc_id,
                    "model_cls": TaskCls,
                    "method": task_spec.method,
                    "method_kwargs": task_spec.method_kwargs,
                    "resolver_context": task_spec.resolver_context,
                }

                process_table[proc_id] = {
                    "task_spec": task_spec,
                    "started": datetime.utcnow(),
                }

                # run the process. It communicates back to this governor process by putting it's
                # results, exceptions etc. onto the work_queue.
                # Note - isolated_processor is a callable
                ayeaye_proc = multiprocessing.Process(
                    target=isolated_processor,
                    kwargs=iso_proc_kwargs,
                )
                ayeaye_proc.start()

            elif isinstance(work_spec, ResultsMessage):
                # this is the result of running a task
                result_spec = work_spec

                task_id = result_spec.task_id
                process_details = process_table.get(task_id)
                if process_details is None:
                    logger.log(f"Unknown task id [{task_id}], skipping callback", level="ERROR")
                    continue

                process_details["finished"] = datetime.utcnow()
                process_details["result_spec"] = result_spec

                # These are the details of the task from before processing
                task_spec = process_details["task_spec"]

                logger.log(f"governor {governor_id} received completion message: {task_spec}")

                # either a fail or complete message
                final_task_message = result_spec.task_message

                # TODO - external code - wrap in try except
                task_spec.on_completion_callback(final_task_message, task_spec)

                # Remove from processing table but keep a log of finished tasks
                previous_tasks.append(process_details)
                del process_table[task_id]

            elif isinstance(work_spec, TerminateMessage):
                logger.log("Received termination message, ending now")
                return
            else:
                logger.log("Unknown message type received and ignored", level="ERROR")

    def set_accepted_class(self, model_cls):
        """
        For security reasons a Fossa compute node must be configured in advance with the models
        it is permitted to run.

        If multiple models with the same name are supplied, an error will be returned.

        :meth:`submit_task` is passed a `task_spec` that names the model class. That name must
        match that from `model_cls.__name__`.

        @param model_cls: (class, not instance of class)
        """
        if not isclass(model_cls):
            msg = "model_class passed to Governor.set_accepted_class must be a class, not object"
            raise ValueError(msg)

        model_name = model_cls.__name__
        if model_name in self.accepted_classes:
            msg = (
                f"{model_name} already exists as an accepted class. This could be a different "
                "class with the same name."
            )
            raise ValueError(msg)

        self.accepted_classes[model_name] = model_cls

    def submit_task(self, task_spec):
        """
        To avoid a race condition this method doesn't check for capacity. Users of this
        method should check :meth:`has_processing_capacity`

        @param task_spec: (TaskMessage)
        @return: (str) identifier for the governor process that accepted the task
        """
        if not isinstance(task_spec, TaskMessage):
            raise ValueError("task_spec must be of type TaskMessage")

        if task_spec.model_class not in self.accepted_classes:
            msg = f"Model class '{task_spec.model_class}' is not in the list of accepted classes."
            raise InvalidTaskSpec(msg)

        self._task_queue_submit.put(task_spec)
        return self.governor_id

    @classmethod
    def _generate_identifier(cls):
        """
        Util method to create a random string.

        @return: (str)
        """
        return "".join([random.choice(string.ascii_lowercase) for _ in range(5)])
