"""
Mount WebDAV diretto per home directory = Nextcloud root
"""
import os
import shutil
import time
from pathlib import Path
from typing import Optional, Dict
from .utils import run, ensure_dir, get_user_uid_gid, is_command_available, is_mounted
from .api import get_nc_config


class WebDAVMountManager:
    """Gestore mount WebDAV diretto per home directories"""
    
    def __init__(self):
        self.davfs_config_dir = Path("/etc/davfs2")
        self.cache_dir = Path("/var/cache/davfs2")
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """Carica configurazione da variabili ambiente"""
        return {
            "cache_size": int(os.environ.get("NC_WEBDAV_CACHE_SIZE", "256")),
            "connect_timeout": int(os.environ.get("NC_WEBDAV_CONNECT_TIMEOUT", "30")),
            "read_timeout": int(os.environ.get("NC_WEBDAV_READ_TIMEOUT", "60")),
            "retry_count": int(os.environ.get("NC_WEBDAV_RETRY_COUNT", "3")),
            "use_locks": os.environ.get("NC_WEBDAV_USE_LOCKS", "true").lower() == "true",
            "file_mode": os.environ.get("NC_WEBDAV_FILE_MODE", "644"),
            "dir_mode": os.environ.get("NC_WEBDAV_DIR_MODE", "755"),
            "umask": os.environ.get("NC_WEBDAV_UMASK", "022"),
        }
    
    def install_davfs2(self) -> bool:
        """Installa davfs2 se non presente"""
        if is_command_available("mount.davfs"):
            print("✅ davfs2 già installato")
            return True
        
        print("📦 Installando davfs2...")
        
        # Rileva il sistema operativo e package manager
        package_managers = [
            # Fedora, RHEL 8+, CentOS 8+
            {"cmd": "dnf", "install": ["dnf", "install", "-y", "davfs2"]},
            # Ubuntu, Debian
            {"cmd": "apt", "install": ["apt", "install", "-y", "davfs2"], "update": ["apt", "update"]},
            # CentOS 7, RHEL 7
            {"cmd": "yum", "install": ["yum", "install", "-y", "davfs2"]},
            # openSUSE
            {"cmd": "zypper", "install": ["zypper", "install", "-y", "davfs2"]},
            # Arch Linux
            {"cmd": "pacman", "install": ["pacman", "-S", "--noconfirm", "davfs2"]},
        ]
        
        for pm in package_managers:
            if is_command_available(pm["cmd"]):
                try:
                    print(f"⚙️ Usando {pm['cmd']} per installare davfs2...")
                    
                    # Esegui update se specificato (per apt)
                    if "update" in pm:
                        print(f"🔄 Aggiornamento repository con {pm['cmd']}...")
                        run(pm["update"], check=False)
                    
                    # Installa il pacchetto
                    run(pm["install"])
                    
                    # Verifica installazione
                    if is_command_available("mount.davfs"):
                        print("✅ davfs2 installato con successo")
                        return True
                    else:
                        print(f"⚠️ Installazione completata ma mount.davfs non trovato")
                        
                except RuntimeError as e:
                    print(f"❌ Errore con {pm['cmd']}: {e}")
                    continue
        
        # Se arriviamo qui, nessun package manager ha funzionato
        print("❌ Impossibile installare davfs2 automaticamente")
        print("💡 Installa manualmente:")
        print("   Fedora/RHEL/CentOS: dnf install davfs2")
        print("   Ubuntu/Debian: apt install davfs2")
        print("   openSUSE: zypper install davfs2")
        print("   Arch Linux: pacman -S davfs2")
        
        return False
    
    def configure_davfs2(self) -> bool:
        """Configura davfs2 per uso ottimale con Nextcloud"""
        try:
            davfs_conf = self.davfs_config_dir / "davfs2.conf"
            
            # Backup configurazione esistente
            if davfs_conf.exists():
                backup_path = f"{davfs_conf}.backup.{int(time.time())}"
                shutil.copy2(davfs_conf, backup_path)
                print(f"📦 Backup configurazione: {backup_path}")
            
            # Configurazione ottimizzata per Nextcloud
            config_content = f"""# Configurazione davfs2 ottimizzata per Nextcloud
# Generata da nextcloud-wrapper v0.3.0

# Davfs2 configuration file
# Questo file deve essere modificato per ogni installazione specifica

# Cache settings
cache_size {self.config['cache_size']}
table_size 4096
delay_upload 0
guess_mime_type 1

# Timeouts (in seconds)
connect_timeout {self.config['connect_timeout']}
read_timeout {self.config['read_timeout']}
retry {self.config['retry_count']}
max_retry 10

# Cache directory (must exist and be writable by davfs2)
cache_dir {self.cache_dir}

# Lock settings
use_locks {1 if self.config['use_locks'] else 0}
lock_timeout 300

# File permissions
umask {self.config['umask']}
file_mode {self.config['file_mode']}
dir_mode {self.config['dir_mode']}

# Network settings
use_expect100 0
n_cookies 0

# Debugging (uncomment for troubleshooting)
# debug config,kernel,cache,http_auth,xml,httpbody

# Trust server certificate (set to 1 only for testing with self-signed certs)
trust_server_cert 0

# Buffer size for network operations  
buf_size 16384
"""
            
            # Crea directory configurazione se non esiste
            ensure_dir(self.davfs_config_dir)
            
            with open(davfs_conf, 'w') as f:
                f.write(config_content)
            
            # Crea directory cache
            ensure_dir(self.cache_dir)
            run(["chmod", "755", str(self.cache_dir)])
            
            print("✅ davfs2 configurato")
            return True
            
        except Exception as e:
            print(f"❌ Errore configurazione davfs2: {e}")
            return False
    
    def test_davfs2_config(self) -> bool:
        """Testa la configurazione davfs2"""
        try:
            davfs_conf = self.davfs_config_dir / "davfs2.conf"
            
            if not davfs_conf.exists():
                print("⚠️ File configurazione davfs2 non trovato")
                return False
            
            # Test parsing del file di configurazione
            # Eseguiamo mount.davfs --help per vedere se funziona
            result = run(["mount.davfs", "--help"], check=False)
            
            if "mount.davfs" in result:
                print("✅ mount.davfs funzionante")
                return True
            else:
                print("❌ mount.davfs non funziona correttamente")
                return False
                
        except Exception as e:
            print(f"❌ Errore test configurazione: {e}")
            return False
    
    def fix_davfs2_permissions(self) -> bool:
        """Corregge i permessi per davfs2"""
        try:
            # Assicurati che l'utente sia nel gruppo davfs2
            run(["usermod", "-a", "-G", "davfs2", "root"], check=False)
            
            # Permessi directory cache
            if self.cache_dir.exists():
                run(["chmod", "755", str(self.cache_dir)], check=False)
                run(["chown", "root:root", str(self.cache_dir)], check=False)
            
            # Permessi file configurazione
            davfs_conf = self.davfs_config_dir / "davfs2.conf"
            if davfs_conf.exists():
                run(["chmod", "644", str(davfs_conf)], check=False)
            
            secrets_file = self.davfs_config_dir / "secrets"
            if secrets_file.exists():
                run(["chmod", "600", str(secrets_file)], check=False)
                run(["chown", "root:root", str(secrets_file)], check=False)
            
            return True
            
        except Exception as e:
            print(f"⚠️ Errore correzione permessi: {e}")
            return False
    
    def setup_user_credentials(self, username: str, password: str, webdav_url: str) -> bool:
        """Setup credenziali davfs2 per utente"""
        try:
            secrets_file = self.davfs_config_dir / "secrets"
            
            # Leggi file esistente
            existing_lines = []
            if secrets_file.exists():
                with open(secrets_file, 'r') as f:
                    existing_lines = f.readlines()
            
            # Rimuovi eventuali righe esistenti per questo URL/utente
            filtered_lines = [
                line for line in existing_lines 
                if not (webdav_url in line or username in line)
            ]
            
            # Aggiungi nuova credenziale
            new_line = f"{webdav_url} {username} {password}\n"
            filtered_lines.append(new_line)
            
            # Scrivi file aggiornato
            with open(secrets_file, 'w') as f:
                f.writelines(filtered_lines)
            
            # Permessi sicuri
            os.chmod(secrets_file, 0o600)
            
            print(f"🔐 Credenziali configurate per {username}")
            return True
            
        except Exception as e:
            print(f"❌ Errore setup credenziali: {e}")
            return False
    
    def backup_existing_home(self, home_path: str, username: str) -> Optional[str]:
        """Backup directory home esistente se necessaria"""
        if not os.path.exists(home_path):
            return None
        
        # Verifica se è già un mount
        if is_mounted(home_path):
            print(f"ℹ️ {home_path} già montato, skip backup")
            return None
        
        # Verifica contenuti
        try:
            contents = os.listdir(home_path)
            if not contents:
                print(f"ℹ️ {home_path} vuoto, skip backup")
                return None
        except PermissionError:
            print(f"⚠️ Impossibile leggere {home_path}, assumo contenuti importanti")
        
        # Crea backup
        backup_path = f"{home_path}.backup.{int(time.time())}"
        try:
            shutil.move(home_path, backup_path)
            print(f"📦 Backup creato: {backup_path}")
            return backup_path
        except Exception as e:
            print(f"⚠️ Errore backup: {e}")
            return None
    
    def restore_important_files(self, backup_path: str, home_path: str, username: str) -> bool:
        """Ripristina file importanti dal backup nella home WebDAV"""
        if not backup_path or not os.path.exists(backup_path):
            return False
        
        try:
            # File di configurazione da ripristinare
            config_files = ['.bashrc', '.profile', '.bash_profile', '.vimrc', '.gitconfig']
            
            restored_count = 0
            for file_name in config_files:
                backup_file = os.path.join(backup_path, file_name)
                home_file = os.path.join(home_path, file_name)
                
                if os.path.exists(backup_file):
                    try:
                        shutil.copy2(backup_file, home_file)
                        print(f"📄 Ripristinato: {file_name}")
                        restored_count += 1
                    except Exception as e:
                        print(f"⚠️ Errore ripristino {file_name}: {e}")
            
            # Crea directory .local-backup per file sensibili
            local_backup_dir = os.path.join(home_path, '.local-backup')
            try:
                os.makedirs(local_backup_dir, exist_ok=True)
                
                # Sposta directory sensibili in .local-backup (NON sincronizzate)
                sensitive_dirs = ['.ssh', '.gnupg', '.pki', '.config/systemd']
                for dir_name in sensitive_dirs:
                    backup_dir_path = os.path.join(backup_path, dir_name)
                    local_dir_path = os.path.join(local_backup_dir, dir_name)
                    
                    if os.path.exists(backup_dir_path):
                        # Crea directory padre se necessario
                        os.makedirs(os.path.dirname(local_dir_path), exist_ok=True)
                        shutil.move(backup_dir_path, local_dir_path)
                        print(f"🔐 Spostato in .local-backup: {dir_name}")
                
                # Imposta ownership corretto
                uid, gid = get_user_uid_gid(username)
                run(["chown", "-R", f"{uid}:{gid}", local_backup_dir])
                        
            except Exception as e:
                print(f"⚠️ Errore setup .local-backup: {e}")
            
            print(f"✅ Ripristinati {restored_count} file di configurazione")
            return restored_count > 0
            
        except Exception as e:
            print(f"❌ Errore ripristino file: {e}")
            return False
    
    def mount_webdav_home(self, username: str, password: str, home_path: str = None) -> bool:
        """
        Monta WebDAV Nextcloud direttamente nella home directory dell'utente
        
        Args:
            username: Nome utente
            password: Password utente
            home_path: Path home custom (default: /home/username)
            
        Returns:
            True se mount riuscito
        """
        if not home_path:
            home_path = f"/home/{username}"
        
        try:
            base_url, _, _ = get_nc_config()
            webdav_url = f"{base_url}/remote.php/dav/files/{username}/"
            
            print(f"🔗 Montando WebDAV {username} in {home_path}")
            print(f"URL: {webdav_url}")
            
            # Setup credenziali
            if not self.setup_user_credentials(username, password, webdav_url):
                return False
            
            # Test e correggi configurazione davfs2
            print("🔍 Test configurazione davfs2...")
            if not self.test_davfs2_config():
                print("🔧 Correzione configurazione davfs2...")
                self.fix_davfs2_permissions()
                
                # Ricrea configurazione con opzioni di base
                self.configure_davfs2()
            
            # Backup home esistente
            backup_path = self.backup_existing_home(home_path, username)
            
            # Crea mount point
            ensure_dir(home_path)
            
            # Ottieni UID/GID utente
            uid, gid = get_user_uid_gid(username)
            
            # Mount WebDAV
            mount_cmd = [
                "mount", "-t", "davfs",
                webdav_url,
                home_path,
                "-o", f"uid={uid},gid={gid},rw,user,noauto"
            ]
            
            try:
                run(mount_cmd)
                print(f"✅ WebDAV montato: {webdav_url} → {home_path}")
            except RuntimeError as e:
                print(f"⚠️ Primo tentativo mount fallito: {e}")
                print("🔧 Provo con opzioni semplificate...")
                
                # Tentativo con opzioni più semplici
                simple_mount_cmd = [
                    "mount", "-t", "davfs",
                    webdav_url,
                    home_path
                ]
                
                try:
                    run(simple_mount_cmd)
                    print(f"✅ WebDAV montato (modalità semplice): {webdav_url} → {home_path}")
                    
                    # Correggi permessi post-mount
                    run(["chown", f"{uid}:{gid}", home_path], check=False)
                    run(["chmod", "755", home_path], check=False)
                    
                except RuntimeError as mount_error:
                    print(f"❌ Anche il mount semplice è fallito: {mount_error}")
                    
                    # Informazioni di debug
                    print("📊 Debug info:")
                    print(f"   URL: {webdav_url}")
                    print(f"   Mount point: {home_path}")
                    print(f"   UID/GID: {uid}/{gid}")
                    
                    # Test connettività WebDAV
                    from .api import test_webdav_connectivity
                    if test_webdav_connectivity(username, password):
                        print("   ✅ Connettività WebDAV OK")
                    else:
                        print("   ❌ Connettività WebDAV fallita")
                    
                    # Suggerimenti
                    print("💡 Suggerimenti:")
                    print("   1. Verifica che davfs2 sia installato: mount.davfs --version")
                    print("   2. Controlla i log: journalctl -u systemd-logind")
                    print("   3. Test manuale: mount -t davfs [URL] [PATH]")
                    print(f"   4. Verifica URL: {webdav_url}")
                    
                    return False
            
            # Ripristina file importanti se esisteva backup
            if backup_path:
                self.restore_important_files(backup_path, home_path, username)
            
            return True
            
        except Exception as e:
            print(f"❌ Errore mount WebDAV per {username}: {e}")
            return False
    
    def unmount_webdav(self, home_path: str) -> bool:
        """Smonta WebDAV"""
        try:
            if not is_mounted(home_path):
                print(f"ℹ️ {home_path} non è montato")
                return True
            
            run(["umount", home_path])
            print(f"✅ WebDAV smontato: {home_path}")
            return True
        except RuntimeError as e:
            print(f"❌ Errore unmount: {e}")
            return False
    
    def create_systemd_service(self, username: str, password: str, home_path: str = None) -> str:
        """Crea servizio systemd per mount WebDAV automatico"""
        if not home_path:
            home_path = f"/home/{username}"
        
        base_url, _, _ = get_nc_config()
        webdav_url = f"{base_url}/remote.php/dav/files/{username}/"
        service_name = f"webdav-home-{username}"
        
        # Setup credenziali prima di creare il servizio
        self.setup_user_credentials(username, password, webdav_url)
        
        uid, gid = get_user_uid_gid(username)
        
        service_content = f"""[Unit]
Description=WebDAV mount for {username} home directory
After=network-online.target
Wants=network-online.target
Before=systemd-user-sessions.service

[Service]
Type=oneshot
RemainAfterExit=yes
User=root
Group=root
ExecStartPre=/bin/mkdir -p {home_path}
ExecStart=/bin/mount -t davfs {webdav_url} {home_path} -o uid={uid},gid={gid},rw,user,noauto
ExecStop=/bin/umount {home_path}
TimeoutSec=60
Restart=no

[Install]
WantedBy=multi-user.target
"""
        
        service_file = f"/etc/systemd/system/{service_name}.service"
        with open(service_file, 'w') as f:
            f.write(service_content)
        
        # Reload systemd
        run(["systemctl", "daemon-reload"])
        
        print(f"✅ Servizio WebDAV creato: {service_name}.service")
        return service_name
    
    def enable_service(self, service_name: str) -> bool:
        """Abilita e avvia servizio WebDAV"""
        try:
            run(["systemctl", "enable", "--now", f"{service_name}.service"])
            print(f"✅ Servizio abilitato: {service_name}")
            return True
        except RuntimeError as e:
            print(f"❌ Errore abilitazione servizio: {e}")
            return False
    
    def disable_service(self, service_name: str) -> bool:
        """Disabilita e ferma servizio WebDAV"""
        try:
            run(["systemctl", "disable", "--now", f"{service_name}.service"])
            print(f"✅ Servizio disabilitato: {service_name}")
            return True
        except RuntimeError as e:
            print(f"❌ Errore disabilitazione servizio: {e}")
            return False
    
    def get_mount_status(self, home_path: str) -> Dict:
        """Ottiene status mount WebDAV"""
        try:
            if not is_mounted(home_path):
                return {"mounted": False, "status": "Not mounted"}
            
            # Ottieni informazioni mount
            mount_output = run(["mount"], check=False)
            for line in mount_output.split('\n'):
                if home_path in line and "davfs" in line:
                    return {
                        "mounted": True,
                        "status": "Active",
                        "details": line.strip()
                    }
            
            return {"mounted": True, "status": "Unknown mount type"}
            
        except Exception as e:
            return {"mounted": False, "status": f"Error: {e}"}
    
    def list_webdav_mounts(self) -> list:
        """Lista tutti i mount WebDAV attivi"""
        try:
            mount_output = run(["mount", "-t", "davfs"], check=False)
            mounts = []
            
            for line in mount_output.split('\n'):
                if line.strip() and "davfs" in line:
                    parts = line.split()
                    if len(parts) >= 3:
                        mounts.append({
                            "url": parts[0],
                            "mountpoint": parts[2],
                            "options": ' '.join(parts[3:]) if len(parts) > 3 else ""
                        })
            
            return mounts
            
        except RuntimeError:
            return []


