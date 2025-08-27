#!/usr/bin/env python3
"""
Test delle correzioni per mount WebDAV esistenti
"""
import subprocess
import sys
import os

def test_mount_detection():
    """Test rilevamento mount esistenti"""
    print("🧪 Test rilevamento mount WebDAV esistenti")
    print("=" * 50)
    
    # Test funzione is_mounted
    test_paths = ["/home/charax.io", "/tmp", "/nonexistent"]
    
    for path in test_paths:
        try:
            # Simula controllo mountpoint
            result = subprocess.run(
                ["mountpoint", "-q", path], 
                capture_output=True
            )
            
            if result.returncode == 0:
                print(f"✅ {path}: Mountpoint rilevato")
                
                # Verifica se è davfs
                mount_result = subprocess.run(
                    ["mount"], 
                    capture_output=True, 
                    text=True
                )
                
                if mount_result.returncode == 0:
                    for line in mount_result.stdout.split('\n'):
                        if path in line:
                            if "davfs" in line:
                                print(f"   🔗 WebDAV: {line.strip()}")
                            else:
                                print(f"   📁 Altro: {line.strip()}")
                            break
                            
            else:
                print(f"❌ {path}: Non montato")
                
        except Exception as e:
            print(f"⚠️ {path}: Errore test - {e}")
    
    print()

def test_already_mounted_detection():
    """Test rilevamento messaggi 'already mounted'"""
    print("🧪 Test rilevamento messaggi 'already mounted'")
    print("=" * 50)
    
    test_messages = [
        "mount.davfs: https://cloud.example.com/remote.php/dav/files/user/ is already mounted on /home/user",
        "Errore eseguendo mount -t davfs: already mounted", 
        "mount: /home/user is already mounted or mount point busy",
        "Device or resource busy",
        "Permission denied"
    ]
    
    for msg in test_messages:
        if "already mounted" in msg.lower():
            print(f"✅ RILEVATO: {msg[:60]}...")
        else:
            print(f"❌ Non rilevato: {msg[:60]}...")
    
    print()

def test_current_mounts():
    """Mostra mount correnti per debug"""
    print("🔍 Mount correnti nel sistema")
    print("=" * 50)
    
    try:
        result = subprocess.run(["mount"], capture_output=True, text=True)
        if result.returncode == 0:
            davfs_mounts = []
            other_mounts = []
            
            for line in result.stdout.split('\n'):
                if line.strip():
                    if "davfs" in line:
                        davfs_mounts.append(line.strip())
                    elif "/home/" in line:
                        other_mounts.append(line.strip())
            
            if davfs_mounts:
                print("📁 Mount WebDAV trovati:")
                for mount in davfs_mounts:
                    print(f"   🔗 {mount}")
            else:
                print("❌ Nessun mount WebDAV trovato")
            
            if other_mounts:
                print("\n📁 Altri mount /home/:")
                for mount in other_mounts[:3]:  # Solo primi 3
                    print(f"   📂 {mount}")
                if len(other_mounts) > 3:
                    print(f"   ... e altri {len(other_mounts) - 3} mount")
        else:
            print("❌ Errore esecuzione comando mount")
            
    except Exception as e:
        print(f"❌ Errore: {e}")
    
    print()

def check_webdav_user_status(username="charax.io"):
    """Verifica status specifico utente WebDAV"""
    print(f"🔍 Status WebDAV per utente: {username}")
    print("=" * 50)
    
    home_path = f"/home/{username}"
    
    # Controllo mountpoint
    try:
        result = subprocess.run(["mountpoint", "-q", home_path])
        if result.returncode == 0:
            print(f"✅ {home_path} è un mountpoint")
            
            # Dettagli mount
            mount_result = subprocess.run(["mount"], capture_output=True, text=True)
            if mount_result.returncode == 0:
                for line in mount_result.stdout.split('\n'):
                    if home_path in line:
                        print(f"   📋 {line.strip()}")
                        
                        if "davfs" in line:
                            print("   🔗 Tipo: WebDAV (davfs2)")
                        else:
                            print("   ⚠️  Tipo: Non WebDAV")
                        break
        else:
            print(f"❌ {home_path} non è montato")
            
    except Exception as e:
        print(f"❌ Errore controllo mount: {e}")
    
    # Test accesso directory
    try:
        if os.path.exists(home_path):
            files = os.listdir(home_path)
            print(f"📁 Contenuto directory ({len(files)} elementi):")
            for f in files[:5]:  # Primi 5 file
                print(f"   📄 {f}")
            if len(files) > 5:
                print(f"   ... e altri {len(files) - 5} file")
        else:
            print("❌ Directory non esistente")
    except PermissionError:
        print("⚠️  Accesso negato alla directory")
    except Exception as e:
        print(f"❌ Errore accesso directory: {e}")
    
    print()

def suggest_fix():
    """Suggerisce come risolvere il problema"""
    print("💡 Soluzioni per mount già esistente")
    print("=" * 50)
    
    print("🔧 Opzione 1: Riavvio setup (raccomandato)")
    print("   git pull  # Aggiorna codice con fix")
    print("   nextcloud-wrapper setup user charax.io 'password' --quota 4G --fs-percentage 0.5")
    print()
    
    print("🔧 Opzione 2: Test mount manuale")
    print("   umount /home/charax.io  # Se necessario")
    print("   mount -t davfs https://ncloud.charax.io/remote.php/dav/files/charax.io/ /home/charax.io")
    print()
    
    print("🔧 Opzione 3: Verifica status servizio")
    print("   systemctl status webdav-home-charax.io")
    print("   systemctl restart webdav-home-charax.io")
    print()
    
    print("📊 Debug dettagliato:")
    print("   mount | grep charax.io")
    print("   mountpoint -q /home/charax.io && echo 'Montato' || echo 'Non montato'")
    print("   ls -la /home/charax.io/")

def main():
    """Esegue tutti i test"""
    print("🚀 Test correzioni mount WebDAV - nextcloud-wrapper v0.3.0")
    print("=" * 60)
    print()
    
    test_mount_detection()
    test_already_mounted_detection()
    test_current_mounts()
    check_webdav_user_status()
    suggest_fix()
    
    print("✅ Test completati")
    print("💡 Ora puoi riprovare il setup con le correzioni applicate")

if __name__ == "__main__":
    main()
