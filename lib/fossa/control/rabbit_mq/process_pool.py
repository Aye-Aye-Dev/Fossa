import copy
from datetime import datetime
import json
import random
import string
import time

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
        self.task_retries = 1  # a retry is after the original subtask has failed
        self.failed_tasks_scoreboard = []  # task_ids

        # When all tasks are complete OR when a subtask or it's results are lost this timeout
        # allows the main wait loop to run.
        # TODO retry if a task takes x percent longer than the slowest known task
        self.inactivity_timeout = 3.0

    def run_subtasks(self, sub_tasks, context_kwargs=None, processes=None):
        """
        Generator yielding instances that are a subclass of :class:`AbstractTaskMessage`. These
        are from subtasks.

        @see doc. string in :meth:`AbstractProcessPool.run_subtasks`
        """
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

        # reduce repetitive log messages
        max_log_seconds = 60
        last_logged = 0

        # Listen for subtasks completing
        self.log(f"Connected to RabbitMQ, now waiting on {self.rabbit_mq.reply_queue} ....")
        for method, properties, body in self.rabbit_mq.channel.consume(
            queue=self.rabbit_mq.reply_queue,
            inactivity_timeout=self.inactivity_timeout,
        ):
            if len(self.tasks_in_flight) == 0:
                self.log("All tasks complete")
                return

            if method is None and properties is None and body is None:
                # on inactivity_timeout
                if last_logged < time.time() - max_log_seconds:
                    in_flight_count = len(self.tasks_in_flight)
                    self.log(f"Waiting on {in_flight_count} tasks to complete...")

                    task_ids = ",".join([t for t in self.tasks_in_flight.keys()])
                    max_output = 1024
                    if len(task_ids) > max_output:
                        task_ids = task_ids[0:max_output] + "..."
                    self.log(f"Waiting on task_ids: {task_ids}", "DEBUG")

                    last_logged = time.time()

                # inactivity timeout doesn't yield a message
                continue

            # 'reply_queue' message is received.
            self.rabbit_mq.channel.basic_ack(delivery_tag=method.delivery_tag)

            # could be a complete, fail or log
            task_message = task_message_factory(body)
            subtask_id = properties.correlation_id

            if isinstance(task_message, TaskFailed):
                # record this failure
                self.failed_tasks_scoreboard.append(subtask_id)

                if subtask_id not in self.tasks_in_flight:
                    msg = (
                        f"Failed subtask {subtask_id} is not registered as in flight so "
                        "must have already been completed"
                    )
                    self.log(msg, "WARNING")
                    continue

                task_attempts = self.failed_tasks_scoreboard.count(subtask_id)
                if task_attempts < self.task_retries + 1:
                    # try it again, don't yield it
                    self.log(f"Failed subtask {subtask_id} is being retried", "WARNING")
                    task_definition = copy.copy(self.tasks_in_flight[subtask_id])
                    del task_definition["start_time"]
                    task_definition_json = json.dumps(task_definition)
                    self.send_task(subtask_id=subtask_id, task_payload=task_definition_json)

                else:
                    self.log(f"Subtask {subtask_id} failed: {body}")
                    if subtask_id in self.tasks_in_flight:
                        del self.tasks_in_flight[subtask_id]

                    yield task_message

            elif isinstance(task_message, TaskComplete):
                if subtask_id in self.tasks_in_flight:
                    elapsed = datetime.utcnow() - self.tasks_in_flight[subtask_id]["start_time"]
                    elapsed_s = elapsed.total_seconds()
                    self.log(f"Subtask {subtask_id} complete. Took {elapsed_s} seconds. {body}")
                    del self.tasks_in_flight[subtask_id]
                else:
                    self.log(f"Complete task {subtask_id} not found in in-flight list", "WARNING")

                yield task_message

            else:
                msg_type = str(type(task_message))
                msg = f"Unknown message type {msg_type} received with subtask_id: {subtask_id} : {body}"
                self.log(msg, "ERROR")

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
            # mandatory=True,
        )
        self.log(f"Subtask: {subtask_id} has been sent to RabbitMq exchange", "DEBUG")
