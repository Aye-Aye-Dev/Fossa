import ayeaye

from fossa.control.message import ResultsMessage


class AyeAyeProcess:
    """
    Run methods on :class:`ayeaye.Model` within an isolated :class:`multiprocess.Process`.
    """

    def __init__(self, task_id, work_queue, available_classes):
        """
        @param task_id: (str)
        @param task_spec: (TaskMessage)
        @param work_queue (pipe) - to post results to
        @param available_classes (dict) - class name -> class
        """
        self.task_id = task_id
        self.work_queue = work_queue
        self.available_classes = available_classes

    def __call__(self, task_spec):
        """
        Execute the model class and method etc. described in `task_spec`.

        The execution is wrapped within an `ayeaye.connector_resolver` and a try except.

        @param task_spec: (TaskMessage)
        @return: None
        """

        model_cls = self.available_classes[task_spec.model_class]

        try:
            with ayeaye.connector_resolver.context(**task_spec.resolver_context):
                model = model_cls()
                sub_task_method = getattr(model, task_spec.method)
                subtask_return_value = sub_task_method(**task_spec.method_kwargs)

            result_spec = ResultsMessage(
                task_id=self.task_id,
                result={"return_value": subtask_return_value},
            )
        except Exception as e:
            # TODO - this is a bit rough
            result_spec = ResultsMessage(
                task_id=self.task_id,
                result={"exception": str(e)},
            )

        self.work_queue.send(result_spec)
