"""
Modulo unificato per gestione mount Nextcloud v1.0.0rc2
Solo rclone engine semplificato
"""
import os
import shutil
import time

from pathlib import Path
from typing import Optional, Dict, List
from enum import Enum

from .utils import run, ensure_dir, get_user_uid_gid, is_command_available, is_mounted
from .api import get_nc_config
from .rclone import (
    add_nextcloud_remote, mount_remote, unmount, is_mounted as rclone_is_mounted,
    create_systemd_mount_service, get_mount_profile_info, MOUNT_PROFILES
)


class MountEngine(str, Enum):
    """Engine di mount supportati"""
    RCLONE = "rclone"


class MountManager:
    """
    Gestore mount Nextcloud v1.0.0rc2 - solo rclone
    """
    
    def __init__(self, preferred_engine: MountEngine = MountEngine.RCLONE):
        self.preferred_engine = MountEngine.RCLONE  # Fisso v1.0
        
        # Configurazione engine
        self.config = {
            "rclone_default_profile": "full",
            "rclone_cache_dir": Path.home() / ".cache" / "rclone" / "ncwrap",
            "service_prefix": "ncwrap"
        }
    
    def detect_available_engines(self) -> Dict[MountEngine, bool]:
        """Rileva quali engine sono disponibili nel sistema"""
        return {
            MountEngine.RCLONE: is_command_available("rclone")
        }
    
    def install_engine(self, engine: MountEngine) -> bool:
        """Installa rclone"""
        if engine == MountEngine.RCLONE:
            return self._install_rclone()
        return False
    
    def _install_rclone(self) -> bool:
        """Installa rclone se non presente"""
        if is_command_available("rclone"):
            print("✅ rclone già installato")
            return True
        
        print("📦 Installando rclone...")
        try:
            # Script ufficiale rclone
            run(["curl", "https://rclone.org/install.sh", "|", "bash"], shell=True)
            
            if is_command_available("rclone"):
                print("✅ rclone installato con successo")
                return True
            else:
                print("❌ Installazione rclone fallita")
                return False
        except Exception as e:
            print(f"❌ Errore installazione rclone: {e}")
            return False
    
    def configure_engine(self, engine: MountEngine) -> bool:
        """Configura rclone"""
        if engine == MountEngine.RCLONE:
            return self._configure_rclone()
        return False
    
    def _configure_rclone(self) -> bool:
        """Configura rclone per performance ottimali"""
        try:
            # Crea directory cache
            ensure_dir(self.config["rclone_cache_dir"])
            
            # Verifica versione rclone
            version_output = run(["rclone", "version"])
            print(f"✅ rclone configurato: {version_output.split()[1]}")
            
            return True
        except Exception as e:
            print(f"❌ Errore configurazione rclone: {e}")
            return False
    
    def setup_credentials(self, username: str, password: str) -> bool:
        """Setup credenziali per rclone"""
        base_url, _, _ = get_nc_config()
        remote_name = f"nc-{username}"
        return add_nextcloud_remote(remote_name, base_url, username, password)
    
    def mount_user_home(self, username: str, password: str, home_path: str = None, 
                       profile: str = "full", remount: bool = False, **kwargs) -> Dict:
        """
        Monta Nextcloud nella home directory con rclone
        
        Returns:
            Dict con informazioni risultato mount
        """
        if not home_path:
            home_path = f"/home/{username}"
        
        result = {
            "success": False,
            "engine_used": MountEngine.RCLONE,
            "mount_point": home_path,
            "profile": profile,
            "message": "",
            "fallback_used": False
        }
        
        print(f"🔗 Montando {username} in {home_path} con rclone (profilo: {profile})")
        
        # Verifica se già montato
        if is_mounted(home_path):
            print(f"✅ {home_path} già montato")
            if remount:
                print(f"🔗 Richiesto remount per {username}")
                if self.unmount_user_home(home_path):
                    print(f"✅ {home_path} smontato")
                else:
                    result["message"] = "Unmount failed"
                    return result
            else:
                result.update({
                    "success": True,
                    "engine_used": MountEngine.RCLONE,
                    "message": "Already mounted"
                })
                return result
        
        # Mount con rclone
        mount_success = self._mount_with_rclone(username, password, home_path, profile)
        
        if mount_success:
            result.update({
                "success": True,
                "message": f"Mounted with rclone"
            })
            print(f"✅ Mount riuscito con rclone")
            return result
        else:
            result["message"] = f"Mount failed with rclone"
            print(f"❌ {result['message']}")
            return result
    
    def _mount_with_rclone(self, username: str, password: str, home_path: str, profile: str = "full") -> bool:
        """Mount con rclone"""
        try:
            # Setup remote se non esiste
            remote_name = f"nc-{username}"
            if not self.setup_credentials(username, password):
                print(f"❌ Errore setup credenziali rclone per {username}")
                return False
            
            # Backup home esistente
            self._backup_existing_home(home_path, username)
            
            # Mount con rclone
            if mount_remote(remote_name, home_path, background=True, profile=profile):
                # Verifica che il mount sia effettivamente attivo
                import time
                time.sleep(3)  # Attendi che rclone si stabilizzi
                
                if not is_mounted(home_path):
                    print(f"❌ Mount non attivo dopo setup per {home_path}")
                    return False
                
                # Test basic I/O
                test_file = os.path.join(home_path, ".mount-test")
                try:
                    with open(test_file, 'w') as f:
                        f.write("test")
                    os.remove(test_file)
                    print(f"✅ Test I/O mount riuscito")
                except Exception as e:
                    print(f"❌ Test I/O mount fallito: {e}")
                    return False
                
                # Impostazioni permessi post-mount
                try:
                    uid, gid = get_user_uid_gid(username)
                    run(["chown", f"{uid}:{gid}", home_path], check=False)
                except:
                    pass  # Non critico
                
                return True
            else:
                print(f"❌ Comando mount rclone fallito")
                return False
            
        except Exception as e:
            print(f"❌ Errore mount rclone: {e}")
            return False
    
    def _backup_existing_home(self, home_path: str, username: str) -> Optional[str]:
        """Backup directory home esistente"""
        if not os.path.exists(home_path):
            return None
            
        try:
            import time
            backup_dir = "/var/backups/nextcloud-wrapper"
            ensure_dir(backup_dir)
            
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            backup_filename = f"{username}-home-{timestamp}.tar.gz"
            backup_path = os.path.join(backup_dir, backup_filename)
            
            tar_cmd = [
                "tar", "-czf", backup_path,
                "-C", os.path.dirname(home_path),
                os.path.basename(home_path)
            ]
            
            run(tar_cmd, check=False)
            print(f"✅ Backup home creato: {backup_path}")
            return backup_path
            
        except Exception as e:
            print(f"⚠️ Errore backup home: {e}")
            return None
    
    def unmount_user_home(self, home_path: str) -> bool:
        """Smonta home directory"""
        try:
            return unmount(home_path)
        except:
            return False
    
    def create_systemd_service(self, username: str, password: str, home_path: str = None,
                              profile: str = "full") -> str:
        """Crea servizio systemd per mount automatico rclone"""
        if not home_path:
            home_path = f"/home/{username}"
        
        service_name = f"{self.config['service_prefix']}-rclone-{username}"
        
        # Setup remote prima di creare servizio
        remote_name = f"nc-{username}"
        self.setup_credentials(username, password)
        
        # Usa il generatore rclone
        service_content = create_systemd_mount_service(
            username, profile or "full"
        )
        
        # Scrivi file servizio
        service_file = f"/etc/systemd/system/{service_name}.service"
        with open(service_file, 'w') as f:
            f.write(service_content)
        
        # Reload systemd
        run(["systemctl", "daemon-reload"])
        
        print(f"✅ Servizio creato: {service_name}.service")
        return service_name
    
    def list_mounts(self) -> List[Dict]:
        """Lista tutti i mount rclone attivi"""
        mounts = []
        
        try:
            mount_output = run(["mount", "-t", "fuse.rclone"], check=False)
            for line in mount_output.split('\n'):
                if line.strip() and "rclone" in line:
                    parts = line.split()
                    if len(parts) >= 3:
                        mounts.append({
                            "engine": MountEngine.RCLONE,
                            "remote": parts[0],
                            "mountpoint": parts[2],
                            "type": "rclone",
                            "options": ' '.join(parts[5:]) if len(parts) > 5 else ""
                        })
        except:
            pass
        
        return mounts
    
    def get_mount_status(self, home_path: str) -> Dict:
        """Status dettagliato di un mount"""
        if not is_mounted(home_path):
            return {
                "mounted": False,
                "engine": None,
                "status": "Not mounted"
            }
        
        return {
            "mounted": True,
            "engine": MountEngine.RCLONE,
            "status": "Active (rclone)",
            "profile": self._detect_rclone_profile(home_path)
        }
    
    def _detect_rclone_profile(self, mount_point: str) -> Optional[str]:
        """Rileva profilo rclone da mount attivo (se possibile)"""
        try:
            # Leggi da systemd se è un servizio
            services = run(["systemctl", "list-units", "--type=service", "--state=active"], check=False)
            for line in services.split('\n'):
                if f"rclone" in line and mount_point.replace("/", "/") in line:
                    # Questo è approssimativo
                    if "full" in line:
                        return "full"
                    elif "writes" in line:
                        return "writes"
                    elif "minimal" in line:
                        return "minimal"
                    elif "hosting" in line:
                        return "hosting"
            
            return "cannot detect"
        except:
            return None


