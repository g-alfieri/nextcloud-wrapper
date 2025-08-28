"""
Modulo unificato per gestione mount Nextcloud
Supporta sia rclone (predefinito) che davfs2 (fallback)
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
from .webdav import WebDAVMountManager


class MountEngine(str, Enum):
    """Engine di mount supportati"""
    RCLONE = "rclone"
    DAVFS2 = "davfs2"


class MountManager:
    """
    Gestore unificato mount Nextcloud con supporto rclone + davfs2
    
    - Default: rclone (performance migliori)
    - Fallback: davfs2 (compatibilità)
    """
    
    def __init__(self, preferred_engine: MountEngine = MountEngine.RCLONE):
        self.preferred_engine = preferred_engine
        self.webdav_manager = WebDAVMountManager()
        
        # Configurazione engine
        self.config = {
            "rclone_default_profile": "writes",
            "rclone_cache_dir": Path.home() / ".cache" / "rclone" / "ncwrap",
            "auto_fallback": True,
            "service_prefix": "ncwrap"
        }
    
    def detect_available_engines(self) -> Dict[MountEngine, bool]:
        """Rileva quali engine sono disponibili nel sistema"""
        return {
            MountEngine.RCLONE: is_command_available("rclone"),
            MountEngine.DAVFS2: is_command_available("mount.davfs")
        }
    
    def install_engine(self, engine: MountEngine) -> bool:
        """Installa un engine se mancante"""
        if engine == MountEngine.RCLONE:
            return self._install_rclone()
        elif engine == MountEngine.DAVFS2:
            return self.webdav_manager.install_davfs2()
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
        """Configura un engine per uso ottimale"""
        if engine == MountEngine.RCLONE:
            return self._configure_rclone()
        elif engine == MountEngine.DAVFS2:
            return self.webdav_manager.configure_davfs2()
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
    
    def setup_credentials(self, username: str, password: str, engine: MountEngine = None) -> bool:
        """Setup credenziali per l'engine specificato"""
        if not engine:
            engine = self.preferred_engine
        
        base_url, _, _ = get_nc_config()
        
        if engine == MountEngine.RCLONE:
            remote_name = f"nc-{username}"
            return add_nextcloud_remote(remote_name, base_url, username, password)
        
        elif engine == MountEngine.DAVFS2:
            webdav_url = f"{base_url}/remote.php/dav/files/{username}/"
            return self.webdav_manager.setup_user_credentials(username, password, webdav_url)
        
        return False
    
    def mount_user_home(self, username: str, password: str, home_path: str = None, 
                       engine: MountEngine = None, profile: str = None,
                       auto_fallback: bool = None) -> Dict:
        """
        Monta WebDAV nella home directory con engine specificato
        
        Returns:
            Dict con informazioni risultato mount
        """
        if not engine:
            engine = self.preferred_engine
        
        if auto_fallback is None:
            auto_fallback = self.config["auto_fallback"]
        
        if not home_path:
            home_path = f"/home/{username}"
        
        result = {
            "success": False,
            "engine_used": None,
            "mount_point": home_path,
            "profile": profile,
            "message": "",
            "fallback_used": False
        }
        
        print(f"🔗 Montando {username} in {home_path} con engine: {engine.value}")
        
        # Verifica se già montato
        if is_mounted(home_path):
            print(f"✅ {home_path} già montato")
            result.update({
                "success": True,
                "engine_used": self._detect_mount_engine(home_path),
                "message": "Already mounted"
            })
            return result
        
        # Tentativo con engine preferito
        mount_success = False
        
        if engine == MountEngine.RCLONE:
            mount_success = self._mount_with_rclone(username, password, home_path, profile or "writes")
            result["engine_used"] = MountEngine.RCLONE
            result["profile"] = profile or "writes"
            
        elif engine == MountEngine.DAVFS2:
            mount_success = self._mount_with_davfs2(username, password, home_path)
            result["engine_used"] = MountEngine.DAVFS2
        
        if mount_success:
            result.update({
                "success": True,
                "message": f"Mounted with {engine.value}"
            })
            print(f"✅ Mount riuscito con {engine.value}")
            return result
        
        # Fallback se abilitato
        if auto_fallback and engine == MountEngine.RCLONE:
            print(f"⚠️ Mount con {engine.value} fallito, tentativo fallback davfs2...")
            
            if self._mount_with_davfs2(username, password, home_path):
                result.update({
                    "success": True,
                    "engine_used": MountEngine.DAVFS2,
                    "fallback_used": True,
                    "message": "Mounted with davfs2 fallback"
                })
                print(f"✅ Mount riuscito con fallback davfs2")
                return result
        
        # Mount completamente fallito
        result["message"] = f"Mount failed with {engine.value}" + (
            " and davfs2 fallback" if auto_fallback and engine == MountEngine.RCLONE else ""
        )
        print(f"❌ {result['message']}")
        
        return result
    
    def _mount_with_rclone(self, username: str, password: str, home_path: str, profile: str) -> bool:
        """Mount con rclone"""
        try:
            # Setup remote se non esiste
            remote_name = f"nc-{username}"
            if not self.setup_credentials(username, password, MountEngine.RCLONE):
                print(f"❌ Errore setup credenziali rclone per {username}")
                return False
            
            # Backup home esistente
            backup_path = self._backup_existing_home(home_path, username)
            
            # Mount con rclone
            if mount_remote(remote_name, home_path, background=True, profile=profile):
                # Impostazioni permessi post-mount
                uid, gid = get_user_uid_gid(username)
                run(["chown", f"{uid}:{gid}", home_path], check=False)
                
                # Ripristina file importanti
                if backup_path:
                    self._restore_important_files(backup_path, home_path, username)
                
                return True
            
            return False
            
        except Exception as e:
            print(f"❌ Errore mount rclone: {e}")
            return False
    
    def _mount_with_davfs2(self, username: str, password: str, home_path: str) -> bool:
        """Mount con davfs2 (fallback)"""
        try:
            # Installa/configura davfs2 se necessario
            if not self.webdav_manager.install_davfs2():
                return False
            if not self.webdav_manager.configure_davfs2():
                return False
            
            # Delega al WebDAVMountManager esistente
            return self.webdav_manager.mount_webdav_home(username, password, home_path)
            
        except Exception as e:
            print(f"❌ Errore mount davfs2: {e}")
            return False
    
    def _detect_mount_engine(self, mount_point: str) -> Optional[MountEngine]:
        """Rileva quale engine sta usando un mount point"""
        try:
            mount_output = run(["mount"], check=False)
            
            for line in mount_output.split('\n'):
                if mount_point in line:
                    if "fuse.rclone" in line or "rclone" in line:
                        return MountEngine.RCLONE
                    elif "davfs" in line:
                        return MountEngine.DAVFS2
            
            return None
        except:
            return None
    
    def _backup_existing_home(self, home_path: str, username: str) -> Optional[str]:
        """Backup directory home esistente (riutilizza logica webdav)"""
        return self.webdav_manager.backup_existing_home(home_path, username)
    
    def _restore_important_files(self, backup_path: str, home_path: str, username: str) -> bool:
        """Ripristina file importanti (riutilizza logica webdav)"""
        return self.webdav_manager.restore_important_files(backup_path, home_path, username)
    
    def unmount_user_home(self, home_path: str) -> bool:
        """Smonta home directory (rileva engine automaticamente)"""
        engine = self._detect_mount_engine(home_path)
        
        if engine == MountEngine.RCLONE:
            return unmount(home_path)
        elif engine == MountEngine.DAVFS2:
            return self.webdav_manager.unmount_webdav(home_path)
        else:
            # Tentativo generico
            try:
                run(["fusermount", "-u", home_path], check=False)
                run(["umount", home_path], check=False)
                return True
            except:
                return False
    
    def create_systemd_service(self, username: str, password: str, home_path: str = None,
                              engine: MountEngine = None, profile: str = None) -> str:
        """Crea servizio systemd per mount automatico"""
        if not engine:
            engine = self.preferred_engine
        
        if not home_path:
            home_path = f"/home/{username}"
        
        service_name = f"{self.config['service_prefix']}-{engine.value}-{username}"
        
        if engine == MountEngine.RCLONE:
            # Setup remote prima di creare servizio
            remote_name = f"nc-{username}"
            self.setup_credentials(username, password, MountEngine.RCLONE)
            
            # Usa il generatore rclone esistente
            service_content = create_systemd_mount_service(
                service_name, remote_name, home_path, "root", profile or "writes"
            )
        elif engine == MountEngine.DAVFS2:
            # Usa il generatore webdav esistente
            service_name = self.webdav_manager.create_systemd_service(username, password, home_path)
            return service_name
        
        # Scrivi file servizio
        service_file = f"/etc/systemd/system/{service_name}.service"
        with open(service_file, 'w') as f:
            f.write(service_content)
        
        # Reload systemd
        run(["systemctl", "daemon-reload"])
        
        print(f"✅ Servizio creato: {service_name}.service")
        return service_name
    
    def list_mounts(self) -> List[Dict]:
        """Lista tutti i mount attivi con informazioni engine"""
        mounts = []
        
        # Mount rclone
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
        
        # Mount davfs2
        webdav_mounts = self.webdav_manager.list_webdav_mounts()
        for mount in webdav_mounts:
            mounts.append({
                "engine": MountEngine.DAVFS2,
                "remote": mount.get("url", ""),
                "mountpoint": mount.get("mountpoint", ""),
                "type": "davfs2",
                "options": mount.get("options", "")
            })
        
        return mounts
    
    def get_mount_status(self, home_path: str) -> Dict:
        """Status dettagliato di un mount"""
        if not is_mounted(home_path):
            return {
                "mounted": False,
                "engine": None,
                "status": "Not mounted"
            }
        
        engine = self._detect_mount_engine(home_path)
        
        if engine == MountEngine.RCLONE:
            return {
                "mounted": True,
                "engine": MountEngine.RCLONE,
                "status": "Active (rclone)",
                "profile": self._detect_rclone_profile(home_path)
            }
        elif engine == MountEngine.DAVFS2:
            return {
                "mounted": True,
                "engine": MountEngine.DAVFS2,
                "status": "Active (davfs2)",
                **self.webdav_manager.get_mount_status(home_path)
            }
        else:
            return {
                "mounted": True,
                "engine": "unknown",
                "status": "Active (unknown engine)"
            }
    
    def _detect_rclone_profile(self, mount_point: str) -> Optional[str]:
        """Rileva profilo rclone da mount attivo (se possibile)"""
        try:
            # Leggi da systemd se è un servizio
            services = run(["systemctl", "list-units", "--type=service", "--state=active"], check=False)
            for line in services.split('\n'):
                if f"rclone" in line and mount_point.replace("/", "-") in line:
                    # Questo è approssimativo, potremmo migliorare
                    if "writes" in line:
                        return "writes"
                    elif "minimal" in line:
                        return "minimal"
                    elif "hosting" in line:
                        return "hosting"
            
            return "writes"  # Default
        except:
            return None
    
    def get_recommended_engine(self) -> MountEngine:
        """Consiglia engine migliore per il sistema corrente"""
        available = self.detect_available_engines()
        
        if available[MountEngine.RCLONE]:
            return MountEngine.RCLONE
        elif available[MountEngine.DAVFS2]:
            return MountEngine.DAVFS2
        else:
            # Preferiamo installare rclone
            return MountEngine.RCLONE
    
    def get_mount_profiles(self, engine: MountEngine = None) -> Dict:
        """Ottieni profili mount disponibili per engine"""
        if not engine:
            engine = self.preferred_engine
        
        if engine == MountEngine.RCLONE:
            return MOUNT_PROFILES
        elif engine == MountEngine.DAVFS2:
            return {
                "default": {
                    "description": "Configurazione davfs2 ottimizzata",
                    "use_case": "WebDAV diretto con cache locale",
                    "storage": "Configurabile (default 10GB)",
                    "performance": "Buona con cache",
                    "sync": "Bidirezionale"
                }
            }
        
        return {}


