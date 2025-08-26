#!/usr/bin/env python3
"""
Test the specific setup command that was failing
"""
import sys
import os
import subprocess

# Add project directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

print("🧪 Testing setup command with .env loading...")
print("=" * 50)

# Show current directory and .env file status
print(f"📂 Current directory: {os.getcwd()}")
env_file = ".env"
if os.path.exists(env_file):
    print(f"✅ Found .env file: {env_file}")
    # Show first few lines (without passwords)
    with open(env_file, 'r') as f:
        lines = f.readlines()[:10]  # First 10 lines
        for i, line in enumerate(lines):
            line = line.strip()
            if line and not line.startswith('#'):
                if 'PASS' in line:
                    # Mask password
                    key, _ = line.split('=', 1)
                    print(f"   {i+1}: {key}=***masked***")
                else:
                    print(f"   {i+1}: {line}")
            elif line:
                print(f"   {i+1}: {line}")
else:
    print(f"❌ .env file not found: {env_file}")

print("\n🎯 Testing the failing command...")

# The original failing command:
# nextcloud-wrapper setup user charax.io 'Fy3qesHymfVQ*1' --quota 10G --fs-percentage 0.1 --service --backup

test_commands = [
    # First test basic commands
    ["--version"],
    ["config"],
    ["status"],
    
    # Then test the setup command (dry run mode if available)
    # ["setup", "user", "charax.io", "Fy3qesHymfVQ*1", "--quota", "10G", "--fs-percentage", "0.1", "--skip-linux", "--skip-test"]
]

for cmd_args in test_commands:
    print(f"\n🔧 Testing: nextcloud-wrapper {' '.join(cmd_args)}")
    
    try:
        result = subprocess.run([
            sys.executable, "-m", "ncwrap.cli"
        ] + cmd_args, 
        capture_output=True, 
        text=True, 
        timeout=60  # Longer timeout for setup commands
        )
        
        if result.returncode == 0:
            print(f"✅ Command succeeded!")
            if result.stdout:
                # Show output lines
                lines = result.stdout.split('\n')
                for line in lines[:10]:  # First 10 lines
                    if line.strip():
                        print(f"   💬 {line.strip()}")
                if len(lines) > 10:
                    print(f"   ... ({len(lines)-10} more lines)")
        else:
            print(f"❌ Command failed (exit code: {result.returncode})")
            if result.stderr:
                stderr_lines = result.stderr.split('\n')
                for line in stderr_lines:
                    if line.strip():
                        print(f"   🚫 {line.strip()}")
            if result.stdout:
                stdout_lines = result.stdout.split('\n')
                for line in stdout_lines[:5]:
                    if line.strip():
                        print(f"   📝 {line.strip()}")
                        
    except subprocess.TimeoutExpired:
        print(f"❌ Command timed out after 60 seconds")
    except Exception as e:
        print(f"❌ Error running command: {e}")

# Test manual environment loading
print(f"\n🧪 Testing manual .env loading...")
try:
    from ncwrap.utils import find_and_load_env
    success = find_and_load_env()
    print(f"📂 Manual .env loading: {'✅ Success' if success else '❌ Failed'}")
    
    if success:
        # Check key variables
        nc_vars = {
            'NC_BASE_URL': os.environ.get('NC_BASE_URL'),
            'NC_ADMIN_USER': os.environ.get('NC_ADMIN_USER'), 
            'NC_ADMIN_PASS': os.environ.get('NC_ADMIN_PASS')
        }
        
        for var, value in nc_vars.items():
            if value:
                if 'PASS' in var:
                    print(f"   ✅ {var}: ***{value[-3:]}")
                else:
                    print(f"   ✅ {var}: {value}")
            else:
                print(f"   ❌ {var}: Not set")
                
        # Now test get_nc_config directly
        try:
            from ncwrap.api import get_nc_config
            base_url, admin_user, admin_pass = get_nc_config()
            print(f"   ✅ get_nc_config() works: {base_url}")
        except Exception as e:
            print(f"   ❌ get_nc_config() failed: {e}")
            
except Exception as e:
    print(f"❌ Error with manual loading: {e}")

print("\n" + "=" * 50)
print("Setup command test completed!")

# Final recommendation
print("\n💡 Next steps:")
print("1. If .env loading works, try the full setup command")
print("2. If config command works, the basic CLI is functional")
print("3. If setup command fails, check the specific error message")
print("\n🎯 Full setup command to try:")
print("nextcloud-wrapper setup user charax.io 'Fy3qesHymfVQ*1' --quota 10G --fs-percentage 0.1 --skip-linux --skip-test")
