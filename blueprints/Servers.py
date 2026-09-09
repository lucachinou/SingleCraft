import ast
import datetime
import json
import os
import shutil
import flask
import modules.MCProperties

from pathlib import Path
from modules.management import servers_logs, running_servers, start_server, stop_server, clear_console_history
from modules import database, MCProperties, management, LevelHandler

bp = flask.Blueprint('servers', __name__, url_prefix='/API/Servers')
servers_path = Path(__file__).parent.parent / "servers"
servers_path.mkdir(exist_ok=True)
jar_path = Path(__file__).parent.parent / "jar"
jar_path.mkdir(exist_ok=True)

@bp.get("/getEnabledFeatures")
def getEnabledFeatures():
    server_id = flask.request.args.get('server_id')
    if not database.is_connected(token=flask.request.cookies.get('token')):
        return flask.redirect(flask.url_for("BaseRoute.home"))
    if server_id is None:
        return flask.jsonify({"success": False, "message": "INVALID_PARAMETERS"})

    return flask.jsonify({"success": True, "enabled_features": LevelHandler.get_enabled_features(server_id)})

@bp.get("/getServerSettings")
def getServerSettings():
    server_id = flask.request.args.get('server_id')
    if not database.is_connected(token=flask.request.cookies.get('token')):
        return flask.jsonify({"success": False, "message": "INVALID_PARAMETERS"})
    if server_id is None:
        return flask.jsonify({"success": False, "message": "INVALID_PARAMETERS"})

    return flask.jsonify({"success": True, "settings": []})

@bp.get('/getName')
def getName():
    server_id = flask.request.args.get('server_id')
    if not database.is_connected(token=flask.request.cookies.get('token')):
        return flask.redirect(flask.url_for("BaseRoute.home"))
    if server_id is None:
        return flask.jsonify({"success": False, "message": "INVALID_PARAMETERS"})

    try:
        server_id = int(server_id)
    except (ValueError, TypeError):
        return flask.jsonify({"success": False, "error": "INVALID_PARAMETERS"})

    return flask.jsonify({"success": True, "name": database.getServerNameFromID(server_id)})

@bp.get('/getID')
def getID():
    server_name = flask.request.args.get('server_name')
    if not database.is_connected(token=flask.request.cookies.get('token')):
        return flask.redirect(flask.url_for("BaseRoute.home"))
    if server_name is None:
        return flask.jsonify({"success": False, "message": "INVALID_PARAMETERS"})

    try:
        server_id = int(server_name)
    except (ValueError, TypeError):
        return flask.jsonify({"success": False, "error": "INVALID_PARAMETERS"})

    return flask.jsonify({"success": True, "ID": server_name})

@bp.get('CanAccessGlobalSettings')
def canAccessGlobalSettings():
    token = flask.request.cookies.get('token')
    if token is None:
        return flask.jsonify({"success": False, "message": "INVALID_TOKEN"})
    user_id = database.GetUserIDByToken(token)
    rank = database.getUserRank(user_id)
    if user_id is None:
        return flask.jsonify({"success": False, "message": "INVALID_TOKEN"})
    # TODO: Allow admins to decrease the permission level required for global settings access instead of hard-coding the rank
    return flask.jsonify({"success": True, "can_access": rank == "ADMIN"})

@bp.delete('/ClearConsoleHistory')
def clearConsoleHistory():
    server_id = flask.request.args.get('server_id')
    if not database.is_connected(token=flask.request.cookies.get('token')):
        return flask.redirect(flask.url_for("BaseRoute.home"))
    if server_id is None:
        return flask.jsonify({"success": False, "message": "INVALID_PARAMETERS"})

    clear_console_history(server_id)
    return flask.jsonify({"success": True})

