"""
Utility functions per nextcloud-wrapper v0.3.0
"""
import os
import subprocess
import pwd
import shutil
import re
from pathlib import Path
from typing import Tuple, Optional


def run(cmd: list, check: bool = True) -> str:
    """Esegue un comando di sistema e ritorna stdout."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(f"Errore eseguendo {' '.join(cmd)}:\n{result.stderr}")
    return result.stdout.strip()


def ensure_dir(path: str) -> None:
    """Crea directory se non esiste"""
    os.makedirs(path, exist_ok=True)


def get_user_uid_gid(username: str) -> Tuple[int, int]:
    """Ottiene UID e GID di un utente"""
    try:
        user_info = pwd.getpwnam(username)
        return user_info.pw_uid, user_info.pw_gid
    except KeyError:
        raise ValueError(f"Utente {username} non trovato")


def is_command_available(command: str) -> bool:
    """Verifica se un comando è disponibile nel sistema"""
    return shutil.which(command) is not None


def is_mounted(path: str) -> bool:
    """Verifica se un percorso è montato"""
    try:
        # Metodo 1: controlla /proc/mounts
        with open('/proc/mounts', 'r') as f:
            mounts = f.read()
            return path in mounts
    except:
        try:
            # Metodo 2: usa comando mount
            result = run(["mount"], check=False)
            return path in result
        except:
            return False


def check_sudo_privileges() -> bool:
    """Verifica se il processo ha privilegi sudo necessari"""
    try:
        result = subprocess.run(
            ["sudo", "-n", "true"], 
            capture_output=True, 
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return False


def parse_size_to_bytes(size_str: str) -> int:
    """Converte stringa size in bytes (es. '1G' -> 1073741824)"""
    size_str = size_str.upper().strip()
    
    multipliers = {
        'B': 1,
        'K': 1024, 'KB': 1024,
        'M': 1024**2, 'MB': 1024**2,
        'G': 1024**3, 'GB': 1024**3,
        'T': 1024**4, 'TB': 1024**4
    }
    
    match = re.match(r'^(\d+(?:\.\d+)?)\s*([BKMGT]B?)$', size_str)
    if not match:
        raise ValueError(f"Formato size non valido: {size_str}")
    
    number, unit = match.groups()
    return int(float(number) * multipliers.get(unit, 1))


def bytes_to_human(bytes_val: int) -> str:
    """Converte bytes in formato human-readable"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024.0:
            return f"{bytes_val:.1f}{unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.1f}PB"


def validate_domain(domain: str) -> bool:
    """Valida formato dominio"""
    domain_pattern = re.compile(
        r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$'
    )
    return bool(domain_pattern.match(domain))


def validate_password(password: str) -> Tuple[bool, str]:
    """Valida robustezza password"""
    if len(password) < 8:
        return False, "Password troppo corta (minimo 8 caratteri)"
    
    if not re.search(r'[A-Z]', password):
        return False, "Password deve contenere almeno una lettera maiuscola"
    
    if not re.search(r'[a-z]', password):
        return False, "Password deve contenere almeno una lettera minuscola"
    
    if not re.search(r'\d', password):
        return False, "Password deve contenere almeno un numero"
    
    return True, "Password valida"


def backup_file(file_path: str) -> Optional[str]:
    """Crea backup di un file aggiungendo timestamp"""
    if not os.path.exists(file_path):
        return None
    
    import time
    timestamp = int(time.time())
    backup_path = f"{file_path}.backup.{timestamp}"
    
    try:
        shutil.copy2(file_path, backup_path)
        return backup_path
    except Exception:
        return None


def get_filesystem_type(path: str) -> str:
    """Rileva tipo filesystem per un percorso"""
    try:
        output = run(["findmnt", "-n", "-o", "FSTYPE", path])
        return output.strip().lower()
    except:
        return "unknown"


def get_available_space(path: str) -> int:
    """Ottiene spazio disponibile in bytes per un percorso"""
    try:
        stat = os.statvfs(path)
        return stat.f_bavail * stat.f_frsize
    except:
        return 0


def create_secure_temp_file(content: str, suffix: str = '.tmp') -> str:
    """Crea file temporaneo sicuro con contenuto"""
    import tempfile
    fd, temp_path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(content)
        os.chmod(temp_path, 0o600)
        return temp_path
    except:
        os.unlink(temp_path)
        raise


