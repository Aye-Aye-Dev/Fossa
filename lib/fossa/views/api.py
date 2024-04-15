"""
API views in JSON
"""
import itertools

from flask import Blueprint, current_app, jsonify, request, url_for

from fossa.control.governor import InvalidTaskSpec
from fossa.control.message import TaskMessage
from fossa.utils import JsonException
from fossa.views.controller import node_summary, task_summary


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
    at_capacity_msg = "Node at full capacity and can't accept new tasks"

    if not current_app.fossa_governor.has_processing_capacity:
        # 503 Service Unavailable
        raise JsonException(message=at_capacity_msg, status_code=503)

    request_doc = request.get_json()
    if "model_class" not in request_doc:
        raise JsonException(message="'model_class' is a mandatory field", status_code=400)

    task_id = current_app.fossa_governor.new_task_id()
    task_attribs = {
        "task_id": task_id,
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

    if governor_id is None:
        raise JsonException(message=at_capacity_msg, status_code=503)

    api_url = url_for(
        "api.task_details",
        task_id=task_id,
        _external=True,
    )

    page_vars = {
        "_metadata": {"links": {"task": api_url}},
        "governor_accepted_ident": governor_id,
        "task_id": task_id,
    }
    return jsonify(page_vars)


@api_views.route("/task/<task_id>")
def task_details(task_id):
    governor = current_app.fossa_governor
    task_info = task_summary(governor, task_id)

    if task_info is None:
        return jsonify({"message": "task unknown"}), 404

    for k, v in task_info.items():
        if callable(v):
            task_info[k] = None

    return jsonify(task_info)


@api_views.route("/node_info")
def node_info():
    "Summary page about the compute node"
    governor = current_app.fossa_governor
    node_info = node_summary(governor)

    for task in itertools.chain(node_info["recent_completed_tasks"], node_info["running_tasks"]):
        # remove not serialisable
        for k, v in task.items():
            if callable(v):
                task[k] = None

    n_info = jsonify(node_info)
    return n_info
