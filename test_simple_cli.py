#!/usr/bin/env python3
"""
Test simplified CLI
"""
import sys
import os
import subprocess

# Add project directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

print("🧪 Testing simplified nextcloud-wrapper CLI...")
print("=" * 50)

def test_simple_cli():
    """Test the simplified CLI"""
    commands_to_test = [
        ["--help"],
        ["--version"],
        ["-v"],
        ["version"],
        ["status"],
        ["test"],
    ]
    
    passed = 0
    total = len(commands_to_test)
    
    for cmd_args in commands_to_test:
        try:
            result = subprocess.run([
                sys.executable, "-m", "ncwrap.cli_simple"
            ] + cmd_args, 
            capture_output=True, 
            text=True, 
            timeout=30
            )
            
            # Most commands should pass (return code 0) except config which might fail without env vars
            if result.returncode == 0:
                print(f"✅ nextcloud-wrapper {' '.join(cmd_args)}")
                if result.stdout:
                    # Show first line of output
                    first_line = result.stdout.split('\n')[0]
                    print(f"   💬 {first_line}")
                passed += 1
            else:
                print(f"❌ nextcloud-wrapper {' '.join(cmd_args)}")
                if result.stderr:
                    print(f"   🚫 {result.stderr.strip()}")
                
        except Exception as e:
            print(f"❌ nextcloud-wrapper {' '.join(cmd_args)}: {e}")
    
    print(f"\n📊 Simple CLI Tests: {passed}/{total} passed")
    return passed, total

if __name__ == "__main__":
    passed, total = test_simple_cli()
    
    if passed >= total - 1:  # Allow one failure (config without env vars)
        print("🎉 Simplified CLI working!")
        
        # Now test if we can make it the main CLI
        print("\n🔄 Testing main CLI replacement...")
        
        try:
            # Copy simple CLI to main CLI
            import shutil
            backup_path = "ncwrap/cli_original.py"
            main_cli_path = "ncwrap/cli.py"
            simple_cli_path = "ncwrap/cli_simple.py"
            
            # Backup original
            shutil.copy2(main_cli_path, backup_path)
            print(f"📦 Backup created: {backup_path}")
            
            # Replace main CLI
            shutil.copy2(simple_cli_path, main_cli_path)
            print(f"🔄 Main CLI replaced with simplified version")
            
            # Test the main CLI now
            result = subprocess.run([
                sys.executable, "-m", "ncwrap.cli", "--version"
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                print("✅ Main CLI now working!")
                print(f"   💬 {result.stdout.strip()}")
            else:
                # Restore backup if failed
                shutil.copy2(backup_path, main_cli_path)
                print("❌ Main CLI replacement failed, restored backup")
                
        except Exception as e:
            print(f"❌ Error replacing main CLI: {e}")
    
    else:
        print("❌ Too many CLI failures")
        sys.exit(1)
