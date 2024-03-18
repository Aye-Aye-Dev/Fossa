"""
Non-API views in HTML
"""
from flask import Blueprint, current_app, render_template

from fossa.views.controller import node_summary

web_views = Blueprint("web", __name__)


@web_views.route("/")
def index():
    "Summary page about the compute node"
    governor = current_app.fossa_governor
    page_vars = node_summary(governor)
    return render_template("web_root.html", **page_vars)
