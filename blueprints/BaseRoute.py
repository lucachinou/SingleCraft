import datetime
from pathlib import Path

import flask

from modules import database

bp = flask.Blueprint('BaseRoute', __name__, url_prefix='/')

@bp.route("/", methods=["GET", "POST"])
def index():
    if flask.request.method == "GET":
        return flask.render_template("index.html")
    else:
        return flask.jsonify({"message": "Running SingleCraft", "date": datetime.datetime.now().isoformat()})

@bp.get("/settings")
def settings():
    token = flask.request.cookies.get("token")
    if token is None:
        return flask.redirect(flask.url_for("BaseRoute.index"))
    g_rank = database.getUserRank(database.GetUserIDByToken(token))
    # TODO: Use setting instead of hard-coding the required rank to access the settings
    if g_rank != "ADMIN":
        return flask.redirect(flask.url_for("BaseRoute.home"))
    return flask.render_template("global_settings.html")

@bp.get("/server/<server_id>")
def get_server(server_id):
    token = flask.request.cookies.get("token")
    if token is None:
        return flask.redirect(flask.url_for("BaseRoute.index"))
    rank = database.getUserRank(database.GetUserIDByToken(token))
    permission = database.getPermission(database.GetUserIDByToken(token), int(server_id))
    if permission is None:
        if rank != "ADMIN":
            return flask.redirect(flask.url_for("BaseRoute.home"))
    return flask.render_template("server.html")

@bp.get("/server/<server_id>/settings")
def get_server_settings(server_id):
    token = flask.request.cookies.get("token")
    if token is None:
        return flask.redirect(flask.url_for("BaseRoute.index"))
    try:
        server_id = int(server_id)
    except (ValueError, TypeError):
        return flask.jsonify({"success": False, "message": "INVALID_PARAMETERS"})

    rank = database.getUserRank(database.GetUserIDByToken(token))
    permission = database.getPermission(database.GetUserIDByToken(token), int(server_id))
    if permission is None:
        if rank != "ADMIN":
            return flask.redirect(flask.url_for("BaseRoute.home"))
    return flask.render_template("server_settings.html")

@bp.get("/home")
def home():
    if flask.request.cookies.get("token"):
        return flask.render_template("home.html")
    else:
        return flask.redirect(flask.url_for("BaseRoute.index"))

@bp.get("/mcp")
def mcp():
    # TODO: Implement new secure routes for stop and start before implementing MCP
    return flask.jsonify({"work_in_progress": True})
    return flask.send_file(Path(__file__).parent.parent / "mcp.json")