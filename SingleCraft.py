import datetime
import os
import platform
import flask
import gunicorn
import logging
import dotenv
import sys
import blueprints.BlueprintsManager as Blueprints

from pathlib import Path
from modules import database

dotenv.load_dotenv()

logger = logging.getLogger(__name__)

if sys.version_info.major != 3 and sys.version_info.minor != 11:
    logger.warning(f"[!] SingleCraft is developed and tested on Python 3.11, not {sys.version_info}")

logger.warning("[!] SingleCraft is in early development, expect bugs and crashes. Please report them on the GitHub repository.")
logger.warning("[*] To run SingleCraft in the best conditions, please run 'pip install -r requirements.txt' (And install Argon2 on first launch to avoid older accounts being locked)")

if not Path(Path(__file__).parent.parent / ".env").exists():
    logger.warning("[!] Cannot find .env file, creating it...")
    Path(Path(__file__).parent.parent / ".env").touch()

if not os.getenv("DATABASE_NAME") or not os.getenv("DATABASE_USER") or not os.getenv("DATABASE_PASSWORD") or not os.getenv("DATABASE_HOST") or not os.getenv("DATABASE_PORT"):
    logger.error("[!] Unable to find database credentials from .env file. Please make sure to fill the .env file with the correct database credentials.")
    sys.exit()

logger.info(f"[*] Retrieved database information from .env file. \n\tDATABASE_HOST: {os.getenv('DATABASE_HOST')}\n\tDATABASE_USER: {os.getenv('DATABASE_USER')}\n\tDATABASE_PASSWORD: {os.getenv('DATABASE_PASSWORD')[0:5]+'***'}\n\tDATABASE_NAME: {os.getenv('DATABASE_NAME')}")

logger.info("[*] Checking database connection...")
try:
    mysql = database.get_db_connection(os.getenv("DATABASE_NAME"))
    mysql.close()
except RuntimeError as error:
    logger.warning("[!] Cannot connect to database")
    sys.exit()

logger.info("[*] Database connection successful.")

if not database.DatabaseUpdated():
    database.SetupDatabase()

app = flask.Flask(__name__)


Blueprints.register_blueprints(app)


class SingleCraftServer:
    """SingleCraft web server (decides whether to use Gunicorn or Waitress)."""

    OPTIONS = {
        "bind": "0.0.0.0:5500",
        "workers": 1,
        "threads": 8,
        "timeout": 120,
        "graceful_timeout": 30,
        "accesslog": "-",
        "errorlog": "-",
        "loglevel": "info",
    }
    using_flask_backend = True

    @classmethod
    def run(cls):
        if cls.using_flask_backend:
            logger.warning("[!] Currently running using Flask which is not recommended on a production server. Please install Gunicorn or Waitress (for Windows).")
            app.run(host="0.0.0.0", port=5500, debug=True)
            return
        if platform.system() == "Windows":
            cls._run_waitress()
        else:
            cls._run_gunicorn()

    @classmethod
    def _run_gunicorn(cls):
        try:
            from gunicorn.app.base import BaseApplication
        except ImportError:
            logger.error("[!] Gunicorn is not installed, run 'pip install gunicorn'.")
            return

        class SingleCraftApplication(BaseApplication):
            def __init__(self, flask_app, options=None):
                self.application = flask_app
                self.options = options or {}
                super().__init__()

            def load_config(self):
                for key, value in self.options.items():
                    if key in self.cfg.settings and value is not None:
                        self.cfg.set(key.lower(), value)

            def load(self):
                return self.application

        logger.info("[*] Starting SingleCraft with Gunicorn on %s", cls.OPTIONS["bind"])
        SingleCraftApplication(app, cls.OPTIONS).run()

    @classmethod
    def _run_waitress(cls):
        try:
            from waitress import serve
        except ImportError:
            logger.error("[!] Waitress is not installed, run 'pip install waitress'. Falling back to Flask.")
            app.run(host="0.0.0.0", port=5500, debug=False)
            return

        host, port = cls.OPTIONS["bind"].rsplit(":", 1)
        logger.info("[*] Gunicorn is not available on Windows, starting SingleCraft with Waitress on %s", cls.OPTIONS["bind"])
        serve(app, host=host, port=int(port), threads=cls.OPTIONS["threads"])


if __name__ == "__main__":
    SingleCraftServer.run()