import time

from tests.base import BaseTest

from fossa.control.message import TerminateMessage


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

        proc = self.governor.start_internal_process()

        # poll every 100ms for a maximum of 5 seconds
        start_time = time.time()
        while time.time() < start_time + 5:
            capacity_observed = self.governor.available_processing_capacity.value
            if capacity_observed != 0:
                # this is the change that is being tested
                break
            time.sleep(0.1)

        # instruct the governor to stop
        self.governor._work_queue_submit.send(TerminateMessage())

        # wait for it to terminate
        proc.join()

        msg = "Capacity should have been adjusted to fit CPUs etc. of executing node"
        self.assertGreater(capacity_observed, 0, msg)
