from dataclasses import asdict
import json


def node_summary(governor):
    """
    @param governor: instance of :class:`fossa.control.governor.Governor`
    @return: dict with keys-
        - "recent_completed_tasks" - list of dict with details of task
                additional 'status' key which can have values-
                - running
                - failed
                - complete
                - unknown (indicates something missing in the code)
        - "running_tasks"
        - "node_info" - dict
    """
    node_info = {
        "node_ident": governor.governor_id,
        "max_concurrent_tasks": governor.runtime.max_concurrent_tasks,
        "available_processing_capacity": governor.available_processing_capacity.value,
    }

    # Just the details of what to execute. Results to be added here later.
    previous_tasks = []
    for t in governor.previous_tasks:
        summary = asdict(t["task_spec"])
        summary["started"] = t["started"]
        summary["finished"] = t["finished"]
        summary["results"] = json.loads(t["result_spec"].task_message)

        if summary["results"]["type"] == "TaskComplete":
            summary["status"] = "complete"
        elif summary["results"]["type"] == "TaskFailed":
            summary["status"] = "failed"
        else:
            summary["status"] = "unknown"

        previous_tasks.append(summary)

    previous_tasks.sort(key=lambda t: t["finished"], reverse=True)

    current_tasks = []
    for task_id, process_details in governor.process_table.items():
        process_extract = asdict(process_details["task_spec"])
        process_extract["task_id"] = task_id
        process_extract["started"] = process_details["started"]
        process_extract["status"] = "running"
        current_tasks.append(process_extract)

    current_tasks.sort(key=lambda t: t["started"], reverse=False)

    ns = {
        "running_tasks": current_tasks,
        "recent_completed_tasks": previous_tasks,
        "node_info": node_info,
    }

    return ns


def task_summary(governor, task_id):
    """
    Return info about the task. It could be currently running or a previous task.

    @return (dict) or None if task_id not known
        keys from :class:`TaskMessage`
    """

    ns = node_summary(governor)

    for t in ns["running_tasks"]:
        if t["task_id"] == task_id:
            return t

    for t in ns["recent_completed_tasks"]:
        if t["task_id"] == task_id:
            return t

    return None  # task not known
