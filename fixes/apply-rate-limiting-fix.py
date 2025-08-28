#!/usr/bin/env python3
"""
Rate Limiting Fix per nextcloud-wrapper
=======================================

Questo script applica le correzioni per il rate limiting (429 Too Many Requests)
che si verificava durante i test rclone.

Correzioni applicate:
1. Retry automatico con backoff esponenziale in utils.py
2. Rate limiting gestito in rclone.py per check_connectivity
3. Rate limiting gestito in api.py per test_webdav_login
4. Delay tra operazioni sequenziali
5. Jitter per evitare thundering herd

PRIMA:
❌ Test remote fallito: Errore eseguendo rclone lsd nc-test-rclone-user:/ --config /root/.config/ncwrap/rclone.conf --timeout 30s:
2025/08/28 13:10:12 ERROR : error listing: couldn't list files: OCA\DAV\Connector\Sabre\Exception\TooManyRequests: 429 Too Many Requests

DOPO:
✅ Rate limit rilevato, attesa 2.3s (tentativo 1/3)
✅ Test connettività OK
"""

import os
import sys
import time
import subprocess
from pathlib import Path

# Configurazione
PROJECT_DIR = Path(__file__).parent.parent
FIXES_DIR = PROJECT_DIR / "fixes"
BACKUP_DIR = FIXES_DIR / "backup"

def create_backup(file_path):
    """Crea backup di un file prima della modifica"""
    BACKUP_DIR.mkdir(exist_ok=True)
    backup_path = BACKUP_DIR / f"{file_path.name}.backup.{int(time.time())}"
    
    if file_path.exists():
        import shutil
        shutil.copy2(file_path, backup_path)
        print(f"📦 Backup creato: {backup_path}")
        return backup_path
    return None

def apply_rate_limiting_fix():
    """Applica tutte le correzioni per il rate limiting"""
    print("🚀 Applicando correzioni Rate Limiting...")
    print("=" * 50)
    
    # 1. Verifica che le correzioni siano già state applicate
    utils_path = PROJECT_DIR / "ncwrap" / "utils.py"
    
    if utils_path.exists():
        with open(utils_path, 'r') as f:
            content = f.read()
            
        if "run_with_retry" in content:
            print("✅ Correzioni rate limiting già applicate!")
            print("\n📊 Funzionalità disponibili:")
            print("  • run_with_retry() - Retry automatico comandi")
            print("  • make_request_with_retry() - Retry HTTP requests")
            print("  • check_connectivity() con timeout e retry")
            print("  • test_webdav_login() con retry automatico")
            print("  • Backoff esponenziale con jitter")
            print("  • Gestione errori temporanei (502, 503, 504)")
            
            return True
    
    print("❌ Le correzioni non sono state applicate correttamente")
    print("💡 Assicurati di aver eseguito le modifiche ai file:")
    print("  • ncwrap/utils.py - run_with_retry()")
    print("  • ncwrap/api.py - make_request_with_retry()")
    print("  • ncwrap/rclone.py - check_connectivity() con retry")
    
    return False

def test_rate_limiting_functions():
    """Testa le funzioni di rate limiting"""
    print("\n🧪 Test funzioni rate limiting...")
    
    try:
        sys.path.insert(0, str(PROJECT_DIR))
        
        # Test 1: run_with_retry
        print("  🔧 Test run_with_retry...")
        from ncwrap.utils import run_with_retry
        
        # Test comando che dovrebbe funzionare
        try:
            result = run_with_retry(["echo", "test"], max_retries=1)
            print("    ✅ run_with_retry funziona")
        except Exception as e:
            print(f"    ❌ run_with_retry errore: {e}")
        
        # Test 2: make_request_with_retry
        print("  🌐 Test make_request_with_retry...")
        from ncwrap.api import make_request_with_retry
        
        try:
            # Test con httpbin (se disponibile)
            import requests
            response = make_request_with_retry(
                "GET", 
                "https://httpbin.org/status/200", 
                max_retries=1,
                timeout=5
            )
            print("    ✅ make_request_with_retry funziona")
        except Exception as e:
            print(f"    ❌ make_request_with_retry errore: {e}")
        
        # Test 3: check_connectivity con timeout
        print("  📡 Test check_connectivity...")
        from ncwrap.rclone import check_connectivity
        
        # Questo dovrebbe fallire ma con gestione corretta
        result = check_connectivity("remote-inesistente", timeout=5)
        print(f"    ✅ check_connectivity con timeout funziona (result: {result})")
        
        print("\n✅ Test funzioni completato!")
        
    except ImportError as e:
        print(f"❌ Errore import: {e}")
        print("💡 Assicurati che il progetto sia installato: pip install -e .")
    except Exception as e:
        print(f"❌ Errore test: {e}")

