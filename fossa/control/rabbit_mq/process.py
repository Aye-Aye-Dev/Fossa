import ayeaye

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

    def on_model_start(self, model):
        """
        @see :meth:`AbstractIsolatedProcessor.on_model_start` for doc. string.
        """
        model_cls = model.__class__
        if issubclass(model_cls, ayeaye.PartitionedModel):
            # Only :meth:`_build` in a `PartitionedModel` can yield tasks but the message
            # passing is rightly or wrongly being setup for all methods.
            model.process_pool = RabbitMqProcessPool(broker_url=self.broker_url)

            # Both RabbitMqProcessor and RabbitMqProcessPool use the LoggingMixin so share the
            # logging setup
            model.process_pool.copy_logging_setup(self)

            # TODO - This should include info on how many workers there are in the pool
            # for now, just set this to anything so it's not confused with local CPU counts
            model.runtime.max_concurrent_tasks = 128
