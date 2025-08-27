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
    subdomains: List[str] = typer.Option([], "--sub", help="Sottodomini da creare"),
    skip_linux: bool = typer.Option(False, "--skip-linux", help="Non creare utente Linux"),
    skip_test: bool = typer.Option(False, "--skip-test", help="Non testare login WebDAV"),
    auto_service: bool = typer.Option(True, "--service/--no-service", help="Crea servizio systemd automatico"),
    # Rimossa opzione backup - gestito a livello superiore
):
    """
    Setup completo utente con WebDAV diretto nella home directory
    
    Crea: Utente Nextcloud + Linux + Mount WebDAV + Quote + Servizi
    """
    rprint(f"[bold blue]🚀 Nextcloud Wrapper v0.3.0 - Setup completo per: {username}[/bold blue]")
    
    try:
        # Verifica configurazione
        base_url, _, _ = get_nc_config()
        rprint(f"[cyan]🔗 Server Nextcloud: {base_url}[/cyan]")
        
        # Verifica privilegi sudo se necessario
        if not skip_linux and not check_sudo_privileges():
            rprint("[bold red]❌ Privilegi sudo richiesti per creare utente Linux[/bold red]")
            rprint("💡 Esegui: sudo nextcloud-wrapper setup user ...")
            sys.exit(1)
        
        # 1. Setup WebDAV completo
        rprint("[yellow]1️⃣ Setup WebDAV completo...[/yellow]")
        if setup_webdav_user(username, password, quota, fs_percentage):
            rprint("[green]✅ Setup WebDAV completato[/green]")
        else:
            rprint("[red]❌ Errore setup WebDAV[/red]")
            sys.exit(1)
        
        # 2. Test login WebDAV
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
        
        # 4. Servizio systemd automatico
        if auto_service:
            rprint("[yellow]4️⃣ Configurazione mount automatico...[/yellow]")
            try:
                systemd_manager = SystemdManager()
                service_name = systemd_manager.create_webdav_mount_service(username, password)
                
                if systemd_manager.enable_service(service_name):
                    rprint(f"[green]✅ Servizio automatico: {service_name}[/green]")
                else:
                    rprint("[yellow]⚠️ Servizio creato ma non abilitato[/yellow]")
                    
            except Exception as e:
                rprint(f"[yellow]⚠️ Avviso servizio systemd: {e}[/yellow]")
        
        # 5. (Backup rimosso - gestito esternamente)
        
        # Riepilogo finale
        rprint(f"\n[bold green]🎉 Setup completato con successo per {username}![/bold green]")
        
        rprint("\n[bold]📋 Configurazione:[/bold]")
        rprint(f"• Utente Nextcloud: {username}")
        rprint(f"• Utente Linux: {username}")
        rprint(f"• Home WebDAV: /home/{username}")
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
        
        rprint("\n[bold]🛠️ Comandi utili:[/bold]")
        rprint(f"nextcloud-wrapper user info {username}      # Info complete utente")
        rprint(f"nextcloud-wrapper webdav status             # Status mount WebDAV")
        rprint(f"nextcloud-wrapper quota show {username}     # Verifica quota")
        rprint(f"nextcloud-wrapper service list              # Status servizi")
        
    except Exception as e:
        rprint(f"[bold red]💥 Errore durante setup: {str(e)}[/bold red]")
        sys.exit(1)


@setup_app.command()
def migrate():
    """Migra configurazione da versioni precedenti"""
    rprint("[blue]🔄 Migrazione da versioni precedenti[/blue]")
    rprint("[yellow]⚠️ Funzionalità di migrazione non ancora implementata[/yellow]")
    rprint("💡 Per ora usa: nextcloud-wrapper setup user <username> <password>")