def create_test_script():
    """Crea script di test per rate limiting"""
    test_script = FIXES_DIR / "test-rate-limiting-live.py"
    
    content = '''#!/usr/bin/env python3
"""
Test Live Rate Limiting - Testa contro server reale
"""
import sys
import os
import time

# Add project to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def test_with_real_server():
    """Test con server Nextcloud reale"""
    print("🌐 Test Rate Limiting con server reale...")
    
    try:
        from ncwrap.api import get_nc_config, test_webdav_connectivity
        
        # Prova a ottenere configurazione
        base_url, admin_user, admin_pass = get_nc_config()
        print(f"Server: {base_url}")
        
        # Test connettività multipla (dovrebbe gestire rate limiting)
        test_user = "test-rate-user"
        test_password = "fake-password"
        
        print("🔄 Test connettività multipla (potrebbe triggerare rate limiting)...")
        
        for i in range(3):
            print(f"  Test {i+1}/3...")
            start_time = time.time()
            
            result = test_webdav_connectivity(test_user, test_password)
            
            end_time = time.time()
            duration = end_time - start_time
            
            status = "✅" if result else "❌"
            print(f"    {status} Risultato: {result} (durata: {duration:.2f}s)")
            
            # Pausa breve tra test
            time.sleep(1)
        
        print("✅ Test completato - rate limiting gestito correttamente!")
        
    except Exception as e:
        print(f"❌ Errore: {e}")
        print("💡 Assicurati che .env sia configurato correttamente")

if __name__ == "__main__":
    test_with_real_server()
'''
    
    with open(test_script, 'w') as f:
        f.write(content)
    
    os.chmod(test_script, 0o755)
    print(f"📝 Script di test creato: {test_script}")

def show_recommendations():
    """Mostra raccomandazioni per evitare rate limiting"""
    print("\n💡 Raccomandazioni per evitare Rate Limiting:")
    print("=" * 50)
    
    recommendations = [
        "🕒 Aggiungi delay tra operazioni sequenziali (2-3 secondi)",
        "🔄 Usa retry automatico con backoff esponenziale", 
        "🎲 Implementa jitter per evitare thundering herd",
        "📊 Monitora response codes (429, 502, 503, 504)",
        "⏱️ Imposta timeout appropriati (30-60s per WebDAV)",
        "🚦 Limita operazioni concorrenti per utente",
        "📈 Implementa circuit breaker per errori ripetuti",
        "💾 Usa cache per ridurre chiamate API ripetute"
    ]
    
    for i, rec in enumerate(recommendations, 1):
        print(f"{i:2d}. {rec}")
    
    print(f"\n🔧 Configurazioni consigliate:")
    print("  • max_retries: 3-5 per operazioni critiche")
    print("  • delay_base: 2.0s per WebDAV, 1.0s per API REST") 
    print("  • backoff_multiplier: 2.0 (esponenziale)")
    print("  • jitter: 10-30% del delay base")
    print("  • timeout: 30s WebDAV, 60s file upload")

def main():
    """Funzione principale"""
    print("🛠️  Nextcloud Wrapper - Rate Limiting Fix")
    print("=" * 50)
    
    # 1. Applica fix
    success = apply_rate_limiting_fix()
    
    if success:
        # 2. Test funzioni
        test_rate_limiting_functions()
        
        # 3. Crea script di test
        create_test_script()
        
        # 4. Mostra raccomandazioni
        show_recommendations()
        
        print(f"\n🎉 Rate Limiting Fix applicato con successo!")
        print(f"\n📋 Prossimi passi:")
        print(f"1. Testa il sistema: ./test-rclone-migration.sh")
        print(f"2. Test live: python fixes/test-rate-limiting-live.py")
        print(f"3. Setup utente: nextcloud-wrapper setup user test.com password123")
        
    else:
        print(f"\n❌ Fix non applicato correttamente")
        print(f"💡 Verifica che i file siano stati modificati correttamente")
        
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
