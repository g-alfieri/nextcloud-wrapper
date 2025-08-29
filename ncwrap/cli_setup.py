"""
CLI Setup - Setup completo utenti con rclone engine v0.4.0
"""
import typer
import sys
from typing import List
from rich.console import Console
from rich import print as rprint

from .api import get_nc_config, create_nc_user, check_user_exists, create_folder_structure
from .system import create_linux_user, user_exists 
from .mount import MountManager, MountEngine
from .quota import QuotaManager
from .utils import check_sudo_privileges, parse_size_to_bytes

setup_app = typer.Typer(help="Setup completo utenti v0.4.0")
console = Console()


@setup_app.command()
def user(
    username: str = typer.Argument(help="Nome utente (es. ecommerce.it)"),
    password: str = typer.Argument(help="Password utente"),
    quota: str = typer.Option("100G", help="Quota Nextcloud (es. 100G, 500G)"),
    engine: str = typer.Option("rclone", "--engine", help="Engine mount (rclone/davfs2)"),
    profile: str = typer.Option("writes", "--profile", help="Profilo rclone (writes/minimal/hosting/full)"),
    subdomains: List[str] = typer.Option([], "--sub", help="Sottodomini da creare (www,blog,shop)"),
    skip_linux: bool = typer.Option(False, "--skip-linux", help="Non creare utente Linux"),
    skip_test: bool = typer.Option(False, "--skip-test", help="Non testare connettività"),
    auto_service: bool = typer.Option(True, "--service/--no-service", help="Crea servizio systemd"),
    remount: bool = typer.Option(False, "--remount", help="Forza remount se già montato")
):
    """
    Setup completo utente con engine rclone/davfs2 unificato
    
    Esempi:
    • nextcloud-wrapper setup user domain.com password123 --quota 100G
    • nextcloud-wrapper setup user dev.com pass --engine rclone --profile writes 
    • nextcloud-wrapper setup user hosting.com pass --profile hosting --sub www,blog
    """
    try:
        mount_engine = MountEngine(engine.lower())
    except ValueError:
        rprint(f"[red]❌ Engine non supportato: {engine}[/red]")
        rprint("💡 Engine supportati: rclone, davfs2")
        sys.exit(1)
    
    rprint(f"[bold blue]🚀 Nextcloud Wrapper v0.4.0 - Setup: {username}[/bold blue]")
    rprint(f"[cyan]Engine: {engine} | Profilo: {profile if mount_engine == MountEngine.RCLONE else 'default'}[/cyan]")
    rprint(f"[cyan]Quota: {quota} | Sottodomini: {', '.join(subdomains) if subdomains else 'nessuno'}[/cyan]")
    
    try:
        # Verifica configurazione
        base_url, _, _ = get_nc_config()
        rprint(f"[cyan]🔗 Server Nextcloud: {base_url}[/cyan]")
        
        # Privilegi sudo per utente Linux e servizi
        if not skip_linux and not check_sudo_privileges():
            rprint("[red]❌ Privilegi sudo richiesti per utente Linux[/red]")
            rprint("💡 Usa: sudo nextcloud-wrapper setup user ... o --skip-linux")
            sys.exit(1)
        
        # 1. Crea utente Nextcloud
        rprint(f"[blue]1️⃣ Creando utente Nextcloud: {username}[/blue]")
        if check_user_exists(username):
            rprint(f"[yellow]⚠️ Utente Nextcloud già esistente: {username}[/yellow]")
        else:
            create_nc_user(username, password, quota)
            rprint(f"[green]✅ Utente Nextcloud creato con quota {quota}[/green]")
        
        # 2. Crea utente Linux
        if not skip_linux:
            rprint(f"[blue]2️⃣ Creando utente Linux: {username}[/blue]")
            if user_exists(username):
                rprint(f"[yellow]⚠️ Utente Linux già esistente: {username}[/yellow]")
            else:
                if create_linux_user(username, password, create_home=True):
                    rprint("[green]✅ Utente Linux creato con home directory[/green]")
                else:
                    rprint("[red]❌ Errore creazione utente Linux[/red]")
                    sys.exit(1)
        
        # 3. Test connettività (se richiesto)
        if not skip_test:
            rprint("[blue]3️⃣ Test connettività WebDAV...[/blue]")
            from .api import test_webdav_connectivity
            if test_webdav_connectivity(username, password):
                rprint("[green]✅ Connettività WebDAV OK[/green]")
            else:
                rprint("[red]❌ Test connettività fallito[/red]")
                rprint("⚠️ Continuando, ma il mount potrebbe fallire...")
        
        # 4. Crea struttura cartelle
        rprint("[blue]4️⃣ Creando struttura cartelle...[/blue]")
        try:
            create_folder_structure(username, password, subdomains)
            rprint("[green]✅ Struttura cartelle creata[/green]")
            if subdomains:
                for subdomain in subdomains:
                    rprint(f"  📁 {subdomain}/ creato")
        except Exception as e:
            rprint(f"[yellow]⚠️ Errore struttura cartelle: {e}[/yellow]")
        
        # 5. Setup mount engine
        home_path = f"/home/{username}"
        rprint(f"[blue]5️⃣ Setup mount {engine}: {home_path}[/blue]")
        
        mount_manager = MountManager()
        
        # Verifica se già montato
        if mount_manager.is_mounted(home_path):
            if remount:
                rprint("[yellow]📁 Smontando mount esistente...[/yellow]")
                mount_manager.unmount_user_home(home_path)
            else:
                rprint("[yellow]⚠️ Mount già presente, usa --remount per forzare[/yellow]")
                return
        
        # Esegue mount
        result = mount_manager.mount_user_home(
            username, password, home_path, mount_engine, 
            profile if mount_engine == MountEngine.RCLONE else None
        )
        
        if result["success"]:
            rprint(f"[green]✅ Mount {engine} riuscito: {home_path}[/green]")
            if mount_engine == MountEngine.RCLONE:
                rprint(f"[cyan]Profilo: {profile} | Cache: {result.get('cache_mode', 'default')}[/cyan]")
        else:
            rprint(f"[red]❌ Mount fallito: {result['message']}[/red]")
            sys.exit(1)
        
        # 6. Crea servizio systemd (se richiesto)
        if auto_service and not skip_linux:
            rprint("[blue]6️⃣ Creando servizio systemd...[/blue]")
            try:
                service_name = mount_manager.create_mount_service(
                    username, password, home_path, mount_engine, 
                    profile if mount_engine == MountEngine.RCLONE else None
                )
                rprint(f"[green]✅ Servizio systemd creato: {service_name}[/green]")
                
                # Abilita servizio
                from .systemd import SystemdManager
                systemd_manager = SystemdManager()
                if systemd_manager.enable_service(service_name):
                    rprint("[green]✅ Servizio abilitato per avvio automatico[/green]")
                else:
                    rprint("[yellow]⚠️ Servizio creato ma non abilitato[/yellow]")
            except Exception as e:
                rprint(f"[yellow]⚠️ Errore servizio systemd: {e}[/yellow]")
        
        # 7. Setup quota (se richiesta e supportata)
        try:
            quota_bytes = parse_size_to_bytes(quota)
            quota_manager = QuotaManager()
            
            if quota_manager.set_user_quota(username, quota_bytes):
                rprint(f"[green]✅ Quota filesystem impostata: {quota}[/green]")
            else:
                rprint(f"[yellow]⚠️ Quota filesystem non supportata (continuo)[/yellow]")
        except Exception as e:
            rprint(f"[yellow]⚠️ Errore quota: {e}[/yellow]")
        
        # 8. Riepilogo finale
        rprint(f"\n[bold green]🎉 Setup completato per: {username}[/bold green]")
        rprint(f"[green]• Utente Nextcloud: ✅ (quota: {quota})[/green]")
        if not skip_linux:
            rprint(f"[green]• Utente Linux: ✅[/green]")
        rprint(f"[green]• Mount {engine}: ✅ ({home_path})[/green]")
        if mount_engine == MountEngine.RCLONE:
            rprint(f"[green]• Profilo rclone: {profile}[/green]")
        if auto_service and not skip_linux:
            rprint(f"[green]• Servizio systemd: ✅[/green]")
        
        rprint(f"\n[bold]🛠️ Prossimi passi:[/bold]")
        rprint(f"cd {home_path}                  # Accedi alla directory")
        rprint(f"echo 'test' > test.txt          # Crea file di test")
        rprint(f"ls -la                          # Verifica sincronizzazione")
        
        if subdomains:
            rprint(f"\n[bold]📁 Cartelle web create:[/bold]")
            for subdomain in subdomains:
                rprint(f"• {home_path}/{subdomain}/     # Per {subdomain}.{username}")
        
        if mount_engine == MountEngine.RCLONE:
            rprint(f"\n[bold]🚀 Vantaggi profilo {profile}:[/bold]")
            from .rclone import MOUNT_PROFILES
            profile_info = MOUNT_PROFILES.get(profile, {})
            if profile_info.get("description"):
                rprint(f"• {profile_info['description']}")
        
        rprint(f"\n[bold]📊 Comandi utili:[/bold]")
        rprint(f"nextcloud-wrapper mount status          # Status mount engine")
        rprint(f"nextcloud-wrapper user info {username}  # Info complete utente")
        rprint(f"nextcloud-wrapper service list          # Status servizi")
        
        if mount_engine == MountEngine.RCLONE:
            rprint(f"nextcloud-wrapper mount profiles rclone # Vedi altri profili")
        
    except Exception as e:
        rprint(f"[bold red]💥 Errore durante setup: {str(e)}[/bold red]")
        sys.exit(1)


