"""
Gestione utenti sistema Linux e sincronizzazione password per Nextcloud Wrapper v0.3.0
"""
import subprocess
import shlex
import pwd
import grp
import os
from typing import Optional, Dict, List
from .utils import run, get_user_uid_gid


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


def group_exists(groupname: str) -> bool:
    """
    Verifica se un gruppo Linux esiste
    
    Args:
        groupname: Nome gruppo da verificare
        
    Returns:
        True se il gruppo esiste, False altrimenti
    """
    try:
        grp.getgrnam(groupname)
        return True
    except KeyError:
        return False


def create_linux_user(username: str, password: str, create_home: bool = True,
                     groups: List[str] = None, shell: str = "/bin/bash") -> bool:
    """
    Crea un nuovo utente Linux con password
    
    Args:
        username: Nome utente (es. casacialde.com)
        password: Password dell'utente
        create_home: Se creare la directory home
        groups: Lista gruppi aggiuntivi
        shell: Shell di default
        
    Returns:
        True se creazione riuscita, False altrimenti
        
    Note:
        Richiede privilegi root (sudo)
    """
    try:
        # Costruisci comando useradd
        useradd_cmd = ["useradd"]
        
        if create_home:
            useradd_cmd.append("-m")
        
        # Shell personalizzata
        if shell != "/bin/bash":
            useradd_cmd.extend(["-s", shell])
        
        # Gruppi aggiuntivi
        if groups:
            # Verifica che i gruppi esistano
            existing_groups = [g for g in groups if group_exists(g)]
            if existing_groups:
                useradd_cmd.extend(["-G", ",".join(existing_groups)])
        
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
        
        print(f"✅ Utente Linux creato: {username}")
        
        # Configura ambiente utente se home creata
        if create_home:
            setup_user_environment(username)
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Errore creazione utente Linux {username}: {e}")
        return False
    except Exception as e:
        print(f"❌ Errore imprevisto: {e}")
        return False


def setup_user_environment(username: str) -> bool:
    """
    Configura ambiente base per nuovo utente
    
    Args:
        username: Nome utente
        
    Returns:
        True se configurazione riuscita
    """
    try:
        home_dir = f"/home/{username}"
        
        if not os.path.exists(home_dir):
            return False
        
        # Ottieni UID/GID utente
        uid, gid = get_user_uid_gid(username)
        
        # File di configurazione base
        config_files = {
            ".bashrc": _generate_bashrc_content(username),
            ".profile": _generate_profile_content(username),
            ".bash_aliases": _generate_aliases_content(username)
        }
        
        for filename, content in config_files.items():
            file_path = os.path.join(home_dir, filename)
            
            # Non sovrascrivere se esiste già
            if not os.path.exists(file_path):
                try:
                    with open(file_path, 'w') as f:
                        f.write(content)
                    
                    # Imposta ownership corretto
                    os.chown(file_path, uid, gid)
                    os.chmod(file_path, 0o644)
                    
                except Exception as e:
                    print(f"⚠️ Avviso creazione {filename}: {e}")
        
        # Crea directory utili
        useful_dirs = [".ssh", ".config", ".local/bin", ".cache"]
        for dir_name in useful_dirs:
            dir_path = os.path.join(home_dir, dir_name)
            if not os.path.exists(dir_path):
                try:
                    os.makedirs(dir_path, mode=0o700 if dir_name == ".ssh" else 0o755)
                    os.chown(dir_path, uid, gid)
                except Exception as e:
                    print(f"⚠️ Avviso creazione directory {dir_name}: {e}")
        
        print(f"✅ Ambiente utente configurato: {username}")
        return True
        
    except Exception as e:
        print(f"❌ Errore configurazione ambiente {username}: {e}")
        return False


