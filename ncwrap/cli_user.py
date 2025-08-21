"""
CLI User - Gestione utenti Nextcloud e Linux
"""
import typer
import sys
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from .api import (
    create_nc_user, 
    test_webdav_login, 
    check_user_exists,
    get_webdav_url,
    set_nc_password
)
from .system import (
    create_linux_user, 
    sync_passwords, 
    get_user_info,
    user_exists
)
from .webdav import WebDAVMountManager
from .quota import get_quota_info
from .utils import check_sudo_privileges, is_mounted

user_app = typer.Typer(help="Gestione utenti")
console = Console()


@user_app.command("create")
def create_user(
    username: str = typer.Argument(help="Nome utente"),
    password: str = typer.Argument(help="Password"),
    skip_linux: bool = typer.Option(False, "--skip-linux", help="Non creare utente Linux")
):
    """Crea solo utente Nextcloud (senza WebDAV mount)"""
    rprint(f"[blue]👤 Creando utente: {username}[/blue]")
    
    try:
        # Crea utente Nextcloud
        if check_user_exists(username):
            rprint(f"[yellow]⚠️ Utente Nextcloud già esistente: {username}[/yellow]")
        else:
            create_nc_user(username, password)
            rprint("[green]✅ Utente Nextcloud creato[/green]")
        
        # Crea utente Linux
        if not skip_linux:
            if not check_sudo_privileges():
                rprint("[red]❌ Privilegi sudo richiesti per utente Linux[/red]")
                sys.exit(1)
            
            if user_exists(username):
                rprint(f"[yellow]⚠️ Utente Linux già esistente: {username}[/yellow]")
            else:
                if create_linux_user(username, password, create_home=False):
                    rprint("[green]✅ Utente Linux creato[/green]")
                else:
                    rprint("[red]❌ Errore creazione utente Linux[/red]")
        
        rprint(f"[green]🎉 Utente {username} creato con successo![/green]")
        
    except Exception as e:
        rprint(f"[red]❌ Errore: {e}[/red]")
        sys.exit(1)


@user_app.command("test")
def test_user(
    username: str = typer.Argument(help="Nome utente"),
    password: str = typer.Argument(help="Password")
):
    """Testa login WebDAV per un utente"""
    rprint(f"[blue]🔐 Test login WebDAV per: {username}[/blue]")
    
    try:
        status_code, response = test_webdav_login(username, password)
        
        if status_code in (200, 207):
            rprint("[green]✅ Login WebDAV riuscito![/green]")
            rprint(f"[cyan]Status: {status_code}[/cyan]")
        elif status_code == 401:
            rprint("[red]❌ Credenziali errate[/red]")
        else:
            rprint(f"[yellow]⚠️ Status imprevisto: {status_code}[/yellow]")
            rprint(f"Response: {response[:200]}...")
            
    except Exception as e:
        rprint(f"[red]❌ Errore test: {e}[/red]")
        sys.exit(1)


@user_app.command("passwd")
def change_password(
    username: str = typer.Argument(help="Nome utente"),
    new_password: str = typer.Argument(help="Nuova password"),
    nc_only: bool = typer.Option(False, "--nc-only", help="Solo Nextcloud")
):
    """Cambia password utente (Nextcloud + Linux)"""
    rprint(f"[blue]🔑 Cambio password per: {username}[/blue]")
    
    try:
        if nc_only:
            set_nc_password(username, new_password)
            rprint("[green]✅ Password Nextcloud aggiornata[/green]")
        else:
            if not check_sudo_privileges():
                rprint("[red]❌ Privilegi sudo richiesti[/red]")
                sys.exit(1)
                
            results = sync_passwords(username, new_password)
            
            if results["nextcloud"]:
                rprint("[green]✅ Password Nextcloud aggiornata[/green]")
            else:
                rprint("[red]❌ Errore Nextcloud[/red]")
                
            if results["linux"]:
                rprint("[green]✅ Password Linux aggiornata[/green]")
            else:
                rprint("[red]❌ Errore Linux[/red]")
                
            if results["errors"]:
                for error in results["errors"]:
                    rprint(f"[red]• {error}[/red]")
                    
            if results["nextcloud"] and results["linux"]:
                rprint("[bold green]🎉 Password sincronizzate![/bold green]")
                
                # Aggiorna credenziali WebDAV se mount attivo
                home_path = f"/home/{username}"
                if is_mounted(home_path):
                    rprint("[yellow]🔄 Aggiornando credenziali WebDAV...[/yellow]")
                    webdav_manager = WebDAVMountManager()
                    from .api import get_nc_config
                    base_url, _, _ = get_nc_config()
                    webdav_url = f"{base_url}/remote.php/dav/files/{username}/"
                    webdav_manager.setup_user_credentials(username, new_password, webdav_url)
                    rprint("[green]✅ Credenziali WebDAV aggiornate[/green]")
            
    except Exception as e:
        rprint(f"[red]❌ Errore: {e}[/red]")
        sys.exit(1)


