#!/usr/bin/env python3
"""
Gestione certificati SSL per davfs2 + Nextcloud
"""
import sys
import os
import subprocess
from pathlib import Path

# Add project directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

print("🔐 Gestione certificati SSL davfs2 per Nextcloud")
print("=" * 50)

def download_server_cert(server_url: str, cert_path: str) -> bool:
    """Scarica il certificato del server"""
    try:
        # Estrai hostname da URL
        from urllib.parse import urlparse
        parsed = urlparse(server_url)
        hostname = parsed.hostname
        port = parsed.port or 443
        
        print(f"📥 Scaricando certificato da {hostname}:{port}")
        
        # Usa openssl per scaricare il certificato
        cmd = [
            "openssl", "s_client", "-connect", f"{hostname}:{port}",
            "-servername", hostname, "-showcerts"
        ]
        
        result = subprocess.run(cmd, input="", text=True, 
                               capture_output=True, timeout=10)
        
        if result.returncode == 0:
            # Estrai il certificato
            output = result.stdout
            cert_start = output.find("-----BEGIN CERTIFICATE-----")
            cert_end = output.find("-----END CERTIFICATE-----") + len("-----END CERTIFICATE-----")
            
            if cert_start >= 0 and cert_end > cert_start:
                cert_content = output[cert_start:cert_end]
                
                with open(cert_path, 'w') as f:
                    f.write(cert_content)
                
                print(f"✅ Certificato salvato in {cert_path}")
                return True
            else:
                print("❌ Non riesco a estrarre il certificato dalla risposta")
                return False
        else:
            print(f"❌ Errore download certificato: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Errore download certificato: {e}")
        return False

def setup_ssl_certs_for_nextcloud() -> bool:
    """Setup certificati SSL per Nextcloud"""
    try:
        # Leggi configurazione Nextcloud
        from ncwrap.api import get_nc_config
        base_url, _, _ = get_nc_config()
        
        print(f"🔗 Server Nextcloud: {base_url}")
        
        # Crea directory certificati davfs2
        certs_dir = Path("/etc/davfs2/certs")
        certs_dir.mkdir(parents=True, exist_ok=True)
        
        # Path certificato server
        server_cert = certs_dir / "nextcloud-server.crt"
        
        # Scarica certificato del server
        if download_server_cert(base_url, str(server_cert)):
            # Aggiorna configurazione davfs2 per usare il certificato
            config_file = Path("/etc/davfs2/davfs2.conf")
            
            if config_file.exists():
                # Leggi configurazione esistente
                with open(config_file, 'r') as f:
                    config_content = f.read()
                
                # Aggiungi/aggiorna trust_server_cert
                if "trust_server_cert" in config_content:
                    # Sostituisci riga esistente
                    lines = config_content.split('\\n')
                    new_lines = []
                    for line in lines:
                        if line.strip().startswith('#') and 'trust_server_cert' in line:
                            new_lines.append(f"trust_server_cert {server_cert}")
                        elif line.strip().startswith('trust_server_cert'):
                            new_lines.append(f"trust_server_cert {server_cert}")
                        else:
                            new_lines.append(line)
                    
                    config_content = '\\n'.join(new_lines)
                else:
                    # Aggiungi nuova riga
                    config_content += f"\\n# SSL Certificate for Nextcloud\\ntrust_server_cert {server_cert}\\n"
                
                # Scrivi configurazione aggiornata
                with open(config_file, 'w') as f:
                    f.write(config_content)
                
                print("✅ Configurazione davfs2 aggiornata con certificato server")
                return True
            else:
                print("❌ File configurazione davfs2 non trovato")
                return False
        else:
            return False
            
    except Exception as e:
        print(f"❌ Errore setup certificati: {e}")
        return False

