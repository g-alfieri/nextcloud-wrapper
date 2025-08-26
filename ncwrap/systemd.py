"""
Gestione servizi systemd per nextcloud-wrapper v0.3.0
"""
import subprocess
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional
from .utils import run, atomic_write, backup_file


class SystemdManager:
    """Gestore servizi systemd per nextcloud-wrapper"""
    
    def __init__(self):
        self.system_dir = Path("/etc/systemd/system")
        self.user_dir = Path.home() / ".config/systemd/user"
        self.service_prefix = "nextcloud-wrapper"
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """Carica configurazione da environment"""
        return {
            "service_user": os.environ.get("NC_SERVICE_USER", "root"),
            "auto_enable": os.environ.get("NC_AUTO_ENABLE_SERVICES", "true").lower() == "true",
            "log_level": os.environ.get("NC_LOG_LEVEL", "INFO"),
            "restart_policy": os.environ.get("NC_RESTART_POLICY", "on-failure"),
            "restart_delay": int(os.environ.get("NC_RESTART_DELAY", "10")),
            "timeout": int(os.environ.get("NC_SERVICE_TIMEOUT", "60"))
        }
    
    def create_webdav_mount_service(self, username: str, password: str, 
                                   mount_point: str = None) -> str:
        """
        Crea servizio systemd per mount WebDAV automatico
        
        Args:
            username: Nome utente
            password: Password
            mount_point: Directory di mount (default: /home/username)
            
        Returns:
            Nome del servizio creato
        """
        if not mount_point:
            mount_point = f"/home/{username}"
        
        service_name = f"webdav-home-{username}"
        
        # Prepara credenziali WebDAV
        from .api import get_nc_config
        base_url, _, _ = get_nc_config()
        webdav_url = f"{base_url}/remote.php/dav/files/{username}/"
        
        # Setup credenziali davfs2
        from .webdav import WebDAVMountManager
        webdav_manager = WebDAVMountManager()
        webdav_manager.setup_user_credentials(username, password, webdav_url)
        
        # Ottieni UID/GID utente
        from .utils import get_user_uid_gid
        uid, gid = get_user_uid_gid(username)
        
        service_content = self._generate_webdav_mount_service_config(
            service_name, username, webdav_url, mount_point, uid, gid
        )
        
        # Scrivi file servizio
        service_file = self.system_dir / f"{service_name}.service"
        if atomic_write(str(service_file), service_content, 0o644):
            # Reload systemd
            self._reload_systemd()
            print(f"✅ Servizio WebDAV creato: {service_name}")
            return service_name
        else:
            raise RuntimeError(f"Errore creazione file servizio: {service_file}")
    
    def create_backup_service(self, username: str, interval: str = "daily") -> str:
        """
        Crea servizio + timer per backup automatico
        
        Args:
            username: Nome utente
            interval: Intervallo backup (hourly, daily, weekly, monthly)
            
        Returns:
            Nome del servizio creato
        """
        service_name = f"nextcloud-backup-{username}"
        
        # Crea servizio backup
        service_content = self._generate_backup_service_config(username)
        timer_content = self._generate_timer_config(interval, service_name)
        
        # Scrivi file servizio e timer
        service_file = self.system_dir / f"{service_name}.service"
        timer_file = self.system_dir / f"{service_name}.timer"
        
        if not atomic_write(str(service_file), service_content, 0o644):
            raise RuntimeError(f"Errore creazione servizio: {service_file}")
        
        if not atomic_write(str(timer_file), timer_content, 0o644):
            raise RuntimeError(f"Errore creazione timer: {timer_file}")
        
        # Reload systemd
        self._reload_systemd()
        
        print(f"✅ Servizio backup creato: {service_name} ({interval})")
        return service_name
    
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
        timer_content = self._generate_timer_config(schedule, service_name)
        
        # Directory appropriata
        service_dir = self.user_dir if user else self.system_dir
        service_dir.mkdir(parents=True, exist_ok=True)
        
        # Scrivi entrambi i file
        service_file = service_dir / f"{service_name}.service"
        timer_file = service_dir / f"{service_name}.timer"
        
        if not atomic_write(str(service_file), service_content, 0o644):
            raise RuntimeError(f"Errore creazione servizio: {service_file}")
        
        if not atomic_write(str(timer_file), timer_content, 0o644):
            raise RuntimeError(f"Errore creazione timer: {timer_file}")
        
        # Reload systemd
        self._reload_systemd(user=user)
        
        return service_name
    
    def enable_service(self, service_name: str, user: bool = False) -> bool:
        """Abilita e avvia un servizio"""
        try:
            cmd = ["systemctl"]
            if user:
                cmd.append("--user")
            cmd.extend(["enable", "--now", f"{service_name}.service"])
            
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
            cmd.extend(["disable", "--now", f"{service_name}.service"])
            
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
            cmd.extend(["start", f"{service_name}.service"])
            
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
            cmd.extend(["stop", f"{service_name}.service"])
            
            run(cmd)
            return True
        except RuntimeError:
            return False
    
    def restart_service(self, service_name: str, user: bool = False) -> bool:
        """Riavvia un servizio"""
        try:
            cmd = ["systemctl"]
            if user:
                cmd.append("--user")
            cmd.extend(["restart", f"{service_name}.service"])
            
            run(cmd)
            return True
        except RuntimeError:
            return False
    
    def get_service_status(self, service_name: str, user: bool = False) -> Optional[Dict]:
        """Recupera stato dettagliato di un servizio"""
        try:
            cmd = ["systemctl"]
            if user:
                cmd.append("--user")
            cmd.extend(["show", f"{service_name}.service", "--no-pager"])
            
            output = run(cmd, check=False)
            
            # Parse output systemctl show
            status_info = {
                "name": service_name,
                "active": "unknown",
                "enabled": "unknown",
                "load": "unknown",
                "sub": "unknown",
                "main_pid": "0",
                "memory": "0",
                "uptime": "0"
            }
            
            for line in output.split('\n'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    
                    if key == "ActiveState":
                        status_info["active"] = value
                    elif key == "UnitFileState":
                        status_info["enabled"] = value
                    elif key == "LoadState":
                        status_info["load"] = value
                    elif key == "SubState":
                        status_info["sub"] = value
                    elif key == "MainPID":
                        status_info["main_pid"] = value
                    elif key == "MemoryCurrent":
                        if value.isdigit():
                            from .utils import bytes_to_human
                            status_info["memory"] = bytes_to_human(int(value))
                        else:
                            status_info["memory"] = value
                    elif key == "ActiveEnterTimestamp":
                        if value and value != "0":
                            status_info["started_at"] = value
            
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
            cmd.extend(["list-units", "--all", "nextcloud-*", "webdav-*", "--no-pager", "--no-legend"])
            
            output = run(cmd, check=False)
            services = []
            
            for line in output.split('\n'):
                if line.strip() and ("nextcloud-" in line or "webdav-" in line):
                    parts = line.split()
                    if len(parts) >= 4:
                        services.append({
                            "name": parts[0].replace('.service', ''),
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
                # Backup prima di eliminare
                backup_file(str(service_file))
                service_file.unlink()
            
            # Rimuovi file .timer se esiste
            timer_file = service_dir / f"{service_name}.timer"
            if timer_file.exists():
                backup_file(str(timer_file))
                timer_file.unlink()
            
            # Reload systemd
            self._reload_systemd(user=user)
            
            return True
            
        except Exception as e:
            print(f"Errore rimozione servizio {service_name}: {e}")
            return False
    
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
            
            # Imposta ownership corretto
            from .utils import get_user_uid_gid
            uid, gid = get_user_uid_gid(username)
            os.chown(user_systemd_dir, uid, gid)
            
            return True
            
        except Exception as e:
            print(f"Errore setup ambiente systemd per {username}: {e}")
            return False
    
    def _generate_webdav_mount_service_config(self, service_name: str, username: str, 
                                             webdav_url: str, mount_point: str, 
                                             uid: int, gid: int) -> str:
        """Genera configurazione servizio mount WebDAV"""
        
        # Ottieni path Python dal virtual environment se disponibile
        try:
            from .venv import get_venv_executable_path
            exec_path = get_venv_executable_path()
        except ImportError:
            exec_path = "/usr/bin/nextcloud-wrapper"
        
        return f"""[Unit]
Description=WebDAV mount for {username} home directory
After=network-online.target
Wants=network-online.target
Before=systemd-user-sessions.service

[Service]
Type=oneshot
RemainAfterExit=yes
User=root
Group=root
ExecStartPre=/bin/mkdir -p {mount_point}
ExecStart=/bin/mount -t davfs {webdav_url} {mount_point} -o uid={uid},gid={gid},rw,user,noauto
ExecStop=/bin/umount {mount_point}
TimeoutSec={self.config['timeout']}
Restart=no

[Install]
WantedBy=multi-user.target
"""
    
    def _generate_backup_service_config(self, username: str) -> str:
        """Genera configurazione servizio backup"""
        
        backup_dir = f"/var/backups/nextcloud/{username}"
        home_dir = f"/home/{username}"
        
        return f"""[Unit]
Description=Nextcloud backup for {username}
After=network.target

[Service]
Type=oneshot
User=root
Group=root
ExecStartPre=/bin/mkdir -p {backup_dir}
ExecStart=/bin/tar -czf {backup_dir}/backup-$(date +\\%Y\\%m\\%d-\\%H\\%M\\%S).tar.gz -C {home_dir} .
ExecStartPost=/bin/find {backup_dir} -name "backup-*.tar.gz" -mtime +7 -delete
StandardOutput=journal
StandardError=journal
"""
    
    def _generate_sync_service_config(self, source: str, dest: str, username: str) -> str:
        """Genera configurazione servizio sync"""
        
        # Ottieni path eseguibile dal virtual environment
        try:
            from .venv import get_venv_executable_path
            exec_path = get_venv_executable_path()
        except ImportError:
            exec_path = "/usr/bin/rsync"
        
        return f"""[Unit]
Description=Nextcloud sync from {source} to {dest}
After=network-online.target

[Service]
Type=oneshot
User={self.config['service_user']}
Group={self.config['service_user']}
ExecStart=/usr/bin/rsync -avz --delete {source}/ {dest}/
StandardOutput=journal
StandardError=journal
"""
    
    def _generate_timer_config(self, schedule: str, service_name: str) -> str:
        """Genera configurazione timer"""
        schedule_map = {
            "minutely": "OnCalendar=*:0/1",
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
    
    def get_service_logs(self, service_name: str, lines: int = 50, 
                        user: bool = False, follow: bool = False) -> str:
        """Ottiene log di un servizio"""
        try:
            cmd = ["journalctl"]
            if user:
                cmd.append("--user")
            
            cmd.extend(["-u", f"{service_name}.service"])
            cmd.extend(["-n", str(lines)])
            cmd.append("--no-pager")
            
            if follow:
                cmd.append("-f")
            
            return run(cmd, check=False)
            
        except Exception as e:
            return f"Errore lettura log: {e}"
    
    def create_monitoring_service(self, username: str) -> str:
        """Crea servizio monitoring per utente"""
        service_name = f"nextcloud-monitor-{username}"
        
        service_content = f"""[Unit]
Description=Nextcloud monitoring for {username}
After=network.target

[Service]
Type=simple
User=root
Group=root
ExecStart=/usr/local/bin/nextcloud-wrapper quota check {username}
Restart={self.config['restart_policy']}
RestartSec={self.config['restart_delay']}
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
        
        timer_content = self._generate_timer_config("hourly", service_name)
        
        # Scrivi file
        service_file = self.system_dir / f"{service_name}.service"
        timer_file = self.system_dir / f"{service_name}.timer"
        
        if not atomic_write(str(service_file), service_content, 0o644):
            raise RuntimeError(f"Errore creazione servizio monitoring: {service_file}")
        
        if not atomic_write(str(timer_file), timer_content, 0o644):
            raise RuntimeError(f"Errore creazione timer monitoring: {timer_file}")
        
        self._reload_systemd()
        
        print(f"✅ Servizio monitoring creato: {service_name}")
        return service_name
    
    def bulk_operation(self, operation: str, service_pattern: str = "nextcloud-*", 
                      user: bool = False) -> Dict:
        """Esegue operazione su multipli servizi"""
        results = {
            "success": [],
            "failed": [],
            "total": 0
        }
        
        # Lista servizi che matchano il pattern
        services = self.list_nextcloud_services(user)
        matching_services = [
            s["name"] for s in services 
            if service_pattern.replace("*", "") in s["name"]
        ]
        
        results["total"] = len(matching_services)
        
        for service_name in matching_services:
            try:
                if operation == "start":
                    success = self.start_service(service_name, user)
                elif operation == "stop":
                    success = self.stop_service(service_name, user)
                elif operation == "restart":
                    success = self.restart_service(service_name, user)
                elif operation == "enable":
                    success = self.enable_service(service_name, user)
                elif operation == "disable":
                    success = self.disable_service(service_name, user)
                else:
                    success = False
                
                if success:
                    results["success"].append(service_name)
                else:
                    results["failed"].append(service_name)
                    
            except Exception as e:
                results["failed"].append(f"{service_name}: {str(e)}")
        
        return results
    
    def export_service_config(self, service_name: str, user: bool = False) -> Optional[str]:
        """Esporta configurazione servizio in formato JSON"""
        try:
            service_dir = self.user_dir if user else self.system_dir
            service_file = service_dir / f"{service_name}.service"
            timer_file = service_dir / f"{service_name}.timer"
            
            config = {
                "name": service_name,
                "type": "user" if user else "system",
                "service_content": "",
                "timer_content": "",
                "status": self.get_service_status(service_name, user)
            }
            
            if service_file.exists():
                with open(service_file, 'r') as f:
                    config["service_content"] = f.read()
            
            if timer_file.exists():
                with open(timer_file, 'r') as f:
                    config["timer_content"] = f.read()
            
            return json.dumps(config, indent=2)
            
        except Exception as e:
            print(f"Errore export configurazione {service_name}: {e}")
            return None
    
    def import_service_config(self, config_json: str) -> bool:
        """Importa configurazione servizio da JSON"""
        try:
            config = json.loads(config_json)
            
            service_name = config["name"]
            user = config["type"] == "user"
            service_dir = self.user_dir if user else self.system_dir
            
            # Crea directory se necessaria
            service_dir.mkdir(parents=True, exist_ok=True)
            
            # Scrivi file servizio
            if config.get("service_content"):
                service_file = service_dir / f"{service_name}.service"
                if not atomic_write(str(service_file), config["service_content"], 0o644):
                    return False
            
            # Scrivi file timer se presente
            if config.get("timer_content"):
                timer_file = service_dir / f"{service_name}.timer"
                if not atomic_write(str(timer_file), config["timer_content"], 0o644):
                    return False
            
            # Reload systemd
            self._reload_systemd(user=user)
            
            print(f"✅ Configurazione servizio importata: {service_name}")
            return True
            
        except Exception as e:
            print(f"Errore import configurazione: {e}")
            return False


# Funzioni di convenienza per backward compatibility
def create_mount_service(username: str, remote_name: str, mount_point: str) -> str:
    """Crea servizio mount automatico"""
    manager = SystemdManager()
    return manager.create_webdav_mount_service(username, "password_placeholder", mount_point)


def enable_service(service: str, user: bool = False) -> bool:
    """Abilita servizio systemd"""
    manager = SystemdManager()
    return manager.enable_service(service, user)


def disable_service(service: str, user: bool = False) -> bool:
    """Disabilita servizio systemd"""
    manager = SystemdManager()
    return manager.disable_service(service, user)


def list_all_webdav_services() -> Dict[str, List[Dict]]:
    """Recupera tutti i servizi nextcloud (system + user)"""
    manager = SystemdManager()
    
    return {
        "system": manager.list_nextcloud_services(user=False),
        "user": manager.list_nextcloud_services(user=True)
    }


def service_health_check() -> Dict:
    """Verifica salute di tutti i servizi nextcloud"""
    manager = SystemdManager()
    
    all_services = list_all_webdav_services()
    health_report = {
        "healthy": [],
        "unhealthy": [],
        "total_system": len(all_services["system"]),
        "total_user": len(all_services["user"]),
        "issues": []
    }
    
    # Verifica servizi system
    for service in all_services["system"]:
        service_name = service["name"]
        status = manager.get_service_status(service_name, user=False)
        
        if status and status["active"] == "active":
            health_report["healthy"].append(f"system:{service_name}")
        else:
            health_report["unhealthy"].append(f"system:{service_name}")
            if status:
                health_report["issues"].append(f"{service_name}: {status['active']}")
    
    # Verifica servizi user
    for service in all_services["user"]:
        service_name = service["name"]
        status = manager.get_service_status(service_name, user=True)
        
        if status and status["active"] == "active":
            health_report["healthy"].append(f"user:{service_name}")
        else:
            health_report["unhealthy"].append(f"user:{service_name}")
            if status:
                health_report["issues"].append(f"{service_name}: {status['active']}")
    
    return health_report


def auto_repair_services() -> Dict:
    """Ripara automaticamente servizi non funzionanti"""
    manager = SystemdManager()
    health = service_health_check()
    
    repair_results = {
        "attempted": [],
        "fixed": [],
        "still_broken": []
    }
    
    for service_name in health["unhealthy"]:
        try:
            # Determina se è system o user service
            service_type, name = service_name.split(":", 1)
            is_user = service_type == "user"
            
            repair_results["attempted"].append(service_name)
            
            # Prova restart
            if manager.restart_service(name, is_user):
                # Attendi e verifica
                time.sleep(5)
                status = manager.get_service_status(name, is_user)
                
                if status and status["active"] == "active":
                    repair_results["fixed"].append(service_name)
                else:
                    repair_results["still_broken"].append(service_name)
            else:
                repair_results["still_broken"].append(service_name)
                
        except Exception as e:
            repair_results["still_broken"].append(f"{service_name}: {str(e)}")
    
    return repair_results


# Alias aggiuntivi per compatibilità
get_all_nextcloud_services = list_all_webdav_services
