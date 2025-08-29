"""
CLI Mount - Gestione mount rclone (v1.0 semplificato)
Solo rclone engine con 4 profili
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

from .mount import MountManager, setup_user_with_mount
from .utils import check_sudo_privileges, is_mounted, bytes_to_human, get_directory_size
from .api import test_webdav_connectivity
from .rclone import MOUNT_PROFILES, check_connectivity

mount_app = typer.Typer(help="Gestione mount rclone (engine unico)")
console = Console()


@mount_app.command("profiles") 
def list_profiles():
    """Mostra profili mount rclone disponibili"""
    rprint("[blue]📊 Profili mount rclone[/blue]")
    
    for profile_name, profile_info in MOUNT_PROFILES.items():
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
    profile: str = typer.Option("full", help="Profilo mount (hosting/minimal/writes/full)"),
    auto_service: bool = typer.Option(True, "--service/--no-service", help="Crea servizio systemd"),
    force: bool = typer.Option(False, "--force", help="Forza mount anche se directory non vuota"),
    remount: bool = typer.Option(False, "--remount", help="Forza remount se già montato")
):
    """Monta Nextcloud con rclone"""
    if not mount_point:
        mount_point = f"/home/{username}"
    
    # Valida profilo
    if profile not in MOUNT_PROFILES:
        rprint(f"[red]❌ Profilo non valido: {profile}[/red]")
        rprint(f"💡 Profili disponibili: {', '.join(MOUNT_PROFILES.keys())}")
        sys.exit(1)
    
    rprint(f"[blue]🔗 Mount rclone {username} → {mount_point}[/blue]")
    rprint(f"Profilo: {profile} ({MOUNT_PROFILES[profile]['description']})")
    
    if not check_sudo_privileges():
        rprint("[red]❌ Privilegi sudo richiesti[/red]")
        sys.exit(1)
    
    try:
        mount_manager = MountManager()
        
        # Installa rclone se necessario
        if not mount_manager.is_rclone_available():
            rprint("[yellow]⚠️ rclone non trovato[/yellow]")
            
            install = Confirm.ask("Installare rclone?")
            if install:
                if not mount_manager.install_rclone():
                    rprint("[red]❌ Installazione rclone fallita[/red]")
                    sys.exit(1)
            else:
                sys.exit(1)
        
        # Test connettività prima del mount
        rprint("[blue]🔍 Test connettività WebDAV...[/blue]")
        if not test_webdav_connectivity(username, password):
            rprint("[red]❌ Test connettività WebDAV fallito[/red]")
            rprint("💡 Verifica credenziali e URL Nextcloud")
            sys.exit(1)
        
        # Verifica directory esistente se non force
        if not force and os.path.exists(mount_point) and not remount:
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
        
        # Mount con rclone
        result = mount_manager.mount_user_home(
            username, password, mount_point, profile, remount
        )
        
        if result["success"]:
            rprint(f"[green]✅ Mount riuscito con rclone[/green]")
            rprint(f"[cyan]📊 Profilo: {result['profile']}[/cyan]")
            
            # Mostra info profilo
            profile_info = MOUNT_PROFILES.get(result['profile'], {})
            if profile_info:
                rprint(f"💾 Cache: {profile_info.get('storage', 'N/A')}")
                rprint(f"🔄 Sync: {profile_info.get('sync', 'N/A')}")
            
            # Crea servizio automatico
            if auto_service:
                try:
                    service_name = mount_manager.create_systemd_service(
                        username, password, mount_point, profile
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
    """Smonta directory rclone"""
    rprint(f"[blue]📁 Smontando rclone: {mount_point}[/blue]")
    
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
    """Mostra status di tutti i mount rclone"""
    rprint("[blue]📊 Status mount rclone[/blue]")
    
    mount_manager = MountManager()
    mounts = mount_manager.list_mounts()
    
    if not mounts:
        rprint("[yellow]Nessun mount rclone trovato[/yellow]")
        rprint("💡 Crea un mount con: nextcloud-wrapper mount mount <user> <password>")
        return
    
    table = Table(title="Mount rclone Attivi")
    table.add_column("Remote", style="blue")
    table.add_column("Mount Point", style="white")
    table.add_column("Type", style="cyan")
    
    if detailed:
        table.add_column("Options", style="yellow")
        table.add_column("Status", style="green")
    
    for mount in mounts:
        mount_point = mount.get("mountpoint", "")
        status = "🟢 Attivo" if is_mounted(mount_point) else "🔴 Inattivo"
        
        row = [
            mount.get("remote", "")[:50] + ("..." if len(mount.get("remote", "")) > 50 else ""),
            mount_point,
            mount.get("type", "rclone")
        ]
        
        if detailed:
            row.extend([
                mount.get("options", "")[:30] + ("..." if len(mount.get("options", "")) > 30 else ""),
                status
            ])
        
        table.add_row(*row)
    
    console.print(table)
    
    rprint(f"\n[bold]📊 Totale mount rclone: {len(mounts)}[/bold]")


@mount_app.command("info")
def mount_info(
    mount_point: str = typer.Argument(help="Directory mount da analizzare"),
    check_space: bool = typer.Option(False, "--check-space", help="Calcola spazio occupato")
):
    """Informazioni dettagliate su un mount rclone"""
    rprint(f"[blue]🔍 Informazioni mount rclone: {mount_point}[/blue]")
    
    mount_manager = MountManager()
    status = mount_manager.get_mount_status(mount_point)
    
    if not status["mounted"]:
        rprint(f"[red]❌ {mount_point} non è montato[/red]")
        return
    
    # Tabella informazioni base
    info_table = Table(title=f"Mount rclone Info - {mount_point}")
    info_table.add_column("Proprietà", style="cyan")
    info_table.add_column("Valore", style="white")
    
    info_table.add_row("Mount Point", mount_point)
    info_table.add_row("Engine", "rclone")
    info_table.add_row("Status", status.get("status", "Unknown"))
    
    if status.get("profile"):
        profile = status["profile"]
        info_table.add_row("Profilo", profile)
        
        # Info profilo dettagliate
        if profile in MOUNT_PROFILES:
            profile_info = MOUNT_PROFILES[profile]
            info_table.add_row("Cache", profile_info.get("storage", "N/A"))
            info_table.add_row("Performance", profile_info.get("performance", "N/A"))
            info_table.add_row("Sync", profile_info.get("sync", "N/A"))
    
    console.print(info_table)
    
    # Informazioni spazio
    try:
        if is_mounted(mount_point) and check_space:
            rprint(f"\n[yellow]📊 Calcolo spazio utilizzato...[/yellow]")
            used_space = get_directory_size(mount_point)
            rprint(f"\n[bold]💾 Utilizzo spazio:[/bold]")
            rprint(f"• Spazio utilizzato: {bytes_to_human(used_space)}")
            rprint(f"• Gestione cache: automatica via rclone")
    except Exception as e:
        rprint(f"[yellow]⚠️ Errore informazioni spazio: {e}[/yellow]")


@mount_app.command("test")
def test_mount(
    username: str = typer.Argument(help="Username per test"),
    password: str = typer.Argument(help="Password per test"),
    profile: str = typer.Option("minimal", help="Profilo per test")
):
    """Test mount rclone temporaneo"""
    rprint(f"[blue]🧪 Test mount rclone per {username}[/blue]")
    rprint(f"Profilo test: {profile}")
    
    if not check_sudo_privileges():
        rprint("[red]❌ Privilegi sudo richiesti[/red]")
        sys.exit(1)
    
    # Verifica profilo
    if profile not in MOUNT_PROFILES:
        rprint(f"[red]❌ Profilo non valido: {profile}[/red]")
        sys.exit(1)
    
    test_dir = f"/tmp/ncwrap-test-{username}-{int(time.time())}"
    
    try:
        mount_manager = MountManager()
        
        # Installa rclone se necessario
        if not mount_manager.is_rclone_available():
            rprint("[red]❌ rclone non disponibile[/red]")
            sys.exit(1)
        
        # Test connettività
        rprint("[blue]🔍 Test connettività...[/blue]")
        if not test_webdav_connectivity(username, password):
            rprint("[red]❌ Test connettività fallito[/red]")
            sys.exit(1)
        
        # Mount temporaneo
        rprint(f"[blue]🔗 Mount temporaneo in {test_dir}...[/blue]")
        result = mount_manager.mount_user_home(
            username, password, test_dir, profile
        )
        
        if not result["success"]:
            rprint(f"[red]❌ Mount fallito: {result['message']}[/red]")
            sys.exit(1)
        
        rprint("[green]✅ Mount test riuscito[/green]")
        
        # Test I/O base
        try:
            rprint("[blue]📝 Test I/O...[/blue]")
            
            test_file = f"{test_dir}/test-io.txt"
            test_content = f"Test rclone {time.time()}"
            
            # Write test
            with open(test_file, 'w') as f:
                f.write(test_content)
            
            # Read test
            with open(test_file, 'r') as f:
                read_content = f.read()
            
            if read_content == test_content:
                rprint("[green]✅ Test I/O riuscito[/green]")
            else:
                rprint("[red]❌ Test I/O fallito (contenuto diverso)[/red]")
            
            # List test
            files = os.listdir(test_dir)
            rprint(f"[cyan]📁 File in mount: {len(files)}[/cyan]")
            
            # Cleanup test file
            os.remove(test_file)
            
        except Exception as e:
            rprint(f"[yellow]⚠️ Test I/O parzialmente fallito: {e}[/yellow]")
        
        # Informazioni mount
        status = mount_manager.get_mount_status(test_dir)
        rprint(f"[cyan]📊 Status: {status.get('status', 'N/A')}[/cyan]")
        rprint(f"[cyan]📋 Profilo: {status.get('profile', 'N/A')}[/cyan]")
        
        rprint("[green]🎉 Test completato con successo![/green]")
        
    except Exception as e:
        rprint(f"[red]❌ Errore test: {e}[/red]")
    finally:
        # Cleanup mount temporaneo
        try:
            rprint("[blue]🧹 Cleanup mount test...[/blue]")
            mount_manager.unmount_user_home(test_dir)
            if os.path.exists(test_dir):
                os.rmdir(test_dir)
            rprint("[green]✅ Cleanup completato[/green]")
        except Exception as e:
            rprint(f"[yellow]⚠️ Avviso cleanup: {e}[/yellow]")


@mount_app.command("setup")
def setup_complete(
    username: str = typer.Argument(help="Nome utente"),
    password: str = typer.Argument(help="Password"),
    profile: str = typer.Option("full", help="Profilo mount"),
    no_service: bool = typer.Option(False, help="Non creare servizio systemd"),
    remount: bool = typer.Option(False, help="Forza remount se esistente")
):
    """Setup completo utente con rclone (v1.0)"""
    # Valida profilo
    if profile not in MOUNT_PROFILES:
        rprint(f"[red]❌ Profilo non valido: {profile}[/red]")
        rprint(f"💡 Profili disponibili: {', '.join(MOUNT_PROFILES.keys())}")
        sys.exit(1)
    
    rprint(f"[blue]🚀 Setup completo per {username}[/blue]")
    rprint(f"Profilo: {profile} ({MOUNT_PROFILES[profile]['description']})")
    
    if not check_sudo_privileges():
        rprint("[red]❌ Privilegi sudo richiesti[/red]")
        sys.exit(1)
    
    try:
        # Test connettività prima di iniziare
        rprint("[blue]🔍 Test connettività WebDAV...[/blue]")
        if not test_webdav_connectivity(username, password):
            rprint("[red]❌ Test connettività WebDAV fallito[/red]")
            rprint("💡 Verifica credenziali e configurazione NC_BASE_URL")
            sys.exit(1)
        
        # Setup completo con funzione semplificata
        success = setup_user_with_mount(
            username=username,
            password=password, 
            profile=profile,
            remount=remount
        )
        
        if success:
            rprint(f"[green]🎉 Setup completo riuscito per {username}![/green]")
            
            # Mostra riepilogo
            rprint(f"\n[bold blue]📋 Riepilogo configurazione:[/bold blue]")
            rprint(f"• Utente Nextcloud: {username}")
            rprint(f"• Utente Linux: {username}")
            rprint(f"• Home directory: /home/{username} → rclone mount")
            rprint(f"• Profilo rclone: {profile}")
            rprint(f"• Cache: {MOUNT_PROFILES[profile].get('storage', 'N/A')}")
            rprint(f"• Servizio systemd: {'✅' if not no_service else '❌'}")
            
            rprint(f"\n[bold green]💡 Mount automatico attivo al boot![/bold green]")
            
        else:
            rprint("[red]❌ Setup fallito[/red]")
            sys.exit(1)
            
    except Exception as e:
        rprint(f"[red]❌ Errore setup: {e}[/red]")
        sys.exit(1)


@mount_app.command("install")
def install_rclone(
    configure: bool = typer.Option(True, "--configure/--no-configure", help="Configura dopo installazione")
):
    """Installa rclone"""
    rprint("[blue]📦 Installazione rclone[/blue]")
    
    if not check_sudo_privileges():
        rprint("[red]❌ Privilegi sudo richiesti[/red]")
        sys.exit(1)
    
    try:
        mount_manager = MountManager()
        
        # Verifica se già installato
        if mount_manager.is_rclone_available():
            rprint("[green]✅ rclone già installato[/green]")
            
            if configure:
                rprint("[blue]⚙️ Configurazione rclone...[/blue]")
                if mount_manager.configure_rclone():
                    rprint("[green]✅ rclone configurato[/green]")
                else:
                    rprint("[red]❌ Errore configurazione rclone[/red]")
            return
        
        # Installazione
        if mount_manager.install_rclone():
            rprint("[green]✅ rclone installato con successo[/green]")
            
            # Configurazione automatica
            if configure:
                rprint("[blue]⚙️ Configurazione rclone...[/blue]")
                if mount_manager.configure_rclone():
                    rprint("[green]✅ rclone configurato[/green]")
                else:
                    rprint("[yellow]⚠️ Avviso configurazione rclone[/yellow]")
        else:
            rprint("[red]❌ Installazione rclone fallita[/red]")
            sys.exit(1)
            
    except Exception as e:
        rprint(f"[red]❌ Errore: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    mount_app()
