#!/usr/bin/env python3
"""
Test script per verificare il rate limiting fix
"""
import sys
import os
import time

# Aggiungi il path del progetto
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ncwrap.api import test_webdav_connectivity, make_request_with_retry
from ncwrap.rclone import check_connectivity, add_nextcloud_remote
from ncwrap.utils import run_with_retry
import requests

def test_api_rate_limiting():
    """Test rate limiting nelle API WebDAV"""
    print("🧪 Test rate limiting API WebDAV...")
    
    # Test connessioni multiple rapide
    test_user = "test-rate-limit-user"
    test_password = "test123"
    
    print(f"Testing connettività per {test_user}...")
    
    # Test multipli in sequenza (dovrebbe gestire rate limiting automaticamente)
    for i in range(5):
        print(f"  Test {i+1}/5...")
        result = test_webdav_connectivity(test_user, test_password)
        print(f"  Risultato: {'✅ OK' if result else '❌ FAIL'}")
        time.sleep(0.5)  # Piccola pausa tra test

def test_rclone_rate_limiting():
    """Test rate limiting per rclone"""
    print("\n🧪 Test rate limiting rclone...")
    
    from ncwrap.api import get_nc_config
    
    try:
        base_url, _, _ = get_nc_config()
        print(f"Server Nextcloud: {base_url}")
        
        # Test creazione remote con rate limiting
        remote_name = "test-rate-limit-remote"
        test_user = "test-rate-limit-user" 
        test_password = "test123"
        
        print(f"Creando remote rclone: {remote_name}")
        result = add_nextcloud_remote(remote_name, base_url, test_user, test_password)
        print(f"Creazione remote: {'✅ OK' if result else '❌ FAIL'}")
        
        if result:
            print(f"Testando connettività remote...")
            connectivity = check_connectivity(remote_name)
            print(f"Test connettività: {'✅ OK' if connectivity else '❌ FAIL'}")
        
    except Exception as e:
        print(f"❌ Errore configurazione: {e}")

def test_http_retry_mechanism():
    """Test diretto del meccanismo retry HTTP"""
    print("\n🧪 Test meccanismo retry HTTP...")
    
    # Test con URL che potrebbe dare rate limiting
    test_url = "https://httpbin.org/status/429"  # Simula sempre 429
    
    try:
        print(f"Testing retry con URL che ritorna sempre 429...")
        response = make_request_with_retry(
            "GET", 
            test_url, 
            max_retries=2,  # Solo 2 retry per test veloce
            delay_base=1.0,
            timeout=10
        )
        print(f"Response status: {response.status_code}")
        
    except Exception as e:
        print(f"❌ Exception attesa per 429 sempre: {e}")
    
    # Test con URL normale
    test_url_ok = "https://httpbin.org/status/200"
    try:
        print(f"Testing retry con URL normale...")
        response = make_request_with_retry(
            "GET",
            test_url_ok,
            max_retries=2,
            delay_base=1.0,
            timeout=10
        )
        print(f"✅ Response status: {response.status_code}")
        
    except Exception as e:
        print(f"❌ Errore imprevisto: {e}")

def main():
    """Esegue tutti i test"""
    print("🚀 Test Rate Limiting Fix per nextcloud-wrapper")
    print("=" * 50)
    
    try:
        # Test 1: API rate limiting
        test_api_rate_limiting()
        
        # Test 2: rclone rate limiting  
        test_rclone_rate_limiting()
        
        # Test 3: Meccanismo HTTP retry
        test_http_retry_mechanism()
        
        print("\n✅ Test completati!")
        print("\n💡 Miglioramenti implementati:")
        print("  • Retry automatico per 429 Too Many Requests")
        print("  • Backoff esponenziale con jitter") 
        print("  • Timeout configurabili")
        print("  • Gestione errori temporanei (502, 503, 504)")
        print("  • Rate limiting per rclone lsd")
        print("  • Rate limiting per WebDAV PROPFIND")
        
    except KeyboardInterrupt:
        print("\n⚠️ Test interrotti dall'utente")
    except Exception as e:
        print(f"\n❌ Errore durante test: {e}")

if __name__ == "__main__":
    main()
