"""
API views in JSON
"""
import os

from flask import Blueprint, current_app, jsonify

from fossa.control.message import TaskMessage
from fossa.utils import JsonException

api_views = Blueprint("api", __name__)


@api_views.route("/")
def index():
    page_vars = {"hello": "world"}
    return jsonify(page_vars)


def test_func(*args):
    print("completed task", args)


@api_views.route("/task", methods=["POST"])
def submit_task():
    if not current_app.fossa_governor.has_processing_capacity:
        # 412 Precondition Failed
        raise JsonException(message="No spare processing capacity", status_code=412)

    task_attribs = {
        "model_class": "todo",
        "method": "todo",
        "method_kwargs": {},
        "resolver_context": {},
        "on_completion_callback": test_func,
    }

    new_task = TaskMessage(**task_attribs)

    # identifier for the governor process that accepted the task
    governor_id = current_app.fossa_governor.submit_task(new_task)

    page_vars = {"governor_accepted_ident": governor_id}
    return jsonify(page_vars)