@user_app.command("info")
def user_info(
    username: str = typer.Argument(help="Nome utente")
):
    """Mostra informazioni complete utente"""
    rprint(f"[blue]ℹ️ Informazioni utente: {username}[/blue]")
    
    # Info Nextcloud
    try:
        nc_exists = check_user_exists(username)
        rprint(f"[bold]Nextcloud:[/bold] {'✅ Presente' if nc_exists else '❌ Non trovato'}")
        
        if nc_exists:
            webdav_url = get_webdav_url(username)
            rprint(f"  WebDAV URL: {webdav_url}")
            
    except Exception as e:
        rprint(f"[bold]Nextcloud:[/bold] [red]❌ Errore: {e}[/red]")
    
    # Info Linux  
    linux_info = get_user_info(username)
    if linux_info:
        rprint("[bold]Linux:[/bold] ✅ Presente")
        
        table = Table(title="Dettagli Utente Linux")
        table.add_column("Campo", style="cyan")
        table.add_column("Valore", style="white")
        
        for key, value in linux_info.items():
            table.add_row(key.upper(), str(value))
            
        console.print(table)
    else:
        rprint("[bold]Linux:[/bold] ❌ Non trovato")
    
    # Info WebDAV mount
    home_path = f"/home/{username}"
    if is_mounted(home_path):
        rprint("[bold]WebDAV Mount:[/bold] ✅ Attivo")
        
        webdav_manager = WebDAVMountManager()
        mount_status = webdav_manager.get_mount_status(home_path)
        if mount_status.get("details"):
            rprint(f"  Details: {mount_status['details']}")
    else:
        rprint("[bold]WebDAV Mount:[/bold] ❌ Non montato")
    
    # Info quota
    quota_info = get_quota_info(username)
    if quota_info:
        rprint(f"[bold]Quota:[/bold] ✅ {quota_info['used']} / {quota_info.get('limit', 'unlimited')}")
        rprint(f"  Filesystem: {quota_info.get('filesystem', 'unknown')}")
    else:
        rprint("[bold]Quota:[/bold] ❌ Non impostata")


@user_app.command("list")
def list_users():
    """Lista tutti gli utenti con mount WebDAV"""
    rprint("[blue]👥 Utenti con mount WebDAV attivi[/blue]")
    
    webdav_manager = WebDAVMountManager()
    mounts = webdav_manager.list_webdav_mounts()
    
    if mounts:
        table = Table(title="Mount WebDAV Attivi")
        table.add_column("Utente", style="cyan")
        table.add_column("Mount Point", style="white")
        table.add_column("URL WebDAV", style="blue")
        table.add_column("Status", style="green")
        
        for mount in mounts:
            # Estrai username dal mount point
            mount_point = mount.get("mountpoint", "")
            if "/home/" in mount_point:
                username = mount_point.replace("/home/", "").split("/")[0]
            else:
                username = "unknown"
            
            table.add_row(
                username,
                mount_point,
                mount.get("url", ""),
                "🟢 Attivo"
            )
            
        console.print(table)
    else:
        rprint("[yellow]Nessun mount WebDAV attivo[/yellow]")


@user_app.command("delete")
def delete_user(
    username: str = typer.Argument(help="Nome utente da eliminare"),
    confirm: bool = typer.Option(False, "--confirm", help="Conferma eliminazione"),
    keep_data: bool = typer.Option(True, "--keep-data/--delete-data", help="Mantieni dati utente")
):
    """Elimina utente (richiede conferma)"""
    if not confirm:
        rprint(f"[red]⚠️ ATTENZIONE: Stai per eliminare l'utente {username}[/red]")
        rprint("💡 Aggiungi --confirm per procedere")
        sys.exit(1)
    
    rprint(f"[blue]🗑️ Eliminazione utente: {username}[/blue]")
    
    if not check_sudo_privileges():
        rprint("[red]❌ Privilegi sudo richiesti[/red]")
        sys.exit(1)
    
    try:
        # Smonta WebDAV se attivo
        home_path = f"/home/{username}"
        if is_mounted(home_path):
            rprint("[yellow]📁 Smontando WebDAV...[/yellow]")
            webdav_manager = WebDAVMountManager()
            webdav_manager.unmount_webdav(home_path)
        
        # Rimuovi servizi systemd
        from .systemd import SystemdManager
        systemd_manager = SystemdManager()
        service_name = f"webdav-home-{username}"
        systemd_manager.remove_service(service_name)
        
        # Rimuovi quota
        from .quota import QuotaManager
        quota_manager = QuotaManager()
        quota_manager.remove_quota(username)
        
        # Elimina utente Linux
        from .system import delete_linux_user
        if delete_linux_user(username, remove_home=not keep_data):
            rprint("[green]✅ Utente Linux eliminato[/green]")
        
        rprint(f"[green]✅ Utente {username} eliminato[/green]")
        if keep_data:
            rprint("[yellow]ℹ️ Dati utente mantenuti in backup[/yellow]")
        
    except Exception as e:
        rprint(f"[red]❌ Errore eliminazione: {e}[/red]")
