import ssl
import time

import pika


# def failure_to_publish_callback(channel, method, properties, body):
#     print("X" * 2000, channel, method, properties, body)


class BasicPikaClient:
    def __init__(self, url):
        """
        @param url: (str) e.g. "amqp://guest:guest@localhost",

        for AWS-
        f"amqps://{rabbitmq_user}:{rabbitmq_password}@{rabbitmq_broker_id}.mq.{region}.amazonaws.com:5671"
        """
        if url.startswith("amqp://"):
            self.parameters = pika.URLParameters(url)
        elif url.startswith("amqps://"):
            # SSL Context for TLS configuration of Amazon MQ for RabbitMQ
            # This project is open source - If you use a different TLS setup send it to me for
            # inclusion.
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
            ssl_context.set_ciphers("ECDHE+AESGCM:!ECDSA")

            self.parameters = pika.URLParameters(url)
            self.parameters.ssl_options = pika.SSLOptions(context=ssl_context)
        else:
            raise ValueError("Rabbit MQ broker urls are expected to start with amqp:// or amqps://")

        # see :meth:`connect`
        self.connection = None
        self.channel = None

        # This is the pool of tasks. Any worker could send a task here for any other worker
        # to pickup
        self.task_queue_name = "fossa_task_queue"
        self._queue_init_flag = False

        # single reply channel
        self._call_back_queue = None

    def connect(self):
        """
        Generator yielding False until a successful connection is made to RabbitMq

        Use it like this-

        >>> rabbit_mq = BasicPikaClient(url=self.broker_url)
        >>> for _not_connected in rabbit_mq.connect():
        >>>   self.log("Waiting to connect to RabbitMQ....", "WARNING")
        """
        if not self._queue_init_flag:
            while True:
                try:
                    self.connection = pika.BlockingConnection(self.parameters)
                except pika.exceptions.AMQPConnectionError:
                    yield False
                    time.sleep(5)
                    continue
                break

            self.channel = self.connection.channel()
            self.channel.basic_qos(prefetch_count=1)
            self.channel.queue_declare(queue=self.task_queue_name, durable=True)
            self._queue_init_flag = True

            # self.channel.add_on_return_callback(failure_to_publish_callback)

    @property
    def reply_queue(self):
        """
        On demand create a queue for results from workers to come back to this executing process.
        """
        if self._call_back_queue is None:
            results_queue = self.channel.queue_declare(queue="", exclusive=True)
            self._call_back_queue = results_queue.method.queue
        return self._call_back_queue