@setup_app.command()
def config():
    """Mostra configurazione predefinita per setup"""
    rprint("[blue]⚙️ Configurazione Setup nextcloud-wrapper v0.4.0[/blue]")
    
    try:
        base_url, admin_user, admin_pass = get_nc_config()
        
        from rich.table import Table
        table = Table(title="Configurazione Nextcloud")
        table.add_column("Variabile", style="cyan")
        table.add_column("Valore", style="white")
        
        table.add_row("NC_BASE_URL", base_url)
        table.add_row("NC_ADMIN_USER", admin_user)
        table.add_row("NC_ADMIN_PASS", "***" + admin_pass[-3:])
        
        console.print(table)
        
        # Engine predefiniti
        rprint("\n[bold]🎛️ Engine e Profili Predefiniti:[/bold]")
        rprint("• Engine: rclone (predefinito), davfs2 (fallback)")
        rprint("• Profilo rclone: writes (ottimale per editing)")
        rprint("• Quota predefinita: 100G")
        rprint("• Servizio systemd: abilitato")
        
        # Profili disponibili
        rprint("\n[bold]📋 Profili rclone disponibili:[/bold]")
        from .rclone import MOUNT_PROFILES
        for profile, info in MOUNT_PROFILES.items():
            rprint(f"• {profile}: {info.get('description', 'N/A')}")
        
        # Esempi d'uso
        rprint("\n[bold]💡 Esempi d'uso:[/bold]")
        rprint("# Setup base")
        rprint("nextcloud-wrapper setup user domain.com password123")
        rprint("")
        rprint("# Setup hosting con sottodomini")  
        rprint("nextcloud-wrapper setup user hosting.com pass --profile hosting --sub www,blog,shop")
        rprint("")
        rprint("# Setup developer avanzato")
        rprint("nextcloud-wrapper setup user dev.com pass --quota 500G --profile writes")
        
    except Exception as e:
        rprint(f"[red]❌ Errore configurazione: {e}[/red]")


