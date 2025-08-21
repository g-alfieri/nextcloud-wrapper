"""
CLI WebDAV - Gestione mount WebDAV
"""
import typer
import sys
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from .webdav import WebDAVMountManager
from .api import test_webdav_connectivity, test_webdav_login, list_webdav_directory
from .utils import check_sudo_privileges, is_mounted

webdav_app = typer.Typer(help="Gestione mount WebDAV")
console = Console()


@webdav_app.command("mount")
def webdav_mount(
    username: str = typer.Argument(help="Nome utente"),
    password: str = typer.Argument(help="Password"),
    mount_point: str = typer.Option(None, help="Directory mount (default: /home/username)"),
    auto_service: bool = typer.Option(True, "--service/--no-service", help="Crea servizio systemd")
):
    """Monta WebDAV Nextcloud in directory"""
    if not mount_point:
        mount_point = f"/home/{username}"
    
    rprint(f"[blue]🔗 Mount WebDAV {username} → {mount_point}[/blue]")
    
    if not check_sudo_privileges():
        rprint("[red]❌ Privilegi sudo richiesti[/red]")
        sys.exit(1)
    
    try:
        webdav_manager = WebDAVMountManager()
        
        # Installa e configura davfs2
        if not webdav_manager.install_davfs2():
            sys.exit(1)
        
        if not webdav_manager.configure_davfs2():
            sys.exit(1)
        
        # Mount WebDAV
        if webdav_manager.mount_webdav_home(username, password, mount_point):
            rprint(f"[green]✅ WebDAV montato: {mount_point}[/green]")
            
            # Crea servizio automatico
            if auto_service:
                try:
                    service_name = webdav_manager.create_systemd_service(username, password, mount_point)
                    if webdav_manager.enable_service(service_name):
                        rprint(f"[green]✅ Servizio automatico: {service_name}[/green]")
                except Exception as e:
                    rprint(f"[yellow]⚠️ Avviso servizio: {e}[/yellow]")
        else:
            rprint("[red]❌ Errore mount WebDAV[/red]")
            sys.exit(1)
            
    except Exception as e:
        rprint(f"[red]❌ Errore: {e}[/red]")
        sys.exit(1)


@webdav_app.command("unmount")
def webdav_unmount(
    mount_point: str = typer.Argument(help="Directory da smontare")
):
    """Smonta WebDAV"""
    rprint(f"[blue]📁 Smontando WebDAV: {mount_point}[/blue]")
    
    if not check_sudo_privileges():
        rprint("[red]❌ Privilegi sudo richiesti[/red]")
        sys.exit(1)
    
    try:
        webdav_manager = WebDAVMountManager()
        if webdav_manager.unmount_webdav(mount_point):
            rprint("[green]✅ WebDAV smontato[/green]")
        else:
            rprint("[red]❌ Errore unmount[/red]")
            
    except Exception as e:
        rprint(f"[red]❌ Errore: {e}[/red]")


@webdav_app.command("status")
def webdav_status():
    """Mostra status di tutti i mount WebDAV"""
    rprint("[blue]📊 Status mount WebDAV[/blue]")
    
    webdav_manager = WebDAVMountManager()
    mounts = webdav_manager.list_webdav_mounts()
    
    if mounts:
        table = Table(title="Mount WebDAV")
        table.add_column("URL", style="blue")
        table.add_column("Mount Point", style="cyan")
        table.add_column("Options", style="white")
        table.add_column("Status", style="green")
        
        for mount in mounts:
            # Verifica se mount è ancora attivo
            mount_point = mount.get("mountpoint", "")
            status = "🟢 Attivo" if is_mounted(mount_point) else "🔴 Inattivo"
            
            table.add_row(
                mount.get("url", ""),
                mount_point,
                mount.get("options", ""),
                status
            )
            
        console.print(table)
    else:
        rprint("[yellow]Nessun mount WebDAV trovato[/yellow]")