@bp.get('sendCommand')
def sendCommand():
    server_id = flask.request.args.get('server_id')
    command = flask.request.args.get('command')
    if server_id is None or command is None:
        return flask.jsonify({"success": False, "message": "INVALID_PARAMETERS"})
    if flask.request.cookies.get('token') is None:
        return flask.redirect(flask.url_for("BaseRoute.home"))

    permission = database.getPermission(database.GetUserIDByToken(flask.request.cookies.get("token")), int(server_id))

    conn = database.get_db_connection(os.getenv("DATABASE_NAME"))
    cursor = conn.cursor()
    cursor.execute("SELECT Access, `Rank` FROM Accounts WHERE Token = %s", (flask.request.cookies.get("token"),))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    if result is None:
        return flask.redirect(flask.url_for('BaseRoute.index'))

    if permission is None:
        if result[1] != "ADMIN":
            return flask.jsonify({"success": False, "message": "MISSING_PERMISSION"})

    try:
        server_id = int(server_id)
    except (ValueError, TypeError):
        return flask.jsonify({"success": False, "error": "INVALID_PARAMETERS"})

    if running_servers.get(server_id) is None:
        return flask.jsonify({"success": False, "message": "SERVER_NOT_RUNNING"})

    date = datetime.datetime.now()
    servers_logs[server_id].append(
        f"[{date.hour}:{date.minute}:{date.second}] [SingleCraft/INFO] {database.GetUsernameByToken(flask.request.cookies.get('token'))[0]} executed \"{command}\" ")
    running_servers[server_id].stdin.write(command + '\n')
    running_servers[server_id].stdin.flush()
    return flask.jsonify({"success": True})

@bp.post('/setServerPort')
def setServerPort():
    server_id = flask.request.args.get('server_id')
    server_port = flask.request.args.get('server_port')
    if flask.request.cookies.get('token') is None:
        return flask.redirect(flask.url_for("BaseRoute.home"))
    if server_id is None or server_port is None:
        return flask.jsonify({"success": False, "message": "INVALID_PARAMETERS"})
    try:
        server_id = int(server_id)
    except (ValueError, TypeError):
        return flask.jsonify({"success": False, "error": "INVALID_PARAMETERS"})

    permission = database.getPermission(database.GetUserIDByToken(flask.request.cookies.get("token")), int(server_id))

    conn = database.get_db_connection(os.getenv("DATABASE_NAME"))
    cursor = conn.cursor()
    cursor.execute("SELECT Access, `Rank` FROM Accounts WHERE Token = %s", (flask.request.cookies.get("token"),))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    if result is None:
        return flask.redirect(flask.url_for('BaseRoute.index'))

    if permission is None:
        if result[1] != "ADMIN":
            return flask.jsonify({"success": False, "message": "MISSING_PERMISSION"})

    properties = MCProperties.Properties(str(servers_path / f"server-{server_id}/server.properties"))
    properties.setValue("server-port", server_port)
    properties.save()
    return flask.jsonify({"success": True, "port": server_port})

@bp.get('/getServerPort')
def getServerPort():
    server_id = flask.request.args.get('server_id')
    if flask.request.cookies.get('token') is None:
        return flask.redirect(flask.url_for("BaseRoute.home"))
    if server_id is None:
        return flask.jsonify({"success": False, "message": "INVALID_PARAMETERS"})
    try:
        server_id = int(server_id)
    except (ValueError, TypeError):
        return flask.jsonify({"success": False, "error": "INVALID_PARAMETERS"})

    permission = database.getPermission(database.GetUserIDByToken(flask.request.cookies.get("token")), int(server_id))

    conn = database.get_db_connection(os.getenv("DATABASE_NAME"))
    cursor = conn.cursor()
    cursor.execute("SELECT Access, `Rank` FROM Accounts WHERE Token = %s", (flask.request.cookies.get("token"),))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    if result is None:
        return flask.redirect(flask.url_for('BaseRoute.index'))

    if permission is None:
        if result[1] != "ADMIN":
            return flask.jsonify({"success": False, "message": "MISSING_PERMISSION"})

    properties = MCProperties.Properties(str(servers_path / f"server-{server_id}/server.properties"))
    return flask.jsonify({"success": True, "port": properties.getValue("server-port")})

