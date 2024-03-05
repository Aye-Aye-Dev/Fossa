"""
Non-API views in HTML
"""
from dataclasses import asdict
from flask import Blueprint, current_app, render_template

web_views = Blueprint("web", __name__)


@web_views.route("/")
def index():
    "Summary page about the compute node"

    governor = current_app.fossa_governor
    node_info = [
        ("Node identifier", governor.governor_id),
        ("Max concurrent tasks", governor.runtime.max_concurrent_tasks),
        ("Available processing capacity", governor.available_processing_capacity.value),
    ]

    # Just the details of what to execute. Results to be added here later.
    previous_tasks = []
    for t in governor.previous_tasks:
        summary = asdict(t["task_spec"])
        summary["started"] = t["started"]
        summary["finished"] = t["finished"]
        summary["results"] = t["result_spec"].task_message
        previous_tasks.append(summary)

    page_vars = {
        "recent_completed_tasks": previous_tasks,
        "node_info": node_info,
    }
    return render_template("web_root.html", **page_vars)
