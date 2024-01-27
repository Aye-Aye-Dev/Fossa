import ayeaye

from fossa.control.message import ResultsMessage


class AbstractIsolatedProcessor:
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
        self.work_queue = None

    def set_work_queue(self, work_queue):
        """
        @param work_queue (one end of :class:`multiprocessing.Queue`) - to post results to
        """
        self.work_queue = work_queue

    def __call__(self, task_id, model_cls, method, method_kwargs, resolver_context):
        """
        Run/execute the model.

        This method is run in a separate :class:`multiprocessing.Process` so don't mutate any
        instance variables.

        The execution is wrapped within an `ayeaye.connector_resolver` and a try except.

        Results, stack-traces etc. are sent back to the parent process over the `self.work_queue`
        Pipe.

        @param task_id: (str)
        @param model_cls: (Class, not instance)
        @param method: (str)
        @param method_kwargs: (dict)
        @param resolver_context: (dict)
        @return: None
        """
        raise NotImplementedError("Must be implemented in subclasses")


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

    def __call__(self, task_id, model_cls, method, method_kwargs, resolver_context):
        """
        Run/execute the model.

        @see doc. string in :meth:`AbstractAyeAyeProcess.__call__`.
        """
        try:
            with ayeaye.connector_resolver.context(**resolver_context):
                model = model_cls()

                if self.enforce_single_partition and issubclass(model_cls, ayeaye.PartitionedModel):
                    # Force a maximum of one process when running a parallel model
                    model.runtime.max_concurrent_tasks = 1

                sub_task_method = getattr(model, method)
                subtask_return_value = sub_task_method(**method_kwargs)

            result_spec = ResultsMessage(
                task_id=task_id,
                result={"return_value": subtask_return_value},
            )
        except Exception as e:
            # TODO - this is a bit rough
            result_spec = ResultsMessage(
                task_id=task_id,
                result={"exception": str(e)},
            )

        self.work_queue.put(result_spec)
