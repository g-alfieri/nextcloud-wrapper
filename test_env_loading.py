#!/usr/bin/env python3
"""
Test .env loading functionality
"""
import sys
import os

# Add project directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

print("🧪 Testing .env file loading...")
print("=" * 50)

# Clear existing environment variables for clean test
env_vars = ['NC_BASE_URL', 'NC_ADMIN_USER', 'NC_ADMIN_PASS']
for var in env_vars:
    if var in os.environ:
        del os.environ[var]

print("🧹 Cleared existing NC_* environment variables")

try:
    # Test utils function
    from ncwrap.utils import find_and_load_env
    
    success = find_and_load_env()
    print(f"📂 find_and_load_env() result: {success}")
    
    if success:
        # Check if variables are now loaded
        for var in env_vars:
            value = os.environ.get(var)
            if value:
                # Mask password for security
                if 'PASS' in var:
                    masked_value = '*' * (len(value) - 3) + value[-3:]
                    print(f"✅ {var} = {masked_value}")
                else:
                    print(f"✅ {var} = {value}")
            else:
                print(f"❌ {var} = Not found")
                
        print("\n🔧 Testing get_nc_config()...")
        
        # Test API config function
        from ncwrap.api import get_nc_config
        
        try:
            base_url, admin_user, admin_pass = get_nc_config()
            print(f"✅ Configuration loaded successfully!")
            print(f"   Base URL: {base_url}")
            print(f"   Admin User: {admin_user}")
            print(f"   Admin Pass: ***{admin_pass[-3:]}")
            
            # Test CLI command now
            print("\n🎯 Testing CLI command with .env loaded...")
            import subprocess
            
            result = subprocess.run([
                sys.executable, "-m", "ncwrap.cli", "config"
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                print("✅ CLI config command works!")
                # Show first few lines
                lines = result.stdout.split('\n')[:5]
                for line in lines:
                    if line.strip():
                        print(f"   💬 {line.strip()}")
            else:
                print("❌ CLI config command failed")
                if result.stderr:
                    print(f"   🚫 {result.stderr.strip()}")
                    
        except Exception as e:
            print(f"❌ get_nc_config() failed: {e}")
            
    else:
        print("❌ Could not find or load .env file")
        print("💡 Make sure .env file exists in the current directory")
        
        # Show what files exist
        for file in ['.env', os.path.expanduser('~/.env')]:
            if os.path.exists(file):
                print(f"   📄 Found: {file}")
            else:
                print(f"   🚫 Not found: {file}")
                
except Exception as e:
    print(f"❌ Error testing .env loading: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 50)
print("Test completed!")
