import json
import time

import boto3

from fossa.tools.logging import AbstractExternalLogger


class CloudwatchLogs(AbstractExternalLogger):
    """
    Send structured log messages to AWS' Cloudwatch logs facility.

    Install boto3 (`pip install boto3`) to use this.

    See https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/WhatIsCloudWatchLogs.html

    If you are using the one config file way to run Fossa, add an instance of this class to your
    config in the `EXTERNAL_LOGGERS` list.
    """

    def __init__(self, group_name, stream_name, region_name):
        """
        @param group_name: (str) - AWS cloudwatch logs's group name - must exist before running this
        @param stream_name: (str) - AWS cloudwatch logs's group name - must exist before running this
        @param region_name: (str) - AWS region, e.g. "eu-west-2"
        """
        self.group_name = group_name
        self.stream_name = stream_name
        self.region_name = region_name

        # lazy
        self._client = None

    def __getstate__(self):
        "Pickle safe so this logger can be moved between processes."
        return dict(
            group_name=self.group_name,
            stream_name=self.stream_name,
            region_name=self.region_name,
        )

    def __setstate__(self, state):
        "Pickle safe so this logger can be moved between processes."
        self.group_name = state["group_name"]
        self.stream_name = state["stream_name"]
        self.region_name = state["region_name"]
        self._client = None

    def __copy__(self):
        """
        Not sure how concurrency safe the boto3 client is so keep it safe by allowing explicit
        copying to create an independent version without the initalised boto3 client.
        """
        c = self.__class__(
            group_name=self.group_name,
            stream_name=self.stream_name,
            region_name=self.region_name,
        )
        return c

    @property
    def client(self):
        "boto3 client for cloudwatch logs"

        if self._client is None:
            self._client = boto3.client("logs", region_name=self.region_name)
        return self._client

    def write(self, msg, level="INFO"):
        "Send a message to Cloudwatch logs"

        structured_log = {
            "log_level": level,
            "message": msg,
        }
        serialised_msg = json.dumps(structured_log)

        response = self.client.put_log_events(
            logGroupName=self.group_name,
            logStreamName=self.stream_name,
            logEvents=[
                {
                    "timestamp": int(time.time() * 1000),  # milliseconds
                    "message": serialised_msg,
                },
            ],
        )

        # did the log work?
        return response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 200