@bp.get('/getServerProperties')
def getServerProperties():
    server_id = flask.request.args.get('server_id')
    token = flask.request.cookies.get('token')
    if not database.is_connected(token=flask.request.cookies.get('token')):
        return flask.redirect(flask.url_for("BaseRoute.home"))
    if server_id is None:
        return flask.jsonify({"success": False, "message": "INVALID_PARAMETERS"})
    try:
        server_id = int(server_id)
    except (ValueError, TypeError):
        return flask.jsonify({"success": False, "error": "INVALID_PARAMETERS"})
    rank = database.getPermission(database.GetUserIDByToken(token), server_id)
    if rank != "owner":
        if rank != "admin":
            if rank != "mod":
                return flask.jsonify({"success": False, "message": "UNAUTHORIZED"})

    properties = MCProperties.Properties(str(servers_path / f"server-{server_id}/server.properties"))
    return flask.jsonify({"success": True, "server": properties})

@bp.get('/getServerJar')
def getServerJar():
    server_id = flask.request.args.get('server_id')

    if flask.request.cookies.get('token') is None:
        return flask.redirect(flask.url_for("BaseRoute.home"))
    if server_id is None:
        return flask.jsonify({"success": False, "message": "INVALID_PARAMETERS"})

    try:
        server_id = int(server_id)
    except (ValueError, TypeError):
        return flask.jsonify({"success": False, "error": "INVALID_PARAMETERS"})

    permission = database.getPermission(database.GetUserIDByToken(flask.request.cookies.get("token")), int(server_id))

    conn = database.get_db_connection(os.getenv("DATABASE_NAME"))
    cursor = conn.cursor()
    cursor.execute("SELECT Access, `Rank` FROM Accounts WHERE Token = %s", (flask.request.cookies.get("token"),))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    if result is None:
        return flask.redirect(flask.url_for('BaseRoute.index'))

    if permission is None:
        if result[1] != "ADMIN":
            return flask.jsonify({"success": False, "message": "MISSING_PERMISSION"})

    return flask.jsonify({"success": True, "jar": database.getServerJar(server_id)})

@bp.get('/getServerMemory')
def getServerMemory():
    server_id = flask.request.args.get('server_id')
    if not database.is_connected(token=flask.request.cookies.get('token')):
        return flask.redirect(flask.url_for("BaseRoute.home"))
    if server_id is None:
        return flask.jsonify({"success": False, "message": "INVALID_PARAMETERS"})
    try:
        server_id = int(server_id)
    except (ValueError, TypeError):
        return flask.jsonify({"success": False, "message": "INVALID_PARAMETERS"})
    rank = database.getUserRank(database.GetUserIDByToken(flask.request.cookies.get("token")))
    server_rank = database.getPermission(database.GetUserIDByToken(flask.request.cookies.get("token")), server_id)
    if server_rank != "owner":
        if rank != "ADMIN":
            return flask.jsonify({"success": False, "message": "UNAUTHORIZED"})
    return flask.jsonify({"success": True, "memory": database.getServerMemory(server_id)})

@bp.get('/setServerMemory')
def setServerMemory():
    server_id = flask.request.args.get('server_id')
    memory = flask.request.args.get('memory')
    if not database.is_connected(token=flask.request.cookies.get('token')):
        return flask.redirect(flask.url_for("BaseRoute.home"))
    if server_id is None or server_id is None:
        return flask.jsonify({"success": False, "message": "INVALID_PARAMETERS"})
    try:
        server_id = int(server_id)
    except (ValueError, TypeError):
        return flask.jsonify({"success": False, "error": "INVALID_PARAMETERS"})
    rank = database.getUserRank(database.GetUserIDByToken(flask.request.cookies.get("token")))
    server_rank = database.getPermission(database.GetUserIDByToken(flask.request.cookies.get("token")), server_id)
    if server_rank != "owner":
        if rank != "ADMIN":
            return flask.jsonify({"success": False, "message": "UNAUTHORIZED"})
    conn = database.get_db_connection(os.getenv("DATABASE_NAME"))
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE Servers SET Memory = %s WHERE ServerID = %s",
        (memory, server_id)
    )
    conn.commit()
    cursor.close()
    conn.close()
    return flask.jsonify({"success": True, "memory": memory})

