"""
Gestione servizi systemd per mount automatici e sincronizzazioni
"""
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Optional
from .utils import run


class SystemdManager:
    """Gestore servizi systemd per nextcloud-wrapper"""
    
    def __init__(self):
        self.system_dir = Path("/etc/systemd/system")
        self.user_dir = Path.home() / ".config/systemd/user"
    
    def create_mount_service(self, username: str, remote_name: str, 
                           mount_point: str, user: bool = False, 
                           profile: str = "writes") -> str:
        """
        Crea servizio systemd per mount rclone automatico con profilo
        
        Args:
            username: Nome utente (per nome servizio)
            remote_name: Nome remote rclone
            mount_point: Directory di mount
            user: Se creare servizio utente (True) o system (False)
            profile: Profilo mount ("hosting", "minimal", "writes")
            
        Returns:
            Nome del servizio creato
        """
        service_name = f"nextcloud-mount-{username}.service"
        
        # Configurazione servizio con profilo
        service_content = self._generate_mount_service_config(
            remote_name, mount_point, username if user else "root", profile
        )
        
        # Path appropriato per il file .service
        service_dir = self.user_dir if user else self.system_dir
        service_dir.mkdir(parents=True, exist_ok=True)
        service_file = service_dir / service_name
        
        # Scrivi file di configurazione
        service_file.write_text(service_content)
        
        # Reload systemd
        self._reload_systemd(user=user)
        
        print(f"✅ Servizio creato con profilo '{profile}': {service_name.replace('.service', '')}")
        
        return service_name.replace('.service', '')
    
    def create_sync_service(self, username: str, source: str, dest: str,
                           schedule: str = "hourly", user: bool = False) -> str:
        """
        Crea servizio + timer systemd per sync automatica
        
        Args:
            username: Nome utente
            source: Path sorgente (può essere remote:path)
            dest: Path destinazione  
            schedule: Frequenza (hourly, daily, weekly)
            user: Servizio utente o system
            
        Returns:
            Nome del servizio creato (senza .service)
        """
        service_name = f"nextcloud-sync-{username}"
        
        # Crea file .service
        service_content = self._generate_sync_service_config(source, dest, username)
        
        # Crea file .timer
        timer_content = self._generate_timer_config(schedule, service_name)
        
        # Directory appropriata
        service_dir = self.user_dir if user else self.system_dir
        service_dir.mkdir(parents=True, exist_ok=True)
        
        # Scrivi entrambi i file
        (service_dir / f"{service_name}.service").write_text(service_content)
        (service_dir / f"{service_name}.timer").write_text(timer_content)
        
        # Reload systemd
        self._reload_systemd(user=user)
        
        return service_name
    
    def enable_service(self, service_name: str, user: bool = False) -> bool:
        """Abilita e avvia un servizio"""
        try:
            cmd = ["systemctl"]
            if user:
                cmd.append("--user")
            cmd.extend(["enable", "--now", service_name])
            
            run(cmd)
            return True
        except RuntimeError as e:
            print(f"Errore abilitazione servizio {service_name}: {e}")
            return False
    
    def disable_service(self, service_name: str, user: bool = False) -> bool:
        """Disabilita e ferma un servizio"""
        try:
            cmd = ["systemctl"]
            if user:
                cmd.append("--user")
            cmd.extend(["disable", "--now", service_name])
            
            run(cmd)
            return True
        except RuntimeError as e:
            print(f"Errore disabilitazione servizio {service_name}: {e}")
            return False
    
    def start_service(self, service_name: str, user: bool = False) -> bool:
        """Avvia un servizio"""
        try:
            cmd = ["systemctl"]
            if user:
                cmd.append("--user")
            cmd.extend(["start", service_name])
            
            run(cmd)
            return True
        except RuntimeError:
            return False
    
    def stop_service(self, service_name: str, user: bool = False) -> bool:
        """Ferma un servizio"""
        try:
            cmd = ["systemctl"]
            if user:
                cmd.append("--user")
            cmd.extend(["stop", service_name])
            
            run(cmd)
            return True
        except RuntimeError:
            return False
    
    def get_service_status(self, service_name: str, user: bool = False) -> Optional[Dict]:
        """Recupera stato di un servizio"""
        try:
            cmd = ["systemctl"]
            if user:
                cmd.append("--user")
            cmd.extend(["status", service_name, "--no-pager", "-l"])
            
            output = run(cmd, check=False)
            
            # Parsing semplificato dello status
            lines = output.split('\n')
            status_info = {
                "name": service_name,
                "active": "inactive",
                "enabled": "disabled",
                "description": ""
            }
            
            for line in lines:
                line = line.strip()
                if "Active:" in line:
                    if "active (running)" in line:
                        status_info["active"] = "running"
                    elif "active" in line:
                        status_info["active"] = "active"
                    elif "failed" in line:
                        status_info["active"] = "failed"
                
                if "Loaded:" in line:
                    if "enabled" in line:
                        status_info["enabled"] = "enabled"
                    if "disabled" in line:
                        status_info["enabled"] = "disabled"
                
                if line.startswith("Description:"):
                    status_info["description"] = line.replace("Description:", "").strip()
            
            return status_info
            
        except Exception as e:
            print(f"Errore recupero status {service_name}: {e}")
            return None
    
    def list_nextcloud_services(self, user: bool = False) -> List[Dict]:
        """Lista tutti i servizi nextcloud-wrapper"""
        try:
            cmd = ["systemctl"]
            if user:
                cmd.append("--user")
            cmd.extend(["list-units", "--all", "nextcloud-*", "--no-pager"])
            
            output = run(cmd, check=False)
            services = []
            
            for line in output.split('\n'):
                if "nextcloud-" in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        services.append({
                            "name": parts[0],
                            "load": parts[1],
                            "active": parts[2],
                            "sub": parts[3],
                            "description": " ".join(parts[4:]) if len(parts) > 4 else ""
                        })
            
            return services
            
        except Exception:
            return []
    
    def remove_service(self, service_name: str, user: bool = False) -> bool:
        """Rimuove completamente un servizio (disabilita + elimina file)"""
        try:
            # Prima disabilita il servizio
            self.disable_service(service_name, user)
            
            # Determina directory
            service_dir = self.user_dir if user else self.system_dir
            
            # Rimuovi file .service
            service_file = service_dir / f"{service_name}.service"
            if service_file.exists():
                service_file.unlink()
            
            # Rimuovi file .timer se esiste
            timer_file = service_dir / f"{service_name}.timer"
            if timer_file.exists():
                timer_file.unlink()
            
            # Reload systemd
            self._reload_systemd(user=user)
            
            return True
            
        except Exception as e:
            print(f"Errore rimozione servizio {service_name}: {e}")
            return False
    
    def _generate_mount_service_config(self, remote_name: str, mount_point: str, 
                                     user: str, profile: str = "writes") -> str:
        """Genera configurazione servizio mount con profilo specifico"""
        from . import rclone  # Import locale
        
        config_path = rclone.RCLONE_CONF
        
        # Opzioni per profilo
        profile_options = {
            "hosting": "--vfs-cache-mode off --buffer-size 0 --read-only",
            "minimal": "--vfs-cache-mode minimal --vfs-cache-max-size 1G --buffer-size 32M", 
            "writes": "--vfs-cache-mode writes --vfs-cache-max-size 2G --buffer-size 64M"
        }
        
        mount_options = profile_options.get(profile, profile_options["writes"])
        
        return f"""[Unit]
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
    --config {config_path} \\
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
    
    def _generate_sync_service_config(self, source: str, dest: str, user: str) -> str:
        """Genera configurazione servizio sync"""
        from . import rclone
        
        config_path = rclone.RCLONE_CONF
        
        return f"""[Unit]
