"""
Non-API views in HTML
"""
from flask import Blueprint, render_template

web_views = Blueprint("web", __name__)


@web_views.route("/")
def index():
    page_vars = {}
    return render_template("web_root.html", **page_vars)
