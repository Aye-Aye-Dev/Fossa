from dataclasses import asdict


def node_summary(governor):
    """
    @param governor: instance of :class:`fossa.control.governor.Governor`
    @return: dict with keys-
        - "recent_completed_tasks" - list of dict with details of task
        - "node_info" - list of tuples
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
        summary["results"] = t["result_spec"].task_message
        previous_tasks.append(summary)

    ns = {
        "recent_completed_tasks": previous_tasks,
        "node_info": node_info,
    }

    return ns
