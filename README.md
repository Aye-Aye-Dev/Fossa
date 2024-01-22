# fossa
Execution engine for Aye-Aye ETL models

## Overview

Fossa runs Aye-aye models and their subtasks across a distributed environment.

Aye-aye models can be run without Fossa (as they are just Python code) but when a model grows too big to execute on a single computer the task needs to be spread across multiple computers. A 'distributed environment' is one with multiple compute node that are networked so messages can be passed between nodes.

An instance of Fossa runs on each compute node where it facilitates the communication of messages between nodes.

A node could be a docker or full computer instance.


## Getting Started

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


## Running it locally

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

