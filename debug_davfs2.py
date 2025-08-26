#!/usr/bin/env python3
"""
Debug e fix per problemi davfs2
"""
import sys
import os
import subprocess

# Add project directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

print("🔧 Nextcloud Wrapper - Debug e Fix davfs2")
print("=" * 50)

def run_command(cmd, description):
    """Esegue un comando e mostra il risultato"""
    print(f"\n🔧 {description}")
    print(f"💻 Comando: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print("✅ Successo")
            if result.stdout:
                lines = result.stdout.split('\n')[:5]  # Prime 5 righe
                for line in lines:
                    if line.strip():
                        print(f"   📝 {line.strip()}")
        else:
            print(f"❌ Errore (exit code: {result.returncode})")
            if result.stderr:
                lines = result.stderr.split('\n')[:3]
                for line in lines:
                    if line.strip():
                        print(f"   🚫 {line.strip()}")
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Errore esecuzione: {e}")
        return False

def main():
    # Test 1: Verifica installazione davfs2
    print("🧪 Test 1: Verifica installazione davfs2")
    if run_command(["which", "mount.davfs"], "Controllo mount.davfs"):
        run_command(["mount.davfs", "--version"], "Versione davfs2")
    else:
        print("💡 Installa davfs2: sudo dnf install davfs2")
    
    # Test 2: Verifica configurazione davfs2
    print(f"\n🧪 Test 2: Verifica file configurazione")
    config_files = [
        "/etc/davfs2/davfs2.conf",
        "/etc/davfs2/secrets"
    ]
    
    for config_file in config_files:
        if os.path.exists(config_file):
            print(f"✅ {config_file} esiste")
            
            # Mostra permessi
            stat_info = os.stat(config_file)
            permissions = oct(stat_info.st_mode)[-3:]
            print(f"   📋 Permessi: {permissions}")
            
            # Test lettura
            try:
                with open(config_file, 'r') as f:
                    lines = f.readlines()[:3]
                    for line in lines:
                        if line.strip() and not line.startswith('#'):
                            print(f"   📄 {line.strip()}")
            except Exception as e:
                print(f"   ❌ Errore lettura: {e}")
        else:
            print(f"❌ {config_file} non trovato")
    
    # Test 3: Prova correzione configurazione
    print(f"\n🧪 Test 3: Test correzione configurazione")
    try:
        from ncwrap.webdav import WebDAVMountManager
        
        webdav_manager = WebDAVMountManager()
        
        print("🔧 Configurazione davfs2...")
        if webdav_manager.configure_davfs2():
            print("✅ Configurazione davfs2 OK")
        else:
            print("❌ Errore configurazione davfs2")
        
        print("🔧 Test configurazione...")
        if webdav_manager.test_davfs2_config():
            print("✅ Test configurazione OK")
        else:
            print("❌ Test configurazione fallito")
            
            print("🔧 Correzione permessi...")
            if webdav_manager.fix_davfs2_permissions():
                print("✅ Permessi corretti")
            else:
                print("❌ Errore correzione permessi")
                
    except Exception as e:
        print(f"❌ Errore test configurazione: {e}")
    
    # Test 4: Verifica connettività Nextcloud
    print(f"\n🧪 Test 4: Test connettività Nextcloud")
    try:
        from ncwrap.api import get_nc_config, test_nextcloud_connectivity
        
        base_url, admin_user, admin_pass = get_nc_config()
        print(f"🔗 Server: {base_url}")
        
        success, message = test_nextcloud_connectivity()
        if success:
            print(f"✅ {message}")
        else:
            print(f"❌ {message}")
            
    except Exception as e:
        print(f"❌ Errore test connettività: {e}")
    
    # Test 5: Suggerimenti risoluzione problemi
    print(f"\n💡 Suggerimenti risoluzione problemi:")
    print("1. Ricreare configurazione davfs2:")
    print("   sudo rm -f /etc/davfs2/davfs2.conf")
    print("   nextcloud-wrapper-debug-davfs2")
    
    print("\n2. Test mount manuale:")
    print("   sudo mkdir -p /tmp/test-webdav")
    print("   sudo mount -t davfs https://your-nextcloud.com/remote.php/dav/files/user/ /tmp/test-webdav")
    print("   # Inserisci credenziali quando richiesto")
    print("   sudo umount /tmp/test-webdav")
    
    print("\n3. Log di sistema:")
    print("   sudo journalctl -u systemd-logind -f")
    print("   dmesg | grep davfs")
    
    print("\n4. Verifica gruppi utente:")
    print("   groups root")
    print("   sudo usermod -a -G davfs2 root")

if __name__ == "__main__":
    main()
    
    print("\n" + "=" * 50)
    print("🎯 Debug completato!")
    print("\n🚀 Per riprovare il setup:")
    print("nextcloud-wrapper setup user charax.io 'Fy3qesHymfVQ*1' --quota 10G --fs-percentage 0.1 --service --backup")
