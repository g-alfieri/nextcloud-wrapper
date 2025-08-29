"""
CLI Setup - Setup completo utenti (v1.0 semplificato)
Solo rclone engine, zero quote filesystem
"""
import typer
import sys
from typing import List
from rich.console import Console
from rich import print as rprint

from .api import get_nc_config, test_webdav_connectivity, create_folder_structure, get_webdav_url
from .mount import setup_user_with_mount
from .utils import check_sudo_privileges
from .rclone import MOUNT_PROFILES

setup_app = typer.Typer(help="Setup completo utenti v1.0")
console = Console()


@setup_app.command()
def user(
    username: str = typer.Argument(help="Nome utente (es. ecommerce.it)"),
    password: str = typer.Argument(help="Password utente"),
    profile: str = typer.Option("full", "--profile", help="Profilo rclone (hosting/minimal/writes/full)"),
    subdomains: List[str] = typer.Option([], "--sub", help="Sottodomini da creare"),
    skip_test: bool = typer.Option(False, "--skip-test", help="Non testare login WebDAV"),
    auto_service: bool = typer.Option(True, "--service/--no-service", help="Crea servizio systemd automatico"),
    remount: bool = typer.Option(False, "--remount", help="Forza remount se esistente")
):
    """
    Setup completo utente con rclone (v1.0 semplificato)
    
    Crea: Utente Nextcloud + Linux + Mount rclone + Servizi + Cartelle
    Zero gestione quote (rclone gestisce spazio automaticamente)
    """
    # Valida profilo
    if profile not in MOUNT_PROFILES:
        rprint(f"[red]❌ Profilo non valido: {profile}[/red]")
        rprint(f"💡 Profili disponibili: {', '.join(MOUNT_PROFILES.keys())}")
        sys.exit(1)
    
    rprint(f"[bold blue]🚀 Nextcloud Wrapper v1.0.0 - Setup completo per: {username}[/bold blue]")
    rprint(f"[cyan]Engine: rclone | Profilo: {profile} ({MOUNT_PROFILES[profile]['description']})[/cyan]")
    
    try:
        # Verifica configurazione
        base_url, _, _ = get_nc_config()
        rprint(f"[cyan]🔗 Server Nextcloud: {base_url}[/cyan]")
        
        # Verifica privilegi sudo
        if not check_sudo_privileges():
            rprint("[bold red]❌ Privilegi sudo richiesti[/bold red]")
            rprint("💡 Esegui: sudo nextcloud-wrapper setup user ...")
            sys.exit(1)
        
        # 1. Test connettività prima di iniziare
        if not skip_test:
            rprint("[yellow]1️⃣ Test connettività WebDAV...[/yellow]")
            if test_webdav_connectivity(username, password):
                rprint("[green]✅ Connettività WebDAV verificata[/green]")
            else:
                rprint("[red]❌ Test connettività WebDAV fallito[/red]")
                rprint("💡 Verifica credenziali e configurazione NC_BASE_URL")
                sys.exit(1)
        
        # 2. Setup completo con rclone
        rprint("[yellow]2️⃣ Setup completo con rclone...[/yellow]")
        
        if setup_user_with_mount(
            username=username,
            password=password, 
            profile=profile,
            remount=remount
        ):
            rprint("[green]✅ Setup rclone completato[/green]")
        else:
            rprint("[red]❌ Errore setup rclone[/red]")
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
        
        # 4. Verifica mount rclone attivo
        rprint("[yellow]4️⃣ Verifica mount rclone...[/yellow]")
        try:
            from .mount import MountManager
            mount_manager = MountManager()
            home_path = f"/home/{username}"
            status = mount_manager.get_mount_status(home_path)
            
            if status["mounted"]:
                rprint("[green]✅ Mount rclone attivo[/green]")
                if status.get("profile"):
                    rprint(f"[cyan]📊 Profilo: {status['profile']}[/cyan]")
            else:
                rprint("[red]❌ Mount non attivo[/red]")
                
        except Exception as e:
            rprint(f"[yellow]⚠️ Avviso verifica mount: {e}[/yellow]")
        
        # Riepilogo finale
        rprint(f"\n[bold green]🎉 Setup completato con successo per {username}![/bold green]")
        
        rprint("\n[bold]📋 Configurazione v1.0:[/bold]")
        rprint(f"• Utente Nextcloud: {username}")
        rprint(f"• Utente Linux: {username}")
        rprint(f"• Home directory: /home/{username}")
        rprint(f"• Engine: rclone (unico supportato)")
        rprint(f"• Profilo rclone: {profile}")
        
        # Info profilo dettagliata
        profile_info = MOUNT_PROFILES[profile]
        rprint(f"  - Descrizione: {profile_info['description']}")
        rprint(f"  - Storage: {profile_info['storage']}")
        rprint(f"  - Performance: {profile_info['performance']}")
        rprint(f"  - Sync: {profile_info['sync']}")
        
        rprint(f"• URL WebDAV: {get_webdav_url(username)}")
        
        if subdomains:
            rprint(f"• Sottodomini: {', '.join(subdomains)}")
        
        # RIMOSSO v1.0: Info quote filesystem (rclone gestisce tutto automaticamente)
        rprint(f"• Gestione spazio: automatica via rclone (cache LRU)")
        
        rprint("\n[bold]🔄 Workflow utente:[/bold]")
        rprint(f"# Login SSH")
        rprint(f"ssh {username}@server")
        rprint(f"# La home directory È lo spazio Nextcloud!")
        rprint(f"echo 'Hello World' > ~/test.txt  # File immediatamente su Nextcloud")
        rprint(f"ls ~/public/                     # Cartelle web del sito")
        
        rprint("\n[bold]🚀 Vantaggi rclone v1.0:[/bold]")
        rprint(f"• Performance superiori per lettura/scrittura")
        rprint(f"• Cache VFS intelligente ({profile} profile)")
        rprint(f"• Gestione automatica spazio (LRU cleanup)")
        rprint(f"• Zero configurazione quote filesystem")
        rprint(f"• Sync bidirezionale automatico")
        
        rprint("\n[bold]🛠️ Comandi utili:[/bold]")
        rprint(f"nextcloud-wrapper mount status               # Status mount rclone")
        rprint(f"nextcloud-wrapper mount info /home/{username} # Info dettagliate mount")
        rprint(f"nextcloud-wrapper user info {username}       # Info complete utente")
        rprint(f"nextcloud-wrapper service list               # Status servizi systemd")
        
        # Suggerimenti ottimizzazione per profili
        rprint("\n[bold]💡 Profili rclone disponibili:[/bold]")
        for prof_name, prof_info in MOUNT_PROFILES.items():
            marker = "👈 ATTIVO" if prof_name == profile else ""
            rprint(f"• {prof_name}: {prof_info['description']} {marker}")
            rprint(f"  Cache: {prof_info['storage']} | {prof_info['use_case']}")
        
        rprint(f"\n[bold]🔧 Per cambiare profilo:[/bold]")
        rprint(f"nextcloud-wrapper mount unmount /home/{username}")
        rprint(f"nextcloud-wrapper setup user {username} <password> --profile=writes --remount")
        
    except Exception as e:
        rprint(f"[bold red]💥 Errore durante setup: {str(e)}[/bold red]")
        sys.exit(1)


