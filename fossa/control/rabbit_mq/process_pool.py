from datetime import datetime
import json
import multiprocessing
import random
import string

from ayeaye.runtime.multiprocess import AbstractProcessPool, MessageType
import pika

from fossa.control.rabbit_mq.pika_client import BasicPikaClient


class RabbitMqProcessPool(AbstractProcessPool):
    """
    Send sub-tasks to workers listening on a Rabbit MQ queue.
    """

    def __init__(self, broker_url):
        self.rabbit_mq = BasicPikaClient(url=broker_url)
        self.tasks_in_flight = {}
        self.pool_id = "".join([random.choice(string.ascii_lowercase) for _ in range(5)])
        # self.task_complete_receive, self.task_complete_submit = multiprocessing.Pipe(duplex=False)

    def log(self, message, level="INFO"):
        # TODO relay these somewhere
        print(message, level)

    def run_subtasks(
        self,
        model_cls,
        sub_tasks,
        initialise=None,
        context_kwargs=None,
        processes=None,
    ):
        """
        Generator yielding (method_name, method_kwargs, subtask_return_value) from completed
        subtasks.
        """
        if processes is None:
            # if the count of processes is used to distribute the workers this will work
            processes = len(sub_tasks)

        # fortunately sub_tasks is a list (not a generator) so all tasks can be sent
        for subtask_number, sub_task in enumerate(sub_tasks):
            subtask_id = f"{self.pool_id}:{subtask_number}"
            method_name, method_kwargs = sub_task

            task_definition = {
                "model_class": model_cls.__name__,
                "method": method_name,
                "method_kwargs": method_kwargs,
                "resolver_context": context_kwargs,
                "initialise": initialise,
            }
            task_definition_json = json.dumps(task_definition)

            self.tasks_in_flight[subtask_id] = task_definition
            self.tasks_in_flight[subtask_id]["start_time"] = datetime.utcnow()
            self.send_task(subtask_id=subtask_id, task_payload=task_definition_json)

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

            processing_complete_task = json.loads(body)

            # TODO - add log messages too
            subtask_return = (
                MessageType.COMPLETE,
                method_name,
                processing_complete_task["task_spec"]["method"],
                processing_complete_task["result_spec"]["result"]["return_value"],
            )
            # (method_name, method_kwargs, subtask_return_value)
            yield subtask_return

            self.log("subtask_complete_callback", body)
            subtask_id = properties.correlation_id
            if subtask_id in self.tasks_in_flight:
                del self.tasks_in_flight[subtask_id]

            if len(self.tasks_in_flight) == 0:
                self.log("All tasks complete")
                return

    def send_task(self, subtask_id, task_payload):
        """
        Send a work instruction to be picked up by any worker.
        @param subtask_id (str):
        @param task_payload (str):
        """
        self.rabbit_mq.init_queue()

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
