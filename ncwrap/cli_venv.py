"""
CLI VEnv - Gestione virtual environment Miniconda
"""
import typer
import sys
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from .venv import (
    VenvManager,
    setup_miniconda_environment,
    install_system_service_wrapper
)
from .utils import check_sudo_privileges

venv_app = typer.Typer(help="Gestione virtual environment Miniconda")
console = Console()


@venv_app.command("setup")
def setup_environment(
    force: bool = typer.Option(False, "--force", help="Forza ricreazione environment"),
    install_wrapper: bool = typer.Option(True, "--wrapper/--no-wrapper", help="Installa wrapper scripts"),
    enable_auto_activation: bool = typer.Option(True, "--auto/--no-auto", help="Abilita auto-attivazione")
):
    """Setup completo environment Miniconda"""
    rprint("[bold blue]🐍 Setup Miniconda Environment[/bold blue]")
    
    try:
        if setup_miniconda_environment(force_recreate=force):
            rprint("[green]✅ Environment configurato con successo![/green]")
            
            # Installa wrapper globale se richiesto
            if install_wrapper and check_sudo_privileges():
                rprint("[yellow]🔧 Installando wrapper SystemD globale...[/yellow]")
                if install_system_service_wrapper():
                    rprint("[green]✅ Wrapper SystemD installato[/green]")
                else:
                    rprint("[red]❌ Errore installazione wrapper SystemD[/red]")
            elif install_wrapper:
                rprint("[yellow]⚠️ Privilegi sudo richiesti per wrapper SystemD[/yellow]")
                rprint("💡 Esegui: sudo python -m ncwrap.cli_venv setup --wrapper")
            
            # Mostra comandi utili
            rprint("\n[bold]🎯 Comandi disponibili:[/bold]")
            rprint("   conda activate nextcloud-wrapper")
            rprint("   source .env  # Carica configurazione")
            rprint("   nextcloud-wrapper config")
            rprint("   nw status  # Alias breve")
            
            rprint("\n[bold]⚙️ Per reload configurazione:[/bold]")
            rprint("   source ~/.bashrc")
            rprint("   cd $(pwd)  # Auto-attivazione")
            
        else:
            rprint("[red]❌ Errore setup environment[/red]")
            sys.exit(1)
            
    except Exception as e:
        rprint(f"[red]❌ Errore: {e}[/red]")
        sys.exit(1)


@venv_app.command("status")
def show_status():
    """Mostra status environment e configurazione"""
    rprint("[blue]📊 Status Virtual Environment[/blue]")
    
    venv_manager = VenvManager()
    
    # Info Conda
    if venv_manager.is_conda_available():
        conda_info = venv_manager.conda_info
        rprint(f"[green]✅ Conda disponibile: {conda_info['version']}[/green]")
        rprint(f"📍 Path: {conda_info['executable']}")
        rprint(f"🏠 Base: {conda_info['base_path']}")
    else:
        rprint("[red]❌ Conda non disponibile[/red]")
        return
    
    # Environment attivo
    current_env = venv_manager.get_current_venv()
    if current_env:
        rprint(f"[green]🐍 Environment attivo: {current_env}[/green]")
    else:
        rprint("[yellow]⚠️ Nessun environment attivo[/yellow]")
    
    # Info environment nextcloud-wrapper
    env_name = venv_manager.config["venv_name"]
    if venv_manager.environment_exists(env_name):
        env_info = venv_manager.get_env_info(env_name)
        if env_info:
            rprint(f"[green]✅ Environment '{env_name}' esistente[/green]")
            rprint(f"🐍 Python: {env_info['python_path']}")
            rprint(f"📦 Packages: {len(env_info['packages'])}")
            
            # Tabella packages principali
            table = Table(title=f"Packages in {env_name}")
            table.add_column("Package", style="cyan")
            table.add_column("Version", style="white")
            
            key_packages = ['nextcloud-wrapper', 'typer', 'rich', 'requests', 'click']
            for pkg in key_packages:
                if pkg in env_info['packages']:
                    table.add_row(pkg, env_info['packages'][pkg])
            
            console.print(table)
    else:
        rprint(f"[red]❌ Environment '{env_name}' non trovato[/red]")
    
    # Path per SystemD
    systemd_path = venv_manager.get_systemd_executable_path()
    rprint(f"[bold]⚙️ Path SystemD:[/bold] {systemd_path}")
    
    # Configurazione
    config = venv_manager.config
    rprint(f"[bold]🔧 Configurazione:[/bold]")
    for key, value in config.items():
        rprint(f"   • {key}: {value}")


