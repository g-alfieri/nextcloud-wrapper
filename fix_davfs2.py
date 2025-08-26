#!/usr/bin/env python3
"""
Fix rapido configurazione davfs2
"""
import sys
import os

# Add project directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

print("🔧 Fix rapido configurazione davfs2")
print("=" * 40)

def main():
    try:
        # Rimuovi configurazione esistente
        config_file = "/etc/davfs2/davfs2.conf"
        if os.path.exists(config_file):
            os.rename(config_file, f"{config_file}.broken.backup")
            print(f"📦 Backup configurazione rotta: {config_file}.broken.backup")
        
        # Ricrea configurazione
        from ncwrap.webdav import WebDAVMountManager
        webdav_manager = WebDAVMountManager()
        
        print("🔧 Ricreando configurazione davfs2...")
        if webdav_manager.configure_davfs2():
            print("✅ Configurazione ricreata")
            
            # Test configurazione
            if webdav_manager.test_davfs2_config():
                print("✅ Test configurazione OK")
            else:
                print("⚠️ Test configurazione fallito")
            
            # Correzione permessi
            webdav_manager.fix_davfs2_permissions()
            print("✅ Permessi corretti")
            
        else:
            print("❌ Errore ricreazione configurazione")
            return False
        
        # Mostra nuova configurazione
        print(f"\n📄 Nuova configurazione davfs2:")
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                lines = f.readlines()
                for i, line in enumerate(lines[:15], 1):  # Prime 15 righe
                    line = line.rstrip()
                    if line and not line.startswith('#'):
                        print(f"   {i:2}: {line}")
                    elif line.startswith('#'):
                        print(f"   {i:2}: {line}")
        
        print(f"\n✅ Configurazione davfs2 corretta!")
        return True
        
    except Exception as e:
        print(f"❌ Errore: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if main():
        print("\n🚀 Ora prova:")
        print("sudo mount -t davfs https://ncloud.charax.io/remote.php/dav/files/charax.io/ /tmp/test")
        print("\nOppure riprova il setup completo:")
        print("nextcloud-wrapper setup user charax.io 'Fy3qesHymfVQ*1' --quota 10G --fs-percentage 0.1 --service --backup")
    else:
        print("\n❌ Fix fallito")
        sys.exit(1)
