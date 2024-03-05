import ssl
import pika


class BasicPikaClient:
    def __init__(self, url):
        """
        @param url: (str) e.g. "amqp://guest:guest@localhost",

        for AWS-
        f"amqps://{rabbitmq_user}:{rabbitmq_password}@{rabbitmq_broker_id}.mq.{region}.amazonaws.com:5671"
        """
        if url.startswith("amqp://"):
            parameters = pika.URLParameters(url)
        elif url.startswith("amqps://"):
            # SSL Context for TLS configuration of Amazon MQ for RabbitMQ
            # This project is open source - If you use a different TLS setup send it to me for
            # inclusion.
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
            ssl_context.set_ciphers("ECDHE+AESGCM:!ECDSA")

            parameters = pika.URLParameters(url)
            parameters.ssl_options = pika.SSLOptions(context=ssl_context)
        else:
            raise ValueError("Rabbit MQ broker urls are expected to start with amqp:// or amqps://")

        self.connection = pika.BlockingConnection(parameters)
        self.channel = self.connection.channel()

        # This is the pool of tasks. Any worker could send a task here for any other worker
        # to pickup
        self.task_queue_name = "fossa_task_queue"
        self._queue_init_flag = False

        # single reply channel
        self._call_back_queue = None

    def init_queue(self):
        if not self._queue_init_flag:
            self.channel.queue_declare(queue=self.task_queue_name, durable=True)
            self._queue_init_flag = True

    @property
    def reply_queue(self):
        """
        On demand create a queue for results from workers to come back to this executing process.
        """
        if self._call_back_queue is None:
            results_queue = self.channel.queue_declare(queue="", exclusive=True)
            self._call_back_queue = results_queue.method.queue
        return self._call_back_queue