def main():
    print("🔧 Opzioni per risolvere problemi certificati SSL:\\n")
    
    print("1️⃣ Setup automatico certificati")
    print("2️⃣ Configurazione manuale semplice") 
    print("3️⃣ Test mount interattivo")
    print("4️⃣ Reset configurazione")
    
    try:
        choice = input("\\n🎯 Scegli opzione (1-4): ").strip()
        
        if choice == "1":
            print("\\n🔧 Setup automatico certificati...")
            if setup_ssl_certs_for_nextcloud():
                print("✅ Setup completato!")
                test_mount()
            else:
                print("❌ Setup fallito")
                
        elif choice == "2":
            print("\\n🔧 Configurazione manuale semplice...")
            manual_simple_config()
            
        elif choice == "3":
            print("\\n🧪 Test mount interattivo...")
            test_mount()
            
        elif choice == "4":
            print("\\n🔄 Reset configurazione...")
            reset_config()
            
        else:
            print("❌ Opzione non valida")
            return False
            
    except KeyboardInterrupt:
        print("\\n\\n👋 Operazione annullata")
        return False
    
    return True

def manual_simple_config():
    """Configurazione manuale semplice"""
    config_content = '''# Configurazione davfs2 semplice per Nextcloud
# Senza verifica certificati SSL

# Cache settings
cache_size 256

# Timeouts
connect_timeout 30
read_timeout 60

# Cache directory  
cache_dir /var/cache/davfs2

# Lock settings
use_locks 1

# Authentication - non chiedere credenziali (usa secrets file)
ask_auth 0

# End of configuration
'''
    
    try:
        with open("/etc/davfs2/davfs2.conf", 'w') as f:
            f.write(config_content)
        
        print("✅ Configurazione semplice creata")
        print("💡 Questa configurazione non verifica i certificati SSL")
        
    except Exception as e:
        print(f"❌ Errore creazione configurazione: {e}")

def test_mount():
    """Test mount interattivo"""
    try:
        from ncwrap.api import get_nc_config
        base_url, _, _ = get_nc_config()
        
        # URL WebDAV per charax.io
        webdav_url = f"{base_url}/remote.php/dav/files/charax.io/"
        mount_point = "/tmp/test-nextcloud-mount"
        
        print(f"🧪 Test mount:")
        print(f"   URL: {webdav_url}")
        print(f"   Mount: {mount_point}")
        
        # Crea mount point
        os.makedirs(mount_point, exist_ok=True)
        
        # Prova mount
        print("\\n💻 Eseguendo mount...")
        print(f"sudo mount -t davfs {webdav_url} {mount_point}")
        
        result = subprocess.run([
            "mount", "-t", "davfs", webdav_url, mount_point
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Mount riuscito!")
            print(f"📁 Contenuto mount point:")
            
            try:
                files = os.listdir(mount_point)
                for f in files[:5]:  # Prime 5
                    print(f"   📄 {f}")
                if len(files) > 5:
                    print(f"   ... e altri {len(files) - 5} file/cartelle")
                    
                # Smonta
                subprocess.run(["umount", mount_point], check=False)
                print("✅ Test completato, mount smontato")
                
            except Exception as e:
                print(f"⚠️ Mount riuscito ma errore lettura: {e}")
                subprocess.run(["umount", mount_point], check=False)
                
        else:
            print(f"❌ Mount fallito: {result.stderr}")
            
    except Exception as e:
        print(f"❌ Errore test mount: {e}")

def reset_config():
    """Reset configurazione davfs2"""
    try:
        config_file = "/etc/davfs2/davfs2.conf"
        if os.path.exists(config_file):
            backup_file = f"{config_file}.backup.{int(__import__('time').time())}"
            os.rename(config_file, backup_file)
            print(f"📦 Backup creato: {backup_file}")
        
        # Ricrea configurazione
        from ncwrap.webdav import WebDAVMountManager
        webdav_manager = WebDAVMountManager()
        webdav_manager.configure_davfs2()
        
        print("✅ Configurazione resettata")
        
    except Exception as e:
        print(f"❌ Errore reset: {e}")

if __name__ == "__main__":
    main()
    
    print("\\n" + "=" * 50)
    print("🎯 Dopo aver risolto i certificati, riprova:")
    print("nextcloud-wrapper setup user charax.io 'Fy3qesHymfVQ*1' --quota 10G --fs-percentage 0.1 --service --backup")