def atomic_write(file_path: str, content: str, mode: int = 0o644) -> bool:
    """Scrive file atomicamente (write + move)"""
    try:
        temp_path = f"{file_path}.tmp.{os.getpid()}"
        
        with open(temp_path, 'w') as f:
            f.write(content)
        
        os.chmod(temp_path, mode)
        os.rename(temp_path, file_path)
        return True
    except Exception:
        try:
            os.unlink(temp_path)
        except:
            pass
        return False


def get_system_info() -> dict:
    """Ottiene informazioni sistema"""
    info = {}
    
    try:
        # OS release
        with open('/etc/os-release', 'r') as f:
            for line in f:
                if line.startswith('PRETTY_NAME='):
                    info['os'] = line.split('=')[1].strip().strip('"')
                    break
    except:
        info['os'] = 'Unknown'
    
    try:
        # Kernel
        info['kernel'] = run(['uname', '-r'])
    except:
        info['kernel'] = 'Unknown'
    
    try:
        # Memory
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                if line.startswith('MemTotal:'):
                    mem_kb = int(line.split()[1])
                    info['memory'] = bytes_to_human(mem_kb * 1024)
                    break
    except:
        info['memory'] = 'Unknown'
    
    try:
        # Load average
        with open('/proc/loadavg', 'r') as f:
            info['load'] = f.read().split()[0]
    except:
        info['load'] = 'Unknown'
    
    return info


def format_table_data(data: list, headers: list) -> str:
    """Formatta dati in tabella ASCII semplice"""
    if not data:
        return "Nessun dato da mostrare"
    
    # Calcola larghezza colonne
    col_widths = [len(h) for h in headers]
    for row in data:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))
    
    # Crea formato riga
    row_format = " | ".join(f"{{:<{w}}}" for w in col_widths)
    separator = "-+-".join("-" * w for w in col_widths)
    
    # Costruisci tabella
    lines = []
    lines.append(row_format.format(*headers))
    lines.append(separator)
    
    for row in data:
        lines.append(row_format.format(*[str(cell) for cell in row]))
    
    return "\n".join(lines)


def safe_remove_file(file_path: str) -> bool:
    """Rimuove file in modo sicuro"""
    try:
        if os.path.exists(file_path):
            os.unlink(file_path)
        return True
    except:
        return False


def safe_remove_directory(dir_path: str, recursive: bool = False) -> bool:
    """Rimuove directory in modo sicuro"""
    try:
        if os.path.exists(dir_path):
            if recursive:
                shutil.rmtree(dir_path)
            else:
                os.rmdir(dir_path)
        return True
    except:
        return False


def get_directory_size(path: str) -> int:
    """Calcola dimensione directory in bytes"""
    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(file_path)
                except:
                    pass
    except:
        pass
    return total_size


def is_port_open(host: str, port: int, timeout: int = 5) -> bool:
    """Verifica se una porta è aperta"""
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False


def get_public_ip() -> Optional[str]:
    """Ottiene IP pubblico del server"""
    try:
        import urllib.request
        response = urllib.request.urlopen('https://api.ipify.org', timeout=10)
        return response.read().decode('utf-8').strip()
    except:
        return None


def wait_for_condition(condition_func, timeout: int = 30, interval: float = 1.0) -> bool:
    """Attende che una condizione sia vera"""
    import time
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        if condition_func():
            return True
        time.sleep(interval)
    
    return False


def random_string(length: int = 16, charset: str = None) -> str:
    """Genera stringa casuale"""
    import random
    import string
    
    if charset is None:
        charset = string.ascii_letters + string.digits
    
    return ''.join(random.choice(charset) for _ in range(length))


def hash_password(password: str) -> str:
    """Hash sicuro di una password"""
    import hashlib
    import secrets
    
    salt = secrets.token_hex(16)
    hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return f"{salt}:{hash_obj.hex()}"


def verify_password_hash(password: str, hash_str: str) -> bool:
    """Verifica password contro hash"""
    import hashlib
    
    try:
        salt, stored_hash = hash_str.split(':')
        hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return hash_obj.hex() == stored_hash
    except:
        return False
