#!/usr/bin/env python3
"""
Quick setup and test script for Nextcloud Wrapper v0.3.0
"""
import os
import sys
import subprocess
from pathlib import Path

def main():
    print("🚀 Nextcloud Wrapper v0.3.0 - Quick Setup")
    print("=" * 50)
    
    # Check if in project directory
    if not Path("pyproject.toml").exists():
        print("❌ Run this script from the project root directory")
        sys.exit(1)
    
    # Install in development mode
    print("📦 Installing in development mode...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-e", "."], check=True)
        print("✅ Installation completed")
    except subprocess.CalledProcessError:
        print("❌ Installation failed")
        sys.exit(1)
    
    # Check configuration
    print("\n⚙️ Configuration check...")
    if Path(".env").exists():
        print("✅ .env file found")
    else:
        print("⚠️ .env file not found - copying from .env.example")
        try:
            import shutil
            shutil.copy(".env.example", ".env")
            print("📋 Please edit .env with your Nextcloud settings:")
            print("   - NC_BASE_URL=https://your-nextcloud.com")
            print("   - NC_ADMIN_USER=admin")
            print("   - NC_ADMIN_PASS=your_password")
        except Exception as e:
            print(f"❌ Error copying .env file: {e}")
    
    # Test installation
    print("\n🧪 Testing installation...")
    try:
        result = subprocess.run([
            sys.executable, "-c", 
            "import ncwrap; print(f'✅ Nextcloud Wrapper v{ncwrap.__version__} imported successfully')"
        ], capture_output=True, text=True, check=True)
        print(result.stdout.strip())
    except subprocess.CalledProcessError as e:
        print(f"❌ Import test failed: {e}")
        sys.exit(1)
    
    # Test CLI command
    print("\n🖥️ Testing CLI command...")
    try:
        result = subprocess.run(["nextcloud-wrapper", "version"], 
                              capture_output=True, text=True, check=True)
        print(result.stdout.strip())
    except subprocess.CalledProcessError as e:
        print(f"❌ CLI test failed: {e}")
        print("💡 Try: python -m ncwrap.cli version")
    except FileNotFoundError:
        print("⚠️ CLI command not found in PATH")
        print("💡 Try: python -m ncwrap.cli version")
    
    # Test virtual environment
    print("\n🐍 Testing virtual environment support...")
    try:
        result = subprocess.run([
            sys.executable, "-c", 
            "from ncwrap.venv import VenvManager; m = VenvManager(); print(f'Conda: {m.is_conda_available()}')"
        ], capture_output=True, text=True, check=True)
        print(result.stdout.strip())
    except subprocess.CalledProcessError:
        print("⚠️ Virtual environment support not available")
    
    # Show next steps
    print("\n✨ Setup completed successfully!")
    print("\n🎯 Next steps:")
    print("1. Edit .env file with your Nextcloud settings")
    print("2. Setup Miniconda environment (optional): chmod +x setup-miniconda.sh && ./setup-miniconda.sh")
    print("3. Test configuration: nextcloud-wrapper config")
    print("4. Run full test: chmod +x test-complete.sh && ./test-complete.sh")
    print("5. Create your first user: nextcloud-wrapper setup user domain.com password")
    print("\n🐍 Virtual Environment:")
    print("   • For production: Use Miniconda with ./setup-miniconda.sh")
    print("   • For development: Current Python installation is fine")
    print("   • Check status: nextcloud-wrapper venv status")
    print("\n📖 Documentation: README.md")
    print("🐛 Issues: https://github.com/your-repo/nextcloud-wrapper/issues")

if __name__ == "__main__":
    main()
