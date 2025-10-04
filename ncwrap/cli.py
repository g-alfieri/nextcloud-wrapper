"""
CLI principale per nextcloud-wrapper v1.0.0rc2 - rclone Engine Semplificato
"""
import typer
import sys
from rich.console import Console
from rich import print as rprint

# Import dei sotto-comandi
try:
    from .cli_setup import setup_app
except ImportError:
    setup_app = None

try:
    from .cli_user import user_app
except ImportError:
    user_app = None

try:
    from .cli_mount import mount_app
except ImportError:
    mount_app = None

# quota_app rimosso in v1.0.0 (gestione spazio automatica rclone)
quota_app = None

# ✅ cli_service rimosso - funzionalità integrate in mount_app
# service_app = None

try:
    from .cli_venv import venv_app
except ImportError:
    venv_app = None

from .api import get_nc_config
from .utils import check_sudo_privileges

def version_callback(value: bool):
    """Callback per --version flag globale"""
    if value:
        from . import __version__
        rprint(f"[bold blue]Nextcloud Wrapper v{__version__}[/bold blue]")
        rprint("[cyan]Engine: rclone Semplificato (v1.0)[/cyan]")
        raise typer.Exit()

app = typer.Typer(
    name="nextcloud-wrapper",
    help="Wrapper v1.0.0rc2 per gestione Nextcloud con rclone engine semplificato",
    add_completion=False
)
console = Console()

# Aggiungi opzione --version globale
@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v", 
        help="Mostra versione del programma", 
        callback=version_callback,
        is_eager=True
    )
):
    """Nextcloud Wrapper v1.0.0rc2 - rclone Engine Semplificato"""

# Aggiungi sotto-comandi (solo se importati con successo)
if setup_app:
    app.add_typer(setup_app, name="setup")
if user_app:
    app.add_typer(user_app, name="user")
if mount_app:
    app.add_typer(mount_app, name="mount")

# ✅ service command rimosso - funzionalità integrate in mount
# quota command rimosso in v1.0.0

if venv_app:
    app.add_typer(venv_app, name="venv")


@app.command()
def config():
    """Mostra configurazione corrente"""
    rprint("[blue]⚙️ Configurazione Nextcloud Wrapper v1.0.0rc2[/blue]")
    
    try:
        base_url, admin_user, admin_pass = get_nc_config()
        
        from rich.table import Table
        table = Table(title="Configurazione Nextcloud")
        table.add_column("Variabile", style="cyan")
        table.add_column("Valore", style="white")
        
        table.add_row("NC_BASE_URL", base_url)
        table.add_row("NC_ADMIN_USER", admin_user)
        table.add_row("NC_ADMIN_PASS", "***" + admin_pass[-3:])
        
        console.print(table)
        
        # Verifica privilegi sudo
        has_sudo = check_sudo_privileges()
        rprint(f"[bold]Privilegi sudo:[/bold] {'✅ Disponibili' if has_sudo else '❌ Non disponibili'}")
        
        # Gestione spazio v1.0 (automatica rclone)
        rprint("[bold]Gestione spazio:[/bold] ✅ Automatica via rclone (cache LRU)")
        
    except Exception as e:
        rprint(f"[red]❌ Errore configurazione: {e}[/red]")


@app.command()
def version():
    """Mostra versione"""
    from . import __version__
    rprint(f"[bold blue]Nextcloud Wrapper v{__version__}[/bold blue]")
    rprint("[cyan]Engine: rclone Semplificato (v1.0)[/cyan]")


@app.command()
def status():
    """Status generale del sistema"""
    rprint("[blue]📊 Status generale nextcloud-wrapper[/blue]")
    
    # Status virtual environment
    try:
        from .venv import VenvManager
        venv_manager = VenvManager()
        
        if venv_manager.is_conda_available():
            current_env = venv_manager.get_current_venv()
            if current_env:
                rprint(f"[bold]Virtual Environment:[/bold] ✅ {current_env}")
            else:
                rprint("[bold]Virtual Environment:[/bold] ❌ Nessuno attivo")
        else:
            rprint("[bold]Virtual Environment:[/bold] ❌ Conda non disponibile")
    except Exception:
        rprint("[bold]Virtual Environment:[/bold] ⚠️ Non rilevato")
    
    # Status mount rclone (engine unico v1.0)
    try:
        from .mount import MountManager
        mount_manager = MountManager()
        mounts = mount_manager.list_mounts()
        rprint(f"[bold]Mount rclone attivi:[/bold] {len(mounts)}")
        
        # Info profili se disponibili
        profiles_used = set()
        for mount in mounts:
            if mount.get("type") == "rclone":
                # Tenta di rilevare il profilo (approssimativo)
                if "full" in str(mount.get("options", "")):
                    profiles_used.add("full")
                elif "writes" in str(mount.get("options", "")):
                    profiles_used.add("writes")
                elif "minimal" in str(mount.get("options", "")):
                    profiles_used.add("minimal")
                elif "hosting" in str(mount.get("options", "")):
                    profiles_used.add("hosting")
        
        if profiles_used:
            rprint(f"  • Profili in uso: {', '.join(profiles_used)}")
            
    except Exception:
        rprint("[bold]Mount rclone:[/bold] ⚠️ Non rilevato")
    
    # Status servizi - ora gestiti da MountManager direttamente
    try:
        from .systemd import list_all_mount_services
        all_services = list_all_mount_services()
        system_count = len(all_services.get("system", []))
        user_count = len(all_services.get("user", []))
        rprint(f"[bold]Servizi systemd:[/bold] {system_count} system, {user_count} user")
        rprint("  💡 Usa 'nextcloud-wrapper mount service --help' per gestire i servizi")
    except Exception:
        rprint("[bold]Servizi systemd:[/bold] ⚠️ Non rilevato")
    
    # Gestione spazio v1.0 (automatica)
    rprint("[bold]Gestione spazio:[/bold] ✅ Automatica via rclone (cache LRU)")


if __name__ == "__main__":
    app()
