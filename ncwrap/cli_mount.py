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


@mount_app.command("info")
def mount_info(
    mount_point: str = typer.Argument(help="Directory mount da analizzare"),
    check_space: bool = typer.Option(False, "--check-space", help="Calcola spazio occupato")

):
    """Informazioni dettagliate su un mount specifico"""
    rprint(f"[blue]🔍 Informazioni mount: {mount_point}[/blue]")
    
    mount_manager = MountManager()
    status = mount_manager.get_mount_status(mount_point)
    
    if not status["mounted"]:
        rprint(f"[red]❌ {mount_point} non è montato[/red]")
        return
    
    # Tabella informazioni base
    info_table = Table(title=f"Mount Info - {mount_point}")
    info_table.add_column("Proprietà", style="cyan")
    info_table.add_column("Valore", style="white")
    
    info_table.add_row("Mount Point", mount_point)
    info_table.add_row("Engine", status.get("engine", "unknown").value if hasattr(status.get("engine"), "value") else str(status.get("engine")))
    info_table.add_row("Status", status.get("status", "Unknown"))
    
    if status.get("profile"):
        info_table.add_row("Profilo", status["profile"])
    
    console.print(info_table)
    
    # Informazioni spazio
    try:
        if is_mounted(mount_point) and check_space:
            rprint(f"\n[yellow]Calcolo spazio occupato (...)[/yellow]")
            used_space = get_directory_size(mount_point)
            rprint(f"\n[bold]💾 Utilizzo spazio:[/bold]")
            rprint(f"• Spazio utilizzato: {bytes_to_human(used_space)}")
    except Exception as e:
        rprint(f"[yellow]⚠️ Errore informazioni spazio: {e}[/yellow]")


@mount_app.command("migrate")
def migrate_mount(
    mount_point: str = typer.Argument(help="Mount point da migrare"),
    target_engine: str = typer.Argument(help="Engine target (rclone/davfs2)"),
    profile: str = typer.Option("full", help="Profilo per rclone"),
    backup: bool = typer.Option(True, "--backup/--no-backup", help="Backup configurazione")
):
    """Migra un mount esistente ad un altro engine"""
    try:
        target = MountEngine(target_engine.lower())
    except ValueError:
        rprint(f"[red]❌ Engine non supportato: {target_engine}[/red]")
        rprint("💡 Engine supportati: rclone, davfs2")
        sys.exit(1)
    
    rprint(f"[blue]🔄 Migrazione mount {mount_point} → {target_engine}[/blue]")
    
    if not check_sudo_privileges():
        rprint("[red]❌ Privilegi sudo richiesti[/red]")
        sys.exit(1)
    
    mount_manager = MountManager()
    
    # Verifica mount esistente
    status = mount_manager.get_mount_status(mount_point)
    if not status["mounted"]:
        rprint(f"[red]❌ {mount_point} non è montato[/red]")
        sys.exit(1)
    
    current_engine = status.get("engine")
    if current_engine == target and status.get("profile") == profile:
        rprint(f"[yellow]⚠️ Mount già usa {target_engine} e profilo {profile}[/yellow]")
        return
    
    rprint(f"[cyan]Migrazione: {current_engine.value if hasattr(current_engine, 'value') else current_engine} → {target_engine} con profilo {profile}[/cyan]")
    
    # Conferma
    if not Confirm.ask("Continuare con la migrazione?"):
        rprint("[cyan]Migrazione annullata[/cyan]")
        return
    
    try:
        # Estrai username dal mount point (assumendo /home/username)
        username = os.path.basename(mount_point)
        
        # Chiedi password (necessaria per rimount)
        password = Prompt.ask(f"Password per {username}", password=True)
        
        # Test connettività
        if not test_webdav_connectivity(username, password):
            rprint("[red]❌ Test connettività fallito[/red]")
            sys.exit(1)
        
        # Backup directory se richiesto
        if backup:
            import shutil
            import time
            backup_path = f"{mount_point}.migration-backup.{int(time.time())}"
            try:
                # Copia solo file di configurazione locali
                config_files = ['.bashrc', '.profile', '.bash_profile', '.vimrc', '.gitconfig']
                os.makedirs(backup_path, exist_ok=True)
                
                for config_file in config_files:
                    src = os.path.join(mount_point, config_file)
                    if os.path.exists(src):
                        shutil.copy2(src, backup_path)
                        
                rprint(f"[green]📦 Backup creato: {backup_path}[/green]")
            except Exception as e:
                rprint(f"[yellow]⚠️ Avviso backup: {e}[/yellow]")
        
        # Unmount corrente
        rprint(f"[blue]📁 Smontando mount corrente...[/blue]")
        if not mount_manager.unmount_user_home(mount_point):
            rprint("[red]❌ Errore unmount[/red]")
            sys.exit(1)
        
        # Mount con nuovo engine
        rprint(f"[blue]🔗 Rimontando con {target_engine}...[/blue]")
        result = mount_manager.mount_user_home(
            username, password, mount_point, target,
            profile if target == MountEngine.RCLONE else None
        )
        
        if result["success"]:
            rprint(f"[green]✅ Migrazione completata![/green]")
            rprint(f"[cyan]Nuovo engine: {result['engine_used'].value}[/cyan]")
            
            if result.get("profile"):
                rprint(f"[cyan]Profilo: {result['profile']}[/cyan]")
        else:
            rprint(f"[red]❌ Migrazione fallita: {result['message']}[/red]")
            sys.exit(1)
            
    except Exception as e:
        rprint(f"[red]❌ Errore migrazione: {e}[/red]")
        sys.exit(1)


