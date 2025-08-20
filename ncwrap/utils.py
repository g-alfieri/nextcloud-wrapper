# utils.py - skeleton
import os
import subprocess

def run(cmd: list[str], check: bool = True) -> str:
    """Esegue un comando di sistema e ritorna stdout."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(f"Errore eseguendo {' '.join(cmd)}:\n{result.stderr}")
    return result.stdout.strip()

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)