@venv_app.command("create")
def create_environment(
    name: str = typer.Option("nextcloud-wrapper", help="Nome environment"),
    force: bool = typer.Option(False, "--force", help="Forza ricreazione se esiste")
):
    """Crea environment Conda"""
    rprint(f"[blue]📦 Creando environment: {name}[/blue]")
    
    venv_manager = VenvManager()
    
    if not venv_manager.is_conda_available():
        rprint("[red]❌ Conda non disponibile[/red]")
        sys.exit(1)
    
    if venv_manager.create_environment(name, force=force):
        rprint(f"[green]✅ Environment {name} creato con successo[/green]")
        
        # Mostra info
        env_info = venv_manager.get_env_info(name)
        if env_info:
            rprint(f"🐍 Python: {env_info['python_path']}")
            rprint(f"📦 Packages installati: {len(env_info['packages'])}")
    else:
        rprint(f"[red]❌ Errore creazione environment {name}[/red]")
        sys.exit(1)


@venv_app.command("remove")
def remove_environment(
    name: str = typer.Option("nextcloud-wrapper", help="Nome environment"),
    confirm: bool = typer.Option(False, "--confirm", help="Conferma eliminazione")
):
    """Rimuove environment Conda"""
    if not confirm:
        rprint(f"[red]⚠️ ATTENZIONE: Stai per eliminare l'environment {name}[/red]")
        rprint("💡 Aggiungi --confirm per procedere")
        sys.exit(1)
    
    rprint(f"[blue]🗑️ Rimuovendo environment: {name}[/blue]")
    
    venv_manager = VenvManager()
    
    if venv_manager.remove_environment(name):
        rprint(f"[green]✅ Environment {name} rimosso[/green]")
    else:
        rprint(f"[red]❌ Errore rimozione environment {name}[/red]")
        sys.exit(1)


@venv_app.command("install-wrapper")
def install_wrapper():
    """Installa wrapper SystemD globale"""
    rprint("[blue]🔧 Installazione wrapper SystemD globale[/blue]")
    
    if not check_sudo_privileges():
        rprint("[red]❌ Privilegi sudo richiesti[/red]")
        rprint("💡 Esegui: sudo nextcloud-wrapper venv install-wrapper")
        sys.exit(1)
    
    if install_system_service_wrapper():
        rprint("[green]✅ Wrapper SystemD installato in /usr/local/bin/[/green]")
        rprint("[cyan]💡 I servizi SystemD ora useranno automaticamente il virtual environment[/cyan]")
    else:
        rprint("[red]❌ Errore installazione wrapper[/red]")
        sys.exit(1)


@venv_app.command("create-wrappers")
def create_wrapper_scripts():
    """Crea script wrapper locali"""
    rprint("[blue]📝 Creazione script wrapper[/blue]")
    
    venv_manager = VenvManager()
    
    if not venv_manager.is_conda_available():
        rprint("[red]❌ Conda non disponibile[/red]")
        sys.exit(1)
    
    env_name = venv_manager.config["venv_name"]
    if not venv_manager.environment_exists(env_name):
        rprint(f"[red]❌ Environment {env_name} non trovato[/red]")
        rprint("💡 Esegui prima: nextcloud-wrapper venv setup")
        sys.exit(1)
    
    if venv_manager.create_wrapper_scripts(env_name):
        rprint("[green]✅ Script wrapper creati[/green]")
        rprint("[cyan]📍 Script utente: ~/.local/bin/nextcloud-wrapper[/cyan]")
        rprint("[cyan]⚙️ Script SystemD: nextcloud-wrapper-systemd[/cyan]")
        rprint("\n💡 Aggiungi ~/.local/bin al PATH se necessario:")
        rprint("   export PATH=\"$HOME/.local/bin:$PATH\"")
    else:
        rprint("[red]❌ Errore creazione wrapper[/red]")


@venv_app.command("setup-auto-activation")
def setup_auto_activation():
    """Configura auto-attivazione environment"""
    rprint("[blue]🔄 Setup auto-attivazione[/blue]")
    
    venv_manager = VenvManager()
    env_name = venv_manager.config["venv_name"]
    
    if venv_manager.setup_auto_activation(env_name):
        rprint("[green]✅ Auto-attivazione configurata[/green]")
        rprint("[cyan]🎯 L'environment si attiverà automaticamente quando entri nella directory[/cyan]")
        rprint("\n💡 Per applicare subito:")
        rprint("   source ~/.bashrc")
        rprint("   cd $(pwd)")
    else:
        rprint("[red]❌ Errore configurazione auto-attivazione[/red]")


