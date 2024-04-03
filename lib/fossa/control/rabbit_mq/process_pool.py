from datetime import datetime
import json
import random
import string

from ayeaye.runtime.multiprocess import AbstractProcessPool
from ayeaye.runtime.task_message import task_message_factory, TaskComplete, TaskFailed

import pika

from fossa.control.rabbit_mq.pika_client import BasicPikaClient
from fossa.tools.logging import LoggingMixin


class RabbitMqProcessPool(AbstractProcessPool, LoggingMixin):
    """
    Send sub-tasks to workers listening on a Rabbit MQ queue.
    """

    def __init__(self, broker_url):
        LoggingMixin.__init__(self)
        self.rabbit_mq = BasicPikaClient(url=broker_url)
        self.tasks_in_flight = {}
        self.pool_id = "".join([random.choice(string.ascii_lowercase) for _ in range(5)])

    def run_subtasks(self, sub_tasks, context_kwargs=None, processes=None):
        """
        Generator yielding instances that are a subclass of :class:`AbstractTaskMessage`. These
        are from subtasks.

        @see doc. string in :meth:`AbstractProcessPool.run_subtasks`
        """
        if processes is None:
            # if the count of processes is used to distribute the workers this will work
            processes = len(sub_tasks)

        # fortunately sub_tasks is a list (not a generator) so all tasks can be sent
        for subtask_number, sub_task in enumerate(sub_tasks):
            # sub_task is a :class:`TaskPartition` object
            # See Aye-aye's `ayeaye.runtime.task_message.TaskPartition`
            subtask_id = f"{self.pool_id}:{subtask_number}"
            task_definition = {
                "model_class": sub_task.model_cls.__name__,
                "method": sub_task.method_name,
                "method_kwargs": sub_task.method_kwargs,
                "resolver_context": context_kwargs,
                "model_construction_kwargs": sub_task.model_construction_kwargs,
                "partition_initialise_kwargs": sub_task.partition_initialise_kwargs,
            }
            task_definition_json = json.dumps(task_definition)

            self.tasks_in_flight[subtask_id] = task_definition
            self.tasks_in_flight[subtask_id]["start_time"] = datetime.utcnow()

            # This JSON encoded payload will be received in :meth:`RabbitMx.run_forever` where
            # all of it will be used alongside some additional args to build :class:`TaskMessage`
            # TODO - Better typing should be used
            self.send_task(subtask_id=subtask_id, task_payload=task_definition_json)

        for _not_connected in self.rabbit_mq.connect():
            self.log("Waiting to connect to RabbitMQ....", "WARNING")
        self.log("Connected to RabbitMQ")

        # Listen for subtasks completing
        self.log(f"Waiting on {self.rabbit_mq.reply_queue} ....")

        # TODO inactivity_timeout (float) – if a number is given (in seconds), will cause the
        # method to yield (None, None, None) after the given period of inactivity;
        # use this to re-issue lost tasks
        for _method, properties, body in self.rabbit_mq.channel.consume(
            queue=self.rabbit_mq.reply_queue,
            auto_ack=True,
        ):
            # 'reply_queue' message is received.

            # could be a complete, fail or log
            task_message = task_message_factory(body)

            # TODO retry failed tasks a limited number of times

            if isinstance(task_message, (TaskComplete, TaskFailed)):
                self.log(f"subtask_complete: {body}")
                subtask_id = properties.correlation_id
                if subtask_id in self.tasks_in_flight:
                    del self.tasks_in_flight[subtask_id]

            yield task_message

            if len(self.tasks_in_flight) == 0:
                self.log("All tasks complete")
                return

    def send_task(self, subtask_id, task_payload):
        """
        Send a work instruction to be picked up by any RabbitMq worker.
        @param subtask_id (str):
        @param task_payload (str):
        """
        for _not_connected in self.rabbit_mq.connect():
            self.log("Waiting to connect to RabbitMQ....", "WARNING")
        self.log("Connected to RabbitMQ")

        self.rabbit_mq.channel.basic_publish(
            exchange="",
            routing_key=self.rabbit_mq.task_queue_name,
            body=task_payload,
            properties=pika.BasicProperties(
                delivery_mode=pika.DeliveryMode.Persistent,
                reply_to=self.rabbit_mq.reply_queue,
                content_type="application/json",
                correlation_id=subtask_id,
            ),
        )
