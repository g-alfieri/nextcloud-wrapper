#!/usr/bin/env python3
"""
Fix per gestione mount già esistenti in webdav.py
"""

# Soluzione: patch per webdav.py per gestire correttamente mount esistenti

WEBDAV_MOUNT_FIX = '''
def mount_webdav_home_fixed(self, username: str, password: str, home_path: str = None) -> bool:
    """
    Monta WebDAV con gestione corretta mount esistenti
    """
    if not home_path:
        home_path = f"/home/{username}"
    
    try:
        from .api import get_nc_config
        base_url, _, _ = get_nc_config()
        webdav_url = f"{base_url}/remote.php/dav/files/{username}/"
        
        print(f"🔗 Montando WebDAV {username} in {home_path}")
        print(f"URL: {webdav_url}")
        
        # ✅ CONTROLLO MOUNT ESISTENTE PRIMA DI TENTARE MOUNT
        if self._is_webdav_mounted(home_path):
            print(f"✅ WebDAV già montato e funzionante: {home_path}")
            return True
        
        # Setup credenziali e mount
        if not self.setup_user_credentials(username, password, webdav_url):
            return False
        
        from .utils import get_user_uid_gid
        uid, gid = get_user_uid_gid(username)
        
        # Tentativo mount con gestione errori migliorata
        mount_cmd = ["mount", "-t", "davfs", webdav_url, home_path, 
                    "-o", f"uid={uid},gid={gid},rw,user,noauto"]
        
        try:
            from .utils import run
            run(mount_cmd)
            print(f"✅ WebDAV montato: {webdav_url} → {home_path}")
            return True
        except RuntimeError as e:
            error_msg = str(e).lower()
            
            # Gestione mount già esistente
            if "already mounted" in error_msg:
                print(f"✅ WebDAV già montato (rilevato da mount.davfs): {home_path}")
                return True
            
            # Tentativo con opzioni semplificate
            try:
                simple_cmd = ["mount", "-t", "davfs", webdav_url, home_path]
                run(simple_cmd)
                print(f"✅ WebDAV montato (modalità semplice): {home_path}")
                return True
            except RuntimeError as e2:
                error_msg2 = str(e2).lower()
                
                if "already mounted" in error_msg2:
                    print(f"✅ WebDAV già montato (secondo controllo): {home_path}")
                    return True
                
                print(f"❌ Mount fallito: {e2}")
                return False
        
    except Exception as e:
        print(f"❌ Errore mount WebDAV: {e}")
        return False

def _is_webdav_mounted(self, home_path: str) -> bool:
    """
    Controlla se il path è già montato con WebDAV funzionante
    """
    try:
        from .utils import run, is_mounted
        
        # Controllo base mount
        if not is_mounted(home_path):
            return False
        
        # Verifica che sia davfs2
        mount_output = run(["mount"], check=False)
        
        # Cerca entry per questo mount point
        for line in mount_output.split('\\n'):
            if home_path in line and "davfs" in line:
                print(f"🔍 Mount WebDAV trovato: {line.strip()}")
                return True
        
        return False
        
    except Exception:
        return False
'''

print("🔧 Fix per gestione mount WebDAV già esistenti")
print("=" * 50)
print()

print("📋 Problema identificato:")
print("   • webdav.py non gestisce correttamente mount già esistenti")
print("   • Comando mount.davfs fallisce con 'already mounted'")
print("   • Setup utente fallisce anche se mount è attivo")
print()

print("✅ Soluzione:")
print("   1. Controllo preventivo mount esistente con is_mounted() + verifica davfs")
print("   2. Gestione errore 'already mounted' come successo")
print("   3. Return True immediato se mount già attivo e funzionante")
print()

print("🛠️ Implementazione:")
print("   • Modificare mount_webdav_home() in webdav.py")
print("   • Aggiungere controllo preventivo mount esistente")  
print("   • Gestire eccezione 'already mounted' come caso di successo")
print()

print("💻 Comando per test:")
print("   nextcloud-wrapper setup user test.local 'TestPass123!' --quota 1G")
print()

# Test della logica di fix
def test_mount_already_exists_logic():
    print("🧪 Test logica gestione mount esistente:")
    
    # Simula messaggio errore
    error_messages = [
        "mount.davfs: https://cloud.example.com/remote.php/dav/files/user/ is already mounted on /home/user",
        "Errore eseguendo mount -t davfs: already mounted",
        "mount: /home/user is already mounted or mount point busy"
    ]
    
    for msg in error_messages:
        if "already mounted" in msg.lower():
            print(f"   ✅ Rilevato: {msg[:50]}...")
        else:
            print(f"   ❌ Non rilevato: {msg[:50]}...")

test_mount_already_exists_logic()
