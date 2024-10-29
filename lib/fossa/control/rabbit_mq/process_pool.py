import copy
from datetime import datetime
import json
from multiprocessing import Queue
import queue
import random
import string
from threading import Thread
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

        # default maximum - this rate limits sending tasks to RabbitMq by allowing this
        # number of tasks to be queued for each task that creates sub-tasks
        self.default_max_in_flight = 1024

        self.subtask_number = None

    def run_subtasks(self, sub_tasks, context_kwargs=None, processes=None):
        """
        Generator yielding instances that are a subclass of :class:`AbstractTaskMessage`. These
        are from subtasks.

        @see doc. string in :meth:`AbstractProcessPool.run_subtasks`
        """
        max_in_flight = processes if processes is not None else self.default_max_in_flight
        if context_kwargs is None:
            context_kwargs = {}

        self.subtask_number = 0

        subtasks_queue = Queue()

        class SubTaskProcessor(Thread):
            """`sub_tasks` is an iterator, it blocks. Thread because of sharing variables.
            This just copies from the iterator to a queue which can be read in non-blocking
            mode. Oh async, where art thou?
            """

            def run(self):
                for sub_task in sub_tasks:
                    subtasks_queue.put(sub_task)

        sub_tasks_thread = SubTaskProcessor()
        sub_tasks_thread.start()

        def send_pending_subtasks():
            """
            If there is processing capacity, send out sub-tasks.
            @return: boolean - There are subtasks that haven't been sent out to workers.
            i.e. the `sub_tasks` iterator hassn't been exhausted.
            """
            while len(self.tasks_in_flight) < max_in_flight:
                if not sub_tasks_thread.is_alive():
                    # the iterator in the thread has been exhausted so no more tasks coming
                    return False

                try:
                    sub_task = subtasks_queue.get(block=False, timeout=1)
                except queue.Empty:
                    # There are probably more tasks to come
                    return True

                subtask_id = f"{self.pool_id}:{self.subtask_number}"
                self.subtask_number += 1
                augmented_context = {**context_kwargs, **sub_task.additional_context}

                task_definition = {
                    "model_class": sub_task.model_cls.__name__,
                    "method": sub_task.method_name,
                    "method_kwargs": sub_task.method_kwargs,
                    "resolver_context": augmented_context,
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

            # There are still tasks in the sub_tasks iterator
            return True

        # send initial batch of sub-tasks
        pending_tasks = send_pending_subtasks()

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
            pending_tasks = send_pending_subtasks()

            if not pending_tasks and len(self.tasks_in_flight) == 0:
                self.log("All tasks complete")
                return

            # heartbeats when using a blocking connection need to be explicitly handled
            self.rabbit_mq.connection.process_data_events()

            if method is None and properties is None and body is None:
                # on inactivity_timeout
                if last_logged < time.time() - max_log_seconds:
                    in_flight_count = len(self.tasks_in_flight)
                    msg = f"Waiting on {in_flight_count} tasks to complete. "
                    if pending_tasks:
                        msg += "There are still tasks to send."
                    else:
                        msg += "All sub-tasks have been sent."

                    self.log(msg)

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
