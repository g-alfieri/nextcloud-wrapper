"""
CLI principale per nextcloud-wrapper v0.3.0 - WebDAV Direct Backend
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
    from .cli_webdav import webdav_app
except ImportError:
    webdav_app = None

try:
    from .cli_mount import mount_app
except ImportError:
    mount_app = None

try:
    from .cli_quota import quota_app
except ImportError:
    quota_app = None

try:
    from .cli_service import service_app
except ImportError:
    service_app = None

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
        rprint("[cyan]Backend: WebDAV Direct Mount[/cyan]")
        raise typer.Exit()

app = typer.Typer(
    name="nextcloud-wrapper",
    help="Wrapper v0.3.0 per gestione Nextcloud con WebDAV diretto, quote e utenti",
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
    """Nextcloud Wrapper v0.4.0 - rclone Engine & WebDAV Unified Backend"""

# Aggiungi sotto-comandi (solo se importati con successo)
if setup_app:
    app.add_typer(setup_app, name="setup")
if user_app:
    app.add_typer(user_app, name="user")
if mount_app:
    app.add_typer(mount_app, name="mount")
if webdav_app:
    app.add_typer(webdav_app, name="webdav")
if quota_app:
    app.add_typer(quota_app, name="quota")
if service_app:
    app.add_typer(service_app, name="service")
if venv_app:
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
        try:
            from .quota import QuotaManager
            quota_manager = QuotaManager()
            fs_info = quota_manager.get_filesystem_usage()
            if fs_info:
                rprint(f"[bold]Filesystem:[/bold] {fs_info['filesystem']} ({fs_info['use_percent']} usato)")
        except Exception:
            rprint("[bold]Filesystem:[/bold] ⚠️ Info non disponibile")
        
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
    
    # Status mount (aggiornato per engine unificato)
    try:
        from .mount import MountManager
        mount_manager = MountManager()
        mounts = mount_manager.list_mounts()
        rprint(f"[bold]Mount attivi:[/bold] {len(mounts)}")
        
        # Breakdown per engine
        from .mount import MountEngine
        rclone_count = sum(1 for m in mounts if m["engine"] == MountEngine.RCLONE)
        davfs2_count = sum(1 for m in mounts if m["engine"] == MountEngine.DAVFS2)
        
        if rclone_count > 0:
            rprint(f"  • rclone: {rclone_count}")
        if davfs2_count > 0:
            rprint(f"  • davfs2: {davfs2_count}")
            
    except Exception:
        try:
            # Fallback al vecchio metodo WebDAV
            from .webdav import WebDAVMountManager
            webdav_manager = WebDAVMountManager()
            mounts = webdav_manager.list_webdav_mounts()
            rprint(f"[bold]Mount WebDAV attivi:[/bold] {len(mounts)}")
        except Exception:
            rprint("[bold]Mount attivi:[/bold] ⚠️ Non rilevato")
    
    # Status servizi
    try:
        from .systemd import list_all_webdav_services
        all_services = list_all_webdav_services()
        system_count = len(all_services.get("system", []))
        user_count = len(all_services.get("user", []))
        rprint(f"[bold]Servizi systemd:[/bold] {system_count} system, {user_count} user")
    except Exception:
        rprint("[bold]Servizi systemd:[/bold] ⚠️ Non rilevato")
    
    # Status quote
    try:
        from .quota import list_all_user_quotas
        quotas = list_all_user_quotas()
        rprint(f"[bold]Quote configurate:[/bold] {len(quotas)}")
    except Exception:
        rprint("[bold]Quote configurate:[/bold] ⚠️ Non rilevato")


if __name__ == "__main__":
    app()
