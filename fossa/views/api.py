"""
API views in JSON
"""
from flask import Blueprint, jsonify

api_views = Blueprint("api", __name__)


@api_views.route("/")
def index():
    page_vars = {"hello": "world"}
    return jsonify(page_vars)