def _generate_bashrc_content(username: str) -> str:
    """Genera contenuto .bashrc personalizzato"""
    return f"""# .bashrc for {username} - Generated by nextcloud-wrapper

# If not running interactively, don't do anything
case $- in
    *i*) ;;
      *) return;;
esac

# History settings
HISTCONTROL=ignoreboth
HISTSIZE=1000
HISTFILESIZE=2000
shopt -s histappend

# Check window size after each command
shopt -s checkwinsize

# Make less more friendly for non-text input files
[ -x /usr/bin/lesspipe ] && eval "$(SHELL=/bin/sh lesspipe)"

# Set variable identifying the chroot you work in
if [ -z "${{debian_chroot:-}}" ] && [ -r /etc/debian_chroot ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi

# Set a fancy prompt
case "$TERM" in
    xterm-color|*-256color) color_prompt=yes;;
esac

if [ "$color_prompt" = yes ]; then
    PS1='${{debian_chroot:+($debian_chroot)}}\\[\\033[01;32m\\]\\u@\\h\\[\\033[00m\\]:\\[\\033[01;34m\\]\\w\\[\\033[00m\\]\\$ '
else
    PS1='${{debian_chroot:+($debian_chroot)}}\\u@\\h:\\w\\$ '
fi
unset color_prompt

# Enable color support of ls and add handy aliases
if [ -x /usr/bin/dircolors ]; then
    test -r ~/.dircolors && eval "$(dircolors -b ~/.dircolors)" || eval "$(dircolors -b)"
    alias ls='ls --color=auto'
    alias grep='grep --color=auto'
    alias fgrep='fgrep --color=auto'
    alias egrep='egrep --color=auto'
fi

# Load aliases
if [ -f ~/.bash_aliases ]; then
    . ~/.bash_aliases
fi

# Programmable completion
if ! shopt -oq posix; then
  if [ -f /usr/share/bash-completion/bash_completion ]; then
    . /usr/share/bash-completion/bash_completion
  elif [ -f /etc/bash_completion ]; then
    . /etc/bash_completion
  fi
fi

# Nextcloud wrapper environment
export NEXTCLOUD_USER="{username}"
export PATH="$HOME/.local/bin:$PATH"

# Welcome message
echo "🌐 Nextcloud WebDAV Home: $HOME"
echo "💡 Tip: Files modified here are automatically synced to Nextcloud!"
"""


def _generate_profile_content(username: str) -> str:
    """Genera contenuto .profile personalizzato"""
    return f"""# .profile for {username} - Generated by nextcloud-wrapper

# Set PATH so it includes user's private bin if it exists
if [ -d "$HOME/.local/bin" ] ; then
    PATH="$HOME/.local/bin:$PATH"
fi

# Set PATH so it includes user's private bin if it exists
if [ -d "$HOME/bin" ] ; then
    PATH="$HOME/bin:$PATH"
fi

# Nextcloud environment
export NEXTCLOUD_USER="{username}"

# If running bash
if [ -n "$BASH_VERSION" ]; then
    # Include .bashrc if it exists
    if [ -f "$HOME/.bashrc" ]; then
        . "$HOME/.bashrc"
    fi
fi
"""


def _generate_aliases_content(username: str) -> str:
    """Genera contenuto .bash_aliases personalizzato"""
    return f"""# .bash_aliases for {username} - Generated by nextcloud-wrapper

# Basic aliases
alias ll='ls -alF'
alias la='ls -A'
alias l='ls -CF'

# Safety aliases
alias rm='rm -i'
alias cp='cp -i'
alias mv='mv -i'

# Directory navigation
alias ..='cd ..'
alias ...='cd ../..'
alias ....='cd ../../..'

# System info
alias df='df -h'
alias du='du -h'
alias free='free -h'
alias ps='ps aux'

# Nextcloud specific aliases
alias nc-status='mount | grep davfs'
alias nc-space='df -h $HOME'
alias nc-quota='echo "User: {username}" && df -h $HOME'

# Development helpers
alias ll='ls -la'
alias tree='tree -C'
alias grep='grep --color=auto'

# Quick file operations
alias backup='tar -czf backup-$(date +%Y%m%d-%H%M%S).tar.gz'
alias extract='tar -xzf'

# Network tools
alias myip='curl -s ifconfig.me'
alias ports='netstat -tuln'

# Log viewing
alias syslog='sudo tail -f /var/log/syslog'
alias accesslog='sudo tail -f /var/log/apache2/access.log'
alias errorlog='sudo tail -f /var/log/apache2/error.log'
"""


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
            print(f"❌ Errore: utente {username} non esiste")
            return False
        
        # Imposta nuova password
        chpasswd_input = f"{username}:{new_password}"
        subprocess.run(
            ["chpasswd"],
            input=chpasswd_input,
            text=True,
            check=True
        )
        
        print(f"✅ Password Linux aggiornata: {username}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Errore aggiornamento password Linux per {username}: {e}")
        return False