@bp.get('/ChangeJar')
def changeJar():
    server_id = flask.request.args.get('server_id')
    server_jar = flask.request.args.get('server_jar')
    if flask.request.cookies.get('token') is None:
        return flask.redirect(flask.url_for("BaseRoute.home"))
    if server_id is None or server_jar is None:
        return flask.jsonify({"success": False, "message": "INVALID_PARAMETERS"})

    permission = database.getPermission(database.GetUserIDByToken(flask.request.cookies.get("token")), int(server_id))

    conn = database.get_db_connection(os.getenv("DATABASE_NAME"))
    cursor = conn.cursor()
    cursor.execute("SELECT Access, `Rank` FROM Accounts WHERE Token = %s", (flask.request.cookies.get("token"),))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    if result is None:
        return flask.redirect(flask.url_for('BaseRoute.index'))

    if permission is None:
        if result[1] != "ADMIN":
            return flask.jsonify({"success": False, "message": "MISSING_PERMISSION"})

    try:
        server_id = int(server_id)
    except (ValueError, TypeError):
        return flask.jsonify({"success": False, "error": "INVALID_PARAMETERS"})

    database.changeServerJar(server_id, server_jar)
    return flask.jsonify({"success": True, "jar": database.getServerJar(server_id)})

@bp.get("/getConsoleUpdate")
def getConsoleUpdate():
    server_id = flask.request.args.get('server_id')
    server_path = Path(servers_path / f"server-{server_id}")
    if server_id is None:
        return flask.jsonify({"success": False, "message": "INVALID_PARAMETERS"})
    try:
        server_id = int(server_id)
    except (ValueError, TypeError):
        return flask.jsonify({"success": False, "error": "INVALID_PARAMETERS"})
    if flask.request.cookies.get("token") is None or server_id is None or server_path.exists() is False:
        return flask.redirect(flask.url_for("BaseRoute.home"))
    if servers_logs.get(server_id) is None:
        servers_logs[server_id] = []

    permission = database.getPermission(database.GetUserIDByToken(flask.request.cookies.get("token")), int(server_id))

    conn = database.get_db_connection(os.getenv("DATABASE_NAME"))
    cursor = conn.cursor()
    cursor.execute("SELECT Access, `Rank` FROM Accounts WHERE Token = %s", (flask.request.cookies.get("token"),))
    result = cursor.fetchone()
    if result is None:
        cursor.close()
        conn.close()
        return flask.redirect(flask.url_for('BaseRoute.index'))

    if permission is None:
        if result[1] != "ADMIN":
            return flask.jsonify({"success": False, "message": "MISSING_PERMISSION"})

    last_elem_date = flask.request.args.get("last_elem_date")
    logs = []

    for index, log in enumerate(servers_logs[server_id]):
        if isinstance(log, dict):
            logs.append({
                "date": str(log.get("date", f"legacy-{index}")),
                "line": str(log.get("line", ""))
            })
            continue

        logs.append({"date": f"legacy-{index}", "line": str(log)})

    if not logs:
        return flask.jsonify({"success": True, "message": []})

    if not last_elem_date:
        return flask.jsonify({"success": True, "message": logs})

    new_messages = []
    last_message_found = False

    for log in logs:
        if last_message_found:
            new_messages.append(log)
            continue

        if str(log.get("date")) == str(last_elem_date):
            last_message_found = True

    if last_message_found:
        return flask.jsonify({"success": True, "message": new_messages})

    return flask.jsonify({"success": True, "message": logs})

