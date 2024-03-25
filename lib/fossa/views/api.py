"""
API views in JSON
"""
from flask import Blueprint, current_app, jsonify, request

from fossa.control.governor import InvalidTaskSpec
from fossa.control.message import TaskMessage
from fossa.utils import JsonException
from fossa.views.controller import node_summary


api_views = Blueprint("api", __name__)


@api_views.route("/")
def index():
    page_vars = {"hello": "world"}
    return jsonify(page_vars)


def test_func(*args):
    # TODO make a proper call back for web posted tasks
    print("completed task", args)


@api_views.route("/task", methods=["POST"])
def submit_task():
    if not current_app.fossa_governor.has_processing_capacity:
        # 412 Precondition Failed
        raise JsonException(message="No spare processing capacity", status_code=412)

    request_doc = request.get_json()
    if "model_class" not in request_doc:
        raise JsonException(message="'model_class' is a mandatory field", status_code=400)

    task_attribs = {
        "model_class": request_doc["model_class"],
        "model_construction_kwargs": request_doc.get("model_construction_kwargs", {}),
        "method": request_doc.get("method", "go"),  # default for Ayeaye is to run the whole model
        "method_kwargs": request_doc.get("method_kwargs", {}),
        "resolver_context": request_doc.get("resolver_context", {}),
        "on_completion_callback": test_func,
    }
    new_task = TaskMessage(**task_attribs)

    # identifier for the governor process that accepted the task
    try:
        governor_id = current_app.fossa_governor.submit_task(new_task)
    except InvalidTaskSpec as e:
        raise JsonException(message=str(e), status_code=412)

    page_vars = {"governor_accepted_ident": governor_id}
    return jsonify(page_vars)


@api_views.route("/node_info")
def node_info():
    "Summary page about the compute node"
    governor = current_app.fossa_governor
    node_info = node_summary(governor)

    for task in node_info["recent_completed_tasks"]:
        # remove not serialisable
        for k, v in task.items():
            if callable(v):
                task[k] = None

    return jsonify(node_info)
