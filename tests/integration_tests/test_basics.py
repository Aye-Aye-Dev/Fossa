import csv
import json
import os
import requests
import shutil
import tempfile
import time
import unittest

from examples.example_etl import StaggeredEtl
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

        # print(f"accepted: {tasks_added}  rejected: {tasks_rejected}")
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
            # print(concurrent_tasks)

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

    def test_rate_limiting(self):
        """
        Rough check of rate limiting.

        Run a fixed number of sub-tasks that sleep with 2 and then 12 workers.

        Total processing time for the tasks will be similar but total running time will be much
        slower for 2 workers.
        """

        working_space = self.working_directory()

        results = {}
        worker_allocations = [2, 12]
        for worker_count in worker_allocations:
            fossa_command = {
                "model_class": "StaggeredEtl",
                "resolver_context": {
                    "output_datasets": working_space,
                    "requested_workers": str(worker_count),
                },
            }
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

            output_file = os.path.join(working_space, "staggered_results.csv")
            first = None
            last = None
            processing_time = 0.0
            with open(output_file, encoding="utf-8-sig") as f:
                r = csv.DictReader(f)
                for x in r:
                    start = float(x["started"])
                    finish = float(x["finished"])

                    if first is None:
                        first = start

                    last = finish
                    processing_time += finish - start

            running_time = last - first
            results[worker_count] = dict(
                first=first,
                last=last,
                running_time=running_time,
                processing_time=processing_time,
            )

        # The time taken by fossa to distribute tasks and return results isn't fixed so the following
        # checks could be flaky.
        # seconds
        minimum_possible_processing_time = StaggeredEtl.sub_tasks_count * StaggeredEtl.sleep_time
        expected_upper_bound_process_time = minimum_possible_processing_time + 1

        for worker_count, result in results.items():
            msg = f"For worker_count:{worker_count}, processing time was higher than expected"
            self.assertLessEqual(result["processing_time"], expected_upper_bound_process_time, msg)

        msg = (
            "12 vs. 2 workers should be 6 times faster but because of how message passing works"
            " the gain should actually be higher."
        )
        wa_12 = worker_allocations[1]  # i.e. == 12
        wa_2 = worker_allocations[0]  # == 2
        expected_minimum_speed_gain = wa_12 / wa_2
        actual_speed_gain = results[wa_2]["running_time"] / results[wa_12]["running_time"]

        self.assertGreaterEqual(actual_speed_gain, expected_minimum_speed_gain, msg)

        msg = "The processing time should be similar for both"
        delta = abs(results[wa_12]["processing_time"] - results[wa_2]["processing_time"])
        self.assertLessEqual(delta, 1, msg)
