from flask import Blueprint, render_template

blueprint = Blueprint("pages", __name__)


@blueprint.route("/")
def home():
    return render_template("index.html")
