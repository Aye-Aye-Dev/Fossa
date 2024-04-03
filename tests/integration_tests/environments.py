from multiprocessing import Process
import os
import requests
import signal
import time

from examples.example_etl import NothingEtl, LongRunningEtl, PartialFailure, PartitionedExampleEtl
from fossa import run_fossa
from fossa.control.rabbit_mq.message_exchange import RabbitMx
from fossa.control.rabbit_mq.process import RabbitMqProcessor


class FossaIntTest:
    def __init__(self):
        self.log_to_stdout = False

    def start(self):
        raise NotImplementedError("Must be implemented in subclasses")

    def stop(self):
        raise NotImplementedError("Must be implemented in subclasses")

    def reset(self):
        raise NotImplementedError("Optionally implemented in subclasses")

    def log(self, msg, level="INFO"):
        if self.log_to_stdout:
            print(msg)


class OneNodeLocalEnvironment(FossaIntTest):
    "Rabbit MQ node must be provided"

    def __init__(self, rabbmitmq_broker_url):
        super().__init__()
        self.rabbmitmq_broker_url = rabbmitmq_broker_url
        self.proc_table = []
        self.gunicorn_proc_id = None
        self.http_port = 2345

    def start(self):
        # TODO - instead of needing to know all the defaults from BaseConfig, use it
        local_config = dict(
            ACCEPTED_MODEL_CLASSES=[
                NothingEtl,
                LongRunningEtl,
                PartialFailure,
                PartitionedExampleEtl,
            ],
            ISOLATED_PROCESSOR=RabbitMqProcessor(broker_url=self.rabbmitmq_broker_url),
            MESSAGE_BROKER_MANAGERS=[RabbitMx(broker_url=self.rabbmitmq_broker_url)],
            LOG_TO_STDOUT=False,
            DEBUG=False,
            APP_TITLE="Fossa",
            PREFERRED_URL_SCHEME="http",
            HTTP_PORT=self.http_port,
            EXTERNAL_LOGGERS=[],  # subclasses of
        )

        parent_proc = Process(target=run_fossa, kwargs={"deployment_config": local_config})
        self.proc_table.append(parent_proc)

        for proc in self.proc_table:
            proc.start()

        while parent_proc.pid is None:
            time.sleep(0.01)

        self.gunicorn_proc_id = parent_proc.pid

        # Wait for gunicorn to be up
        # There is probably a more elegant way to determine when the gunicorn workers are ready
        fossa_api_url = f"http://127.0.0.1:{self.http_port}/api/0.01/"
        while True:
            try:
                requests.get(fossa_api_url)
            except requests.ConnectionError:
                time.sleep(0.05)
                continue
            # TODO - should wait on API to say processing is available
            time.sleep(1)
            break

    def stop(self):
        # TODO - this results is error messages, it should find child processes and send them a term

        if self.gunicorn_proc_id is not None:
            self.log(f"killing gunicorn with pid={self.gunicorn_proc_id}")

            # time.sleep(10)

            # This signal indicates the governor should shutdown. See :func:`fossa.main.run_fossa`.
            os.kill(self.gunicorn_proc_id, signal.SIGABRT)
            time.sleep(1)

            # Kill actual gunicorn
            os.kill(self.gunicorn_proc_id, signal.SIGTERM)
            time.sleep(1)

        for proc in self.proc_table:
            if proc.is_alive():
                proc.terminate()

        # wait for processes to end
        for proc in self.proc_table:
            proc.join()

        self.gunicorn_proc_id = None
        self.proc_table = []


if __name__ == "__main__":
    # These bits are just for fiddling during development.

    x = OneNodeLocalEnvironment(rabbmitmq_broker_url="amqp://guest:guest@lobster")
    x.start()
    # print(x.proc_table[0].pid)
    # time.sleep(1)
    # main_proc x.proc_table[0].pid

    time.sleep(5)
    print("stopping")
    x.stop()
