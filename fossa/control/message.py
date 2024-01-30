from dataclasses import dataclass
from typing import Any, Callable, Optional


class AbstractMessage:
    "Just to mark-up subclasses as being types of message"
    pass


@dataclass
class TaskMessage(AbstractMessage):
    model_class: str
    method: str
    method_kwargs: dict
    resolver_context: dict
    on_completion_callback: Callable  # takes final_task_message (str), task_spec (this TaskMessage)
    task_id: Optional[str] = None


@dataclass
class ResultsMessage(AbstractMessage):
    """
    Return from running a task/subtask.
    """

    task_id: str
    task_message: Any  # subclass obj. of :class:`ayeaye.runtime.task_message.AbstractTaskMessage`


@dataclass
class TerminateMessage(AbstractMessage):
    """
    Used in unittests but could be used for graceful shutdown. Instructs the governor's long
    running process to terminate.
    """

    pass