@venv_app.command("test")
def test_environment():
    """Testa environment e configurazione"""
    rprint("[blue]🧪 Test environment[/blue]")
    
    venv_manager = VenvManager()
    
    # Test Conda
    if not venv_manager.is_conda_available():
        rprint("[red]❌ Test fallito: Conda non disponibile[/red]")
        sys.exit(1)
    
    rprint("[green]✅ Conda disponibile[/green]")
    
    # Test environment
    env_name = venv_manager.config["venv_name"]
    if not venv_manager.environment_exists(env_name):
        rprint(f"[red]❌ Environment {env_name} non trovato[/red]")
        sys.exit(1)
    
    rprint(f"[green]✅ Environment {env_name} esistente[/green]")
    
    # Test Python path
    python_path = venv_manager.get_env_python_path(env_name)
    if not python_path or not python_path.exists():
        rprint("[red]❌ Python path non valido[/red]")
        sys.exit(1)
    
    rprint(f"[green]✅ Python path: {python_path}[/green]")
    
    # Test import nextcloud-wrapper
    try:
        import subprocess
        result = subprocess.run([
            str(python_path), "-c", 
            "import ncwrap; print(f'nextcloud-wrapper v{ncwrap.__version__}')"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            rprint(f"[green]✅ Import test: {result.stdout.strip()}[/green]")
        else:
            rprint(f"[red]❌ Import fallito: {result.stderr}[/red]")
            sys.exit(1)
            
    except Exception as e:
        rprint(f"[red]❌ Errore test import: {e}[/red]")
        sys.exit(1)
    
    # Test wrapper scripts
    systemd_path = venv_manager.get_systemd_executable_path()
    rprint(f"[green]✅ Path SystemD: {systemd_path}[/green]")
    
    # Test configurazione
    from pathlib import Path
    if Path(".env").exists():
        rprint("[green]✅ File .env trovato[/green]")
    else:
        rprint("[yellow]⚠️ File .env non trovato[/yellow]")
    
    rprint("[bold green]🎉 Tutti i test passati![/bold green]")


@venv_app.command("info")
def show_detailed_info():
    """Mostra informazioni dettagliate environment"""
    rprint("[blue]ℹ️ Informazioni dettagliate environment[/blue]")
    
    venv_manager = VenvManager()
    
    # Info sistema
    if venv_manager.is_conda_available():
        conda_info = venv_manager.conda_info
        
        table = Table(title="Conda Information")
        table.add_column("Campo", style="cyan")
        table.add_column("Valore", style="white")
        
        table.add_row("Available", "✅ Yes" if conda_info["available"] else "❌ No")
        table.add_row("Executable", str(conda_info["executable"]))
        table.add_row("Version", str(conda_info["version"]))
        table.add_row("Base Path", str(conda_info["base_path"]))
        
        console.print(table)
    
    # Info environment
    env_name = venv_manager.config["venv_name"]
    env_info = venv_manager.get_env_info(env_name)
    
    if env_info:
        table = Table(title=f"Environment: {env_name}")
        table.add_column("Campo", style="cyan")
        table.add_column("Valore", style="white")
        
        table.add_row("Name", env_info["name"])
        table.add_row("Python Path", str(env_info["python_path"]))
        table.add_row("Exists", "✅ Yes" if env_info["exists"] else "❌ No")
        table.add_row("Packages Count", str(len(env_info["packages"])))
        
        console.print(table)
        
        # Packages dettagliati se richiesti
        if env_info["packages"]:
            rprint(f"\n[bold]📦 Packages installati ({len(env_info['packages'])}):[/bold]")
            packages_list = list(env_info["packages"].items())[:10]  # Prime 10
            for pkg, version in packages_list:
                rprint(f"   • {pkg}: {version}")
            
            if len(env_info["packages"]) > 10:
                rprint(f"   ... e altri {len(env_info['packages']) - 10} packages")
    
    # Configurazione
    config = venv_manager.config
    table = Table(title="Configurazione VEnv")
    table.add_column("Opzione", style="cyan")
    table.add_column("Valore", style="white")
    
    for key, value in config.items():
        table.add_row(key.replace("_", " ").title(), str(value))
    
    console.print(table)


@venv_app.command("activate")
def show_activation_info():
    """Mostra informazioni per attivazione manuale"""
    rprint("[blue]🔄 Informazioni attivazione environment[/blue]")
    
    venv_manager = VenvManager()
    env_name = venv_manager.config["venv_name"]
    
    if not venv_manager.environment_exists(env_name):
        rprint(f"[red]❌ Environment {env_name} non trovato[/red]")
        rprint("💡 Crea prima l'environment: nextcloud-wrapper venv setup")
        sys.exit(1)
    
    rprint(f"[bold]🐍 Per attivare manualmente l'environment:[/bold]")
    rprint(f"   conda activate {env_name}")
    
    rprint(f"\n[bold]📋 Per caricare configurazione:[/bold]")
    rprint(f"   source .env")
    
    rprint(f"\n[bold]🧪 Per testare:[/bold]")
    rprint(f"   nextcloud-wrapper --version")
    rprint(f"   nextcloud-wrapper config")
    
    rprint(f"\n[bold]⚙️ Per servizi SystemD:[/bold]")
    systemd_path = venv_manager.get_systemd_executable_path()
    rprint(f"   ExecStart={systemd_path}")
    
    # Info environment attivo
    current_env = venv_manager.get_current_venv()
    if current_env == env_name:
        rprint(f"\n[green]✅ Environment {env_name} già attivo![/green]")
    elif current_env:
        rprint(f"\n[yellow]⚠️ Environment diverso attivo: {current_env}[/yellow]")
    else:
        rprint(f"\n[cyan]ℹ️ Nessun environment attivo[/cyan]")


if __name__ == "__main__":
    venv_app()
