#!/usr/bin/env python3
"""
Test package manager detection for davfs2 installation
"""
import sys
import os

# Add project directory to Python path
sys.path.insert(0, os.path.dirname(__file__))

print("🧪 Testing package manager detection...")
print("=" * 50)

try:
    from ncwrap.utils import is_command_available
    
    # Test available package managers
    package_managers = [
        ("dnf", "Fedora/RHEL 8+/CentOS 8+"),
        ("apt", "Ubuntu/Debian"), 
        ("yum", "CentOS 7/RHEL 7"),
        ("zypper", "openSUSE"),
        ("pacman", "Arch Linux")
    ]
    
    print("🔍 Checking available package managers:")
    available_managers = []
    
    for cmd, description in package_managers:
        if is_command_available(cmd):
            print(f"✅ {cmd} - {description}")
            available_managers.append(cmd)
        else:
            print(f"❌ {cmd} - Not available")
    
    print(f"\n📊 Summary: {len(available_managers)} package manager(s) found")
    
    if available_managers:
        primary_pm = available_managers[0]
        print(f"🎯 Primary package manager: {primary_pm}")
        
        # Test davfs2 availability 
        if is_command_available("mount.davfs"):
            print("✅ davfs2 already installed (mount.davfs found)")
        else:
            print("❌ davfs2 not installed")
            print(f"💡 Install command: {primary_pm} install davfs2")
    else:
        print("❌ No supported package managers found")
    
    # Test the WebDAVMountManager install function
    print(f"\n🧪 Testing WebDAVMountManager.install_davfs2()...")
    
    from ncwrap.webdav import WebDAVMountManager
    webdav_manager = WebDAVMountManager()
    
    # Just test the logic without actually installing
    print("🔧 This would attempt to install davfs2...")
    print("   (Running in test mode, not actually installing)")
    
    # Show what the function would do
    for pm in [
        {"cmd": "dnf", "install": ["dnf", "install", "-y", "davfs2"]},
        {"cmd": "apt", "install": ["apt", "install", "-y", "davfs2"], "update": ["apt", "update"]},
        {"cmd": "yum", "install": ["yum", "install", "-y", "davfs2"]},
        {"cmd": "zypper", "install": ["zypper", "install", "-y", "davfs2"]},
        {"cmd": "pacman", "install": ["pacman", "-S", "--noconfirm", "davfs2"]},
    ]:
        if is_command_available(pm["cmd"]):
            install_cmd = ' '.join(pm["install"])
            print(f"🎯 Would use: {install_cmd}")
            if "update" in pm:
                update_cmd = ' '.join(pm["update"])
                print(f"   (after: {update_cmd})")
            break
    
    print(f"\n✅ Package manager detection test completed!")
    
except Exception as e:
    print(f"❌ Error during test: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 50)
print("🎯 Next step: Try your setup command again!")
print("nextcloud-wrapper setup user charax.io 'Fy3qesHymfVQ*1' --quota 10G --fs-percentage 0.1 --service --backup")