@bp.get("/Start")
def start():
    server_id = flask.request.args.get("server_id")
    server_path = Path(servers_path / f"server-{server_id}")

    try:
        server_id = int(server_id)
    except (ValueError, TypeError):
        return flask.jsonify({"success": False, "error": "INVALID_PARAMETERS"})
    if not database.is_connected(token=flask.request.cookies.get('token')) or server_id is None or server_path.exists() is False:
        return flask.redirect(flask.url_for("BaseRoute.home"))
    if server_id in running_servers:
        return flask.jsonify({"success": False, "message": "ALREADY_RUNNING"})

    permission = database.getPermission(database.GetUserIDByToken(flask.request.cookies.get("token")), int(server_id))

    conn = database.get_db_connection(os.getenv("DATABASE_NAME"))
    cursor = conn.cursor()
    cursor.execute("SELECT Access, `Rank` FROM Accounts WHERE Token = %s", (flask.request.cookies.get("token"),))
    result = cursor.fetchone()
    if result is None:
        cursor.close()
        conn.close()
        return flask.redirect(flask.url_for('BaseRoute.index'))

    if permission is None:
        if result[1] != "ADMIN":
            return flask.jsonify({"success": False, "message": "MISSING_PERMISSION"})

    start_server(server_id, database.getServerJar(server_id))

    return flask.jsonify({"success": True})

@bp.get("/Stop")
def Stop():
    server_id = flask.request.args.get("server_id")
    server_path = Path(servers_path / f"server-{server_id}")

    try:
        server_id = int(server_id)
    except (ValueError, TypeError):
        return flask.jsonify({"success": False, "error": "INVALID_PARAMETERS"})
    if database.is_connected(token=flask.request.cookies.get("token")) or server_id is None or server_path.exists() is False:
        return flask.redirect(flask.url_for("BaseRoute.home"))
    if server_id not in running_servers:
        return flask.jsonify({"success": False, "message": "NOT_RUNNING"})

    conn = database.get_db_connection(os.getenv("DATABASE_NAME"))
    cursor = conn.cursor()
    cursor.execute("SELECT Access, `Rank` FROM Accounts WHERE Token = %s", (flask.request.cookies.get("token"),))
    result = cursor.fetchone()
    if result is None:
        cursor.close()
        conn.close()
        return flask.redirect(flask.url_for('BaseRoute.index'))

    permission = database.getPermission(database.GetUserIDByToken(flask.request.cookies.get("token")), int(server_id))

    if permission is None:
        if result[1] != "ADMIN":
            return flask.jsonify({"success": False, "message": "MISSING_PERMISSION"})

    stop_server(server_id)

    return flask.jsonify({"success": True})

@bp.get('/GetServers')
def GetServers():
    token = flask.request.cookies.get('token')
    if token is None:
        return flask.redirect(flask.url_for('BaseRoute.index'))

    conn = database.get_db_connection(os.getenv("DATABASE_NAME"))
    cursor = conn.cursor()
    cursor.execute("SELECT Access, `Rank` FROM Accounts WHERE Token = %s", (token,))
    result = cursor.fetchone()
    if result is None:
        cursor.close()
        conn.close()
        return flask.redirect(flask.url_for('BaseRoute.index'))

    if result[1] == "ADMIN":
        cursor.execute("SELECT ID, Name, Owner FROM servers")
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        servers_list = []

        for server in result:
            servers_list.append({"id": server[0], "name": server[1], "owner": database.GetUsernameByID(int(server[2]))})
        return flask.jsonify({"servers": servers_list})
    cursor.close()
    conn.close()

    if isinstance(result[0], bytes):
        servers_list = ast.literal_eval(result[0].decode())
    else:
        servers_list = ast.literal_eval(result[0])
    for server in servers_list:
        server['owner'] = database.GetUsernameByID(int(server['owner']))
    return flask.jsonify({"servers": servers_list})