def setup_user_with_mount(username: str, password: str, quota: str = None,
                         profile: str = "full", remount: bool = False) -> bool:
    """
    Setup completo utente con rclone engine (v1.0.0rc2 semplificato)
    
    Args:
        username: Nome utente
        password: Password
        quota: Quota Nextcloud (es. "100G") - solo per info
        profile: Profilo rclone mount
        remount: Forza remount se già esistente
    
    Returns:
        True se setup completato
    """
    print(f"🚀 Setup completo per {username} (v1.0.0rc2 - rclone)")
    
    # Validazione profilo
    from .rclone import MOUNT_PROFILES
    if profile not in MOUNT_PROFILES:
        print(f"❌ Profilo non valido: {profile}")
        print(f"💡 Profili disponibili: {', '.join(MOUNT_PROFILES.keys())}")
        return False
    
    mount_manager = MountManager(MountEngine.RCLONE)
    
    # 1. Verifica e installa rclone
    available_engines = mount_manager.detect_available_engines()
    if not available_engines[MountEngine.RCLONE]:
        print("📦 Installando rclone...")
        if not mount_manager.install_engine(MountEngine.RCLONE):
            return False
    
    # 2. Configura rclone
    if not mount_manager.configure_engine(MountEngine.RCLONE):
        return False
    
    # 3. Crea utente Nextcloud se non esiste
    from .api import create_nc_user, check_user_exists
    if not check_user_exists(username):
        try:
            create_nc_user(username, password)
            print(f"✅ Utente Nextcloud creato: {username}")
        except Exception as e:
            print(f"❌ Errore creazione utente Nextcloud: {e}")
            return False
    else:
        print(f"ℹ️ Utente Nextcloud già esistente: {username}")
    
    # 4. Crea utente Linux se non esiste
    from .system import create_linux_user, user_exists
    if not user_exists(username):
        if create_linux_user(username, password, create_home=False):
            print(f"✅ Utente Linux creato: {username}")
        else:
            print(f"❌ Errore creazione utente Linux: {username}")
            return False
    else:
        print(f"ℹ️ Utente Linux già esistente: {username}")
    
    # 5. Mount con rclone (v1.0 - no fallback, solo rclone)
    home_path = f"/home/{username}"
    mount_result = mount_manager.mount_user_home(
        username=username,
        password=password, 
        home_path=home_path,
        profile=profile,
        remount=remount
    )
    
    if not mount_result["success"]:
        print(f"❌ {mount_result['message']}")
        return False
    
    print(f"✅ Mount rclone riuscito")
    print(f"📊 Profilo: {mount_result.get('profile', profile)}")
    
    # 6. Gestione spazio v1.0 (automatica via rclone)
    profile_info = MOUNT_PROFILES.get(profile, {})
    if profile_info.get('storage'):
        print(f"💾 Cache rclone: {profile_info['storage']}")
    print("✅ Gestione spazio: automatica via rclone (cache LRU)")
    
    # 7. Crea servizio systemd rclone
    try:
        service_name = mount_manager.create_systemd_service(
            username, password, home_path, profile
        )
        
        # Abilita servizio
        from .utils import run
        run(["systemctl", "enable", "--now", f"{service_name}.service"], check=False)
        print(f"✅ Servizio systemd: {service_name}")
        
    except Exception as e:
        print(f"⚠️ Avviso servizio systemd: {e}")
    
    print(f"🎉 Setup completato per {username}")
    print(f"• Engine: rclone")
    print(f"• Profilo: {profile}")
    print(f"• Home directory: {home_path} → Nextcloud WebDAV")
    print(f"• Gestione spazio: automatica (cache LRU)")
    
    return True
