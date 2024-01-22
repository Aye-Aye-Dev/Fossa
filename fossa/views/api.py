"""
API views in JSON
"""
import os

from flask import Blueprint, current_app, jsonify
from fossa.utils import JsonException

api_views = Blueprint("api", __name__)


@api_views.route("/")
def index():
    page_vars = {"hello": "world"}
    return jsonify(page_vars)


@api_views.route("/task", methods=["POST"])
def submit_task():
    if not current_app.fossa_governor.has_processing_capacity:
        # 412 Precondition Failed
        raise JsonException(message="No spare processing capacity", status_code=412)

    x = current_app.fossa_governor.submit_task()

    xx = {k: v for k, v in current_app.fossa_governor.process_table.items()}

    page_vars = {
        "governor_says": x,
        "current_pid": os.getpid(),
        "proc_table": xx,
    }
    return jsonify(page_vars)
