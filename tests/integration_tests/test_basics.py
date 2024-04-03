import json
import os
import requests
import time
import unittest

from tests.integration_tests.environments import OneNodeLocalEnvironment

# The integration tests need external resources. For now, a RabbitMq server is used but not created
# by these test.
RABBIT_MQ_BROKER = os.environ.get("RABBITMQ_URL")
RABBIT_MQ_IS_DEFINED = RABBIT_MQ_BROKER is not None


@unittest.skipUnless(RABBIT_MQ_IS_DEFINED, "Rabbit MQ environmental variable not set")
class TestFossaBasics(unittest.TestCase):
    """
    Run fossa via gunicorn in a local process; send API calls to it and check the results.
    """

    def setUp(self):
        """
        Set up each test
        """
        self.fossa_integration_environment = OneNodeLocalEnvironment(
            rabbmitmq_broker_url=RABBIT_MQ_BROKER
        )
        self.fossa_integration_environment.start()

        http_port = self.fossa_integration_environment.http_port
        self.fossa_api_url = f"http://127.0.0.1:{http_port}/api/0.01/"
        self.api_headers = {"Content-type": "application/json"}

    def tearDown(self):
        self.fossa_integration_environment.stop()

    def test_run_nothing_etl(self):
        """
        Send request to process a task; wait until the task finishes by using the task's url.
        """
        fossa_command = {"model_class": "NothingEtl"}
        r = requests.post(
            self.fossa_api_url + "task",
            data=json.dumps(fossa_command),
            headers=self.api_headers,
        )

        self.assertEqual(200, r.status_code)

        task_submit_doc = r.json()
        task_url = task_submit_doc["_metadata"]["links"]["task"]
        self.assertTrue(task_url.startswith(self.fossa_api_url))

        while True:
            r = requests.get(task_url)
            task_doc = r.json()

            if "status" not in task_doc:
                # TODO - fix this work around upstream in Fossa. It happens when
                # a new task is in the queue from web frontend to the governor.
                time.sleep(0.1)
                continue

            elif task_doc["status"] == "running":
                time.sleep(0.1)
                continue
            elif task_doc["status"] == "complete":
                break

        self.assertIn("finished", task_doc)

    def test_terminates_running_etls(self):
        """
        When Fossa is shutdown it should kill any running ETL tasks.
        """
        fossa_command = {"model_class": "LongRunningEtl"}
        r = requests.post(
            self.fossa_api_url + "task",
            data=json.dumps(fossa_command),
            headers=self.api_headers,
        )

        self.assertEqual(200, r.status_code)

        task_submit_doc = r.json()
        task_url = task_submit_doc["_metadata"]["links"]["task"]

        # Wait for the task to be running
        while True:
            task_doc = requests.get(task_url).json()
            if "status" not in task_doc:
                # TODO - fix this work around upstream in Fossa. It happens when
                # a new task is in the queue from web frontend to the governor.
                time.sleep(0.1)
                continue

            elif task_doc["status"] != "running":
                time.sleep(0.1)
                continue
            break

        # Ideally, fossa's _terminate_etl_processes() would be run here
        # instead, this test terminating without any hanging processes should be enough of a test
        # or maybe check the host's process table and see if it's there. DEBUG mode could be used
        # to expose the process number??

    def test_propagate_failures(self):
        """
        When a sub-task fails the parent task should finish with the failed status.
        """
        fossa_command = {"model_class": "PartialFailure"}
        r = requests.post(
            self.fossa_api_url + "task",
            data=json.dumps(fossa_command),
            headers=self.api_headers,
        )

        self.assertEqual(200, r.status_code)

        task_submit_doc = r.json()
        task_url = task_submit_doc["_metadata"]["links"]["task"]

        # Wait for the task to be running
        while True:
            task_doc = requests.get(task_url).json()
            if "status" not in task_doc:
                # TODO - fix this work around upstream in Fossa. It happens when
                # a new task is in the queue from web frontend to the governor.
                time.sleep(0.1)
                continue

            elif task_doc["status"] == "running":
                time.sleep(0.1)
                continue
            else:
                break

        self.assertEqual("failed", task_doc["status"])

        failed_subtask_id = task_doc["results"]["payload"]["failure_origin_task_id"]
        failed_task_url = self.fossa_api_url + f"task/{failed_subtask_id}"
        failed_task_doc = requests.get(failed_task_url).json()

        self.assertEqual(
            "<class 'ZeroDivisionError'>",
            failed_task_doc["results"]["payload"]["exception_class_name"],
        )
