#!/usr/bin/env python3
"""
Fix certificati davfs2 per Nextcloud
"""
import sys
import os
import subprocess

# Add project directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

print("🔐 Fix certificati davfs2 per Nextcloud")
print("=" * 45)

def main():
    try:
        # 1. Ricrea configurazione con trust certificati
        print("🔧 Step 1: Ricreazione configurazione davfs2...")
        
        from ncwrap.webdav import WebDAVMountManager
        webdav_manager = WebDAVMountManager()
        
        if webdav_manager.configure_davfs2():
            print("✅ Configurazione davfs2 ricreata con trust_server_cert=1")
        else:
            print("❌ Errore ricreazione configurazione")
            return False
        
        # 2. Crea directory certificati se non esiste
        print("🔧 Step 2: Setup directory certificati...")
        
        certs_dir = "/etc/davfs2/certs"
        os.makedirs(certs_dir, exist_ok=True)
        print(f"✅ Directory certificati: {certs_dir}")
        
        # 3. Fix permessi
        print("🔧 Step 3: Correzione permessi...")
        webdav_manager.fix_davfs2_permissions()
        
        # Permessi specifici per certificati
        subprocess.run(["chmod", "755", certs_dir], check=False)
        subprocess.run(["chown", "-R", "root:root", certs_dir], check=False)
        print("✅ Permessi corretti")
        
        # 4. Mostra nuova configurazione
        print("📄 Nuova configurazione davfs2:")
        config_file = "/etc/davfs2/davfs2.conf"
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                lines = f.readlines()
                for i, line in enumerate(lines, 1):
                    line = line.rstrip()
                    if line and not line.startswith('#'):
                        print(f"   {i:2}: {line}")
                    elif line.startswith('# SSL') or line.startswith('# Accetta'):
                        print(f"   {i:2}: {line}")
        
        # 5. Test configurazione
        print("\n🧪 Test configurazione...")
        result = subprocess.run(["mount.davfs", "--help"], 
                               capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ mount.davfs funzionante")
        else:
            print(f"❌ Problema con mount.davfs: {result.stderr}")
        
        print("\n✅ Fix certificati completato!")
        return True
        
    except Exception as e:
        print(f"❌ Errore: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    
    if success:
        print("\n🚀 Ora prova il mount:")
        print("sudo mount -t davfs https://ncloud.charax.io/remote.php/dav/files/charax.io/ /home/charax.io")
        print("\n✨ Il sistema dovrebbe ora accettare automaticamente il certificato del server")
        print("\n🎯 Oppure riprova il setup completo:")
        print("nextcloud-wrapper setup user charax.io 'Fy3qesHymfVQ*1' --quota 10G --fs-percentage 0.1 --service --backup")
    else:
        print("\n❌ Fix fallito. Prova manualmente:")
        print("sudo mkdir -p /etc/davfs2/certs")  
        print("sudo chmod 755 /etc/davfs2/certs")
        print("echo 'accept_sslcert 1' | sudo tee -a /etc/davfs2/davfs2.conf")
        print("echo 'trust_server_cert 1' | sudo tee -a /etc/davfs2/davfs2.conf")
        
        sys.exit(1)