def get_user_info(username: str) -> Optional[Dict]:
    """
    Recupera informazioni complete su un utente Linux
    
    Args:
        username: Nome utente
        
    Returns:
        Dict con info utente o None se non esiste
    """
    try:
        user_info = pwd.getpwnam(username)
        
        # Info gruppi
        groups = []
        for group in grp.getgrall():
            if username in group.gr_mem or group.gr_gid == user_info.pw_gid:
                groups.append(group.gr_name)
        
        # Info home directory
        home_stats = {}
        if os.path.exists(user_info.pw_dir):
            from .utils import get_directory_size, bytes_to_human
            
            stat = os.stat(user_info.pw_dir)
            home_stats = {
                "exists": True,
                "size": bytes_to_human(get_directory_size(user_info.pw_dir)),
                "permissions": oct(stat.st_mode)[-3:],
                "last_modified": stat.st_mtime
            }
        else:
            home_stats = {"exists": False}
        
        return {
            "username": user_info.pw_name,
            "uid": user_info.pw_uid,
            "gid": user_info.pw_gid,
            "home": user_info.pw_dir,
            "shell": user_info.pw_shell,
            "gecos": user_info.pw_gecos,
            "groups": groups,
            "home_stats": home_stats
        }
        
    except KeyError:
        return None


def sync_passwords(username: str, new_password: str) -> Dict:
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
        print(f"✅ Password Nextcloud aggiornata: {username}")
    except Exception as e:
        results["errors"].append(f"Nextcloud: {str(e)}")
        print(f"❌ Errore password Nextcloud: {e}")
    
    # Aggiorna password Linux
    if set_linux_password(username, new_password):
        results["linux"] = True
    else:
        results["errors"].append("Linux: fallimento aggiornamento password")
    
    return results


def delete_linux_user(username: str, remove_home: bool = False, 
                     backup_home: bool = True) -> bool:
    """
    Elimina un utente Linux
    
    Args:
        username: Nome utente da eliminare
        remove_home: Se eliminare anche la directory home
        backup_home: Se creare backup della home prima di eliminarla
        
    Returns:
        True se eliminazione riuscita, False altrimenti
    """
    try:
        if not user_exists(username):
            print(f"ℹ️ Utente {username} non esiste")
            return True
        
        # Backup home directory se richiesto
        if remove_home and backup_home:
            home_dir = f"/home/{username}"
            if os.path.exists(home_dir):
                backup_user_home(username)
        
        # Comando userdel
        userdel_cmd = ["userdel"]
        if remove_home:
            userdel_cmd.append("-r")
        userdel_cmd.append(username)
        
        subprocess.run(userdel_cmd, check=True, capture_output=True, text=True)
        
        print(f"✅ Utente Linux eliminato: {username}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Errore eliminazione utente {username}: {e}")
        return False


def backup_user_home(username: str, backup_dir: str = "/var/backups/users") -> Optional[str]:
    """
    Crea backup della home directory di un utente
    
    Args:
        username: Nome utente
        backup_dir: Directory dove salvare il backup
        
    Returns:
        Path del backup creato o None se errore
    """
    try:
        import time
        from .utils import ensure_dir
        
        home_dir = f"/home/{username}"
        if not os.path.exists(home_dir):
            return None
        
        # Crea directory backup
        ensure_dir(backup_dir)
        
        # Nome file backup con timestamp
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        backup_filename = f"{username}-home-{timestamp}.tar.gz"
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # Crea archivio tar.gz
        tar_cmd = [
            "tar", "-czf", backup_path,
            "-C", "/home",
            username
        ]
        
        subprocess.run(tar_cmd, check=True, capture_output=True)
        
        print(f"✅ Backup home creato: {backup_path}")
        return backup_path
        
    except Exception as e:
        print(f"❌ Errore creazione backup per {username}: {e}")
        return None


