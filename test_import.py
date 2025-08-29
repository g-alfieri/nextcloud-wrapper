#!/usr/bin/env python3
"""
Test script per verificare import nextcloud-wrapper v1.0 (semplificato)
Solo rclone engine, zero quote filesystem
"""
import sys
import os

# Add project directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

print("🧪 Testing nextcloud-wrapper v1.0 imports...")
print("=" * 50)

# Test basic package import
try:
    import ncwrap
    print(f"✅ Basic package import: OK (v{ncwrap.__version__})")
except Exception as e:
    print(f"❌ Basic package import failed: {e}")

# Test core modules v1.0 (solo quelli mantenuti)
core_modules = [
    'ncwrap.api',
    'ncwrap.utils', 
    'ncwrap.system',
    'ncwrap.systemd',
    'ncwrap.venv',
    'ncwrap.rclone',
    'ncwrap.mount'
]

print("\n🔧 Testing core modules v1.0...")
print("-" * 30)

for module in core_modules:
    try:
        __import__(module)
        print(f"✅ {module}: OK")
    except Exception as e:
        print(f"❌ {module}: {e}")

# Test CLI modules v1.0 (solo quelli mantenuti)
cli_modules = [
    'ncwrap.cli',
    'ncwrap.cli_venv',
    'ncwrap.cli_setup',
    'ncwrap.cli_user',
    'ncwrap.cli_mount',
    'ncwrap.cli_service'
]

print("\n🎯 Testing CLI modules v1.0...")
print("-" * 30)

for module in cli_modules:
    try:
        __import__(module)
        print(f"✅ {module}: OK")
    except Exception as e:
        print(f"❌ {module}: {e}")

# Test moduli RIMOSSI v1.0 (dovrebbero fallire)
removed_modules = [
    'ncwrap.webdav',
    'ncwrap.quota',
    'ncwrap.cli_webdav', 
    'ncwrap.cli_quota'
]

print("\n🗑️ Testing REMOVED modules v1.0 (should fail)...")
print("-" * 40)

for module in removed_modules:
    try:
        __import__(module)
        print(f"⚠️ {module}: UNEXPECTED SUCCESS (should be removed!)")
    except Exception:
        print(f"✅ {module}: Correctly removed")

# Test main CLI
print("\n🚀 Testing main CLI v1.0...")
print("-" * 25)

try:
    from ncwrap.cli import app
    print("✅ Main CLI app import: OK")
    
    # Test if app has commands
    if hasattr(app, 'commands'):
        commands = list(app.commands.keys())
        print(f"📋 Available commands: {commands}")
        print(f"📊 Total commands: {len(commands)}")
        
        # Verifica che i comandi rimossi non ci siano
        removed_commands = ['webdav', 'quota']
        for cmd in removed_commands:
            if cmd in commands:
                print(f"⚠️ Command '{cmd}' still present (should be removed!)")
            else:
                print(f"✅ Command '{cmd}' correctly removed")
                
    else:
        print("ℹ️  App commands not accessible")
        
except Exception as e:
    print(f"❌ Main CLI import failed: {e}")

# Test rclone profiles
print("\n📊 Testing rclone profiles...")
print("-" * 25)

try:
    from ncwrap.rclone import MOUNT_PROFILES
    print(f"✅ rclone profiles loaded: {list(MOUNT_PROFILES.keys())}")
    print(f"📊 Total profiles: {len(MOUNT_PROFILES)}")
    
    for profile_name, profile_info in MOUNT_PROFILES.items():
        print(f"  • {profile_name}: {profile_info['description']}")
        
except Exception as e:
    print(f"❌ rclone profiles test failed: {e}")

# Test mount manager
print("\n🔗 Testing mount manager v1.0...")
print("-" * 30)

try:
    from ncwrap.mount import MountManager
    manager = MountManager()
    print("✅ MountManager init: OK")
    
    # Test metodi disponibili
    methods = [m for m in dir(manager) if not m.startswith('_')]
    print(f"📋 Available methods: {len(methods)}")
    
    # Test metodi rimossi (dovrebbero non esistere)
    removed_methods = ['detect_available_engines', '_mount_with_davfs2']
    for method in removed_methods:
        if hasattr(manager, method):
            print(f"⚠️ Method '{method}' still present (should be removed!)")
        else:
            print(f"✅ Method '{method}' correctly removed")
            
except Exception as e:
    print(f"❌ MountManager test failed: {e}")

# Test version consistency
print("\n📋 Testing version consistency...")
print("-" * 30)

try:
    from ncwrap import __version__, __description__
    print(f"✅ Package version: {__version__}")
    print(f"✅ Description: {__description__}")
    
    # Verifica che sia v1.0.x
    if __version__.startswith('1.0'):
        print("✅ Version format correct (1.0.x)")
    else:
        print(f"⚠️ Version should be 1.0.x, got {__version__}")
        
    # Verifica descrizione semplificata
    if 'rclone' in __description__ and 'semplificato' in __description__:
        print("✅ Description updated for v1.0")
    else:
        print("⚠️ Description may need updating for v1.0")
        
except Exception as e:
    print(f"❌ Version test failed: {e}")

print("\n" + "=" * 50)
print("🎉 Import test v1.0 completed!")
print("\n📊 Summary:")
print("• Core modules: rclone, mount, api, system, venv")
print("• CLI modules: setup, user, mount, service, venv") 
print("• REMOVED: webdav, quota (and related CLI)")
print("• Engine: rclone unico (4 profili)")
print("• Gestione spazio: automatica via rclone")
