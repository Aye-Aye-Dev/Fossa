import hashlib
import time

import ayeaye
from ayeaye.common_pattern.connect_helper import MultiConnectorNewDataset


class NothingEtl(ayeaye.Model):
    "Test ETL model that doesn't ETL anything."

    def build(self):
        pass


class LongRunningEtl(ayeaye.Model):
    "Takes ages but does nothing; is used when working on Fossa"

    def build(self):
        total_loops = 60
        for i in range(total_loops):
            self.log(f"Loop {i} of {total_loops}")
            time.sleep(10)


class PartialFailure(ayeaye.PartitionedModel):
    """
    Create 4 pointless subtasks; one of the subtasks always fails. This model is used in tests.
    """

    def build(self):
        pass

    def partition_slice(self, _partition_count):
        subtasks = [("do_something", {"subtask_id": task_id}) for task_id in range(4)]
        return subtasks

    def do_something(self, subtask_id):
        return 1 / subtask_id


class SecondTimeLucky(ayeaye.PartitionedModel):
    """
    Sub-tasks only succeed the second time they are run. This model is used by an integration test
    to check failed task retries.
    """

    output_file_template = "csv://{output_datasets}/{subtask_id}_results.csv"
    subtask_docs = ayeaye.Connect(
        engine_url=[],
        method_overlay=(MultiConnectorNewDataset(template=output_file_template), "new_doc"),
        access=ayeaye.AccessMode.WRITE,
    )

    def build(self):
        pass

    def partition_slice(self, _partition_count):
        subtasks = [("build_document", {"doc_name": d}) for d in ["a", "b", "c"]]
        return subtasks

    def build_document(self, doc_name):
        doc = self.subtask_docs.new_doc(subtask_id=doc_name)

        # if the data source doesn't exist, create it and throw an exception. The second time the
        # subtask is run, the file will exist so no exception and subtask is considered a success.
        throw_a_wobbly = not doc.datasource_exists

        if throw_a_wobbly:
            doc.add({"name": "hello_world"})
            raise ValueError("Fake error")


class PartitionedExampleEtl(ayeaye.PartitionedModel):
    """
    Example task that can be split into independent subtasks.
    """

    def build(self):
        # bigger number means more compute needed
        # With complexity=4, the longest running sub-task takes approx 45 seconds on my Mac
        # When running all subtasks in parallel the longest task is the length of the overall task.
        self.complexity = 4

    def partition_slice(self, partition_count):
        md5_characters = "0123456789abcdef"
        subtasks = [
            ("crypto_challenge", {"ch": char, "count": self.complexity}) for char in md5_characters
        ]
        return subtasks

    def partition_subtask_complete(self, subtask_method_name, subtask_kwargs, subtask_return_value):
        msg = f"Subtask results are: {subtask_kwargs}, {subtask_return_value}"
        self.log(msg)

    def crypto_challenge(self, ch, count):
        """
        @param ch: ascii character found in an md5sum

        return an int which is the length of a string composed of 'ch'
        which has the md5sum starting with count number of 'ch'

        e.g.
        >>> crypto_challenge('a',3)
        27

        [si@buru ~]$ echo -n aaaaaaaaaaaaaaaaaaaaaaaaaaa | md5sum
        aaab9c59a88bf0bdfcb170546c5459d6  -
        [si@buru ~]$

        inspired by the bitcoin mining algorithm.
        """
        s = ""
        while True:
            md5 = hashlib.md5(s.encode("utf-8")).hexdigest()
            if md5[0:count] == str(ch) * count:
                return (ch, len(s))
            s += ch
