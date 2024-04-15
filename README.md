# fossa
Execution engine for Aye-Aye ETL models

## Overview

Fossa runs Aye-aye models and their subtasks across a distributed environment.

Aye-aye models can be run without Fossa (they're just Python code) but when a model grows too big to execute on a single computer the task needs to be spread across multiple computers. A 'distributed environment' is one with multiple compute node that are networked so messages can be passed between nodes.

An instance of Fossa runs on each compute node where it facilitates the communication of messages between nodes.

A node could be a docker or full computer instance.


## Getting Started

Setup your virtual environment (venv, pipenv, poetry etc.)

```shell
pip install ayeaye-fossa
```

Make a python module to use this-

```python
import ayeaye

from fossa import run_fossa, BaseConfig

class NothingEtl(ayeaye.Model):
    def build(self):
        pass

class FossaConfig(BaseConfig):
    ACCEPTED_MODEL_CLASSES = [NothingEtl]

run_fossa(FossaConfig)
```

Run it and point your browser to *http://0.0.0.0:2345/*. You have a fossa node that will only run the `NothingEtl` model locally. This is useless as that model doesn't do anything but it's a start.

The [examples](./examples) directory has that example plus a few more.



## Running Fossa locally

For local development (so an IDE and debugging tools etc. can be used) the Flask built in server can be used. `run_fossa` (demonstrated above) uses gunicorn.

Ensure your working directory is the same directory as this README file.

Then install dependencies and run the tests-

```shell
cp local_env_example .env
pipenv shell
pipenv install --dev
python -m unittest discover tests
```

The `.env` file is used by pipenv.

For all python commands below you will need to be in this pipenv shell.


In a distributed environment one instance of Fossa would run on each compute node. To experiment with Fossa just run one or more instances on a local computer.

Fossa runs a small web-server app which can be used to submit tasks and query the progress and status of tasks. In production, jobs are more likely to be fetched from a message queue.

Copy the example config file into your own person config; sym-link to `local_config.py` so the `run_local_app()` function in `fossa.app` can find it.

e.g.

```
cd fossa/settings
# replace xxxxx with your name or a more useful identifier for your environment
cp local_config_example.py local_config_xxxxx.py
# have a look in your config file. Is there anything you'd like to change to fit with your system?
ln -s local_config_xxxxx.py local_config.py
```

In the virtual env (provided by pipenv) from above and with the current working directory being the project's root directory-

```
python fossa/app.py
```

You'll now have a locally running web app. It will output IP addresses it is accepting connections from. Typically just point a browser at `http://0.0.0.0:2345/'

## Running Fossa locally using gunicorn

```shell
export PYTHONPATH=`pwd`:`pwd`/lib
DEPLOYMENT_ENVIRONMENT=local python lib/fossa/main.py
```

### Posting a task

In a production environment tasks are more likely to arrive through a message queue. But it's also possible to use an HTTP POST to submit a task.

If you used the `local_config_example.py` file as a starting point for your local config it will have a single model already in the `ACCEPTED_MODEL_CLASSES` parameter. This is a tiny example ETL model.

Fossa will only run models that have been pre-defined before start-up. A simple way to supply these models is through the config file but there are other ways too.

POST to your local instance of Fossa a task specification. This example runs the complete `SimpleExampleEtl` model-

```shell
curl --header "Content-Type: application/json" \
     --data '{"model_class":"NothingEtl"}'  \
     --request POST http://0.0.0.0:2345/api/0.01/task
```


### Distributed (but still local) processing

TODO

```shell
curl --header "Content-Type: application/json" \
     --data '{"model_class":"PartitionedExampleEtl"}'  \
     --request POST http://0.0.0.0:2345/api/0.01/task
```

### Tests

The normal unittests will run with the `` command detailed above. There are also some integration tests in an early stage of development. They are message and output a lot of rubbish to the console. Enable them by supplying a RabbitMQ broker through an environmental variable. e.g. `export RABBITMQ_URL=amqp://guest:guest@localhost`.
