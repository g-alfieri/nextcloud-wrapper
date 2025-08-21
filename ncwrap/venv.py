"""
Gestione virtual environment Miniconda/Conda per Nextcloud Wrapper v0.3.0
"""
import os
import sys
import subprocess
import shutil
from pathlib import Path
from typing import Optional, Dict, Tuple
from .utils import run, atomic_write


class VenvManager:
    """Gestore virtual environment Conda/Miniconda"""
    
    def __init__(self):
        self.venv_name = "nextcloud-wrapper"
        self.config = self._load_config()
        self.conda_info = self._detect_conda()
    
    def _load_config(self) -> Dict:
        """Carica configurazione environment"""
        return {
            "venv_name": os.environ.get("NC_VENV_NAME", "nextcloud-wrapper"),
            "python_version": os.environ.get("NC_PYTHON_VERSION", "3.11"),
            "auto_activate": os.environ.get("NC_AUTO_ACTIVATE", "true").lower() == "true",
            "create_wrapper_scripts": os.environ.get("NC_CREATE_WRAPPERS", "true").lower() == "true",
            "systemd_use_venv": os.environ.get("NC_SYSTEMD_USE_VENV", "true").lower() == "true"
        }
    
    def _detect_conda(self) -> Dict:
        """Rileva installazione Conda/Miniconda"""
        conda_info = {
            "available": False,
            "executable": None,
            "base_path": None,
            "version": None
        }
        
        # Cerca conda negli path comuni
        conda_paths = [
            shutil.which("conda"),
            shutil.which("mamba"),  # Alternativa più veloce
            os.path.expanduser("~/miniconda3/bin/conda"),
            os.path.expanduser("~/anaconda3/bin/conda"),
            "/opt/miniconda3/bin/conda",
            "/opt/anaconda3/bin/conda"
        ]
        
        for conda_path in conda_paths:
            if conda_path and os.path.exists(conda_path):
                try:
                    result = subprocess.run([conda_path, "--version"], 
                                          capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        conda_info.update({
                            "available": True,
                            "executable": conda_path,
                            "version": result.stdout.strip(),
                            "base_path": str(Path(conda_path).parent.parent)
                        })
                        break
                except:
                    continue
        
        return conda_info
    
    def is_conda_available(self) -> bool:
        """Verifica se Conda è disponibile"""
        return self.conda_info["available"]
    
    def get_current_venv(self) -> Optional[str]:
        """Ottiene virtual environment attivo"""
        # Conda environment
        conda_env = os.environ.get("CONDA_DEFAULT_ENV")
        if conda_env and conda_env != "base":
            return conda_env
        
        # Virtual environment standard
        venv_path = os.environ.get("VIRTUAL_ENV")
        if venv_path:
            return Path(venv_path).name
        
        return None
    
    def environment_exists(self, env_name: str = None) -> bool:
        """Verifica se environment esiste"""
        if not self.is_conda_available():
            return False
        
        env_name = env_name or self.config["venv_name"]
        
        try:
            result = subprocess.run([
                self.conda_info["executable"], "env", "list", "--json"
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                import json
                envs_data = json.loads(result.stdout)
                env_paths = envs_data.get("envs", [])
                
                for env_path in env_paths:
                    if Path(env_path).name == env_name:
                        return True
            
            return False
            
        except Exception:
            return False
    
    def create_environment(self, env_name: str = None, force: bool = False) -> bool:
        """
        Crea environment Conda dal file environment.yml
        
        Args:
            env_name: Nome environment (default: nextcloud-wrapper)
            force: Forza ricreazione se esiste già
            
        Returns:
            True se creazione riuscita
        """
        if not self.is_conda_available():
            print("❌ Conda/Miniconda non disponibile")
            return False
        
        env_name = env_name or self.config["venv_name"]
        
        # Verifica se environment.yml esiste
        env_file = Path("environment.yml")
        if not env_file.exists():
            print(f"❌ File environment.yml non trovato in {env_file.absolute()}")
            return False
        
        # Rimuovi environment esistente se force=True
        if force and self.environment_exists(env_name):
            print(f"🗑️ Rimozione environment esistente: {env_name}")
            if not self.remove_environment(env_name):
                return False
        
        try:
            print(f"📦 Creando environment Conda: {env_name}")
            print(f"📄 File environment: {env_file.absolute()}")
            
            # Crea environment da file yml
            cmd = [
                self.conda_info["executable"], "env", "create",
                "-f", str(env_file),
                "-n", env_name
            ]
            
            result = subprocess.run(cmd, text=True, timeout=300)
            
            if result.returncode == 0:
                print(f"✅ Environment {env_name} creato con successo")
                
                # Installa il package in modalità development
                if self._install_package_in_env(env_name):
                    print("✅ Package installato in modalità development")
                else:
                    print("⚠️ Errore installazione package")
                
                return True
            else:
                print(f"❌ Errore creazione environment: {result.returncode}")
                return False
                
        except subprocess.TimeoutExpired:
            print("❌ Timeout creazione environment (>5 minuti)")
            return False
        except Exception as e:
            print(f"❌ Errore creazione environment: {e}")
            return False
    
    def _install_package_in_env(self, env_name: str) -> bool:
        """Installa il package corrente nell'environment"""
        try:
            # Ottieni path Python dell'environment
            python_path = self.get_env_python_path(env_name)
            if not python_path:
                return False
            
            # Installa in modalità development
            result = subprocess.run([
                str(python_path), "-m", "pip", "install", "-e", "."
            ], capture_output=True, text=True, timeout=120)
            
            return result.returncode == 0
            
        except Exception:
            return False
    
    def remove_environment(self, env_name: str = None) -> bool:
        """Rimuove environment"""
        if not self.is_conda_available():
            return False
        
        env_name = env_name or self.config["venv_name"]
        
        try:
            result = subprocess.run([
                self.conda_info["executable"], "env", "remove",
                "-n", env_name, "-y"
            ], capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                print(f"✅ Environment {env_name} rimosso")
                return True
            else:
                print(f"❌ Errore rimozione environment: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Errore rimozione environment: {e}")
            return False
    
    def get_env_python_path(self, env_name: str = None) -> Optional[Path]:
        """Ottiene path Python dell'environment"""
        if not self.is_conda_available():
            return None
        
        env_name = env_name or self.config["venv_name"]
        
        try:
            result = subprocess.run([
                self.conda_info["executable"], "env", "list", "--json"
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                import json
                envs_data = json.loads(result.stdout)
                
                for env_path in envs_data.get("envs", []):
                    if Path(env_path).name == env_name:
                        python_path = Path(env_path) / "bin" / "python"
                        if python_path.exists():
                            return python_path
                        # Windows
                        python_path = Path(env_path) / "python.exe"
                        if python_path.exists():
                            return python_path
            
            return None
            
        except Exception:
            return None
    
    def get_env_info(self, env_name: str = None) -> Optional[Dict]:
        """Ottiene informazioni dettagliate environment"""
        env_name = env_name or self.config["venv_name"]
        
        if not self.environment_exists(env_name):
            return None
        
        python_path = self.get_env_python_path(env_name)
        
        info = {
            "name": env_name,
            "python_path": str(python_path) if python_path else None,
            "exists": True,
            "packages": {}
        }
        
        # Lista packages installati
        if python_path:
            try:
                result = subprocess.run([
                    str(python_path), "-m", "pip", "list", "--format=json"
                ], capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    import json
                    packages = json.loads(result.stdout)
                    info["packages"] = {pkg["name"]: pkg["version"] for pkg in packages}
                    
            except Exception:
                pass
        
        return info
    
    def create_wrapper_scripts(self, env_name: str = None) -> bool:
        """
        Crea script wrapper globali per comandi nextcloud-wrapper
        
        Returns:
            True se creazione riuscita
        """
        if not self.config["create_wrapper_scripts"]:
            return True
        
        env_name = env_name or self.config["venv_name"]
        python_path = self.get_env_python_path(env_name)
        
        if not python_path:
            print("❌ Path Python environment non trovato")
            return False
        
        # Script wrapper principale
        wrapper_content = f"""#!/bin/bash
# Nextcloud Wrapper - Auto-generated conda environment launcher
# Environment: {env_name}
# Python: {python_path}

export CONDA_DEFAULT_ENV="{env_name}"
export PATH="{python_path.parent}:$PATH"

# Load environment variables if .env exists
if [ -f "$(dirname "$0")/.env" ]; then
    set -a
    source "$(dirname "$0")/.env"
    set +a
elif [ -f "$HOME/.nextcloud-wrapper/.env" ]; then
    set -a
    source "$HOME/.nextcloud-wrapper/.env"
    set +a
fi

# Execute nextcloud-wrapper with all arguments
exec "{python_path}" -m ncwrap.cli "$@"
"""
        
        # SystemD wrapper per servizi
        systemd_wrapper_content = f"""#!/bin/bash
# Nextcloud Wrapper SystemD - Auto-generated conda launcher
# Environment: {env_name}
# Python: {python_path}

export CONDA_DEFAULT_ENV="{env_name}"
export PATH="{python_path.parent}:$PATH"

# Load environment from standard locations
for env_file in /etc/nextcloud-wrapper/.env /root/.nextcloud-wrapper/.env /opt/nextcloud-wrapper/.env; do
    if [ -f "$env_file" ]; then
        set -a
        source "$env_file"
        set +a
        break
    fi
done

# Execute with all arguments
exec "{python_path}" -m ncwrap.cli "$@"
"""
        
        try:
            # Crea directory bin locale se non esiste
            local_bin = Path.home() / ".local" / "bin"
            local_bin.mkdir(parents=True, exist_ok=True)
            
            # Script wrapper utente
            wrapper_script = local_bin / "nextcloud-wrapper"
            if atomic_write(str(wrapper_script), wrapper_content, 0o755):
                print(f"✅ Script wrapper creato: {wrapper_script}")
            
            # Script wrapper SystemD globale
            systemd_bin = Path("/usr/local/bin")
            if systemd_bin.exists() and os.access(systemd_bin, os.W_OK):
                systemd_script = systemd_bin / "nextcloud-wrapper-systemd"
                if atomic_write(str(systemd_script), systemd_wrapper_content, 0o755):
                    print(f"✅ Script SystemD creato: {systemd_script}")
            else:
                # Fallback: crea in directory progetto
                systemd_script = Path("nextcloud-wrapper-systemd")
                if atomic_write(str(systemd_script), systemd_wrapper_content, 0o755):
                    print(f"✅ Script SystemD creato: {systemd_script}")
                    print(f"💡 Copia manualmente in /usr/local/bin/ con sudo")
            
            return True
            
        except Exception as e:
            print(f"❌ Errore creazione wrapper scripts: {e}")
            return False
    
    def setup_auto_activation(self, env_name: str = None) -> bool:
        """
        Setup auto-attivazione environment quando si entra nella directory
        
        Returns:
            True se setup completato
        """
        if not self.config["auto_activate"]:
            return True
        
        env_name = env_name or self.config["venv_name"]
        
        # Script auto-attivazione per .bashrc
        activation_script = f"""
# Nextcloud Wrapper Auto-Activation
# Auto-generated for environment: {env_name}

_nw_auto_activate() {{
    if [[ "$PWD" == *"nextcloud-wrapper"* ]] && [[ "$CONDA_DEFAULT_ENV" != "{env_name}" ]]; then
        if command -v conda &> /dev/null; then
            echo "🐍 Auto-activating nextcloud-wrapper environment..."
            conda activate {env_name} 2>/dev/null || true
            
            # Load .env if exists
            if [ -f ".env" ]; then
                echo "📋 Loading .env file..."
                set -a
                source .env
                set +a
            fi
        fi
    fi
}}

# Hook into cd command
_nw_original_cd=$(type -p cd)
cd() {{
    $_nw_original_cd "$@"
    _nw_auto_activate
}}

# Auto-activate on shell start if in nextcloud-wrapper directory
_nw_auto_activate
"""
        
        try:
            # Aggiungi a .bashrc se non presente
            bashrc = Path.home() / ".bashrc"
            if bashrc.exists():
                with open(bashrc, 'r') as f:
                    content = f.read()
                
                if "nextcloud-wrapper" not in content:
                    with open(bashrc, 'a') as f:
                        f.write(f"\n{activation_script}\n")
                    print(f"✅ Auto-attivazione aggiunta a {bashrc}")
                else:
                    print(f"ℹ️ Auto-attivazione già presente in {bashrc}")
            
            # Crea alias utili
            aliases = f"""
# Nextcloud Wrapper Aliases
alias nw='nextcloud-wrapper'
alias nw-activate='conda activate {env_name} && [ -f .env ] && source .env'
alias nw-config='nextcloud-wrapper config'
alias nw-status='nextcloud-wrapper status'
alias nw-logs='sudo journalctl -u nextcloud-* --since "1 hour ago"'
"""
            
            bash_aliases = Path.home() / ".bash_aliases"
            if bash_aliases.exists():
                with open(bash_aliases, 'r') as f:
                    content = f.read()
                
                if "nw-activate" not in content:
                    with open(bash_aliases, 'a') as f:
                        f.write(aliases)
                    print(f"✅ Aliases aggiunti a {bash_aliases}")
            
            return True
            
        except Exception as e:
            print(f"❌ Errore setup auto-attivazione: {e}")
            return False
    
    def get_systemd_python_path(self, env_name: str = None) -> str:
        """
        Ottiene path Python per servizi SystemD
        
        Returns:
            Path assoluto Python environment o python di sistema
        """
        if not self.config["systemd_use_venv"]:
            return "/usr/bin/python3"
        
        env_name = env_name or self.config["venv_name"]
        python_path = self.get_env_python_path(env_name)
        
        if python_path and python_path.exists():
            return str(python_path)
        else:
            # Fallback a Python di sistema
            return "/usr/bin/python3"
    
    def get_systemd_executable_path(self, env_name: str = None) -> str:
        """
        Ottiene path eseguibile per servizi SystemD
        
        Returns:
            Path wrapper script o comando diretto
        """
        # Cerca wrapper script SystemD
        systemd_wrapper = Path("/usr/local/bin/nextcloud-wrapper-systemd")
        if systemd_wrapper.exists():
            return str(systemd_wrapper)
        
        # Fallback al wrapper locale
        local_wrapper = Path.home() / ".local/bin/nextcloud-wrapper"
        if local_wrapper.exists():
            return str(local_wrapper)
        
        # Fallback al comando Python diretto
        python_path = self.get_systemd_python_path(env_name)
        return f"{python_path} -m ncwrap.cli"


def setup_miniconda_environment(force_recreate: bool = False) -> bool:
    """
    Setup completo environment Miniconda per nextcloud-wrapper
    
    Args:
        force_recreate: Forza ricreazione environment se esiste
        
    Returns:
        True se setup completato con successo
    """
    print("🐍 Setup Miniconda Environment per Nextcloud Wrapper v0.3.0")
    print("=" * 60)
    
    venv_manager = VenvManager()
    
    # Verifica Conda
    if not venv_manager.is_conda_available():
        print("❌ Conda/Miniconda non trovato!")
        print("\n💡 Installa Miniconda:")
        print("   wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh")
        print("   bash Miniconda3-latest-Linux-x86_64.sh")
        print("   source ~/.bashrc")
        return False
    
    conda_info = venv_manager.conda_info
    print(f"✅ Conda trovato: {conda_info['version']}")
    print(f"📍 Path: {conda_info['executable']}")
    
    env_name = venv_manager.config["venv_name"]
    
    # Crea environment
    if venv_manager.environment_exists(env_name) and not force_recreate:
        print(f"ℹ️ Environment '{env_name}' già esistente")
    else:
        if not venv_manager.create_environment(env_name, force=force_recreate):
            return False
    
    # Crea wrapper scripts
    if not venv_manager.create_wrapper_scripts(env_name):
        print("⚠️ Errore creazione wrapper scripts")
    
    # Setup auto-attivazione
    if not venv_manager.setup_auto_activation(env_name):
        print("⚠️ Errore setup auto-attivazione")
    
    # Info finale
    env_info = venv_manager.get_env_info(env_name)
    if env_info:
        print(f"\n✅ Environment '{env_name}' configurato con successo!")
        print(f"🐍 Python: {env_info['python_path']}")
        print(f"📦 Packages installati: {len(env_info['packages'])}")
        
        # Mostra packages principali
        key_packages = ['nextcloud-wrapper', 'typer', 'rich', 'requests']
        for pkg in key_packages:
            if pkg in env_info['packages']:
                print(f"   • {pkg}: {env_info['packages'][pkg]}")
    
    print(f"\n🎯 Comandi disponibili:")
    print(f"   conda activate {env_name}")
    print(f"   nextcloud-wrapper --help")
    print(f"   nw config  # alias breve")
    
    print(f"\n⚙️ Per servizi SystemD:")
    systemd_path = venv_manager.get_systemd_executable_path()
    print(f"   ExecStart={systemd_path}")
    
    return True


def install_system_service_wrapper() -> bool:
    """
    Installa wrapper SystemD globale per servizi
    
    Returns:
        True se installazione riuscita
    """
    venv_manager = VenvManager()
    
    if not venv_manager.is_conda_available():
        print("❌ Conda non disponibile")
        return False
    
    # Crea wrapper script globale per SystemD
    env_name = venv_manager.config["venv_name"]
    python_path = venv_manager.get_env_python_path(env_name)
    
    if not python_path:
        print(f"❌ Environment {env_name} non trovato")
        return False
    
    wrapper_content = f"""#!/bin/bash
# Nextcloud Wrapper SystemD Global Launcher
# Auto-generated for production use

export CONDA_DEFAULT_ENV="{env_name}"
export PATH="{python_path.parent}:$PATH"

# Load production environment variables
if [ -f "/etc/nextcloud-wrapper/.env" ]; then
    set -a
    source "/etc/nextcloud-wrapper/.env"
    set +a
fi

# Execute with full python path for reliability
exec "{python_path}" -m ncwrap.cli "$@"
"""
    
    try:
        # Installa in /usr/local/bin
        wrapper_path = Path("/usr/local/bin/nextcloud-wrapper")
        
        if atomic_write(str(wrapper_path), wrapper_content, 0o755):
            print(f"✅ Wrapper SystemD installato: {wrapper_path}")
            
            # Crea directory config globale
            config_dir = Path("/etc/nextcloud-wrapper")
            config_dir.mkdir(exist_ok=True)
            
            # Copia .env se non esiste
            env_file = config_dir / ".env"
            if not env_file.exists() and Path(".env").exists():
                import shutil
                shutil.copy(".env", env_file)
                print(f"✅ Configurazione copiata: {env_file}")
            
            return True
        else:
            print("❌ Errore installazione wrapper")
            return False
            
    except PermissionError:
        print("❌ Privilegi insufficienti per installare in /usr/local/bin")
        print("💡 Esegui con sudo o usa: python -m ncwrap.venv install-system-wrapper")
        return False
    except Exception as e:
        print(f"❌ Errore installazione: {e}")
        return False


# Funzioni di compatibilità
def get_venv_python_path() -> str:
    """Ottiene path Python per compatibilità"""
    venv_manager = VenvManager()
    return venv_manager.get_systemd_python_path()


def get_venv_executable_path() -> str:
    """Ottiene path eseguibile per compatibilità"""
    venv_manager = VenvManager()
    return venv_manager.get_systemd_executable_path()