@webdav_app.command("test")
def webdav_test(
    username: str = typer.Argument(help="Nome utente"),
    password: str = typer.Argument(help="Password")
):
    """Testa connettività WebDAV senza mount"""
    rprint(f"[blue]🧪 Test connettività WebDAV per {username}[/blue]")
    
    try:
        if test_webdav_connectivity(username, password):
            rprint("[green]✅ Connettività WebDAV OK[/green]")
            
            # Test dettagliato
            status_code, response = test_webdav_login(username, password)
            rprint(f"[cyan]Status Code: {status_code}[/cyan]")
            
            # Lista directory root
            list_status, xml_content = list_webdav_directory(username, password)
            if list_status in (200, 207):
                rprint("[green]✅ Listing directory OK[/green]")
            else:
                rprint(f"[yellow]⚠️ Listing status: {list_status}[/yellow]")
        else:
            rprint("[red]❌ Test connettività fallito[/red]")
            
    except Exception as e:
        rprint(f"[red]❌ Errore test: {e}[/red]")


@webdav_app.command("install")
def install_davfs2():
    """Installa e configura davfs2"""
    rprint("[blue]📦 Installazione e configurazione davfs2[/blue]")
    
    if not check_sudo_privileges():
        rprint("[red]❌ Privilegi sudo richiesti[/red]")
        sys.exit(1)
    
    try:
        webdav_manager = WebDAVMountManager()
        
        if webdav_manager.install_davfs2():
            rprint("[green]✅ davfs2 installato[/green]")
        else:
            rprint("[red]❌ Errore installazione davfs2[/red]")
            sys.exit(1)
        
        if webdav_manager.configure_davfs2():
            rprint("[green]✅ davfs2 configurato[/green]")
        else:
            rprint("[red]❌ Errore configurazione davfs2[/red]")
            
    except Exception as e:
        rprint(f"[red]❌ Errore: {e}[/red]")


@webdav_app.command("config")
def show_webdav_config():
    """Mostra configurazione davfs2 corrente"""
    rprint("[blue]⚙️ Configurazione davfs2[/blue]")
    
    try:
        from pathlib import Path
        
        # File configurazione davfs2
        davfs_conf = Path("/etc/davfs2/davfs2.conf")
        secrets_file = Path("/etc/davfs2/secrets")
        
        if davfs_conf.exists():
            rprint(f"[green]✅ Configurazione: {davfs_conf}[/green]")
        else:
            rprint(f"[red]❌ File configurazione non trovato: {davfs_conf}[/red]")
        
        if secrets_file.exists():
            rprint(f"[green]✅ File secrets: {secrets_file}[/green]")
        else:
            rprint(f"[red]❌ File secrets non trovato: {secrets_file}[/red]")
        
        # Mostra cache directory
        cache_dir = Path("/var/cache/davfs2")
        if cache_dir.exists():
            rprint(f"[green]✅ Cache directory: {cache_dir}[/green]")
        else:
            rprint(f"[yellow]⚠️ Cache directory non trovata: {cache_dir}[/yellow]")
        
    except Exception as e:
        rprint(f"[red]❌ Errore: {e}[/red]")


@webdav_app.command("cleanup")
def cleanup_cache():
    """Pulisce cache davfs2"""
    rprint("[blue]🧹 Pulizia cache davfs2[/blue]")
    
    if not check_sudo_privileges():
        rprint("[red]❌ Privilegi sudo richiesti[/red]")
        sys.exit(1)
    
    try:
        from pathlib import Path
        import shutil
        
        cache_dir = Path("/var/cache/davfs2")
        if cache_dir.exists():
            # Calcola dimensione prima
            total_size = sum(f.stat().st_size for f in cache_dir.rglob('*') if f.is_file())
            
            if total_size > 0:
                from .utils import bytes_to_human
                rprint(f"[yellow]Cache corrente: {bytes_to_human(total_size)}[/yellow]")
                
                # Rimuovi file cache
                for item in cache_dir.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir() and item.name != "lost+found":
                        shutil.rmtree(item)
                
                rprint("[green]✅ Cache pulita[/green]")
            else:
                rprint("[yellow]Cache già vuota[/yellow]")
        else:
            rprint("[yellow]Directory cache non trovata[/yellow]")
            
    except Exception as e:
        rprint(f"[red]❌ Errore pulizia cache: {e}[/red]")