Description=RClone sync from {source} to {dest}
After=network-online.target

[Service]
Type=oneshot
User={user}
Group={user}
ExecStart=/usr/bin/rclone sync {source} {dest} \\
    --config {config_path} \\
    --progress \\
    --log-level INFO \\
    --log-file /var/log/rclone-sync-{user}.log \\
    --exclude-from /etc/ncwrap/sync-exclude.txt
StandardOutput=journal
StandardError=journal
"""
    
    def _generate_timer_config(self, schedule: str, service_name: str) -> str:
        """Genera configurazione timer"""
        schedule_map = {
            "hourly": "OnCalendar=hourly",
            "daily": "OnCalendar=daily", 
            "weekly": "OnCalendar=weekly",
            "monthly": "OnCalendar=monthly"
        }
        
        calendar = schedule_map.get(schedule, "OnCalendar=hourly")
        
        return f"""[Unit]
Description=Timer for {service_name}
Requires={service_name}.service

[Timer]
{calendar}
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
"""
    
    def _reload_systemd(self, user: bool = False) -> bool:
        """Ricarica configurazione systemd"""
        try:
            cmd = ["systemctl"]
            if user:
                cmd.append("--user")
            cmd.append("daemon-reload")
            
            run(cmd)
            return True
        except RuntimeError:
            return False
    
    def create_user_mount_services(self, username: str, remote_configs: List[Dict]) -> List[str]:
        """
        Crea multipli servizi mount per un utente
        
        Args:
            username: Nome utente
            remote_configs: Lista dict con {remote_name, mount_point}
            
        Returns:
            Lista nomi servizi creati
        """
        services = []
        
        for config in remote_configs:
            remote_name = config.get('remote_name')
            mount_point = config.get('mount_point')
            
            if remote_name and mount_point:
                service_name = self.create_mount_service(
                    f"{username}-{remote_name}", 
                    remote_name, 
                    mount_point,
                    user=True
                )
                services.append(service_name)
        
        return services
    
    def setup_user_environment(self, username: str) -> bool:
        """
        Setup completo ambiente systemd per utente
        
        Args:
            username: Nome utente
            
        Returns:
            True se setup completato
        """
        try:
            # Abilita lingering per utente (servizi persistenti)
            run(["loginctl", "enable-linger", username])
            
            # Crea directory systemd utente se non esiste
            user_systemd_dir = Path(f"/home/{username}/.config/systemd/user")
            user_systemd_dir.mkdir(parents=True, exist_ok=True)
            
            return True
            
        except Exception as e:
            print(f"Errore setup ambiente systemd per {username}: {e}")
            return False


# Funzioni di convenienza per backward compatibility
def enable_service(service: str, user: bool = False) -> bool:
    """Abilita servizio systemd"""
    manager = SystemdManager()
    return manager.enable_service(service, user)


def disable_service(service: str, user: bool = False) -> bool:
    """Disabilita servizio systemd"""
    manager = SystemdManager()
    return manager.disable_service(service, user)


def create_mount_service(username: str, remote_name: str, mount_point: str) -> str:
    """Crea servizio mount automatico"""
    manager = SystemdManager()
    return manager.create_mount_service(username, remote_name, mount_point)


def get_all_nextcloud_services() -> Dict[str, List[Dict]]:
    """Recupera tutti i servizi nextcloud (system + user)"""
    manager = SystemdManager()
    
    return {
        "system": manager.list_nextcloud_services(user=False),
        "user": manager.list_nextcloud_services(user=True)
    }