@mount_app.command("benchmark")
def benchmark_engines(
    username: str = typer.Argument(help="Username per test"),
    test_dir: str = typer.Option("/tmp/ncwrap-benchmark", help="Directory test"),
    file_size_mb: int = typer.Option(10, help="Dimensione file test in MB"),
    iterations: int = typer.Option(3, help="Numero iterazioni per test")
):
    """Benchmark performance engine di mount"""
    rprint(f"[blue]⚡ Benchmark engine mount per {username}[/blue]")
    rprint(f"Test: file {file_size_mb}MB, {iterations} iterazioni")
    
    if not check_sudo_privileges():
        rprint("[red]❌ Privilegi sudo richiesti[/red]")
        sys.exit(1)
    
    password = Prompt.ask(f"Password per {username}", password=True)
    
    # Test connettività
    if not test_webdav_connectivity(username, password):
        rprint("[red]❌ Test connettività WebDAV fallito[/red]")
        sys.exit(1)
    
    mount_manager = MountManager()
    available = mount_manager.detect_available_engines()
    
    # Prepara directory test
    os.makedirs(test_dir, exist_ok=True)
    
    results = {}
    
    for engine in [MountEngine.RCLONE, MountEngine.DAVFS2]:
        if not available[engine]:
            rprint(f"[yellow]⚠️ {engine.value} non disponibile, skip[/yellow]")
            continue
        
        rprint(f"\n[bold cyan]🧪 Test {engine.value}[/bold cyan]")
        
        test_mount = f"{test_dir}/{engine.value}-{username}"
        
        try:
            # Mount
            result = mount_manager.mount_user_home(
                username, password, test_mount, engine,
                "writes" if engine == MountEngine.RCLONE else None
            )
            
            if not result["success"]:
                rprint(f"[red]❌ Mount {engine.value} fallito[/red]")
                continue
            
            # Benchmark
            import time
            import random
            import string
            
            times = {"write": [], "read": [], "list": []}
            
            for i in range(iterations):
                rprint(f"[blue]  Iterazione {i+1}/{iterations}[/blue]")
                
                # Write test
                test_file = f"{test_mount}/benchmark_{i}.dat"
                test_data = ''.join(random.choices(string.ascii_letters, k=file_size_mb * 1024 * 1024))
                
                start = time.time()
                with open(test_file, 'w') as f:
                    f.write(test_data)
                write_time = time.time() - start
                times["write"].append(write_time)
                
                # Read test
                start = time.time()
                with open(test_file, 'r') as f:
                    _ = f.read()
                read_time = time.time() - start
                times["read"].append(read_time)
                
                # List test
                start = time.time()
                _ = os.listdir(test_mount)
                list_time = time.time() - start
                times["list"].append(list_time)
                
                # Cleanup
                os.remove(test_file)
            
            # Calcola medie
            avg_write = sum(times["write"]) / len(times["write"])
            avg_read = sum(times["read"]) / len(times["read"])
            avg_list = sum(times["list"]) / len(times["list"])
            
            results[engine.value] = {
                "write": avg_write,
                "read": avg_read,
                "list": avg_list,
                "write_speed": file_size_mb / avg_write if avg_write > 0 else 0,  # MB/s
                "read_speed": file_size_mb / avg_read if avg_read > 0 else 0       # MB/s
            }
            
            rprint(f"[green]✅ {engine.value} completato[/green]")
            
        except Exception as e:
            rprint(f"[red]❌ Errore test {engine.value}: {e}[/red]")
        finally:
            # Cleanup mount
            try:
                mount_manager.unmount_user_home(test_mount)
                if os.path.exists(test_mount):
                    os.rmdir(test_mount)
            except:
                pass
    
    # Mostra risultati
    if results:
        rprint(f"\n[bold blue]📊 Risultati benchmark[/bold blue]")
        
        table = Table(title=f"Performance Test - File {file_size_mb}MB")
        table.add_column("Engine", style="cyan")
        table.add_column("Write (s)", style="white")
        table.add_column("Read (s)", style="white")
        table.add_column("List (s)", style="white")
        table.add_column("Write Speed", style="green")
        table.add_column("Read Speed", style="green")
        
        for engine, metrics in results.items():
            table.add_row(
                engine,
                f"{metrics['write']:.2f}",
                f"{metrics['read']:.2f}",
                f"{metrics['list']:.3f}",
                f"{metrics['write_speed']:.1f} MB/s",
                f"{metrics['read_speed']:.1f} MB/s"
            )
        
        console.print(table)
        
        # Raccomandazione
        if len(results) > 1:
            best_write = min(results.items(), key=lambda x: x[1]['write'])
            best_read = min(results.items(), key=lambda x: x[1]['read'])
            
            rprint(f"\n[bold green]🏆 Engine migliori:[/bold green]")
            rprint(f"• Scrittura: {best_write[0]} ({best_write[1]['write_speed']:.1f} MB/s)")
            rprint(f"• Lettura: {best_read[0]} ({best_read[1]['read_speed']:.1f} MB/s)")
    
    # Cleanup directory test
    try:
        import shutil
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)
    except:
        pass


@mount_app.command("install")
def install_engine(
    engine: str = typer.Argument(help="Engine da installare (rclone/davfs2)"),
    configure: bool = typer.Option(True, "--configure/--no-configure", help="Configura dopo installazione")
):
    """Installa engine di mount"""
    try:
        mount_engine = MountEngine(engine.lower())
    except ValueError:
        rprint(f"[red]❌ Engine non supportato: {engine}[/red]")
        rprint("💡 Engine supportati: rclone, davfs2")
        sys.exit(1)
        
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
            
    except Exception as e:
        rprint(f"[red]❌ Errore: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    mount_app()
