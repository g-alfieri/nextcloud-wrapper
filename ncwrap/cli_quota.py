"""
CLI Quota - Gestione quote filesystem
"""
import typer
import sys
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from .quota import (
    QuotaManager, 
    setup_quota_for_user,
    get_quota_info,
    list_all_user_quotas
)
from .utils import check_sudo_privileges, parse_size_to_bytes, bytes_to_human

quota_app = typer.Typer(help="Gestione quote filesystem")
console = Console()


@quota_app.command("set")
def set_quota(
    username: str = typer.Argument(help="Nome utente"),
    nextcloud_quota: str = typer.Argument(help="Quota Nextcloud (es. 100G)"),
    fs_percentage: float = typer.Option(0.02, "--fs-percentage", help="Percentuale filesystem")
):
    """Imposta quota filesystem come percentuale della quota Nextcloud"""
    rprint(f"[blue]💾 Impostando quota per {username}[/blue]")
    rprint(f"[cyan]NC: {nextcloud_quota} → FS: {fs_percentage:.1%}[/cyan]")
    
    if not check_sudo_privileges():
        rprint("[red]❌ Privilegi sudo richiesti[/red]")
        sys.exit(1)
    
    try:
        if setup_quota_for_user(username, nextcloud_quota, fs_percentage):
            # Calcola quota risultante
            nc_bytes = parse_size_to_bytes(nextcloud_quota)
            fs_bytes = int(nc_bytes * fs_percentage)
            fs_quota = bytes_to_human(fs_bytes)
            
            rprint(f"[green]✅ Quota impostata: NC {nextcloud_quota} → FS {fs_quota}[/green]")
        else:
            rprint("[red]❌ Errore impostazione quota[/red]")
            
    except Exception as e:
        rprint(f"[red]❌ Errore: {e}[/red]")


@quota_app.command("show")
def show_quota(
    username: Optional[str] = typer.Argument(None, help="Nome utente (vuoto = tutti)")
):
    """Mostra quota utente o tutti gli utenti"""
    if username:
        rprint(f"[blue]💾 Quota per {username}[/blue]")
        
        quota_info = get_quota_info(username)
        if quota_info:
            table = Table(title=f"Quota {username}")
            table.add_column("Campo", style="cyan")
            table.add_column("Valore", style="white")
            
            for key, value in quota_info.items():
                display_key = key.replace("_", " ").title()
                table.add_row(display_key, str(value or "N/A"))
                
            console.print(table)
        else:
            rprint("[yellow]Nessuna quota configurata[/yellow]")
    else:
        rprint("[blue]💾 Quote di tutti gli utenti[/blue]")
        
        quotas = list_all_user_quotas()
        if quotas:
            table = Table(title="Quote Utenti")
            table.add_column("Utente", style="cyan")
            table.add_column("Usato", style="white")
            table.add_column("Limite", style="yellow")
            table.add_column("Filesystem", style="blue")
            
            for user, info in quotas.items():
                table.add_row(
                    user,
                    info.get("used", "N/A"),
                    info.get("limit", "N/A"),
                    info.get("filesystem", "N/A")
                )
                
            console.print(table)
        else:
            rprint("[yellow]Nessuna quota configurata[/yellow]")


@quota_app.command("remove")
def remove_quota(
    username: str = typer.Argument(help="Nome utente")
):
    """Rimuove quota per utente"""
    rprint(f"[blue]🗑️ Rimuovendo quota per {username}[/blue]")
    
    if not check_sudo_privileges():
        rprint("[red]❌ Privilegi sudo richiesti[/red]")
        sys.exit(1)
    
    try:
        quota_manager = QuotaManager()
        if quota_manager.remove_quota(username):
            rprint("[green]✅ Quota rimossa[/green]")
        else:
            rprint("[red]❌ Errore rimozione quota[/red]")
            
    except Exception as e:
        rprint(f"[red]❌ Errore: {e}[/red]")


