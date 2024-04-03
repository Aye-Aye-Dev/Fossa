"""
Non-API views in HTML
"""
from flask import Blueprint, current_app, render_template

from fossa.views.controller import node_summary, task_summary

web_views = Blueprint("web", __name__)


@web_views.route("/")
def index():
    "Summary page about the compute node"
    governor = current_app.fossa_governor
    page_vars = node_summary(governor)
    return render_template("web_root.html", **page_vars)


@web_views.route("/task/<task_id>")
def task_details(task_id):
    "Info on both running and completed tasks"
    governor = current_app.fossa_governor
    task_details = task_summary(governor, task_id)
    if task_details is None:
        return "Task not found", 404
    page_vars = {"task": task_details}
    return render_template("task_details.html", **page_vars)
