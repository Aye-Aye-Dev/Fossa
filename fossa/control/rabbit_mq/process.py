import traceback
import sys

import ayeaye

from fossa.control.message import ResultsMessage
from fossa.control.process import AbstractIsolatedProcessor
from fossa.control.rabbit_mq.process_pool import RabbitMqProcessPool


class RabbitMqProcessor(AbstractIsolatedProcessor):
    """
    Run single process :class:`ayeaye.Model`s in a single Process on the current single compute node.

    Send subtasks from :class:`ayeaye.PartitionedModel`s across the Rabbit MQ (message broker)
    connected distribution of compute nodes so these subtasks can be run elsewhere.
    """

    def __init__(self, *args, **kwargs):
        """
        @param broker_url: (str) to connect to Rabbit MQ
        e.g.
        "amqp://guest:guest@localhost",

        # for AWS-
        f"amqps://{rabbitmq_user}:{rabbitmq_password}@{rabbitmq_broker_id}.mq.{region}.amazonaws.com:5671"

        """
        self.broker_url = kwargs.pop("broker_url")
        super().__init__(*args, **kwargs)

    def __call__(self, task_id, model_cls, method, method_kwargs, resolver_context):
        """
        Run/execute the model. This method runs in a separate process.

        @see doc. string in :meth:`AbstractAyeAyeProcess.__call__`.
        """

        try:
            with ayeaye.connector_resolver.context(**resolver_context):
                model = model_cls()

                if issubclass(model_cls, ayeaye.PartitionedModel):
                    # Only :meth:`_build` in a `PartitionedModel` can yield tasks but the message
                    # passing is rightly or wrongly being setup for all methods.
                    model.process_pool = RabbitMqProcessPool(broker_url=self.broker_url)

                    # TODO - This should include info on how many workers there are in the pool
                    # for now, just set this to anything so it's not confused with local CPU counts
                    model.runtime.max_concurrent_tasks = 128

                sub_task_method = getattr(model, method)
                subtask_return_value = sub_task_method(**method_kwargs)

                result_spec = ResultsMessage(
                    task_id=task_id,
                    result={"return_value": subtask_return_value},
                )

        except Exception as e:
            # TODO - this is a bit rough

            _e_type, _e_value, e_traceback = sys.exc_info()
            traceback_ln = []
            tb_list = traceback.extract_tb(e_traceback)
            for filename, line, funcname, text in tb_list:
                traceback_ln.append(f"Traceback:  File[{filename}] Line[{line}] Text[{text}]")

            result_spec = ResultsMessage(
                task_id=task_id,
                result={
                    "exception": str(type(e)) + " : " + str(e),
                    "traceback": "\n".join(traceback_ln),
                },
            )

        self.work_queue.put(result_spec)