def lock_user_account(username: str) -> bool:
    """
    Blocca account utente (disabilita login)
    
    Args:
        username: Nome utente da bloccare
        
    Returns:
        True se operazione riuscita
    """
    try:
        subprocess.run(["usermod", "-L", username], check=True)
        print(f"🔒 Account bloccato: {username}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Errore blocco account {username}: {e}")
        return False


def unlock_user_account(username: str) -> bool:
    """
    Sblocca account utente
    
    Args:
        username: Nome utente da sbloccare
        
    Returns:
        True se operazione riuscita
    """
    try:
        subprocess.run(["usermod", "-U", username], check=True)
        print(f"🔓 Account sbloccato: {username}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Errore sblocco account {username}: {e}")
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


def get_system_users(include_system: bool = False) -> List[Dict]:
    """
    Lista tutti gli utenti del sistema
    
    Args:
        include_system: Se includere utenti di sistema (UID < 1000)
        
    Returns:
        Lista di dict con info utenti
    """
    users = []
    
    try:
        for user_entry in pwd.getpwall():
            # Filtra utenti di sistema se non richiesti
            if not include_system and user_entry.pw_uid < 1000:
                continue
            
            user_info = {
                "username": user_entry.pw_name,
                "uid": user_entry.pw_uid,
                "gid": user_entry.pw_gid,
                "home": user_entry.pw_dir,
                "shell": user_entry.pw_shell,
                "gecos": user_entry.pw_gecos
            }
            
            # Aggiungi info se è utente Nextcloud (ha home in /home/)
            if user_entry.pw_dir.startswith("/home/"):
                user_info["is_nextcloud_user"] = True
                user_info["home_exists"] = os.path.exists(user_entry.pw_dir)
                
                # Verifica se è montato WebDAV
                from .utils import is_mounted
                user_info["webdav_mounted"] = is_mounted(user_entry.pw_dir)
            else:
                user_info["is_nextcloud_user"] = False
            
            users.append(user_info)
    
    except Exception as e:
        print(f"❌ Errore listing utenti: {e}")
    
    return users


def get_user_login_history(username: str, days: int = 7) -> List[Dict]:
    """
    Ottiene cronologia login utente
    
    Args:
        username: Nome utente
        days: Giorni di cronologia da recuperare
        
    Returns:
        Lista eventi di login
    """
    try:
        # Usa last command per ottenere cronologia
        cmd = ["last", "-n", "50", username]
        output = run(cmd, check=False)
        
        login_events = []
        for line in output.split('\n'):
            if username in line and 'reboot' not in line:
                parts = line.split()
                if len(parts) >= 7:
                    event = {
                        "user": parts[0],
                        "terminal": parts[1],
                        "ip": parts[2] if parts[2] != "console" else "local",
                        "login_time": " ".join(parts[3:7]),
                        "duration": " ".join(parts[7:]) if len(parts) > 7 else "still logged in"
                    }
                    login_events.append(event)
        
        return login_events[:20]  # Limita a 20 eventi più recenti
        
    except Exception as e:
        print(f"❌ Errore recupero cronologia login per {username}: {e}")
        return []


def monitor_user_activity(username: str) -> Dict:
    """
    Monitora attività corrente utente
    
    Args:
        username: Nome utente da monitorare
        
    Returns:
        Dict con info attività
    """
    activity = {
        "logged_in": False,
        "processes": [],
        "connections": [],
        "last_login": None
    }
    
    try:
        # Verifica se utente è loggato
        who_output = run(["who"], check=False)
        activity["logged_in"] = username in who_output
        
        # Processi dell'utente
        ps_output = run(["ps", "-u", username, "-o", "pid,cmd"], check=False)
        for line in ps_output.split('\n')[1:]:  # Skip header
            if line.strip():
                parts = line.strip().split(None, 1)
                if len(parts) >= 2:
                    activity["processes"].append({
                        "pid": parts[0],
                        "command": parts[1]
                    })
        
        # Ultimo login
        last_output = run(["last", "-1", username], check=False)
        if last_output:
            lines = last_output.strip().split('\n')
            if lines and username in lines[0]:
                activity["last_login"] = lines[0]
        
    except Exception as e:
        print(f"❌ Errore monitoraggio attività {username}: {e}")
    
    return activity


