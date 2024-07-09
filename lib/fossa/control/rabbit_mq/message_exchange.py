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
        self.rabbit_mq = None

    def run_forever(self, work_queue_submit, available_processing_capacity):
        """
        Take a task received from RabbitMq exchange and pass it to the local governor.

        Runs in a separate Process
        """

        # in order to maintain heartbeats with the broker :meth:`process_data_events` must
        # be called more frequently than the heartbeat interval x2. This interval defaults
        # to 30 seconds.
        broker_timeout = 10

        log_throttle = set()
        self.log("RabbitMx exchange is starting")
        while True:
            try:
                rabbit_mq = BasicPikaClient(url=self.broker_url)
                for _not_connected in rabbit_mq.connect():
                    self.log("Waiting to connect to RabbitMQ....", "WARNING")
                self.log("Connected to RabbitMQ")

                self.log("RabbitMx starting .. waiting for messages ...")

                # `basic_get` fetches a single message.
                # Previously, `rabbit_mq.channel.consume` was used but would result in a blocking
                # condition if tasks took too long to be accepted by `RabbitMx.submit_task`. This
                # resulted in the `consume` method not being visited enough.
                # last_events = time.time()
                while True:
                    # This is a race condition. For simplicity, the governor uses a queue. If a
                    # concurrency primative like a semaphore was used a slot could be booked
                    # here and only then fetch a message from RabbitMQ.
                    timed_out = RabbitMx.wait_for_capacity(
                        work_queue_submit,
                        available_processing_capacity,
                        timeout=broker_timeout,
                    )

                    # time_now = time.time()
                    # elapsed = time_now - last_events
                    # last_events = time_now
                    # self.log(f"Last message exchange events {elapsed} seconds", level="DEBUG")

                    # heartbeats when using a blocking connection need to be explicitly handled
                    rabbit_mq.connection.process_data_events()

                    if timed_out:
                        if "processing_capacity" not in log_throttle:
                            self.log("Waiting on processing capacity", level="DEBUG")
                            log_throttle.add("processing_capacity")
                        continue
                    elif "processing_capacity" in log_throttle:
                        log_throttle.remove("processing_capacity")
                        self.log("Processing capacity found", level="DEBUG")

                    method, properties, body = rabbit_mq.channel.basic_get(
                        queue=rabbit_mq.task_queue_name
                    )

                    if method is None and properties is None and body is None:
                        if "channel_empty" not in log_throttle:
                            self.log(
                                "No messages available from channel .. sleeping", level="DEBUG"
                            )
                            log_throttle.add("channel_empty")
                        time.sleep(5)
                        continue
                    elif "channel_empty" in log_throttle:
                        log_throttle.remove("channel_empty")
                        self.log("Messages available on channel again", level="DEBUG")

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

                    # avoidance of blocking condition - the message is being acked before the
                    # governor has accepted the task.
                    rabbit_mq.channel.basic_ack(delivery_tag=method.delivery_tag)

                    # This message must wait until RabbitMx.submit_task has found capacity.
                    # 'wait_for_capacity' above is to stop messages being taken from RabbitMq
                    # but still leaves the following potential race condition.
                    while not RabbitMx.submit_task(
                        task_spec,
                        work_queue_submit,
                        available_processing_capacity,
                        timeout=broker_timeout,
                    ):
                        # Block on race condition encountered. A message will be in limbo. i.e.
                        # not in RabbitMq or in the governor's queue.
                        self.log(f"Waiting on processing capacity for subtask_id: {subtask_id}")
                        # heartbeats when using a blocking connection need to be explicitly handled
                        rabbit_mq.connection.process_data_events()
                        # last_events = time.time()

                    self.log(f"Submitted subtask_id: {subtask_id} to the work queue")

            except Exception as e:
                self.log(f"Restarting after exception in RabbitMQ exchange: {e}", "ERROR")

                # maybe pika.exceptions.ConnectionWrongStateError ?
                try:
                    rabbit_mq.close_connection()
                except:
                    pass

                time.sleep(5)

    def callback_on_processing_complete(self, final_task_message, task_spec):
        """
        This callback is executed by the govenor with results from the task.

        Send these results to the originating task.
        """

        if self.rabbit_mq is None:
            self.log("Init RabbitMQ for callbacks")
            self.rabbit_mq = BasicPikaClient(url=self.broker_url)
        else:
            self.log("No Init RabbitMQ for callbacks")

        for _not_connected in self.rabbit_mq.connect():
            self.log("Waiting to connect to RabbitMQ....", "WARNING")
        self.log("Connected to RabbitMQ")

        composite_task_id = task_spec.task_id
        subtask_id, reply_to = composite_task_id.split("::", maxsplit=1)

        msg = f"Processing of subtask_id:{subtask_id} is complete, sending result to {reply_to}"
        self.log(msg)

        self.rabbit_mq.channel.basic_publish(
            exchange="",
            routing_key=reply_to,
            properties=pika.BasicProperties(correlation_id=subtask_id),
            body=final_task_message,
        )
        self.log(f"reply complete for {subtask_id}")
        self.rabbit_mq.connection.process_data_events()
