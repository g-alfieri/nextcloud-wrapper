# ncwrap/users.py
import os
import pwd
import subprocess
from pathlib import Path
from .utils import ensure_dir

def add_user(username: str, homedir: str):
    try:
        pwd.getpwnam(username)
        print(f"Utente {username} già esistente")
        return
    except KeyError:
        pass
    subprocess.run(["useradd", "-m", "-d", homedir, username], check=True)
    ensure_dir(homedir)

def del_user(username: str):
    subprocess.run(["userdel", "-r", username], check=True)

