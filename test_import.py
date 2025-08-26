#!/usr/bin/env python3
"""
Test script per verificare se il package nextcloud-wrapper si importa correttamente
"""
import sys
import os

# Add project directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

print("🧪 Testing nextcloud-wrapper imports...")
print("=" * 50)

# Test basic package import
try:
    import ncwrap
    print("✅ Basic package import: OK")
except Exception as e:
    print(f"❌ Basic package import failed: {e}")

# Test individual module imports
modules_to_test = [
    'ncwrap.api',
    'ncwrap.utils', 
    'ncwrap.quota',
    'ncwrap.system',
    'ncwrap.systemd',
    'ncwrap.webdav',
    'ncwrap.venv',
    'ncwrap.rclone'
]

for module in modules_to_test:
    try:
        __import__(module)
        print(f"✅ {module}: OK")
    except Exception as e:
        print(f"❌ {module}: {e}")

# Test CLI modules
cli_modules = [
    'ncwrap.cli',
    'ncwrap.cli_venv',
    'ncwrap.cli_setup',
    'ncwrap.cli_user',
    'ncwrap.cli_webdav',
    'ncwrap.cli_quota', 
    'ncwrap.cli_service'
]

print("\n🎯 Testing CLI modules...")
print("-" * 30)

for module in cli_modules:
    try:
        __import__(module)
        print(f"✅ {module}: OK")
    except Exception as e:
        print(f"❌ {module}: {e}")

# Test main CLI
print("\n🚀 Testing main CLI...")
print("-" * 20)

try:
    from ncwrap.cli import app
    print("✅ Main CLI app import: OK")
    
    # Test if app has commands
    if hasattr(app, 'commands'):
        print(f"📋 Available commands: {len(app.commands)}")
    else:
        print("ℹ️  App commands not accessible")
        
except Exception as e:
    print(f"❌ Main CLI import failed: {e}")

print("\n" + "=" * 50)
print("Test completed!")
