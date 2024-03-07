"""
Use RabbitMq to connect multiple fossa nodes to distribute and joinly run sub-tasks.

Fossa nodes would normally run on separate compute nodes (e.g. a compute node being a machine or
docker container). Each fossa 'daemon' process would would use all the available CPUs on the
compute node so it doesn't make sense to run duplicate fossa processes on a single compute node.

To keep this demo simple, run multiple fossa processes on a single compute node. They each listen
for http requests so will need to use their own port numbers. Run each in a separate console.

You'll need to run RabbitMQ. There are loads of ways to do this (local install, docker container,
cloud provider service etc.). Update the `broker_url` value below.
See https://www.rabbitmq.com/docs/download 

e.g.

```shell
pipenv shell
export PYTHONPATH=`pwd`/lib:`pwd`
FOSSA_HTTP_PORT=2345 python examples/rabbit_mq.py
```

and in another terminal-
```shell
pipenv shell
export PYTHONPATH=`pwd`/lib:`pwd`
FOSSA_HTTP_PORT=2344 python examples/rabbit_mq.py
```

Choose either node and submit a task-

And send a task to it via it's API like this-

```shell
curl --header "Content-Type: application/json" \
     --data '{"model_class":"PartitionedExampleEtl"}'  \
     --request POST http://0.0.0.0:2345/api/0.01/task
```


You should see the console output from both detailing sub-tasks that are being executed.

You can point a browser at 'http://0.0.0.0:2345/' and 'http://0.0.0.0:2344/' and see which sub-tasks
each has run.
"""
import os

from fossa import run_fossa, BaseConfig
from fossa.control.rabbit_mq.message_exchange import RabbitMx
from fossa.control.rabbit_mq.process import RabbitMqProcessor
from examples.example_etl import PartitionedExampleEtl


class FossaConfig(BaseConfig):
    HTTP_PORT = os.environ["FOSSA_HTTP_PORT"]
    ACCEPTED_MODEL_CLASSES = [PartitionedExampleEtl]
    # in productions, use secrets management here
    broker_url = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@lobster")
    ISOLATED_PROCESSOR = RabbitMqProcessor(broker_url=broker_url)
    MESSAGE_BROKER_MANAGERS = [RabbitMx(broker_url=broker_url)]


if __name__ == "__main__":
    run_fossa(FossaConfig)