@quota_app.command("init")
def init_quota_system():
    """Inizializza sistema quote"""
    rprint("[blue]🔧 Inizializzazione sistema quote[/blue]")
    
    if not check_sudo_privileges():
        rprint("[red]❌ Privilegi sudo richiesti[/red]")
        sys.exit(1)
    
    try:
        quota_manager = QuotaManager()
        
        if quota_manager.setup_quota_system():
            rprint("[green]✅ Sistema quote inizializzato[/green]")
            
            # Mostra info filesystem
            fs_info = quota_manager.get_filesystem_usage()
            if fs_info:
                rprint(f"[cyan]Filesystem: {fs_info['filesystem']}[/cyan]")
                rprint(f"[cyan]Totale: {fs_info['total']}, Usato: {fs_info['used']}, Disponibile: {fs_info['available']}[/cyan]")
        else:
            rprint("[red]❌ Errore inizializzazione sistema quote[/red]")
            
    except Exception as e:
        rprint(f"[red]❌ Errore: {e}[/red]")


@quota_app.command("status")
def quota_status():
    """Mostra status sistema quote"""
    rprint("[blue]📊 Status sistema quote[/blue]")
    
    try:
        quota_manager = QuotaManager()
        
        # Info filesystem
        fs_info = quota_manager.get_filesystem_usage()
        if fs_info:
            table = Table(title="Filesystem Info")
            table.add_column("Campo", style="cyan")
            table.add_column("Valore", style="white")
            
            for key, value in fs_info.items():
                display_key = key.replace("_", " ").title()
                table.add_row(display_key, str(value))
            
            console.print(table)
        
        # Tipo filesystem
        rprint(f"[bold]Tipo filesystem:[/bold] {quota_manager.fs_type}")
        
        # Numero quote attive
        quotas = list_all_user_quotas()
        rprint(f"[bold]Quote attive:[/bold] {len(quotas)}")
        
        if quotas:
            # Calcola totale spazio utilizzato
            total_used = 0
            for user, info in quotas.items():
                used_str = info.get("used", "0B")
                if used_str and used_str != "N/A":
                    try:
                        if used_str.endswith('K'):
                            total_used += int(float(used_str[:-1]) * 1024)
                        elif used_str.endswith('M'):
                            total_used += int(float(used_str[:-1]) * 1024 * 1024)
                        elif used_str.endswith('G'):
                            total_used += int(float(used_str[:-1]) * 1024 * 1024 * 1024)
                    except:
                        pass
            
            if total_used > 0:
                rprint(f"[bold]Spazio quote utilizzato:[/bold] {bytes_to_human(total_used)}")
        
    except Exception as e:
        rprint(f"[red]❌ Errore: {e}[/red]")


@quota_app.command("check")
def check_quota_usage():
    """Verifica uso quote per tutti gli utenti"""
    rprint("[blue]🔍 Verifica uso quote[/blue]")
    
    quotas = list_all_user_quotas()
    if not quotas:
        rprint("[yellow]Nessuna quota configurata[/yellow]")
        return
    
    # Analizza uso quote
    over_quota = []
    warnings = []
    
    for user, info in quotas.items():
        used_str = info.get("used", "0B")
        limit_str = info.get("limit", "")
        
        if used_str == "N/A" or limit_str == "N/A" or not limit_str:
            continue
        
        try:
            # Parsing semplificato
            used_val = float(used_str.replace("B", "").replace("K", "").replace("M", "").replace("G", ""))
            limit_val = float(limit_str.replace("B", "").replace("K", "").replace("M", "").replace("G", ""))
            
            # Normalizza unità (assumiamo stessa unità)
            usage_percent = (used_val / limit_val) * 100
            
            if usage_percent > 100:
                over_quota.append((user, usage_percent))
            elif usage_percent > 80:
                warnings.append((user, usage_percent))
                
        except:
            continue
    
    # Report risultati
    if over_quota:
        rprint("[red]❌ Utenti oltre quota:[/red]")
        for user, percent in over_quota:
            rprint(f"  • {user}: {percent:.1f}%")
    
    if warnings:
        rprint("[yellow]⚠️ Utenti vicini al limite (>80%):[/yellow]")
        for user, percent in warnings:
            rprint(f"  • {user}: {percent:.1f}%")
    
    if not over_quota and not warnings:
        rprint("[green]✅ Tutte le quote sotto controllo[/green]")
