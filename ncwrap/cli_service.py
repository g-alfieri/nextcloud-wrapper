"""
CLI Service - Gestione servizi systemd
"""
import typer
import sys
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from .systemd import SystemdManager, list_all_webdav_services
from .utils import check_sudo_privileges

service_app = typer.Typer(help="Gestione servizi systemd")
console = Console()


@service_app.command("list")
def list_services():
    """Lista tutti i servizi nextcloud-wrapper"""
    rprint("[blue]⚙️ Servizi nextcloud-wrapper[/blue]")
    
    all_services = list_all_webdav_services()
    
    # Servizi system
    system_services = all_services.get("system", [])
    if system_services:
        table = Table(title="Servizi System")
        table.add_column("Nome", style="cyan")
        table.add_column("Load", style="white")
        table.add_column("Active", style="green")
        table.add_column("Sub", style="yellow")
        table.add_column("Descrizione", style="blue")
        
        for service in system_services:
            table.add_row(
                service["name"],
                service["load"],
                service["active"],
                service["sub"],
                service["description"]
            )
        console.print(table)
    
    # Servizi user
    user_services = all_services.get("user", [])
    if user_services:
        table = Table(title="Servizi User")
        table.add_column("Nome", style="cyan")
        table.add_column("Load", style="white")
        table.add_column("Active", style="green")
        table.add_column("Sub", style="yellow")
        table.add_column("Descrizione", style="blue")
        
        for service in user_services:
            table.add_row(
                service["name"],
                service["load"],
                service["active"],
                service["sub"],
                service["description"]
            )
        console.print(table)
    
    if not system_services and not user_services:
        rprint("[yellow]Nessun servizio nextcloud-wrapper trovato[/yellow]")


@service_app.command("status")
def service_status(
    service_name: str = typer.Argument(help="Nome servizio"),
    user: bool = typer.Option(False, "--user", help="Servizio utente")
):
    """Mostra status dettagliato di un servizio"""
    rprint(f"[blue]📊 Status servizio: {service_name}[/blue]")
    
    try:
        systemd_manager = SystemdManager()
        status = systemd_manager.get_service_status(service_name, user)
        
        if status:
            table = Table(title=f"Status {service_name}")
            table.add_column("Campo", style="cyan")
            table.add_column("Valore", style="white")
            
            for key, value in status.items():
                display_key = key.replace("_", " ").title()
                table.add_row(display_key, str(value or "N/A"))
            
            console.print(table)
        else:
            rprint(f"[red]❌ Servizio {service_name} non trovato[/red]")
            
    except Exception as e:
        rprint(f"[red]❌ Errore: {e}[/red]")


@service_app.command("enable")
def enable_service(
    service_name: str = typer.Argument(help="Nome servizio"),
    user: bool = typer.Option(False, "--user", help="Servizio utente")
):
    """Abilita e avvia un servizio"""
    rprint(f"[blue]▶️ Abilitando servizio: {service_name}[/blue]")
    
    if not user and not check_sudo_privileges():
        rprint("[red]❌ Privilegi sudo richiesti per servizi system[/red]")
        sys.exit(1)
    
    try:
        systemd_manager = SystemdManager()
        if systemd_manager.enable_service(service_name, user):
            rprint(f"[green]✅ Servizio {service_name} abilitato e avviato[/green]")
        else:
            rprint(f"[red]❌ Errore abilitazione servizio {service_name}[/red]")
            
    except Exception as e:
        rprint(f"[red]❌ Errore: {e}[/red]")


@service_app.command("disable")
def disable_service(
    service_name: str = typer.Argument(help="Nome servizio"),
    user: bool = typer.Option(False, "--user", help="Servizio utente")
):
    """Disabilita e ferma un servizio"""
    rprint(f"[blue]⏹️ Disabilitando servizio: {service_name}[/blue]")
    
    if not user and not check_sudo_privileges():
        rprint("[red]❌ Privilegi sudo richiesti per servizi system[/red]")
        sys.exit(1)
    
    try:
        systemd_manager = SystemdManager()
        if systemd_manager.disable_service(service_name, user):
            rprint(f"[green]✅ Servizio {service_name} disabilitato e fermato[/green]")
        else:
            rprint(f"[red]❌ Errore disabilitazione servizio {service_name}[/red]")
            
    except Exception as e:
        rprint(f"[red]❌ Errore: {e}[/red]")


@service_app.command("start")
def start_service(
    service_name: str = typer.Argument(help="Nome servizio"),
    user: bool = typer.Option(False, "--user", help="Servizio utente")
):
    """Avvia un servizio"""
    rprint(f"[blue]▶️ Avviando servizio: {service_name}[/blue]")
    
    if not user and not check_sudo_privileges():
        rprint("[red]❌ Privilegi sudo richiesti per servizi system[/red]")
        sys.exit(1)
    
    try:
        systemd_manager = SystemdManager()
        if systemd_manager.start_service(service_name, user):
            rprint(f"[green]✅ Servizio {service_name} avviato[/green]")
        else:
            rprint(f"[red]❌ Errore avvio servizio {service_name}[/red]")
            
    except Exception as e:
        rprint(f"[red]❌ Errore: {e}[/red]")