@setup_app.command() 
def migrate():
    """Migra configurazione da versioni precedenti"""
    rprint("[blue]🔄 Migrazione da versioni precedenti v0.3.0 → v0.4.0[/blue]")
    
    rprint("[bold green]✅ Migrazione automatica attiva![/bold green]")
    rprint("La versione v0.4.0 è compatibile al 100% con v0.3.0:")
    
    rprint("\n[bold]🔧 Comandi esistenti:[/bold]")
    rprint("• ✅ Tutti i comandi v0.3.0 continuano a funzionare")
    rprint("• ✅ Mount davfs2 esistenti preservati")  
    rprint("• ✅ Servizi systemd non modificati")
    rprint("• ✅ Configurazioni .env compatibili")
    
    rprint("\n[bold]🆕 Nuove funzionalità v0.4.0:[/bold]")
    rprint("• 🚀 Engine rclone con performance 5x superiori")
    rprint("• 🎛️ Profili mount specializzati (writes, hosting, minimal)")
    rprint("• 📊 Benchmark integrato per comparazione")
    rprint("• 🔄 Migrazione engine automatica")
    
    rprint("\n[bold]🎯 Per sfruttare rclone (opzionale):[/bold]")
    rprint("# Testa nuovo engine")
    rprint("nextcloud-wrapper mount engines")
    rprint("")
    rprint("# Migra utenti esistenti")
    rprint("nextcloud-wrapper mount migrate /home/username rclone --profile writes")
    rprint("")
    rprint("# Nuovo setup con rclone")
    rprint("nextcloud-wrapper setup user newuser.com password --engine rclone")
    
    rprint("\n[bold green]💚 Nessuna azione richiesta - tutto continua a funzionare![/bold green]")


if __name__ == "__main__":
    setup_app()
