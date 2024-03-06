"""
The bare minimum to run a Fossa node.

The node doesn't do anything useful as the only ETL model it can run is `NothingEtl` which doesn't
do anything.

Run it by going to the top level directory for this project and running a pipenv shell (or similar
python virtual environment) like this-

```shell
pipenv shell
export PYTHONPATH=`pwd`/lib:`pwd`
python examples/simple.py
```

And send a task to it via it's API like this-

```shell
curl --header "Content-Type: application/json" \
     --data '{"model_class":"NothingEtl"}'  \
     --request POST http://0.0.0.0:2345/api/0.01/task
```

You should see console output from `simple.py` and pointing a brower at 'http://0.0.0.0:2345/' will
display info about the task that ran.
"""
from examples.example_etl import NothingEtl
from fossa import run_fossa, BaseConfig


class FossaConfig(BaseConfig):
    ACCEPTED_MODEL_CLASSES = [NothingEtl]


if __name__ == "__main__":
    run_fossa(FossaConfig)
