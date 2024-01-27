import time

from fossa.control.message import TaskMessage, TerminateMessage

from tests.base import BaseTest
from tests.example_etl import SimpleExampleEtl


class TestGovernor(BaseTest):
    def test_available_processing_capacity(self):
        """
        The internal governor process should dynamically adjust the number of parallel processes
        it's able to run.
        """
        msg = (
            "Before the internal governor Process is running the processing "
            "capacity is unknown so set to 0"
        )
        self.assertEqual(0, self.governor.available_processing_capacity.value, msg)

        proc = self.governor.start_internal_processes()

        # poll every 100ms for a maximum of 5 seconds
        start_time = time.time()
        while time.time() < start_time + 5:
            capacity_observed = self.governor.available_processing_capacity.value
            if capacity_observed != 0:
                # this is the change that is being tested
                break
            time.sleep(0.1)

        # instruct the governor to stop
        self.governor._task_queue_submit.put(TerminateMessage())

        # wait for it to terminate
        proc.join()

        msg = "Capacity should have been adjusted to fit CPUs etc. of executing node"
        self.assertGreater(capacity_observed, 0, msg)

    def test_no_duplicates_set_accepted_class(self):
        self.governor.set_accepted_class(SimpleExampleEtl)
        with self.assertRaises(ValueError) as context:
            self.governor.set_accepted_class(SimpleExampleEtl)

        self.assertIn("already exists as an accepted class", str(context.exception))

    def test_submit_task(self):
        task_spec = TaskMessage(
            model_class="SimpleExampleEtl",
            method="go",
            method_kwargs={},
            resolver_context={},
            on_completion_callback=None,
        )

        with self.assertRaises(ValueError) as context:
            self.governor.submit_task(task_spec)

        self.assertIn("not in the list of accepted classes", str(context.exception))

        self.governor.set_accepted_class(SimpleExampleEtl)

        msg = "Should be allowed now"
        governor_id = self.governor.submit_task(task_spec)
        self.assertIsNotNone(governor_id, msg)
