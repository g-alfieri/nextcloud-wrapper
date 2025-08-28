"""
CLI Mount - Gestione mount unificato (rclone + davfs2)
"""
import typer
import sys
import os
import time
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich import print as rprint
from rich.prompt import Prompt, Confirm

from .mount import MountManager, MountEngine, setup_user_with_mount
from .utils import check_sudo_privileges, is_mounted, bytes_to_human, get_directory_size
from .api import test_webdav_connectivity

mount_app = typer.Typer(help="Gestione mount unificato (rclone/davfs2)")
console = Console()


@mount_app.command("engines")
def list_engines():
    """Mostra engine di mount disponibili"""
    rprint("[blue]🔧 Engine di mount disponibili[/blue]")
    
    mount_manager = MountManager()
    available = mount_manager.detect_available_engines()
    recommended = mount_manager.get_recommended_engine()
    
    table = Table(title="Engine Mount Nextcloud")
    table.add_column("Engine", style="cyan")
    table.add_column("Disponibile", style="white")
    table.add_column("Status", style="green")
    table.add_column("Caratteristiche", style="yellow")
    
    table.add_row(
        "rclone",
        "✅ Sì" if available[MountEngine.RCLONE] else "❌ No",
        "🚀 Consigliato" if recommended == MountEngine.RCLONE else "📋 Disponibile",
        "Performance superiori, profili cache, VFS avanzato"
    )
    
    table.add_row(
        "davfs2",
        "✅ Sì" if available[MountEngine.DAVFS2] else "❌ No", 
        "🛡️ Fallback" if recommended == MountEngine.RCLONE else "📋 Disponibile",
        "Compatibilità massima, cache disco, supporto lock"
    )
    
    console.print(table)
    
    rprint(f"\n[bold green]🎯 Engine raccomandato: {recommended.value}[/bold green]")
    
    if not available[recommended]:
        rprint(f"[yellow]⚠️ Engine raccomandato non installato[/yellow]")
        rprint(f"💡 Installa con: nextcloud-wrapper mount install {recommended.value}")


@mount_app.command("profiles") 
def list_profiles(
    engine: str = typer.Option("rclone", help="Engine per cui mostrare i profili")
):
    """Mostra profili mount disponibili"""
    mount_engine = MountEngine(engine.lower())
    rprint(f"[blue]📊 Profili mount per {engine}[/blue]")
    
    mount_manager = MountManager()
    profiles = mount_manager.get_mount_profiles(mount_engine)
    
    if not profiles:
        rprint(f"[yellow]Nessun profilo disponibile per {engine}[/yellow]")
        return
    
    for profile_name, profile_info in profiles.items():
        rprint(f"\n[bold cyan]📋 Profilo: {profile_name}[/bold cyan]")
        rprint(f"📝 {profile_info['description']}")
        rprint(f"🎯 Uso: {profile_info['use_case']}")
        rprint(f"💾 Storage: {profile_info['storage']}")
        rprint(f"⚡ Performance: {profile_info['performance']}")
        rprint(f"🔄 Sync: {profile_info['sync']}")


@mount_app.command("mount")
def mount_user(
    username: str = typer.Argument(help="Nome utente"),
    password: str = typer.Argument(help="Password"),
    mount_point: str = typer.Option(None, help="Directory mount (default: /home/username)"),
    engine: str = typer.Option("rclone", help="Engine mount (rclone/davfs2)"),
    profile: str = typer.Option("writes", help="Profilo mount (solo rclone)"),
    auto_service: bool = typer.Option(True, "--service/--no-service", help="Crea servizio systemd"),
    force: bool = typer.Option(False, "--force", help="Forza mount anche se directory non vuota")
):
    """Monta Nextcloud in directory utente"""
    mount_engine = MountEngine(engine.lower())
    
    if not mount_point:
        mount_point = f"/home/{username}"
    
    rprint(f"[blue]🔗 Mount {username} → {mount_point}[/blue]")
    rprint(f"Engine: {engine} | Profilo: {profile if mount_engine == MountEngine.RCLONE else 'default'}")
    
    if not check_sudo_privileges():
        rprint("[red]❌ Privilegi sudo richiesti[/red]")
        sys.exit(1)
    
    try:
        mount_manager = MountManager()
        
        # Verifica engine disponibile
        available = mount_manager.detect_available_engines()
        if not available[mount_engine]:
            rprint(f"[red]❌ Engine {engine} non disponibile[/red]")
            
            install = Confirm.ask(f"Installare {engine}?")
            if install:
                if not mount_manager.install_engine(mount_engine):
                    rprint(f"[red]❌ Installazione {engine} fallita[/red]")
                    sys.exit(1)
            else:
                sys.exit(1)
        
        # Test connettività prima del mount
        if not test_webdav_connectivity(username, password):
            rprint("[red]❌ Test connettività WebDAV fallito[/red]")
            rprint("💡 Verifica credenziali e URL Nextcloud")
            sys.exit(1)
        
        # Verifica directory esistente se non force
        if not force and os.path.exists(mount_point):
            try:
                contents = os.listdir(mount_point)
                if contents and not is_mounted(mount_point):
                    rprint(f"[yellow]⚠️ Directory {mount_point} non vuota[/yellow]")
                    rprint(f"Contenuti: {', '.join(contents[:5])}{'...' if len(contents) > 5 else ''}")
                    
                    if not Confirm.ask("Continuare? (verrà fatto backup)"):
                        rprint("[cyan]Operazione annullata[/cyan]")
                        return
            except PermissionError:
                pass
        
        # Mount
        result = mount_manager.mount_user_home(
            username, password, mount_point, mount_engine, 
            profile if mount_engine == MountEngine.RCLONE else None
        )
        
        if result["success"]:
            engine_used = result["engine_used"]
            rprint(f"[green]✅ Mount riuscito con {engine_used.value}[/green]")
            
            if result["fallback_used"]:
                rprint(f"[yellow]⚠️ Usato fallback {engine_used.value}[/yellow]")
            
            if result.get("profile"):
                rprint(f"[cyan]📊 Profilo: {result['profile']}[/cyan]")
            
            # Crea servizio automatico
            if auto_service:
                try:
                    service_name = mount_manager.create_systemd_service(
                        username, password, mount_point, engine_used, result.get("profile")
                    )
                    
                    # Abilita servizio
                    from .utils import run
                    run(["systemctl", "enable", "--now", f"{service_name}.service"], check=False)
                    rprint(f"[green]✅ Servizio automatico: {service_name}[/green]")
                except Exception as e:
                    rprint(f"[yellow]⚠️ Avviso servizio: {e}[/yellow]")
        else:
            rprint(f"[red]❌ {result['message']}[/red]")
            sys.exit(1)
            
    except Exception as e:
        rprint(f"[red]❌ Errore: {e}[/red]")
        sys.exit(1)


