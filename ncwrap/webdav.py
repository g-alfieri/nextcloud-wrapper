# ncwrap/webdav.py
from pathlib import Path
from .rclone import RCLONE_CONF, ensure_config
from .utils import run

def add_remote(name: str, url: str, user: str, password: str):
    """Configura un remote WebDAV in rclone.conf"""
    ensure_config()
    run([
        "rclone", "config", "create", name, "webdav",
        f"url={url}",
        f"user={user}",
        f"pass={password}",
        "--config", str(RCLONE_CONF)
    ])

def remove_remote(name: str):
    run(["rclone", "config", "delete", name, "--config", str(RCLONE_CONF)])

