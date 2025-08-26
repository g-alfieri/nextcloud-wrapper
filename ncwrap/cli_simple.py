"""
CLI principale per nextcloud-wrapper v0.3.0 - WebDAV Direct Backend (Simplified)
"""
import typer
import sys
from rich.console import Console
from rich import print as rprint

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
    """Nextcloud Wrapper v0.3.0 - WebDAV Direct Backend"""

# Importa e registra solo i moduli CLI che si caricano correttamente
def register_cli_modules():
    """Registra moduli CLI in modo sicuro"""
    cli_modules = {
        'setup': ('cli_setup', 'setup_app'),
        'user': ('cli_user', 'user_app'), 
        'webdav': ('cli_webdav', 'webdav_app'),
        'quota': ('cli_quota', 'quota_app'),
        'service': ('cli_service', 'service_app'),
        'venv': ('cli_venv', 'venv_app')
    }
    
    registered = []
    
    for name, (module_name, app_name) in cli_modules.items():
        try:
            module = __import__(f"ncwrap.{module_name}", fromlist=[app_name])
            cli_app = getattr(module, app_name)
            app.add_typer(cli_app, name=name)
            registered.append(name)
        except Exception as e:
            # Silent fail - module not available
            pass
    
    return registered

# Registra moduli CLI disponibili
_registered_modules = register_cli_modules()

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
        
        # Moduli CLI caricati
        rprint(f"[bold]Moduli CLI:[/bold] {', '.join(_registered_modules) if _registered_modules else 'Solo comandi base'}")
        
    except Exception as e:
        rprint(f"[red]❌ Errore configurazione: {e}[/red]")
        rprint("[yellow]💡 Assicurati di aver impostato le variabili d'ambiente:[/yellow]")
        rprint("   export NC_BASE_URL='https://your-nextcloud.example.com'")
        rprint("   export NC_ADMIN_USER='admin'")
        rprint("   export NC_ADMIN_PASS='your_password'")


@app.command()
def version():
    """Mostra versione"""
    from . import __version__
    rprint(f"[bold blue]Nextcloud Wrapper v{__version__}[/bold blue]")
    rprint("[cyan]Backend: WebDAV Direct Mount[/cyan]")
    
    # Info aggiuntive
    rprint(f"[yellow]Python:[/yellow] {sys.version.split()[0]}")
    
    try:
        import requests
        rprint(f"[yellow]Requests:[/yellow] {requests.__version__}")
    except:
        rprint("[yellow]Requests:[/yellow] Non disponibile")
    
    try:
        import rich
        rprint(f"[yellow]Rich:[/yellow] {rich.__version__}")
    except:
        rprint("[yellow]Rich:[/yellow] Non disponibile")


@app.command()
def status():
    """Status generale del sistema"""
    rprint("[blue]📊 Status generale nextcloud-wrapper[/blue]")
    
    # Test connettività Nextcloud
    try:
        from .api import test_nextcloud_connectivity
        success, message = test_nextcloud_connectivity()
        status_icon = "✅" if success else "❌"
        rprint(f"[bold]Nextcloud Server:[/bold] {status_icon} {message}")
    except Exception as e:
        rprint(f"[bold]Nextcloud Server:[/bold] ⚠️ Test non disponibile ({e})")
    
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
    try:
        from .webdav import WebDAVMountManager
        webdav_manager = WebDAVMountManager()
        mounts = webdav_manager.list_webdav_mounts()
        rprint(f"[bold]Mount WebDAV attivi:[/bold] {len(mounts)}")
    except Exception:
        rprint("[bold]Mount WebDAV attivi:[/bold] ⚠️ Non rilevato")
    
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
    
    # Moduli disponibili
    rprint(f"[bold]Moduli CLI attivi:[/bold] {len(_registered_modules)}")
    if _registered_modules:
        for module in _registered_modules:
            rprint(f"  • nextcloud-wrapper {module}")


@app.command()
def test():
    """Test completo del sistema"""
    rprint("[blue]🧪 Test completo nextcloud-wrapper[/blue]")
    
    tests_passed = 0
    tests_total = 0
    
    # Test 1: Configurazione
    tests_total += 1
    try:
        get_nc_config()
        rprint("[green]✅ Test 1: Configurazione ambiente[/green]")
        tests_passed += 1
    except Exception as e:
        rprint(f"[red]❌ Test 1: Configurazione ambiente - {e}[/red]")
    
    # Test 2: Connettività Nextcloud
    tests_total += 1
    try:
        from .api import test_nextcloud_connectivity
        success, message = test_nextcloud_connectivity()
        if success:
            rprint("[green]✅ Test 2: Connettività Nextcloud[/green]")
            tests_passed += 1
        else:
            rprint(f"[red]❌ Test 2: Connettività Nextcloud - {message}[/red]")
    except Exception as e:
        rprint(f"[red]❌ Test 2: Connettività Nextcloud - {e}[/red]")
    
    # Test 3: Moduli Python
    tests_total += 1
    try:
        import requests, rich, typer
        rprint("[green]✅ Test 3: Dipendenze Python[/green]")
        tests_passed += 1
    except Exception as e:
        rprint(f"[red]❌ Test 3: Dipendenze Python - {e}[/red]")
    
    # Test 4: Privilegi sistema
    tests_total += 1
    if check_sudo_privileges():
        rprint("[green]✅ Test 4: Privilegi sudo (disponibili)[/green]")
        tests_passed += 1
    else:
        rprint("[yellow]⚠️ Test 4: Privilegi sudo (non disponibili - alcune funzioni limitate)[/yellow]")
    
    # Test 5: Moduli CLI
    tests_total += 1
    if len(_registered_modules) >= 3:  # Almeno 3 moduli caricati
        rprint(f"[green]✅ Test 5: Moduli CLI ({len(_registered_modules)} caricati)[/green]")
        tests_passed += 1
    else:
        rprint(f"[yellow]⚠️ Test 5: Moduli CLI ({len(_registered_modules)} caricati - funzionalità limitata)[/yellow]")
    
    # Risultato finale
    rprint(f"\n[bold]📊 Risultati test: {tests_passed}/{tests_total} superati[/bold]")
    
    if tests_passed >= 3:
        rprint("[green]🎉 Sistema funzionante! Puoi utilizzare nextcloud-wrapper.[/green]")
    elif tests_passed >= 2:
        rprint("[yellow]⚠️ Sistema parzialmente funzionante. Alcune funzioni potrebbero non essere disponibili.[/yellow]")
    else:
        rprint("[red]❌ Sistema non funzionante. Verifica configurazione e dipendenze.[/red]")
        sys.exit(1)


# Comandi diretti per funzionalità base (quando i moduli CLI non sono disponibili)
@app.command()
def quick_test(
    username: str = typer.Argument(help="Username da testare"),
    password: str = typer.Argument(help="Password da testare")
):
    """Test rapido login WebDAV utente"""
    rprint(f"[blue]🔐 Test rapido login per: {username}[/blue]")
    
    try:
        from .api import test_webdav_connectivity
        if test_webdav_connectivity(username, password):
            rprint("[green]✅ Login WebDAV riuscito![/green]")
        else:
            rprint("[red]❌ Login WebDAV fallito[/red]")
    except Exception as e:
        rprint(f"[red]❌ Errore test: {e}[/red]")


if __name__ == "__main__":
    app()