def setup_user_with_mount(username: str, password: str, quota: str = None,
                         fs_percentage: float = 0.02, engine: MountEngine = None,
                         profile: str = None) -> bool:
    """
    Setup completo utente con mount engine unificato
    
    Args:
        username: Nome utente
        password: Password
        quota: Quota Nextcloud (es. "100G")
        fs_percentage: Percentuale filesystem per quota BTRFS
        engine: Engine mount (default: rclone)
        profile: Profilo mount (solo per rclone)
    
    Returns:
        True se setup completato
    """
    print(f"🚀 Setup completo per {username} (engine: {engine or 'auto'})")
    
    mount_manager = MountManager(engine or MountEngine.RCLONE)
    
    # 1. Rileva e installa engine necessario
    available_engines = mount_manager.detect_available_engines()
    target_engine = engine or mount_manager.get_recommended_engine()
    
    if not available_engines[target_engine]:
        print(f"📦 Installando {target_engine.value}...")
        if not mount_manager.install_engine(target_engine):
            return False
    
    # 2. Configura engine
    if not mount_manager.configure_engine(target_engine):
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
    
    # 5. Mount con engine unificato
    home_path = f"/home/{username}"
    mount_result = mount_manager.mount_user_home(
        username, password, home_path, target_engine, profile
    )
    
    if not mount_result["success"]:
        print(f"❌ {mount_result['message']}")
        return False
    
    engine_used = mount_result["engine_used"]
    if mount_result["fallback_used"]:
        print(f"⚠️ Usato fallback {engine_used.value}")
    else:
        print(f"✅ Mount riuscito con {engine_used.value}")
    
    if mount_result.get("profile"):
        print(f"📊 Profilo: {mount_result['profile']}")
    
    # 6. Setup quota se richiesta
    if quota:
        from .quota import setup_quota_for_user
        if setup_quota_for_user(username, quota, fs_percentage):
            print(f"✅ Quota configurata: {quota}")
        else:
            print(f"⚠️ Avviso: errore configurazione quota")
    
    # 7. Crea servizio systemd
    try:
        service_name = mount_manager.create_systemd_service(
            username, password, home_path, engine_used, mount_result.get("profile")
        )
        
        # Abilita servizio
        run(["systemctl", "enable", "--now", f"{service_name}.service"], check=False)
        print(f"✅ Servizio automatico: {service_name}")
        
    except Exception as e:
        print(f"⚠️ Avviso servizio systemd: {e}")
    
    print(f"🎉 Setup completato per {username}")
    print(f"Engine: {engine_used.value}" + (f" (profilo: {mount_result.get('profile', 'default')})" if engine_used == MountEngine.RCLONE else ""))
    print(f"Home directory: {home_path} → Nextcloud WebDAV")
    
    return True