def create_user_group(groupname: str, members: List[str] = None) -> bool:
    """
    Crea un gruppo Linux e aggiunge membri
    
    Args:
        groupname: Nome del gruppo da creare
        members: Lista utenti da aggiungere al gruppo
        
    Returns:
        True se operazione riuscita
    """
    try:
        # Crea gruppo
        subprocess.run(["groupadd", groupname], check=True)
        print(f"✅ Gruppo creato: {groupname}")
        
        # Aggiungi membri se specificati
        if members:
            for username in members:
                if user_exists(username):
                    subprocess.run(["usermod", "-a", "-G", groupname, username], check=True)
                    print(f"✅ Utente {username} aggiunto al gruppo {groupname}")
                else:
                    print(f"⚠️ Utente {username} non esiste, saltato")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Errore creazione gruppo {groupname}: {e}")
        return False


def setup_ssh_key(username: str, public_key: str) -> bool:
    """
    Configura chiave SSH per utente
    
    Args:
        username: Nome utente
        public_key: Chiave pubblica SSH
        
    Returns:
        True se configurazione riuscita
    """
    try:
        home_dir = f"/home/{username}"
        ssh_dir = os.path.join(home_dir, ".ssh")
        authorized_keys = os.path.join(ssh_dir, "authorized_keys")
        
        # Crea directory .ssh se non esiste
        if not os.path.exists(ssh_dir):
            os.makedirs(ssh_dir, mode=0o700)
            uid, gid = get_user_uid_gid(username)
            os.chown(ssh_dir, uid, gid)
        
        # Aggiungi chiave a authorized_keys
        with open(authorized_keys, "a") as f:
            f.write(f"\n{public_key.strip()}\n")
        
        # Imposta permessi corretti
        os.chmod(authorized_keys, 0o600)
        uid, gid = get_user_uid_gid(username)
        os.chown(authorized_keys, uid, gid)
        
        print(f"✅ Chiave SSH configurata per {username}")
        return True
        
    except Exception as e:
        print(f"❌ Errore configurazione SSH per {username}: {e}")
        return False


def system_cleanup() -> Dict:
    """
    Pulizia generale sistema (logs, temp files, cache)
    
    Returns:
        Dict con risultati pulizia
    """
    cleanup_results = {
        "space_freed": 0,
        "files_removed": 0,
        "errors": []
    }
    
    cleanup_paths = [
        "/tmp/*",
        "/var/tmp/*",
        "/var/log/*.log.1",
        "/var/log/*.log.*.gz",
        "/var/cache/apt/archives/*.deb",
        "/home/*/.cache/thumbnails/*",
        "/home/*/.local/share/Trash/*"
    ]
    
    import glob
    from .utils import get_directory_size, bytes_to_human
    
    for pattern in cleanup_paths:
        try:
            matches = glob.glob(pattern, recursive=True)
            
            for path in matches:
                try:
                    if os.path.isfile(path):
                        size = os.path.getsize(path)
                        os.unlink(path)
                        cleanup_results["space_freed"] += size
                        cleanup_results["files_removed"] += 1
                    elif os.path.isdir(path) and not os.path.islink(path):
                        size = get_directory_size(path)
                        import shutil
                        shutil.rmtree(path)
                        cleanup_results["space_freed"] += size
                        cleanup_results["files_removed"] += 1
                        
                except Exception as e:
                    cleanup_results["errors"].append(f"{path}: {str(e)}")
                    
        except Exception as e:
            cleanup_results["errors"].append(f"Pattern {pattern}: {str(e)}")
    
    cleanup_results["space_freed_human"] = bytes_to_human(cleanup_results["space_freed"])
    
    print(f"🧹 Pulizia completata: {cleanup_results['files_removed']} files, "
          f"{cleanup_results['space_freed_human']} liberati")
    
    return cleanup_results
