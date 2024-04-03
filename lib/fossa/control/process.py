import traceback
import sys

import ayeaye
from ayeaye.exception import SubTaskFailed
from ayeaye.runtime.task_message import TaskComplete, TaskFailed

from fossa.control.message import ResultsMessage
from fossa.tools.logging import LoggingMixin


class AbstractIsolatedProcessor(LoggingMixin):
    """
    Run methods on an :class:`ayeaye.Model` within an isolated :class:`multiprocess.Process`.

    Instances of subclasses of this abstract class will be use by the :class:`Governor` to run
    Aye-aye models.

    The :meth:`__call__` is run in a separate Process.

    :meth:`set_work_queue` will be called after the 'isolated_processor' is accepted by the
    :class:`Governor`.

    Subclasses can connect to messaging brokers etc. so the subtasks from
    :class:`ayeaye.PartitionedModel` can be distributed to other workers.
    """

    def __init__(self):
        """
        This construction happens 'pre-fork' so should only contain strong types that can
        survive being serialised (pickled) and passed to a new `Process`.

        Subclasses are expected to have their own constructors which pass any left over
        arguments to this superclass.
        """
        LoggingMixin.__init__(self)
        self.work_queue = None

    def set_work_queue(self, work_queue):
        """
        @param work_queue (one end of :class:`multiprocessing.Queue`) - to post results to
        """
        self.work_queue = work_queue

    def on_model_start(self, model):
        """
        Optionally implemented by subclasses to makes it easy for subclasses to act on the model
        before methods on the model are run.

        For example, if just the `process_pool` needs to be changed then the subclass won't need to
        implement :meth:`__call__` etc.

        @param model: (subclass of :class:`ayeaye.Model`)
        """
        return None

    def __call__(
        self,
        task_id,
        model_cls,
        model_construction_kwargs,
        method,
        method_kwargs,
        resolver_context,
        partition_initialise_kwargs,
    ):
        """
        Run/execute the model.

        This method is run in a separate :class:`multiprocessing.Process` so don't mutate any
        instance variables.

        The execution is wrapped within an `ayeaye.connector_resolver` and a try except.

        Results, stack-traces etc. are sent back to the parent process over the `self.work_queue`
        Pipe.

        @param task_id: (str)
        @param model_cls: (Class, not instance)
        @param model_construction_kwargs: (dict)
        @param method: (str)
        @param method_kwargs: (dict)
        @param resolver_context: (dict)
        @param partition_initialise_kwargs: (dict)
        @return: None
        """
        try:
            with ayeaye.connector_resolver.context(**resolver_context):
                model = model_cls(**model_construction_kwargs)

                if isinstance(model, ayeaye.PartitionedModel):
                    model.partition_initialise(**partition_initialise_kwargs)

                # optional hook used by subclasses
                self.on_model_start(model)

                # TODO - attach logging - hint - send TaskLogMessage down self.work_queue

                sub_task_method = getattr(model, method)
                subtask_return_value = sub_task_method(**method_kwargs)

            task_complete = TaskComplete(
                method_name=method,
                method_kwargs=method_kwargs,
                return_value=subtask_return_value,
            )

            result_spec = ResultsMessage(
                task_id=task_id,
                task_message=task_complete.to_json(),
            )

        except SubTaskFailed as e:
            # This exception was probably raised by
            # :meth:`ayeaye.PartitionedModel.partition_subtask_failed`
            # Unless the subclass of :class:`PartitionedModel` overrides this method then it's
            # a brutal death for the parent class on failure of any subtask.
            # This process pool can have a re-try strategy for failed tasks as does the
            # :class:`RabbitMqProcessPool`.

            # originating :class:`TaskFailed` obj describing the failure in the subtask
            subtask_task_failed = e.task_fail_message

            task_failed = TaskFailed(
                model_class_name=model_cls.__name__,
                method_name=method,
                method_kwargs=method_kwargs,
                resolver_context=resolver_context,
                exception_class_name=str(type(e)),
                traceback=[],
                model_construction_kwargs=model_construction_kwargs,
                partition_initialise_kwargs=partition_initialise_kwargs,
                task_id=task_id,
                failure_origin_task_id=subtask_task_failed.task_id,  # link to failed subtask
            )

            # 'task_id' is the parent task. It is considered failed as a subtask has failed.
            result_spec = ResultsMessage(
                task_id=task_id,
                task_message=task_failed.to_json(),
            )

        except Exception as e:
            # TODO - recording the traceback is a bit rough
            _e_type, _e_value, e_traceback = sys.exc_info()
            traceback_ln = []
            tb_list = traceback.extract_tb(e_traceback)
            for filename, line, funcname, text in tb_list:
                traceback_ln.append(f"Traceback:  File[{filename}] Line[{line}] Text[{text}]")

            # Record a fair amount about the failure to send back to the originating model
            task_failed = TaskFailed(
                model_class_name=model_cls.__name__,
                method_name=method,
                method_kwargs=method_kwargs,
                resolver_context=resolver_context,
                exception_class_name=str(type(e)),
                traceback=traceback_ln,
                model_construction_kwargs=model_construction_kwargs,
                partition_initialise_kwargs=partition_initialise_kwargs,
                task_id=task_id,
            )
            result_spec = ResultsMessage(
                task_id=task_id,
                task_message=task_failed.to_json(),
            )

        self.work_queue.put(result_spec)


class LocalAyeAyeProcessor(AbstractIsolatedProcessor):
    """
    Run all or part of an :class:`ayeaye.Model` and :class:`ayeaye.PartitionedModel` within a
    single compute node.
    """

    def __init__(self, *args, **kwargs):
        """
        @param enforce_single_partition: (boolean) [default is True] when processing an
            :class:`ayeaye.PartitionedModel` don't allow the process to spill out across CPUs. This
            help's the governor's assumption about CPU resources.
            To distribute the processing of subtasks, instead use another type of
            `AbstractIsolatedProcessor` for example :class:`RabbitMqProcessor`
        """
        self.enforce_single_partition = kwargs.pop("enforce_single_partition", True)
        super().__init__(*args, **kwargs)

    def on_model_start(self, model):
        """
        @see :meth:`AbstractIsolatedProcessor.on_model_start` for doc. string.
        """
        model_cls = model.__class__
        if self.enforce_single_partition and issubclass(model_cls, ayeaye.PartitionedModel):
            # Force a maximum of one process when running a parallel model
            model.runtime.max_concurrent_tasks = 1
