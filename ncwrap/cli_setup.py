"""
CLI Setup - Comando principale per setup completo utenti
"""
import typer
import sys
from typing import List
from rich.console import Console
from rich import print as rprint

from .api import get_nc_config, test_webdav_connectivity, create_folder_structure, get_webdav_url
from .webdav import setup_webdav_user
from .systemd import SystemdManager
from .utils import check_sudo_privileges, parse_size_to_bytes, bytes_to_human

setup_app = typer.Typer(help="Setup completo utenti")
console = Console()


@setup_app.command()
def user(
    username: str = typer.Argument(help="Nome utente (es. ecommerce.it)"),
    password: str = typer.Argument(help="Password utente"),
    quota: str = typer.Option("100G", help="Quota Nextcloud (es. 100G, 50G)"),
    fs_percentage: float = typer.Option(0.02, "--fs-percentage", help="Percentuale filesystem (default: 2%)"),
    engine: str = typer.Option("rclone", "--engine", help="Engine mount (rclone/davfs2)"),
    profile: str = typer.Option("writes", "--profile", help="Profilo mount (solo rclone)"),
    subdomains: List[str] = typer.Option([], "--sub", help="Sottodomini da creare"),
    skip_linux: bool = typer.Option(False, "--skip-linux", help="Non creare utente Linux"),
    skip_test: bool = typer.Option(False, "--skip-test", help="Non testare login WebDAV"),
    auto_service: bool = typer.Option(True, "--service/--no-service", help="Crea servizio systemd automatico")
):
    """
    Setup completo utente con mount engine unificato (rclone/davfs2)
    
    Crea: Utente Nextcloud + Linux + Mount + Quote + Servizi + Cartelle
    """
    mount_engine = MountEngine(engine.lower())
    
    rprint(f"[bold blue]🚀 Nextcloud Wrapper v0.4.0 - Setup completo per: {username}[/bold blue]")
    rprint(f"[cyan]Engine mount: {engine} | Profilo: {profile if mount_engine == MountEngine.RCLONE else 'default'}[/cyan]")
    
    try:
        # Verifica configurazione
        base_url, _, _ = get_nc_config()
        rprint(f"[cyan]🔗 Server Nextcloud: {base_url}[/cyan]")
        
        # Verifica privilegi sudo se necessario
        if not skip_linux and not check_sudo_privileges():
            rprint("[bold red]❌ Privilegi sudo richiesti per creare utente Linux[/bold red]")
            rprint("💡 Esegui: sudo nextcloud-wrapper setup user ...")
            sys.exit(1)
        
        # 1. Setup completo con mount engine unificato
        rprint("[yellow]1️⃣ Setup completo con mount engine...[/yellow]")
        
        if setup_user_with_mount(
            username=username,
            password=password, 
            quota=quota,
            fs_percentage=fs_percentage,
            engine=mount_engine,
            profile=profile if mount_engine == MountEngine.RCLONE else None
        ):
            rprint("[green]✅ Setup mount completato[/green]")
        else:
            rprint("[red]❌ Errore setup mount[/red]")
            sys.exit(1)
        
        # 2. Test connettività WebDAV
        if not skip_test:
            rprint("[yellow]2️⃣ Test connettività WebDAV...[/yellow]")
            if test_webdav_connectivity(username, password):
                rprint("[green]✅ Connettività WebDAV verificata[/green]")
            else:
                rprint("[red]❌ Test connettività WebDAV fallito[/red]")
                sys.exit(1)
        
        # 3. Crea struttura cartelle standard
        rprint("[yellow]3️⃣ Creazione struttura cartelle...[/yellow]")
        results = create_folder_structure(username, password, username, subdomains)
        
        folder_count = 0
        for path, status in results.items():
            if status == 201:
                rprint(f"[green]✅ Creata: {path}[/green]")
                folder_count += 1
            elif status == 405:
                rprint(f"[yellow]📁 Già esistente: {path}[/yellow]")
                folder_count += 1
            else:
                rprint(f"[red]❌ Errore {status}: {path}[/red]")
        
        rprint(f"[cyan]📊 Cartelle configurate: {folder_count}[/cyan]")
        
        # 4. Informazioni mount engine utilizzato
        rprint("[yellow]4️⃣ Verifica mount attivo...[/yellow]")
        try:
            from .mount import MountManager
            mount_manager = MountManager()
            home_path = f"/home/{username}"
            status = mount_manager.get_mount_status(home_path)
            
            if status["mounted"]:
                engine_used = status.get("engine")
                rprint(f"[green]✅ Mount attivo: {engine_used.value if hasattr(engine_used, 'value') else engine_used}[/green]")
                
                if status.get("profile"):
                    rprint(f"[cyan]📊 Profilo: {status['profile']}[/cyan]")
            else:
                rprint("[red]❌ Mount non attivo[/red]")
                
        except Exception as e:
            rprint(f"[yellow]⚠️ Avviso verifica mount: {e}[/yellow]")
        
        # Riepilogo finale
        rprint(f"\n[bold green]🎉 Setup completato con successo per {username}![/bold green]")
        
        rprint("\n[bold]📋 Configurazione:[/bold]")
        rprint(f"• Utente Nextcloud: {username}")
        rprint(f"• Utente Linux: {username}")
        rprint(f"• Home directory: /home/{username}")
        rprint(f"• Mount engine: {engine}")
        
        if mount_engine == MountEngine.RCLONE:
            rprint(f"• Profilo rclone: {profile}")
            
            # Info profilo
            from .mount import MountManager
            mount_manager = MountManager()
            profile_info = mount_manager.get_mount_profiles(mount_engine).get(profile)
            if profile_info:
                rprint(f"  - Tipo: {profile_info['description']}")
                rprint(f"  - Storage: {profile_info['storage']}")
                rprint(f"  - Performance: {profile_info['performance']}")
        
        rprint(f"• URL WebDAV: {get_webdav_url(username)}")
        rprint(f"• Quota Nextcloud: {quota}")
        
        # Info quota filesystem
        nc_bytes = parse_size_to_bytes(quota)
        fs_bytes = int(nc_bytes * fs_percentage)
        fs_quota = bytes_to_human(fs_bytes)
        rprint(f"• Quota filesystem: {fs_quota} ({fs_percentage:.1%})")
        
        if subdomains:
            rprint(f"• Sottodomini: {', '.join(subdomains)}")
        
        rprint("\n[bold]🔄 Workflow utente:[/bold]")
        rprint(f"# Login SSH")
        rprint(f"ssh {username}@server")
        rprint(f"# La home directory È lo spazio Nextcloud!")
        rprint(f"echo 'Hello World' > ~/test.txt  # File immediatamente su Nextcloud")
        rprint(f"ls ~/public/                     # Cartelle web del sito")
        
        if mount_engine == MountEngine.RCLONE:
            rprint("\n[bold]🚀 Vantaggi rclone:[/bold]")
            rprint(f"• Performance superiori per lettura/scrittura")
            rprint(f"• Cache VFS intelligente ({profile} profile)")
            rprint(f"• Gestione avanzata connessioni di rete")
            rprint(f"• Supporto streaming per file grandi")
        
        rprint("\n[bold]🛠️ Comandi utili:[/bold]")
        rprint(f"nextcloud-wrapper mount status               # Status mount engine")
        rprint(f"nextcloud-wrapper mount info /home/{username} # Info dettagliate mount")
        rprint(f"nextcloud-wrapper user info {username}       # Info complete utente")
        rprint(f"nextcloud-wrapper quota show {username}      # Verifica quota")
        rprint(f"nextcloud-wrapper service list               # Status servizi")
        
        # Suggerimenti ottimizzazione
        if mount_engine == MountEngine.RCLONE:
            rprint("\n[bold]💡 Suggerimenti ottimizzazione:[/bold]")
            rprint(f"• Profilo 'writes': ottimale per editing file")
            rprint(f"• Profilo 'minimal': per hosting web leggero")
            rprint(f"• Profilo 'hosting': per massima compatibilità web server")
            rprint(f"nextcloud-wrapper mount profiles rclone     # Vedi tutti i profili")
        
    except ValueError as ve:
        if "engine" in str(ve).lower():
            rprint(f"[red]❌ Engine non supportato: {engine}[/red]")
            rprint("💡 Engine supportati: rclone, davfs2")
        else:
            rprint(f"[red]❌ Errore validazione: {ve}[/red]")
        sys.exit(1)
    except Exception as e:
        rprint(f"[bold red]💥 Errore durante setup: {str(e)}[/bold red]")
        sys.exit(1)


@setup_app.command()
def migrate():
    """Migra configurazione da versioni precedenti"""
    rprint("[blue]🔄 Migrazione da versioni precedenti[/blue]")
    rprint("[yellow]⚠️ Funzionalità di migrazione non ancora implementata[/yellow]")
    rprint("💡 Per ora usa: nextcloud-wrapper setup user <username> <password>")
