import json
import os
import requests
import shutil
import tempfile
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
        self._working_directory = None

    def tearDown(self):
        self.fossa_integration_environment.stop()
        if self._working_directory and os.path.isdir(self._working_directory):
            shutil.rmtree(self._working_directory)

    def working_directory(self):
        self._working_directory = tempfile.mkdtemp()
        return self._working_directory

    def wait_for_task_status(self, task_url, desired_status, negate=False):
        """
        @param desired_status: (str or list of str)
            if None, return as soon as there is any status

        @param negate: bool
            any state *apart from* desired_state

        @return: task's doc when the status == `desired_status`
        """
        if isinstance(desired_status, str):
            _dstatus = [desired_status]
        elif isinstance(desired_status, list):
            _dstatus = desired_status
        else:
            raise ValueError("Unknown type")

        while True:
            r = requests.get(task_url)
            task_doc = r.json()

            if "status" not in task_doc:
                # TODO - fix this work around upstream in Fossa. It happens when
                # a new task is in the queue from web frontend to the governor.
                time.sleep(0.1)
                continue

            if negate:
                if task_doc["status"] in _dstatus:
                    time.sleep(0.1)
                    continue
            else:
                if task_doc["status"] not in _dstatus:
                    time.sleep(0.1)
                    continue

            return task_doc

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

        task_doc = self.wait_for_task_status(task_url, "complete")
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

        _task_doc = self.wait_for_task_status(task_url, "running")

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

        task_doc = self.wait_for_task_status(task_url, "running", negate=True)

        self.assertEqual("failed", task_doc["status"])

        failed_subtask_id = task_doc["results"]["payload"]["failure_origin_task_id"]
        failed_task_url = self.fossa_api_url + f"task/{failed_subtask_id}"
        failed_task_doc = requests.get(failed_task_url).json()

        self.assertEqual(
            "<class 'ZeroDivisionError'>",
            failed_task_doc["results"]["payload"]["exception_class_name"],
        )

    def test_retry_on_failed_subtask(self):
        """
        Each subtask in SecondTimeLucky will fail the first time it's run and succeed the second
        time.
        """
        working_space = self.working_directory()

        fossa_command = {
            "model_class": "SecondTimeLucky",
            "resolver_context": {"output_datasets": working_space},
        }
        r = requests.post(
            self.fossa_api_url + "task",
            data=json.dumps(fossa_command),
            headers=self.api_headers,
        )

        self.assertEqual(200, r.status_code)

        task_submit_doc = r.json()
        task_url = task_submit_doc["_metadata"]["links"]["task"]

        task_doc = self.wait_for_task_status(task_url, ["failed", "complete"])
        self.assertEqual("complete", task_doc["status"])

    def test_exceeds_available_processing_capacity(self):
        """
        This could end up as a flaky test as this is really a race condition.

        It's caused by many writes to the governor's task queue before the governor is able to
        process items on the queue.
        """

        fossa_command = {"model_class": "HalfSecondEtl"}

        start = time.time()
        loop_time = 0.5  # time given to inject tasks
        tasks_added = 0
        tasks_rejected = 0
        while time.time() < start + loop_time:
            r = requests.post(
                self.fossa_api_url + "task",
                data=json.dumps(fossa_command),
                headers=self.api_headers,
            )
            if r.status_code == 200:
                tasks_added += 1
            elif r.status_code == 503:
                tasks_rejected += 1
            else:
                raise ValueError(f"Unexpected status code: {r.status_code}")

        print(f"accepted: {tasks_added}  rejected: {tasks_rejected}")
        self.assertGreater(tasks_added, 0, "Zero tasks accepted")

        r = requests.get(self.fossa_api_url + "node_info")
        node_info = r.json()
        concurrent_allowed = node_info["node_info"]["max_concurrent_tasks"]

        msg = (
            "POST loop not fast enough for this test. The time given by 'loop_time' wasn't "
            "enough to generate enough tasks to give fossa the opportunity to get it wrong and "
            "run too many tasks."
        )
        self.assertGreater(tasks_added + tasks_rejected, concurrent_allowed, msg)

        msg = (
            "Should only accept/run 'max_concurrent_tasks' capacity tasks in half a second. "
            f"accepted: {tasks_added} rejected: {tasks_rejected} allowed: {concurrent_allowed}"
        )
        # Add a bit of tolerance around a small race condition that will be fixed in time.
        # The race condition allows for a slight under or over allocation of tasks
        tolerance = 1
        self.assertLessEqual(tasks_added, concurrent_allowed + tolerance, msg)

        max_concurrent_tasks = 0
        while True:
            node_info = requests.get(self.fossa_api_url + "node_info").json()
            concurrent_tasks = len(node_info["running_tasks"])
            print(concurrent_tasks)

            if concurrent_tasks == 0:
                # all tasks complete
                break

            max_concurrent_tasks = max(max_concurrent_tasks, concurrent_tasks)
            time.sleep(0.1)

        msg = (
            f"Concurrent tasks peaked at {max_concurrent_tasks}, max concurrent is "
            f"{concurrent_allowed}"
        )
        self.assertGreaterEqual(concurrent_allowed + tolerance, max_concurrent_tasks, msg)
