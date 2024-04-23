import json
import time

import pika

from fossa.control.broker import AbstractMycorrhiza
from fossa.control.message import TaskMessage
from fossa.control.rabbit_mq.pika_client import BasicPikaClient


class RabbitMx(AbstractMycorrhiza):
    """
    Rabbit MQ (https://www.rabbitmq.com/) message exchange.

    Message passing within a distributed network of Aye-aye models.

    This runs as a sidecar process within Fossa. It receives tasks from the Rabbit MQ network,
    keeps track of the correlation_id; send the tasks to the :class:`Governor` ; sends results
    from the task back to the originator.
    """

    def __init__(self, broker_url, *args, **kwargs):
        """
        @param broker_url: (str) to connect to Rabbit MQ
        e.g.
        "amqp://guest:guest@localhost",

        # for AWS-
        f"amqps://{rabbitmq_user}:{rabbitmq_password}@{rabbitmq_broker_id}.mq.{region}.amazonaws.com:5671"
        """
        self.broker_url = broker_url
        super().__init__(*args, **kwargs)

    def run_forever(self, work_queue_submit, available_processing_capacity):
        """
        Take a task received from RabbitMq exchange and pass it to the local governor.

        Runs in a separate Process
        """

        while True:
            try:
                rabbit_mq = BasicPikaClient(url=self.broker_url)
                for _not_connected in rabbit_mq.connect():
                    self.log("Waiting to connect to RabbitMQ....", "WARNING")
                self.log("Connected to RabbitMQ")

                self.log("RabbitMx starting .. waiting for messages ...")
                for method, properties, body in rabbit_mq.channel.consume(
                    queue=rabbit_mq.task_queue_name
                ):
                    subtask_id = properties.correlation_id
                    msg = f"Exchange received subtask_id: {subtask_id} from {properties.reply_to}"
                    self.log(msg)

                    # TODO use proper types
                    rabbit_decoded_task = json.loads(body)

                    # keep track of where the sub-task's work should be sent.
                    composite_task_id = f"{subtask_id}::{properties.reply_to}"
                    task_spec = TaskMessage(
                        task_id=composite_task_id,
                        **rabbit_decoded_task,
                        on_completion_callback=self.callback_on_processing_complete,
                    )

                    RabbitMx.submit_task(
                        task_spec, work_queue_submit, available_processing_capacity
                    )

                    rabbit_mq.channel.basic_ack(delivery_tag=method.delivery_tag)

            except Exception as e:
                self.log(f"Restarting after exception in RabbitMQ exchange: {e}", "ERROR")
                time.sleep(5)

    def callback_on_processing_complete(self, final_task_message, task_spec):
        """
        This callback is executed by the govenor with results from the task.

        Send these results to the originating task.
        """

        rabbit_mq = BasicPikaClient(url=self.broker_url)
        for _not_connected in rabbit_mq.connect():
            self.log("Waiting to connect to RabbitMQ....", "WARNING")
        self.log("Connected to RabbitMQ")

        composite_task_id = task_spec.task_id
        subtask_id, reply_to = composite_task_id.split("::", maxsplit=1)

        msg = f"Processing of subtask_id:{subtask_id} is complete, sending result to {reply_to}"
        self.log(msg)

        rabbit_mq.channel.basic_publish(
            exchange="",
            routing_key=reply_to,
            properties=pika.BasicProperties(correlation_id=subtask_id),
            body=final_task_message,
        )
        self.log(f"reply complete for {subtask_id}")
