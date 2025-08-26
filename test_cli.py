#!/usr/bin/env python3
"""
Test CLI functionality
"""
import sys
import os
import subprocess

# Add project directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

print("🧪 Testing nextcloud-wrapper CLI...")
print("=" * 50)

def run_cli_command(cmd_args, expected_to_pass=True):
    """Run a CLI command and check if it passes"""
    try:
        result = subprocess.run([
            sys.executable, "-m", "ncwrap.cli"
        ] + cmd_args, 
        capture_output=True, 
        text=True, 
        timeout=30
        )
        
        success = (result.returncode == 0) if expected_to_pass else (result.returncode != 0)
        
        if success:
            print(f"✅ {'nextcloud-wrapper ' + ' '.join(cmd_args)}")
            if result.stdout:
                # Show first few lines of output
                lines = result.stdout.split('\n')[:3]
                for line in lines:
                    if line.strip():
                        print(f"   💬 {line.strip()}")
        else:
            print(f"❌ {'nextcloud-wrapper ' + ' '.join(cmd_args)}")
            if result.stderr:
                print(f"   🚫 {result.stderr.strip()}")
            if result.stdout:
                print(f"   📝 {result.stdout.strip()}")
                
        return success
        
    except Exception as e:
        print(f"❌ nextcloud-wrapper {' '.join(cmd_args)}: {e}")
        return False

# Test basic commands
tests = [
    (["--help"], True),
    (["--version"], True), 
    (["-v"], True),
    (["version"], True),
    (["config"], False),  # Will fail without environment variables but that's expected
    (["status"], True),
]

print("🎯 Testing CLI commands...")
print("-" * 30)

passed = 0
total = 0

for cmd_args, should_pass in tests:
    total += 1
    if run_cli_command(cmd_args, should_pass):
        passed += 1

print("\n" + "=" * 50)
print(f"📊 Test Results: {passed}/{total} passed")

if passed == total:
    print("🎉 All CLI tests passed!")
    sys.exit(0)
else:
    print("❌ Some CLI tests failed")
    sys.exit(1)