@service_app.command("stop")
def stop_service(
    service_name: str = typer.Argument(help="Nome servizio"),
    user: bool = typer.Option(False, "--user", help="Servizio utente")
):
    """Ferma un servizio"""
    rprint(f"[blue]⏹️ Fermando servizio: {service_name}[/blue]")
    
    if not user and not check_sudo_privileges():
        rprint("[red]❌ Privilegi sudo richiesti per servizi system[/red]")
        sys.exit(1)
    
    try:
        systemd_manager = SystemdManager()
        if systemd_manager.stop_service(service_name, user):
            rprint(f"[green]✅ Servizio {service_name} fermato[/green]")
        else:
            rprint(f"[red]❌ Errore stop servizio {service_name}[/red]")
            
    except Exception as e:
        rprint(f"[red]❌ Errore: {e}[/red]")


@service_app.command("restart")
def restart_service(
    service_name: str = typer.Argument(help="Nome servizio"),
    user: bool = typer.Option(False, "--user", help="Servizio utente")
):
    """Riavvia un servizio"""
    rprint(f"[blue]🔄 Riavviando servizio: {service_name}[/blue]")
    
    if not user and not check_sudo_privileges():
        rprint("[red]❌ Privilegi sudo richiesti per servizi system[/red]")
        sys.exit(1)
    
    try:
        systemd_manager = SystemdManager()
        
        # Stop
        if systemd_manager.stop_service(service_name, user):
            rprint(f"[yellow]⏹️ Servizio {service_name} fermato[/yellow]")
        
        # Start
        if systemd_manager.start_service(service_name, user):
            rprint(f"[green]✅ Servizio {service_name} riavviato[/green]")
        else:
            rprint(f"[red]❌ Errore riavvio servizio {service_name}[/red]")
            
    except Exception as e:
        rprint(f"[red]❌ Errore: {e}[/red]")


@service_app.command("remove")
def remove_service(
    service_name: str = typer.Argument(help="Nome servizio"),
    user: bool = typer.Option(False, "--user", help="Servizio utente"),
    confirm: bool = typer.Option(False, "--confirm", help="Conferma rimozione")
):
    """Rimuove completamente un servizio"""
    if not confirm:
        rprint(f"[red]⚠️ ATTENZIONE: Stai per rimuovere il servizio {service_name}[/red]")
        rprint("💡 Aggiungi --confirm per procedere")
        sys.exit(1)
    
    rprint(f"[blue]🗑️ Rimuovendo servizio: {service_name}[/blue]")
    
    if not user and not check_sudo_privileges():
        rprint("[red]❌ Privilegi sudo richiesti per servizi system[/red]")
        sys.exit(1)
    
    try:
        systemd_manager = SystemdManager()
        if systemd_manager.remove_service(service_name, user):
            rprint(f"[green]✅ Servizio {service_name} rimosso completamente[/green]")
        else:
            rprint(f"[red]❌ Errore rimozione servizio {service_name}[/red]")
            
    except Exception as e:
        rprint(f"[red]❌ Errore: {e}[/red]")


@service_app.command("logs")
def show_service_logs(
    service_name: str = typer.Argument(help="Nome servizio"),
    user: bool = typer.Option(False, "--user", help="Servizio utente"),
    lines: int = typer.Option(50, "--lines", help="Numero righe da mostrare"),
    follow: bool = typer.Option(False, "--follow", help="Segui log in tempo reale")
):
    """Mostra log di un servizio"""
    rprint(f"[blue]📋 Log servizio: {service_name}[/blue]")
    
    try:
        from .utils import run
        
        cmd = ["journalctl"]
        if user:
            cmd.append("--user")
        
        cmd.extend(["-u", f"{service_name}.service"])
        cmd.extend(["-n", str(lines)])
        cmd.append("--no-pager")
        
        if follow:
            cmd.append("-f")
        
        output = run(cmd, check=False)
        
        if output:
            rprint(output)
        else:
            rprint("[yellow]Nessun log trovato[/yellow]")
            
    except Exception as e:
        rprint(f"[red]❌ Errore lettura log: {e}[/red]")


@service_app.command("create")
def create_webdav_service(
    username: str = typer.Argument(help="Nome utente"),
    password: str = typer.Argument(help="Password"),
    mount_point: str = typer.Option(None, help="Directory mount (default: /home/username)"),
    enable: bool = typer.Option(True, "--enable/--no-enable", help="Abilita automaticamente")
):
    """Crea servizio WebDAV mount per utente"""
    if not mount_point:
        mount_point = f"/home/{username}"
    
    rprint(f"[blue]⚙️ Creando servizio WebDAV per {username}[/blue]")
    
    if not check_sudo_privileges():
        rprint("[red]❌ Privilegi sudo richiesti[/red]")
        sys.exit(1)
    
    try:
        systemd_manager = SystemdManager()
        service_name = systemd_manager.create_webdav_mount_service(username, password, mount_point)
        
        rprint(f"[green]✅ Servizio creato: {service_name}[/green]")
        
        if enable:
            if systemd_manager.enable_service(service_name):
                rprint(f"[green]✅ Servizio abilitato e avviato[/green]")
            else:
                rprint(f"[yellow]⚠️ Servizio creato ma non abilitato[/yellow]")
                
    except Exception as e:
        rprint(f"[red]❌ Errore creazione servizio: {e}[/red]")





@service_app.command("reload")
def reload_systemd():
    """Ricarica configurazione systemd"""
    rprint("[blue]🔄 Ricaricando configurazione systemd[/blue]")
    
    if not check_sudo_privileges():
        rprint("[red]❌ Privilegi sudo richiesti[/red]")
        sys.exit(1)
    
    try:
        from .utils import run
        run(["systemctl", "daemon-reload"])
        rprint("[green]✅ Configurazione systemd ricaricata[/green]")
        
    except Exception as e:
        rprint(f"[red]❌ Errore reload: {e}[/red]")
