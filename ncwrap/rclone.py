"""
Gestione rclone per sync e mount Nextcloud
"""
import os
import subprocess
import json
from pathlib import Path
from typing import List, Dict, Optional
from .utils import run, ensure_dir

# Configurazione globale
RCLONE_CONF = Path.home() / ".config" / "ncwrap" / "rclone.conf"
DEFAULT_MOUNT_OPTIONS = [
    "--vfs-cache-mode", "full",
    "--vfs-cache-max-age", "1h",
    "--buffer-size", "256M",
    "--dir-cache-time", "5m",
    "--allow-other"
]


def ensure_config():
    """Assicura che il file di configurazione rclone esista"""
    ensure_dir(RCLONE_CONF.parent)
    if not RCLONE_CONF.exists():
        RCLONE_CONF.write_text("")


def add_nextcloud_remote(name: str, base_url: str, username: str, password: str) -> bool:
    """
    Aggiunge un remote Nextcloud WebDAV a rclone
    
    Args:
        name: Nome del remote
        base_url: URL base Nextcloud (es. https://cloud.example.com)
        username: Username Nextcloud
        password: Password Nextcloud
        
    Returns:
        True se aggiunto con successo
    """
    ensure_config()
    
    webdav_url = f"{base_url.rstrip('/')}/remote.php/dav/files/{username}/"
    
    try:
        run([
            "rclone", "config", "create", name, "webdav",
            f"url={webdav_url}",
            f"user={username}",
            f"pass={password}",
            "vendor=nextcloud",
            "--config", str(RCLONE_CONF)
        ])
        return True
    except RuntimeError as e:
        print(f"Errore creazione remote {name}: {e}")
        return False


def remove_remote(name: str) -> bool:
    """Rimuove un remote dalla configurazione"""
    try:
        run(["rclone", "config", "delete", name, "--config", str(RCLONE_CONF)])
        return True
    except RuntimeError:
        return False


def list_remotes() -> List[str]:
    """Lista tutti i remote configurati"""
    try:
        output = run([
            "rclone", "listremotes", 
            "--config", str(RCLONE_CONF)
        ])
        return [line.rstrip(':') for line in output.split('\n') if line.strip()]
    except RuntimeError:
        return []


def mount_remote(remote_name: str, mount_point: str, background: bool = True, 
                 options: Optional[List[str]] = None) -> bool:
    """
    Monta un remote rclone su un punto di mount
    
    Args:
        remote_name: Nome del remote da montare
        mount_point: Directory dove montare
        background: Se eseguire in background (daemon)
        options: Opzioni aggiuntive per rclone mount
        
    Returns:
        True se mount riuscito
    """
    ensure_config()
    ensure_dir(mount_point)
    
    cmd = [
        "rclone", "mount", f"{remote_name}:/", mount_point,
        "--config", str(RCLONE_CONF)
    ]
    
    # Aggiungi opzioni di default
    cmd.extend(options or DEFAULT_MOUNT_OPTIONS)
    
    # Modalità daemon se richiesta
    if background:
        cmd.append("--daemon")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Errore mount: {result.stderr}")
            return False
        return True
    except Exception as e:
        print(f"Errore durante mount {remote_name}: {e}")
        return False


def unmount(mount_point: str) -> bool:
    """Smonta un punto di mount"""
    try:
        # Prova fusermount prima (più sicuro)
        run(["fusermount", "-u", mount_point], check=False)
        return True
    except:
        try:
            # Fallback su umount
            run(["umount", mount_point], check=False)
            return True
        except:
            return False


def is_mounted(mount_point: str) -> bool:
    """Verifica se un punto è montato"""
    try:
        output = run(["mount"], check=False)
        return mount_point in output
    except:
        return False


def sync_directories(source: str, dest: str, dry_run: bool = False, 
                    delete: bool = False) -> bool:
    """
    Sincronizza due directory con rclone sync
    
    Args:
        source: Directory sorgente (può essere remote:path)
        dest: Directory destinazione (può essere remote:path)
        dry_run: Solo simulazione senza modifiche
        delete: Elimina file nella destinazione non presenti nella sorgente
        
    Returns:
        True se sync riuscita
    """
    cmd = [
        "rclone", "sync", source, dest,
        "--config", str(RCLONE_CONF),
        "--progress"
    ]
    
    if dry_run:
        cmd.append("--dry-run")
    
    if delete:
        cmd.append("--delete-during")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Errore sync: {result.stderr}")
            return False
        return True
    except Exception as e:
        print(f"Errore durante sync: {e}")
        return False


def copy_files(source: str, dest: str, dry_run: bool = False) -> bool:
    """
    Copia file con rclone copy (non elimina file extra in dest)
    
    Args:
        source: Sorgente
        dest: Destinazione
        dry_run: Solo simulazione
        
    Returns:
        True se copia riuscita
    """
    cmd = [
        "rclone", "copy", source, dest,
        "--config", str(RCLONE_CONF),
        "--progress"
    ]
    
    if dry_run:
        cmd.append("--dry-run")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
    except:
        return False


def get_remote_info(remote_name: str) -> Optional[Dict]:
    """Recupera informazioni su un remote"""
    try:
        output = run([
            "rclone", "config", "show", remote_name,
            "--config", str(RCLONE_CONF)
        ])
        
        # Parsing semplificato della configurazione
        config = {}
        for line in output.split('\n'):
            if '=' in line and not line.strip().startswith('['):
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip()
        
        return config
    except:
        return None


def list_files(remote_path: str, max_depth: int = 1) -> List[str]:
    """Lista file in un remote path"""
    try:
        cmd = [
            "rclone", "lsf", remote_path,
            "--config", str(RCLONE_CONF)
        ]
        
        if max_depth > 1:
            cmd.extend(["--max-depth", str(max_depth)])
        
        output = run(cmd)
        return [line for line in output.split('\n') if line.strip()]
    except:
        return []


def check_connectivity(remote_name: str) -> bool:
    """Testa connettività con un remote"""
    try:
        run([
            "rclone", "lsd", f"{remote_name}:/",
            "--config", str(RCLONE_CONF)
        ])
        return True
    except:
        return False


def get_space_info(remote_name: str) -> Optional[Dict]:
    """Recupera informazioni spazio disponibile"""
    try:
        output = run([
            "rclone", "about", f"{remote_name}:/",
            "--config", str(RCLONE_CONF),
            "--json"
        ])
        return json.loads(output)
    except:
        return None


def create_systemd_mount_service(service_name: str, remote_name: str, 
                                mount_point: str, user: str = "root") -> str:
    """
    Genera configurazione systemd per mount automatico
    
    Args:
        service_name: Nome del servizio (es. nextcloud-mount-user1)
        remote_name: Nome remote rclone
        mount_point: Punto di mount
        user: Utente che esegue il servizio
        
    Returns:
        Contenuto file .service
    """
    service_content = f"""[Unit]
Description=RClone mount for {remote_name}
After=network.target
Wants=network.target

[Service]
Type=notify
User={user}
Group={user}
ExecStart=/usr/bin/rclone mount {remote_name}:/ {mount_point} \\
    --config {RCLONE_CONF} \\
    --vfs-cache-mode full \\
    --allow-other \\
    --daemon
ExecStop=/bin/fusermount -u {mount_point}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
"""
    return service_content
