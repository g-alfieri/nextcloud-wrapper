"""
CLI User - Gestione utenti Nextcloud e Linux (v1.0 semplificato)
Solo rclone, zero quote filesystem
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
    user_exists,
    get_system_users
)
from .utils import check_sudo_privileges, is_mounted

user_app = typer.Typer(help="Gestione utenti v1.0")
console = Console()


@user_app.command("create")
def create_user(
    username: str = typer.Argument(help="Nome utente"),
    password: str = typer.Argument(help="Password"),
    skip_linux: bool = typer.Option(False, "--skip-linux", help="Non creare utente Linux")
):
    """Crea utente Nextcloud e Linux (senza mount rclone)"""
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
        
        rprint(f"[green]🎉 Utente {username} creato![/green]")
        rprint("[cyan]💡 Per mount rclone: nextcloud-wrapper setup user <user> <password>[/cyan]")
        
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
                
                # RIMOSSO v1.0: Aggiornamento credenziali WebDAV (ora gestito da rclone)
                rprint("[cyan]💡 Per aggiornare mount rclone: nextcloud-wrapper mount unmount e remount[/cyan]")
            
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
            if key != "home_stats":  # Salta info dettagliate home
                table.add_row(key.upper(), str(value))
            
        console.print(table)
    else:
        rprint("[bold]Linux:[/bold] ❌ Non trovato")
    
    # Info mount rclone (v1.0)
    home_path = f"/home/{username}"
    if is_mounted(home_path):
        rprint("[bold]Mount rclone:[/bold] ✅ Attivo")
        
        try:
            from .mount import MountManager
            mount_manager = MountManager()
            mount_status = mount_manager.get_mount_status(home_path)
            
            if mount_status.get("status"):
                rprint(f"  Status: {mount_status['status']}")
            if mount_status.get("profile"):
                rprint(f"  Profilo: {mount_status['profile']}")
                
        except Exception as e:
            rprint(f"  [yellow]⚠️ Errore info mount: {e}[/yellow]")
    else:
        rprint("[bold]Mount rclone:[/bold] ❌ Non montato")
        rprint("  [cyan]💡 Per montare: nextcloud-wrapper setup user <user> <password>[/cyan]")
    
    # RIMOSSO v1.0: Info quota filesystem (gestione automatica rclone)
    rprint("[bold]Gestione spazio:[/bold] ✅ Automatica via rclone")


@user_app.command("list")
def list_users(
    show_system: bool = typer.Option(False, "--show-system", help="Mostra anche utenti di sistema")
):
    """Lista tutti gli utenti con informazioni mount rclone"""
    rprint("[blue]👥 Utenti sistema con informazioni mount[/blue]")
    
    try:
        users = get_system_users(include_system=show_system)
        
        if not users:
            rprint("[yellow]Nessun utente trovato[/yellow]")
            return
        
        table = Table(title="Utenti Sistema")
        table.add_column("Username", style="cyan")
        table.add_column("UID", style="white")
        table.add_column("Home", style="blue")
        table.add_column("Mount rclone", style="green")
        table.add_column("Nextcloud", style="yellow")
        
        for user in users:
            username = user["username"]
            
            # Verifica se è utente Nextcloud
            try:
                nc_exists = check_user_exists(username) if user.get("is_nextcloud_user") else False
                nc_status = "✅" if nc_exists else "❌"
            except:
                nc_status = "❓"
            
            # Status mount rclone
            home_path = user.get("home", "")
            mount_status = "✅ Attivo" if is_mounted(home_path) else "❌ Non montato"
            
            table.add_row(
                username,
                str(user["uid"]),
                home_path,
                mount_status,
                nc_status
            )
            
        console.print(table)
        
        # Statistiche
        total_users = len(users)
        mounted_users = sum(1 for user in users if is_mounted(user.get("home", "")))
        
        rprint(f"\n[bold]📊 Riepilogo:[/bold]")
        rprint(f"• Utenti totali: {total_users}")
        rprint(f"• Con mount rclone: {mounted_users}")
        rprint(f"• Senza mount: {total_users - mounted_users}")
        
    except Exception as e:
        rprint(f"[red]❌ Errore listing utenti: {e}[/red]")
        sys.exit(1)


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
        rprint("💡 Aggiungi --delete-data per eliminare anche i dati")
        sys.exit(1)
    
    rprint(f"[blue]🗑️ Eliminazione utente: {username}[/blue]")
    
    if not check_sudo_privileges():
        rprint("[red]❌ Privilegi sudo richiesti[/red]")
        sys.exit(1)
    
    try:
        # Smonta rclone se attivo
        home_path = f"/home/{username}"
        if is_mounted(home_path):
            rprint("[yellow]📁 Smontando rclone...[/yellow]")
            try:
                from .mount import MountManager
                mount_manager = MountManager()
                if mount_manager.unmount_user_home(home_path):
                    rprint("[green]✅ Mount rclone smontato[/green]")
                else:
                    rprint("[yellow]⚠️ Errore unmount, continuo...[/yellow]")
            except Exception as e:
                rprint(f"[yellow]⚠️ Errore smount rclone: {e}[/yellow]")
        
        # Rimuovi servizi systemd
        try:
            from .utils import run
            services_output = run(["systemctl", "list-units", "--all"], check=False)
            if f"ncwrap-rclone-{username}" in services_output:
                rprint("[yellow]🔧 Rimuovendo servizio systemd...[/yellow]")
                run(["systemctl", "stop", f"ncwrap-rclone-{username}.service"], check=False)
                run(["systemctl", "disable", f"ncwrap-rclone-{username}.service"], check=False)
                
                import os
                service_file = f"/etc/systemd/system/ncwrap-rclone-{username}.service"
                if os.path.exists(service_file):
                    os.remove(service_file)
                    run(["systemctl", "daemon-reload"], check=False)
                    rprint("[green]✅ Servizio systemd rimosso[/green]")
        except Exception as e:
            rprint(f"[yellow]⚠️ Errore rimozione servizio: {e}[/yellow]")
        
        # Elimina utente Linux
        from .system import delete_linux_user
        if delete_linux_user(username, remove_home=not keep_data):
            rprint("[green]✅ Utente Linux eliminato[/green]")
        
        # RIMOSSO v1.0: Rimozione quota (non più necessaria)
        
        rprint(f"[green]✅ Utente {username} eliminato[/green]")
        if keep_data:
            rprint("[yellow]ℹ️ Dati utente mantenuti in backup[/yellow]")
        
        rprint("\n[cyan]💡 Nota: I dati Nextcloud rimangono intatti sul server[/cyan]")
        
    except Exception as e:
        rprint(f"[red]❌ Errore eliminazione: {e}[/red]")
        sys.exit(1)


@user_app.command("mount")
def user_mount(
    username: str = typer.Argument(help="Nome utente"),
    profile: str = typer.Option("full", help="Profilo rclone")
):
    """Mount veloce rclone per utente esistente"""
    rprint(f"[blue]🔗 Mount veloce rclone per: {username}[/blue]")
    
    # Valida profilo
    from .rclone import MOUNT_PROFILES
    if profile not in MOUNT_PROFILES:
        rprint(f"[red]❌ Profilo non valido: {profile}[/red]")
        rprint(f"💡 Profili disponibili: {', '.join(MOUNT_PROFILES.keys())}")
        sys.exit(1)
    
    # Chiedi password
    from rich.prompt import Prompt
    password = Prompt.ask(f"Password per {username}", password=True)
    
    # Test connettività
    rprint("[blue]🔍 Test connettività...[/blue]")
    try:
        from .api import test_webdav_connectivity
        if not test_webdav_connectivity(username, password):
            rprint("[red]❌ Test connettività fallito[/red]")
            sys.exit(1)
    except Exception as e:
        rprint(f"[red]❌ Errore test: {e}[/red]")
        sys.exit(1)
    
    # Mount rclone
    try:
        from .mount import MountManager
        mount_manager = MountManager()
        
        home_path = f"/home/{username}"
        result = mount_manager.mount_user_home(username, password, home_path, profile)
        
        if result["success"]:
            rprint(f"[green]✅ Mount rclone riuscito (profilo: {profile})[/green]")
        else:
            rprint(f"[red]❌ Mount fallito: {result['message']}[/red]")
            sys.exit(1)
            
    except Exception as e:
        rprint(f"[red]❌ Errore mount: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    user_app()