@mount_app.command("unmount")
def unmount_user(
    mount_point: str = typer.Argument(help="Directory da smontare")
):
    """Smonta directory utente"""
    rprint(f"[blue]📁 Smontando: {mount_point}[/blue]")
    
    if not check_sudo_privileges():
        rprint("[red]❌ Privilegi sudo richiesti[/red]")
        sys.exit(1)
    
    try:
        mount_manager = MountManager()
        
        if mount_manager.unmount_user_home(mount_point):
            rprint("[green]✅ Smontato con successo[/green]")
        else:
            rprint("[red]❌ Errore unmount[/red]")
            sys.exit(1)
            
    except Exception as e:
        rprint(f"[red]❌ Errore: {e}[/red]")
        sys.exit(1)


@mount_app.command("status")
def mount_status(
    detailed: bool = typer.Option(False, "--detailed", help="Mostra informazioni dettagliate")
):
    """Mostra status di tutti i mount"""
    rprint("[blue]📊 Status mount Nextcloud[/blue]")
    
    mount_manager = MountManager()
    mounts = mount_manager.list_mounts()
    
    if not mounts:
        rprint("[yellow]Nessun mount attivo trovato[/yellow]")
        return
    
    table = Table(title="Mount Attivi")
    table.add_column("Engine", style="cyan")
    table.add_column("Remote/URL", style="blue")
    table.add_column("Mount Point", style="white")
    table.add_column("Type", style="green")
    
    if detailed:
        table.add_column("Options", style="yellow")
        table.add_column("Status", style="green")
    
    for mount in mounts:
        mount_point = mount.get("mountpoint", "")
        status = "🟢 Attivo" if is_mounted(mount_point) else "🔴 Inattivo"
        
        row = [
            mount["engine"].value,
            mount.get("remote", "")[:50] + ("..." if len(mount.get("remote", "")) > 50 else ""),
            mount_point,
            mount.get("type", "")
        ]
        
        if detailed:
            row.extend([
                mount.get("options", "")[:30] + ("..." if len(mount.get("options", "")) > 30 else ""),
                status
            ])
        
        table.add_row(*row)
    
    console.print(table)
    
    # Statistiche
    rclone_count = sum(1 for m in mounts if m["engine"] == MountEngine.RCLONE)
    davfs2_count = sum(1 for m in mounts if m["engine"] == MountEngine.DAVFS2)
    
    rprint(f"\n[bold]📊 Riepilogo:[/bold]")
    rprint(f"• Mount rclone: {rclone_count}")
    rprint(f"• Mount davfs2: {davfs2_count}")
    rprint(f"• Totale: {len(mounts)}")


@mount_app.command("install")
def install_engine(
    engine: str = typer.Argument(help="Engine da installare (rclone/davfs2)"),
    configure: bool = typer.Option(True, "--configure/--no-configure", help="Configura dopo installazione")
):
    """Installa engine di mount"""
    mount_engine = MountEngine(engine.lower())
    rprint(f"[blue]📦 Installazione {engine}[/blue]")
    
    if not check_sudo_privileges():
        rprint("[red]❌ Privilegi sudo richiesti[/red]")
        sys.exit(1)
    
    try:
        mount_manager = MountManager()
        
        # Verifica se già installato
        available = mount_manager.detect_available_engines()
        if available[mount_engine]:
            rprint(f"[green]✅ {engine} già installato[/green]")
            
            if configure:
                rprint(f"[blue]⚙️ Configurazione {engine}...[/blue]")
                if mount_manager.configure_engine(mount_engine):
                    rprint(f"[green]✅ {engine} configurato[/green]")
                else:
                    rprint(f"[red]❌ Errore configurazione {engine}[/red]")
            return
        
        # Installazione
        if mount_manager.install_engine(mount_engine):
            rprint(f"[green]✅ {engine} installato con successo[/green]")
            
            # Configurazione automatica
            if configure:
                rprint(f"[blue]⚙️ Configurazione {engine}...[/blue]")
                if mount_manager.configure_engine(mount_engine):
                    rprint(f"[green]✅ {engine} configurato[/green]")
                else:
                    rprint(f"[yellow]⚠️ Avviso configurazione {engine}[/yellow]")
        else:
            rprint(f"[red]❌ Installazione {engine} fallita[/red]")
            sys.exit(1)
            
    except ValueError:
        rprint(f"[red]❌ Engine non supportato: {engine}[/red]")
        rprint("💡 Engine supportati: rclone, davfs2")
        sys.exit(1)
    except Exception as e:
        rprint(f"[red]❌ Errore: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    mount_app()
