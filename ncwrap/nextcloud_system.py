"""
Gestione utenti sistema Linux e sincronizzazione password
"""
import subprocess
import shlex
import pwd
from typing import Optional


def user_exists(username: str) -> bool:
    """
    Verifica se un utente Linux esiste già
    
    Args:
        username: Nome utente da verificare
        
    Returns:
        True se l'utente esiste, False altrimenti
    """
    try:
        pwd.getpwnam(username)
        return True
    except KeyError:
        return False


def create_linux_user(username: str, password: str, create_home: bool = True) -> bool:
    """
    Crea un nuovo utente Linux con password
    
    Args:
        username: Nome utente (es. casacialde.com)
        password: Password dell'utente
        create_home: Se creare la directory home
        
    Returns:
        True se creazione riuscita, False altrimenti
        
    Note:
        Richiede privilegi root (sudo)
    """
    try:
        # Crea utente (ignora errore se esiste già)
        useradd_cmd = ["useradd"]
        if create_home:
            useradd_cmd.append("-m")
        useradd_cmd.append(username)
        
        result = subprocess.run(useradd_cmd, capture_output=True, text=True)
        
        # Se utente esiste già, non è un errore fatale
        if result.returncode != 0 and "already exists" not in result.stderr:
            print(f"Avviso useradd: {result.stderr.strip()}")
        
        # Imposta password
        chpasswd_input = f"{username}:{password}"
        subprocess.run(
            ["chpasswd"],
            input=chpasswd_input,
            text=True,
            check=True
        )
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Errore creazione utente Linux {username}: {e}")
        return False
    except Exception as e:
        print(f"Errore imprevisto: {e}")
        return False


def set_linux_password(username: str, new_password: str) -> bool:
    """
    Aggiorna password di un utente Linux esistente
    
    Args:
        username: Nome utente
        new_password: Nuova password
        
    Returns:
        True se aggiornamento riuscito, False altrimenti
    """
    try:
        # Verifica che l'utente esista
        if not user_exists(username):
            print(f"Errore: utente {username} non esiste")
            return False
        
        # Imposta nuova password
        chpasswd_input = f"{username}:{new_password}"
        subprocess.run(
            ["chpasswd"],
            input=chpasswd_input,
            text=True,
            check=True
        )
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Errore aggiornamento password Linux per {username}: {e}")
        return False


def get_user_info(username: str) -> Optional[dict]:
    """
    Recupera informazioni su un utente Linux
    
    Args:
        username: Nome utente
        
    Returns:
        Dict con info utente o None se non esiste
    """
    try:
        user_info = pwd.getpwnam(username)
        return {
            "username": user_info.pw_name,
            "uid": user_info.pw_uid,
            "gid": user_info.pw_gid,
            "home": user_info.pw_dir,
            "shell": user_info.pw_shell,
            "gecos": user_info.pw_gecos
        }
    except KeyError:
        return None


def sync_passwords(username: str, new_password: str) -> dict:
    """
    Sincronizza password su Nextcloud e sistema Linux
    
    Args:
        username: Nome utente
        new_password: Nuova password
        
    Returns:
        Dict con risultati delle operazioni
    """
    from .api import set_nc_password  # Import locale per evitare cicli
    
    results = {
        "nextcloud": False,
        "linux": False,
        "errors": []
    }
    
    # Aggiorna password Nextcloud
    try:
        set_nc_password(username, new_password)
        results["nextcloud"] = True
    except Exception as e:
        results["errors"].append(f"Nextcloud: {str(e)}")
    
    # Aggiorna password Linux
    if set_linux_password(username, new_password):
        results["linux"] = True
    else:
        results["errors"].append("Linux: fallimento aggiornamento password")
    
    return results


def delete_linux_user(username: str, remove_home: bool = False) -> bool:
    """
    Elimina un utente Linux
    
    Args:
        username: Nome utente da eliminare
        remove_home: Se eliminare anche la directory home
        
    Returns:
        True se eliminazione riuscita, False altrimenti
    """
    try:
        if not user_exists(username):
            print(f"Utente {username} non esiste")
            return True
        
        userdel_cmd = ["userdel"]
        if remove_home:
            userdel_cmd.append("-r")
        userdel_cmd.append(username)
        
        subprocess.run(userdel_cmd, check=True, capture_output=True, text=True)
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Errore eliminazione utente {username}: {e}")
        return False


def check_sudo_privileges() -> bool:
    """
    Verifica se il processo ha privilegi sudo necessari
    
    Returns:
        True se ha privilegi sufficienti
    """
    try:
        result = subprocess.run(
            ["sudo", "-n", "true"], 
            capture_output=True, 
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return False