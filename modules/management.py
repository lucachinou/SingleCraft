import datetime
import os
import subprocess
from pathlib import Path
from mcrcon import MCRcon
from dotenv import load_dotenv
import atexit
from threading import Thread
import shlex

from modules.MCProperties import Properties
from modules import database

load_dotenv()

running_servers = {}
servers_logs = {}

SERVER_PATH = Path(Path.cwd() / "servers")
JAR_PATH = Path(Path.cwd() / "jar")

def start_server(server_id, jar_name):
    if server_id in running_servers: return False
    if server_id not in servers_logs: servers_logs[server_id] = []

    date = datetime.datetime.now()

    server_dir = SERVER_PATH / f"server-{server_id}"
    jar_path = JAR_PATH / jar_name

    if not jar_path.exists():
        servers_logs[server_id].append(f"[{date.strftime('%H:%M:%S')}] [SingleCraft/ERROR] jar file not found.")
        return "jar file not found", 404
    if not server_dir.exists():
        servers_logs[server_id].append(f"[{date.strftime('%H:%M:%S')}] [SingleCraft/ERROR] Server directory not found.")
        return "Server directory not found", 404

    if "spigot" in jar_name:
        if database.GetSetting(1) == "True":
            servers_logs[server_id].append(f"[{date.strftime('%H:%M:%S')}] [SingleCraft/WARN] Spigot servers are currently not supported due to a bug that affects commands.")
            return False
        else:
            servers_logs[server_id].append(f"[{date.strftime('%H:%M:%S')}] [SingleCraft/WARN] Spigot servers are currently experimental. Please use RCon instead of stdin.")

    server_dir.mkdir(parents=True, exist_ok=True)

    conn = database.get_db_connection(os.getenv("DATABASE_NAME"))
    cursor = conn.cursor()
    cursor.execute("SELECT Memory FROM servers WHERE ID = %s", (server_id,))
    MaxMemory = cursor.fetchone()

    cursor.execute("SELECT start_command FROM InstalledVersions WHERE file_name = %s", (jar_name,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    if result is None:
        servers_logs[server_id].append(f"[{date.strftime('%H:%M:%S')}] [SingleCraft/ERROR] Server version not found in database.")
        result = f"java -Xmx{MaxMemory[0]}M -jar {jar_path} nogui"
    else:
        result = result[0]

        if not "java" in result:
            servers_logs[server_id].append(f"[{date.strftime('%H:%M:%S')}] [SingleCraft/WARN] Custom files are currently experimental. Please report any issues you have!")

    command = result.format(max_memory=MaxMemory[0], file_name=str(jar_path))

    process = subprocess.Popen(
        shlex.split(command),
        cwd=server_dir,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    print(f"Running server: {server_id} with jar: {jar_name}")

    if servers_logs.get(server_id) is None:
        servers_logs[server_id] = []
    servers_logs[server_id].append(f"[{date.strftime('%H:%M:%S')}] [SingleCraft/INFO] Starting server.")
    running_servers[server_id] = process

    def read_output():
        for line in iter(process.stdout.readline, ''):
            servers_logs[server_id].append({"date": date.now(), "line": line})

    Thread(target=read_output, daemon=True).start()
    return True


def stop_server(server_id):
    process = None
    try:
        process = running_servers.get(server_id)
        date = datetime.datetime.now()

        if not process:
            servers_logs[server_id].append(
                f"[{date.hour}:{date.minute}:{date.second}] [SingleCraft/INFO] Server already stopped.")
            return False

        if database.GetSetting(2) == "False":
            servers_logs[server_id].append(
                f"[{date.hour}:{date.minute}:{date.second}] [SingleCraft/INFO] Server RCon disabled, using fallback method.")
            servers_logs[server_id].append(f"[{date.hour}:{date.minute}:{date.second}] [SingleCraft/INFO] Stopping server.")
            process.stdin.write("stop\n")
            process.stdin.flush()
            process.wait(timeout=10)
        else:
            server_properties = Properties(SERVER_PATH / f"Server-{server_id}" / "server.properties")
            server_port = server_properties.get("rcon.port")
            server_password = server_properties.get("rcon.password")
            with MCRcon("127.0.0.1", server_password, port=int(server_port)) as m:
                m.connect()
                m.command("stop")
                m.disconnect()
        del running_servers[server_id]
    except TimeoutError:
        process.kill()
        process.terminate()
        del running_servers[server_id]
    except OSError:
        del running_servers[server_id]
    return True

def stop_all_servers():
    copy = running_servers.copy()
    for server in copy:
        stop_server(server)

def clear_console_history(server_id):
    global servers_logs
    if not isinstance(servers_logs.get(server_id), list):
        print(type(servers_logs.get(server_id)))
        return False
    servers_logs[server_id].clear()
    return True

def get_console_output(server_name):
    if servers_logs.get(server_name) is None or servers_logs.get(server_name) == "[]":
        return ["No console history for this server!"]
    return servers_logs.get(server_name)

def get_console_latest_line(server_name):
    if servers_logs.get(server_name) is None or servers_logs.get(server_name) == "[]":
        return ["No console history for this server!"]
    try:
        return servers_logs.get(server_name)[-1]
    except AttributeError:
        return ["No console history for this server!"]

atexit.register(stop_all_servers)