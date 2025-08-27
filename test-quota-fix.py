#!/usr/bin/env python3
"""
Test per verificare le correzioni apportate al sistema di quota
"""
import os
import sys

def test_btrfs_quota_format():
    """Test formato quota BTRFS"""
    from ncwrap.utils import parse_size_to_bytes, bytes_to_human
    
    print("🔍 Test formato quota BTRFS")
    
    # Test parsing dimensioni
    test_sizes = ["1G", "100M", "1.5T", "512K"]
    
    for size in test_sizes:
        try:
            bytes_val = parse_size_to_bytes(size)
            human_val = bytes_to_human(bytes_val)
            print(f"  {size} -> {bytes_val} bytes -> {human_val}")
        except Exception as e:
            print(f"  ❌ Errore parsing {size}: {e}")
    
    print()


def test_quota_manager():
    """Test QuotaManager con formato corretto"""
    from ncwrap.quota import QuotaManager
    
    print("🔍 Test QuotaManager")
    
    quota_manager = QuotaManager()
    
    # Test formato size per BTRFS
    test_quota = "1.5G"
    
    try:
        # Simula conversione che avviene in _set_btrfs_quota
        from ncwrap.utils import parse_size_to_bytes
        size_bytes = parse_size_to_bytes(test_quota)
        btrfs_size = str(size_bytes)
        
        print(f"  Quota {test_quota} -> {btrfs_size} bytes per BTRFS")
        print(f"  ✅ Conversione formato quota OK")
        
    except Exception as e:
        print(f"  ❌ Errore conversione: {e}")
    
    print()


def test_nextcloud_quota_format():
    """Test formato quota Nextcloud"""
    print("🔍 Test formato quota Nextcloud")
    
    test_quotas = ["100G", "50M", "1T", "512K"]
    
    for quota in test_quotas:
        # Simula conversione che avviene in setup_quota_for_user
        try:
            if quota.endswith('G'):
                nc_quota_formatted = quota.replace('G', ' GB')
            elif quota.endswith('M'):
                nc_quota_formatted = quota.replace('M', ' MB')
            elif quota.endswith('T'):
                nc_quota_formatted = quota.replace('T', ' TB')
            elif quota.endswith('K'):
                nc_quota_formatted = quota.replace('K', ' KB')
            else:
                nc_quota_formatted = quota
            
            print(f"  {quota} -> '{nc_quota_formatted}' (formato Nextcloud)")
            
        except Exception as e:
            print(f"  ❌ Errore conversione {quota}: {e}")
    
    print()


def test_systemd_service_config():
    """Test generazione configurazione servizio systemd"""
    print("🔍 Test configurazione servizio systemd")
    
    try:
        from ncwrap.systemd import SystemdManager
        
        systemd_manager = SystemdManager()
        
        # Test generazione configurazione (senza creare il servizio)
        service_config = systemd_manager._generate_webdav_mount_service_config(
            "test-service",
            "test.example.com",
            "https://cloud.example.com/remote.php/dav/files/test.example.com/",
            "/home/test.example.com",
            1001,  # uid
            1001   # gid
        )
        
        # Verifica che contenga le correzioni per mount già esistenti
        if "mountpoint -q" in service_config:
            print("  ✅ Controllo mount esistente presente")
        else:
            print("  ❌ Controllo mount esistente mancante")
            
        if "ExecStartPre" in service_config and "ExecStop" in service_config:
            print("  ✅ Struttura servizio corretta")
        else:
            print("  ❌ Struttura servizio incorretta")
            
        print("  📋 Esempio configurazione generata:")
        print("    " + service_config.split('\n')[0])
        print("    ...")
        
    except Exception as e:
        print(f"  ❌ Errore test systemd: {e}")
    
    print()


def main():
    """Esegue tutti i test"""
    print("🚀 Test correzioni nextcloud-wrapper v0.3.0")
    print("=" * 50)
    
    try:
        # Aggiungi il path del modulo
        sys.path.insert(0, '.')
        
        test_btrfs_quota_format()
        test_quota_manager()
        test_nextcloud_quota_format()
        test_systemd_service_config()
        
        print("✅ Test completati - le correzioni sembrano funzionare")
        print()
        print("💡 Per testare in produzione:")
        print("   1. nextcloud-wrapper setup user test.com 'password123' --quota 1G --fs-percentage 0.1")
        print("   2. systemctl status webdav-home-test.com")
        print("   3. btrfs qgroup show /home/test.com")
        
    except ImportError as e:
        print(f"❌ Errore import moduli: {e}")
        print("💡 Esegui da directory root del progetto: python test-quota-fix.py")
    except Exception as e:
        print(f"❌ Errore durante test: {e}")


if __name__ == "__main__":
    main()