@bp.post('/CreateServer')
def CreateServer():
    server_name = flask.request.form.get('name')
    if server_name is None:
        return flask.jsonify({"error": "MISSING_PARAMETERS"})

    token = flask.request.cookies.get('token')
    if not database.is_connected(token=flask.request.cookies.get('token')):
        return flask.redirect(flask.url_for("BaseRoute.home"))

    user_id = database.GetUserIDByToken(token)

    conn = database.get_db_connection(os.getenv("DATABASE_NAME"))
    cursor = conn.cursor()
    cursor.execute("INSERT INTO servers (ID, Name, Owner, jar, Memory) VALUES (DEFAULT, %s, %s, %s, DEFAULT)", (server_name, user_id, "Default.jar"))
    server_id = cursor.lastrowid
    conn.commit()

    server_path = Path(servers_path / f"server-{server_id}")
    server_path.mkdir(exist_ok=True)

    EulaFile = server_path / "eula.txt"
    EulaFile.touch()
    EulaFile.write_text(
        f"#By changing the setting below to TRUE you are indicating your agreement to our EULA (https://aka.ms/MinecraftEULA).\n#{datetime.datetime.now().astimezone().strftime('%a %b %d %H:%M:%S %Z %Y')}\neula=true")

    propertiesFile = servers_path / f"server-{server_id}/server.properties"
    propertiesFile.touch(exist_ok=True)
    propertiesFile.write_text(f"server-port=25565\nrcon.password=k9(S3@e2£|\nrcon.port=25575\nenable-rcon=true")

    cursor.execute("SELECT Access FROM Accounts WHERE Token = %s", (token,))
    result = cursor.fetchone()
    if result is None:
        return flask.jsonify({"success": False, "servers": "UNKNOWN"})

    if isinstance(result[0], bytes):
        servers_list = ast.literal_eval(result[0].decode())
    else:
        servers_list = ast.literal_eval(result[0])

    servers_list.append({"id": server_id, "name": server_name, "owner": user_id, 'rank': "owner"})
    cursor.execute("UPDATE Accounts SET Access = %s WHERE Token = %s", (json.dumps(servers_list), token,))
    conn.commit()
    cursor.close()
    conn.close()

    return flask.jsonify({"success": True, "servers": servers_list})

@bp.delete('/DeleteServer')
def DeleteServer():
    try:
        server_id = int(flask.request.args.get('server_id'))
    except (ValueError, TypeError):
        return flask.jsonify({"error": "INVALID_PARAMETERS"})

    token = flask.request.cookies.get('token')
    if token is None:
        return flask.redirect(flask.url_for('BaseRoute.home'))

    conn = database.get_db_connection(os.getenv("DATABASE_NAME"))
    cursor = conn.cursor()
    cursor.execute("SELECT ID, Access, `Rank` FROM Accounts WHERE Token = %s", (token,))
    result = cursor.fetchone()
    if result is None:
        return flask.redirect(flask.url_for('BaseRoute.home'))
    if isinstance(result[1], bytes):
        servers_list = ast.literal_eval(result[1].decode())
    else:
        servers_list = ast.literal_eval(result[1])
    server_index = next((i for i, server in enumerate(servers_list) if server.get("id") == server_id), None)

    if server_index is not None:
        servers_list.pop(server_index)

    if result[2] == "admin" or database.getPermission(result[0], int(server_id)) == "owner":
        conn = database.get_db_connection(os.getenv("DATABASE_NAME"))
        cursor = conn.cursor()
        cursor.execute("DELETE FROM servers WHERE ID = %s", (server_id,))
        cursor.execute("UPDATE Accounts SET Access = %s WHERE Token = %s", (json.dumps(servers_list), token,))
        conn.commit()
        cursor.close()
        conn.close()

        server_path = Path(servers_path / f"server-{server_id}")
        shutil.rmtree(server_path)
        return flask.jsonify({"success": True})
    return flask.redirect(flask.url_for('BaseRoute.home'))