import hashlib

import ayeaye


class NothingEtl(ayeaye.Model):
    "Test ETL model that doesn't ETL anything."

    def build(self):
        pass


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