def setup_webdav_user(username: str, password: str, quota: str = None, 
                      fs_percentage: float = 0.02) -> bool:
    """
    Setup completo utente con WebDAV mount diretto nella home
    
    Args:
        username: Nome utente
        password: Password utente
        quota: Quota Nextcloud (es. "100G")
        fs_percentage: Percentuale filesystem per quota BTRFS
        
    Returns:
        True se setup completato con successo
    """
    print(f"🚀 Setup WebDAV completo per {username}")
    
    webdav_manager = WebDAVMountManager()
    
    # 1. Installa e configura davfs2
    if not webdav_manager.install_davfs2():
        return False
    
    if not webdav_manager.configure_davfs2():
        return False
    
    # 2. Crea utente Nextcloud se non esiste
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
    
    # 3. Crea utente Linux se non esiste
    from .system import create_linux_user, user_exists
    if not user_exists(username):
        # Non creare home directory qui, sarà il mount WebDAV
        if create_linux_user(username, password, create_home=False):
            print(f"✅ Utente Linux creato: {username}")
        else:
            print(f"❌ Errore creazione utente Linux: {username}")
            return False
    else:
        print(f"ℹ️ Utente Linux già esistente: {username}")
    
    # 4. Mount WebDAV nella home
    home_path = f"/home/{username}"
    if webdav_manager.mount_webdav_home(username, password, home_path):
        print(f"✅ WebDAV montato in home: {home_path}")
    else:
        print(f"❌ Errore mount WebDAV: {home_path}")
        return False
    
    # 5. Setup quota se richiesta
    if quota:
        from .quota import setup_quota_for_user
        if setup_quota_for_user(username, quota, fs_percentage):
            print(f"✅ Quota configurata: {quota}")
        else:
            print(f"⚠️ Avviso: errore configurazione quota")
    
    # 6. Crea servizio systemd per mount automatico
    try:
        service_name = webdav_manager.create_systemd_service(username, password, home_path)
        if webdav_manager.enable_service(service_name):
            print(f"✅ Mount automatico configurato")
        else:
            print(f"⚠️ Avviso: errore abilitazione servizio automatico")
    except Exception as e:
        print(f"⚠️ Avviso: errore creazione servizio systemd: {e}")
    
    print(f"🎉 Setup WebDAV completato per {username}")
    print(f"Home directory: {home_path} → WebDAV Nextcloud")
    
    return True
