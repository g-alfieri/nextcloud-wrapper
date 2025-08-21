"""
CLI principale per nextcloud-wrapper v0.3.0 - WebDAV Direct Backend
"""
import typer
import sys
from rich.console import Console
from rich import print as rprint

# Import dei sotto-comandi
from .cli_setup import setup_app
from .cli_user import user_app
from .cli_webdav import webdav_app
from .cli_quota import quota_app
from .cli_service import service_app
from .cli_venv import venv_app
from .api import get_nc_config
from .utils import check_sudo_privileges

app = typer.Typer(
    name="nextcloud-wrapper",
    help="Wrapper v0.3.0 per gestione Nextcloud con WebDAV diretto, quote e utenti",
    add_completion=False
)
console = Console()

# Aggiungi sotto-comandi
app.add_typer(setup_app, name="setup")
app.add_typer(user_app, name="user")
app.add_typer(webdav_app, name="webdav")
app.add_typer(quota_app, name="quota")
app.add_typer(service_app, name="service")
app.add_typer(venv_app, name="venv")


@app.command()
def config():
    """Mostra configurazione corrente"""
    rprint("[blue]⚙️ Configurazione Nextcloud Wrapper v0.3.0[/blue]")
    
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
        
        # Info filesystem
        from .quota import QuotaManager
        quota_manager = QuotaManager()
        fs_info = quota_manager.get_filesystem_usage()
        if fs_info:
            rprint(f"[bold]Filesystem:[/bold] {fs_info['filesystem']} ({fs_info['use_percent']} usato)")
        
    except Exception as e:
        rprint(f"[red]❌ Errore configurazione: {e}[/red]")


@app.command()
def version():
    """Mostra versione"""
    from . import __version__
    rprint(f"[bold blue]Nextcloud Wrapper v{__version__}[/bold blue]")
    rprint("[cyan]Backend: WebDAV Direct Mount[/cyan]")


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
    
    # Status mount WebDAV
    from .webdav import WebDAVMountManager
    webdav_manager = WebDAVMountManager()
    mounts = webdav_manager.list_webdav_mounts()
    rprint(f"[bold]Mount WebDAV attivi:[/bold] {len(mounts)}")
    
    # Status servizi
    from .systemd import list_all_webdav_services
    all_services = list_all_webdav_services()
    system_count = len(all_services.get("system", []))
    user_count = len(all_services.get("user", []))
    rprint(f"[bold]Servizi systemd:[/bold] {system_count} system, {user_count} user")
    
    # Status quote
    from .quota import list_all_user_quotas
    quotas = list_all_user_quotas()
    rprint(f"[bold]Quote configurate:[/bold] {len(quotas)}")


if __name__ == "__main__":
    app()
