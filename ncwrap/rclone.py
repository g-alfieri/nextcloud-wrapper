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
# Configurazioni per diversi scenari di hosting
HOSTING_MOUNT_OPTIONS = [
    "--vfs-cache-mode", "off",      # Zero cache locale, streaming puro
    "--buffer-size", "0",           # No buffer locale 
    "--vfs-read-chunk-size", "128M", # Chunk size per performance lettura
    "--vfs-read-chunk-size-limit", "2G", # Limite chunk per file grandi
    "--dir-cache-time", "5m",       # Cache solo metadata directory
    "--allow-other",
    "--read-only"                   # Mount read-only per sicurezza
]

MINIMAL_CACHE_OPTIONS = [
    "--vfs-cache-mode", "minimal",  # Cache minimal con auto-cleanup
    "--vfs-cache-max-size", "1G",   # Limite cache: max 1GB
    "--vfs-cache-max-age", "1h",    # Auto-cleanup dopo 1 ora
    "--buffer-size", "32M",
    "--dir-cache-time", "5m",
    "--allow-other"
]

WRITES_CACHE_OPTIONS = [
    "--vfs-cache-mode", "writes",   # Sync bidirezionale con cache intelligente
    "--vfs-cache-max-size", "2G",   # Limite cache: max 2GB (LRU cleanup)
    "--buffer-size", "64M",
    "--dir-cache-time", "10m",
    "--allow-other"
]

# Default: modalità writes per sync bidirezionale
DEFAULT_MOUNT_OPTIONS = WRITES_CACHE_OPTIONS

# Profili predefiniti
MOUNT_PROFILES = {
    "hosting": {
        "options": HOSTING_MOUNT_OPTIONS,
        "description": "Web hosting - streaming puro, zero cache locale",
        "use_case": "Apache/Nginx serving, SFTP read-only",
        "storage": "0 bytes (streaming)",
        "performance": "Network dependent",
        "sync": "Read-only, no uploads"
    },
    "minimal": {
        "options": MINIMAL_CACHE_OPTIONS, 
        "description": "Cache minimal con auto-cleanup intelligente",
        "use_case": "Hosting con cache temporanea",
        "storage": "Max 1GB, auto-cleanup",
        "performance": "Buona con cache",
        "sync": "Read-only, no uploads"
    },
    "writes": {
        "options": WRITES_CACHE_OPTIONS,
        "description": "Sync bidirezionale con cache file modificati",
        "use_case": "Editing files, sync automatico modifiche",
        "storage": "Max 2GB, persistente (LRU cleanup)",
        "performance": "Ottima con cache persistente",
        "sync": "Bidirezionale completo"
    }
}


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
                 profile: str = "writes", custom_options: Optional[List[str]] = None) -> bool:
    """
    Monta un remote rclone con profilo specifico
    
    Args:
        remote_name: Nome del remote da montare
        mount_point: Directory dove montare
        background: Se eseguire in background (daemon)
        profile: Profilo mount ("hosting", "minimal", "writes")
        custom_options: Opzioni personalizzate (sovrascrivono profilo)
        
    Returns:
        True se mount riuscito
    """
    ensure_config()
    ensure_dir(mount_point)
    
    cmd = [
        "rclone", "mount", f"{remote_name}:/", mount_point,
        "--config", str(RCLONE_CONF)
    ]
    
    # Usa opzioni custom o profilo
    if custom_options:
        cmd.extend(custom_options)
    elif profile in MOUNT_PROFILES:
        cmd.extend(MOUNT_PROFILES[profile]["options"])
    else:
        # Default: writes profile
        cmd.extend(DEFAULT_MOUNT_OPTIONS)
    
    # Modalità daemon se richiesta
    if background:
        cmd.append("--daemon")
    
    # Log comando per debug
    print(f"Mount command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Errore mount: {result.stderr}")
            return False
        
        # Mostra info profilo usato
        if profile in MOUNT_PROFILES:
            profile_info = MOUNT_PROFILES[profile]
            print(f"✅ Mount attivo con profilo '{profile}':")
            print(f"   📁 Storage: {profile_info['storage']}")
            print(f"   🔄 Sync: {profile_info['sync']}")
            print(f"   💾 Use case: {profile_info['use_case']}")
        
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


def get_mount_profile_info(profile: str) -> Optional[Dict]:
    """Recupera informazioni su un profilo mount"""
    return MOUNT_PROFILES.get(profile)


def list_mount_profiles() -> Dict[str, Dict]:
    """Lista tutti i profili mount disponibili"""
    return MOUNT_PROFILES


def estimate_storage_usage(profile: str, files_accessed_daily: int = 100, 
                          avg_file_size_mb: float = 1.0) -> str:
    """
    Stima uso storage per un profilo dato il pattern di accesso
    
    Args:
        profile: Nome profilo
        files_accessed_daily: File mediamente acceduti al giorno
        avg_file_size_mb: Dimensione media file in MB
        
    Returns:
        Stima uso storage come stringa
    """
    if profile == "hosting":
        return "0 MB (streaming puro - zero storage locale)"
    elif profile == "minimal":
        daily_cache = files_accessed_daily * avg_file_size_mb
        max_cache = min(daily_cache, 1024)  # Limite 1GB
        return f"~{max_cache:.0f} MB (con auto-cleanup ogni ora)"
    elif profile == "writes":
        return "Max 2GB (cache persistente con LRU cleanup)"
    else:
        return "Sconosciuto"


def create_systemd_mount_service(service_name: str, remote_name: str, 
                                mount_point: str, user: str = "root", 
                                profile: str = "writes") -> str:
    """
    Genera configurazione systemd per mount automatico con profilo
    
    Args:
        service_name: Nome del servizio (es. nextcloud-mount-user1)
        remote_name: Nome remote rclone
        mount_point: Punto di mount
        user: Utente che esegue il servizio
        profile: Profilo mount ("hosting", "minimal", "writes")
        
    Returns:
        Contenuto file .service
    """
    # Opzioni per profilo
    profile_options = {
        "hosting": "--vfs-cache-mode off --buffer-size 0 --read-only",
        "minimal": "--vfs-cache-mode minimal --vfs-cache-max-size 1G --buffer-size 32M", 
        "writes": "--vfs-cache-mode writes --vfs-cache-max-size 2G --buffer-size 64M"
    }
    
    mount_options = profile_options.get(profile, profile_options["writes"])
    
    service_content = f"""[Unit]
Description=RClone mount for {remote_name} -> {mount_point} (profile: {profile})
After=network-online.target
Wants=network-online.target
AssertPathIsDirectory={mount_point}

[Service]
Type=notify
User={user}
Group={user}
ExecStartPre=/bin/mkdir -p {mount_point}
ExecStart=/usr/bin/rclone mount {remote_name}:/ {mount_point} \\
    --config {RCLONE_CONF} \\
    {mount_options} \\
    --dir-cache-time 10m \\
    --allow-other \\
    --log-level INFO \\
    --log-file /var/log/rclone-{remote_name}.log
ExecStop=/bin/fusermount -u {mount_point}
Restart=on-failure
RestartSec=10
KillMode=process

[Install]
WantedBy=multi-user.target
"""
    return service_content