@setup_app.command()
def quick(
    username: str = typer.Argument(help="Nome utente"),
    password: str = typer.Argument(help="Password utente")
):
    """Setup veloce con impostazioni predefinite (profilo full)"""
    rprint(f"[blue]⚡ Setup veloce per {username} (profilo: full)[/blue]")
    
    # Usa il comando completo con impostazioni predefinite
    try:
        from .mount import setup_user_with_mount
        
        if setup_user_with_mount(username, password, "full"):
            rprint(f"[green]🎉 Setup veloce completato per {username}![/green]")
            rprint(f"[cyan]Home directory: /home/{username} → rclone mount (cache 5GB)[/cyan]")
        else:
            rprint("[red]❌ Setup veloce fallito[/red]")
            sys.exit(1)
            
    except Exception as e:
        rprint(f"[red]❌ Errore setup veloce: {e}[/red]")
        sys.exit(1)


@setup_app.command()
def profiles():
    """Mostra tutti i profili rclone disponibili"""
    rprint("[blue]📊 Profili rclone disponibili per setup[/blue]")
    
    for profile_name, profile_info in MOUNT_PROFILES.items():
        rprint(f"\n[bold cyan]📋 {profile_name.upper()}[/bold cyan]")
        rprint(f"📝 {profile_info['description']}")
        rprint(f"🎯 Uso ideale: {profile_info['use_case']}")
        rprint(f"💾 Storage: {profile_info['storage']}")
        rprint(f"⚡ Performance: {profile_info['performance']}")
        rprint(f"🔄 Sync: {profile_info['sync']}")
        rprint(f"[dim]Comando: nextcloud-wrapper setup user <user> <pass> --profile={profile_name}[/dim]")


@setup_app.command()
def migrate():
    """Informazioni migrazione da versioni precedenti"""
    rprint("[blue]🔄 Migrazione a Nextcloud Wrapper v1.0[/blue]")
    
    rprint("\n[bold yellow]🚨 IMPORTANTE - Versione 1.0 Semplificata:[/bold yellow]")
    rprint("• Sistema WebDAV/davfs2: RIMOSSO (ora solo rclone)")
    rprint("• Gestione quote filesystem: RIMOSSA (rclone gestisce automaticamente)")
    rprint("• Engine dual-mode: RIMOSSO (solo rclone)")
    
    rprint("\n[bold blue]✨ Vantaggi v1.0:[/bold blue]")
    rprint("• Performance superiori (solo rclone)")
    rprint("• Setup più semplice (zero configurazioni quote)")
    rprint("• Manutenzione ridotta (-5.000 righe di codice)")
    rprint("• Cache intelligente automatica")
    
    rprint("\n[bold green]🔧 Migrazione automatica:[/bold green]")
    rprint("1. Backup configurazioni esistenti")
    rprint("2. Setup nuovo utente con rclone:")
    rprint("   nextcloud-wrapper setup user <username> <password> --profile=full")
    rprint("3. I dati Nextcloud rimangono intatti")
    
    rprint("\n[bold cyan]💡 Scelta profilo per migrazione:[/bold cyan]")
    rprint("• Da WebDAV cache → profilo 'full' (cache 5GB)")
    rprint("• Da hosting web → profilo 'hosting' (streaming)")
    rprint("• Da setup leggero → profilo 'minimal' (cache 1GB)")
    
    rprint("\n[yellow]Per assistenza migrazione: nextcloud-wrapper setup profiles[/yellow]")


if __name__ == "__main__":
    setup_app()
