"""
CLI unificata per nextcloud-wrapper con tutte le funzionalità
"""
import typer
import sys
from typing import List, Optional
from rich.console import Console
from rich.table import Table
from rich import print as rprint
from pathlib import Path

# Import dei moduli
from .nextcloud_api import (
    create_nc_user, 
    dav_probe, 
    ensure_tree, 
    check_user_exists,
    list_directory,
    get_nc_config
)
from .nextcloud_system import (
    create_linux_user, 
    sync_passwords, 
    get_user_info,
    check_sudo_privileges,
    user_exists
)
from .rclone import (
    add_nextcloud_remote,
    mount_remote,
    unmount,
    list_remotes,
    sync_directories,
    check_connectivity
)
from .quota import QuotaManager, list_all_quotas
from .systemd import SystemdManager
from .utils import ensure_dir

app = typer.Typer(
    name="nextcloud-wrapper",
    help="Wrapper completo per gestione Nextcloud + Linux + rclone + quote"
)
console = Console()

# Sotto-comandi
user_app = typer.Typer(help="Gestione utenti")
mount_app = typer.Typer(help="Gestione mount rclone")
quota_app = typer.Typer(help="Gestione quote filesystem")
service_app = typer.Typer(help="Gestione servizi systemd")

app.add_typer(user_app, name="user")
app.add_typer(mount_app, name="mount")
app.add_typer(quota_app, name="quota")
app.add_typer(service_app, name="service")


# =================== COMANDI UTENTI ===================

@user_app.command("create")
def create_user(
    dominio: str = typer.Argument(help="Dominio/username (es. casacialde.com)"),
    password: str = typer.Argument(help="Password utente"),
    subdomini: List[str] = typer.Option([], "--sub", help="Sottodomini da creare"),
    skip_linux: bool = typer.Option(False, "--skip-linux", help="Non creare utente Linux"),
    skip_test: bool = typer.Option(False, "--skip-test", help="Non testare login WebDAV"),
    mount_profile: str = typer.Option("writes", help="Profilo mount (hosting/minimal/writes)"),
    quota: Optional[str] = typer.Option(None, "--quota", help="Quota Nextcloud (es. 100G)"),
    fs_percentage: float = typer.Option(0.02, "--fs-percentage", help="Percentuale filesystem (default: 2%)")
):
    """Crea utente completo: Nextcloud + Linux + remote rclone + quota"""
    rprint(f"[bold blue]🚀 Creazione utente completo: {dominio}[/bold blue]")
    
    try:
        # Verifica configurazione
        base_url, _, _ = get_nc_config()
        
        # Verifica privilegi sudo se necessario
        if not skip_linux and not check_sudo_privileges():
            rprint("[bold red]❌ Privilegi sudo richiesti per creare utente Linux[/bold red]")
            sys.exit(1)
        
        # 1. Crea utente Nextcloud
        rprint("[yellow]📋 Creando utente Nextcloud...[/yellow]")
        if check_user_exists(dominio):
            rprint(f"[yellow]⚠️  Utente {dominio} già esistente in Nextcloud[/yellow]")
        else:
            create_nc_user(dominio, password)
            rprint("[green]✅ Utente Nextcloud creato[/green]")
        
        # 2. Test login WebDAV
        if not skip_test:
            rprint("[yellow]🔐 Testando login WebDAV...[/yellow]")
            status_code, _ = dav_probe(dominio, password)
            if status_code in (200, 207):
                rprint("[green]✅ Login WebDAV riuscito[/green]")
            else:
                rprint(f"[red]❌ Login WebDAV fallito: HTTP {status_code}[/red]")
                sys.exit(1)
        
        # 3. Crea struttura cartelle  
        rprint("[yellow]📁 Creando struttura cartelle...[/yellow]")
        results = ensure_tree(dominio, password, dominio, subdomini)
        
        for path, status in results.items():
            if status == 201:
                rprint(f"[green]✅ Creata: {path}[/green]")
            elif status == 405:
                rprint(f"[yellow]📁 Già esistente: {path}[/yellow]")
            else:
                rprint(f"[red]❌ Errore {status}: {path}[/red]")
        
        # 4. Crea utente Linux
        if not skip_linux:
            rprint("[yellow]🐧 Creando utente Linux...[/yellow]")
            if user_exists(dominio):
                rprint(f"[yellow]⚠️  Utente Linux {dominio} già esistente[/yellow]")
            else:
                if create_linux_user(dominio, password):
                    rprint("[green]✅ Utente Linux creato[/green]")
                else:
                    rprint("[red]❌ Errore creazione utente Linux[/red]")
        
        # 5. Crea remote rclone
        rprint("[yellow]🔗 Creando remote rclone...[/yellow]")
        if add_nextcloud_remote(dominio, base_url, dominio, password):
            rprint("[green]✅ Remote rclone creato[/green]")
        else:
            rprint("[red]❌ Errore creazione remote rclone[/red]")
            
        # Info profilo mount scelto
        from .rclone import get_mount_profile_info
        profile_info = get_mount_profile_info(mount_profile)
        if profile_info:
            rprint(f"[cyan]ℹ️  Profilo mount: {mount_profile} - {profile_info['description']}[/cyan]")
        
        # 6. Imposta quota
        if quota and not skip_linux:
            rprint(f"[yellow]💾 Impostando quota Nextcloud {quota} → Filesystem {fs_percentage:.1%}...[/yellow]")
            quota_manager = QuotaManager()
            if quota_manager.set_quota(dominio, quota, fs_percentage):
                filesystem_quota = int(quota_manager._parse_size(quota) * fs_percentage)
                fs_human = quota_manager._bytes_to_human(filesystem_quota)
                rprint(f"[green]✅ Quota impostata: NC {quota} → FS {fs_human}[/green]")
            else:
                rprint("[red]❌ Errore impostazione quota[/red]")
        
        rprint(f"[bold green]🎉 Utente {dominio} configurato con successo![/bold green]")
        
    except Exception as e:
        rprint(f"[bold red]💥 Errore: {str(e)}[/bold red]")
        sys.exit(1)


@user_app.command("test")
def test_login(
    utente: str = typer.Argument(help="Username da testare"),
    password: str = typer.Argument(help="Password da testare")
):
    """Testa login WebDAV di un utente"""
    rprint(f"[blue]🔐 Testing login per: {utente}[/blue]")
    
    try:
        status_code, response_preview = dav_probe(utente, password)
        
        if status_code in (200, 207):
            rprint("[green]✅ Login riuscito![/green]")
            rprint(f"Status: {status_code}")
        elif status_code == 401:
            rprint("[red]❌ Credenziali errate[/red]")
        else:
            rprint(f"[yellow]⚠️  Status imprevisto: {status_code}[/yellow]")
            rprint(f"Response preview: {response_preview[:200]}...")
            
    except Exception as e:
        rprint(f"[red]💥 Errore: {str(e)}[/red]")
        sys.exit(1)


@user_app.command("passwd")
def change_password(
    utente: str = typer.Argument(help="Username"),
    nuova_password: str = typer.Argument(help="Nuova password"),
    solo_nextcloud: bool = typer.Option(False, "--nc-only", help="Solo Nextcloud, non Linux")
):
    """Cambia password utente (Nextcloud + Linux sincronizzati)"""
    rprint(f"[blue]🔑 Aggiornamento password per: {utente}[/blue]")
    
    try:
        if solo_nextcloud:
            from .nextcloud_api import set_nc_password
            set_nc_password(utente, nuova_password)
            rprint("[green]✅ Password Nextcloud aggiornata[/green]")
        else:
            if not check_sudo_privileges():
                rprint("[red]❌ Privilegi sudo richiesti per aggiornare password Linux[/red]")
                sys.exit(1)
                
            results = sync_passwords(utente, nuova_password)
            
            if results["nextcloud"]:
                rprint("[green]✅ Password Nextcloud aggiornata[/green]")
            else:
                rprint("[red]❌ Errore aggiornamento Nextcloud[/red]")
                
            if results["linux"]:
                rprint("[green]✅ Password Linux aggiornata[/green]")
            else:
                rprint("[red]❌ Errore aggiornamento Linux[/red]")
                
            if results["errors"]:
                rprint("[red]Errori:[/red]")
                for error in results["errors"]:
                    rprint(f"  • {error}")
                    
            if results["nextcloud"] and results["linux"]:
                rprint("[bold green]🎉 Password sincronizzate con successo![/bold green]")
            
    except Exception as e:
        rprint(f"[red]💥 Errore: {str(e)}[/red]")
        sys.exit(1)


@user_app.command("info")
def user_info(
    utente: str = typer.Argument(help="Username da verificare")
):
    """Mostra informazioni complete su utente"""
    rprint(f"[blue]ℹ️  Informazioni utente: {utente}[/blue]")
    
    # Info Nextcloud
    try:
        nc_exists = check_user_exists(utente)
        rprint(f"[bold]Nextcloud:[/bold] {'✅ Presente' if nc_exists else '❌ Non trovato'}")
    except Exception as e:
        rprint(f"[bold]Nextcloud:[/bold] [red]❌ Errore: {e}[/red]")
    
    # Info Linux  
    linux_info = get_user_info(utente)
    if linux_info:
        rprint("[bold]Linux:[/bold] ✅ Presente")
        
        table = Table(title="Dettagli Utente Linux")
        table.add_column("Campo", style="cyan")
        table.add_column("Valore", style="white")
        
        for key, value in linux_info.items():
            table.add_row(key.upper(), str(value))
            
        console.print(table)
    else:
        rprint("[bold]Linux:[/bold] ❌ Non trovato")
    
    # Info remote rclone
    remotes = list_remotes()
    if utente in remotes:
        rprint("[bold]Remote rclone:[/bold] ✅ Configurato")
    else:
        rprint("[bold]Remote rclone:[/bold] ❌ Non trovato")
    
    # Info quota
    quota_manager = QuotaManager()
    quota_info = quota_manager.get_quota(utente)
    if quota_info:
        rprint(f"[bold]Quota:[/bold] ✅ {quota_info['used']} / {quota_info.get('soft_limit', 'unlimited')}")
    else:
        rprint("[bold]Quota:[/bold] ❌ Non impostata")


# =================== COMANDI MOUNT ===================

@mount_app.command("add")
def add_mount(
    name: str = typer.Argument(help="Nome del remote"),
    url: str = typer.Argument(help="URL Nextcloud"),
    username: str = typer.Argument(help="Username"),
    password: str = typer.Argument(help="Password")
):
    """Aggiunge remote rclone per Nextcloud"""
    rprint(f"[blue]🔗 Aggiungendo remote: {name}[/blue]")
    
    if add_nextcloud_remote(name, url, username, password):
        rprint("[green]✅ Remote aggiunto con successo[/green]")
    else:
        rprint("[red]❌ Errore aggiunta remote[/red]")


@mount_app.command("mount")
def mount_remote_cmd(
    remote: str = typer.Argument(help="Nome remote da montare"),
    mount_point: str = typer.Argument(help="Directory di mount"),
    profile: str = typer.Option("writes", help="Profilo mount (hosting/minimal/writes)"),
    background: bool = typer.Option(True, "--daemon/--foreground", help="Esegui in background")
):
    """
    Monta remote rclone con profilo specifico
    
    Profili disponibili:
    - hosting: Zero cache locale, streaming puro (read-only)
    - minimal: Cache 1GB max con auto-cleanup
    - writes: Sync bidirezionale con cache intelligente (DEFAULT)
    """
    rprint(f"[blue]📁 Montando {remote} in {mount_point} (profilo: {profile})[/blue]")
    
    # Mostra info profilo prima del mount
    from .rclone import get_mount_profile_info
    profile_info = get_mount_profile_info(profile)
    if profile_info:
        rprint(f"[cyan]ℹ️  {profile_info['description']}[/cyan]")
        rprint(f"[yellow]💾 Storage locale: {profile_info['storage']}[/yellow]")
    
    if mount_remote(remote, mount_point, background, profile):
        rprint(f"[green]✅ Mount riuscito con profilo {profile}[/green]")
        
        # Consigli specifici per profilo
        if profile == "writes":
            rprint("[green]🔄 Sync bidirezionale attivo:[/green]")
            rprint("   • File modificati localmente sincronizzati su Nextcloud")
            rprint("   • Modifiche da client Nextcloud sincronizzate localmente") 
            rprint("   • Cache persistente per performance")
        elif profile == "minimal":
            rprint("[green]⚡ Cache intelligente attiva:[/green]")
            rprint("   • File frequenti cached localmente")
            rprint("   • Auto-cleanup quando cache > 1GB")
            rprint("   • Read-only (nessun upload)")
        elif profile == "hosting":
            rprint("[green]🌐 Hosting ottimizzato:[/green]")
            rprint("   • File serviti direttamente da Nextcloud")
            rprint("   • Zero storage locale utilizzato") 
            rprint("   • Read-only sicuro")
    else:
        rprint("[red]❌ Errore durante mount[/red]")


@mount_app.command("unmount")
def unmount_cmd(
    mount_point: str = typer.Argument(help="Directory da smontare")
):
    """Smonta directory"""
    rprint(f"[blue]📁 Smontando {mount_point}[/blue]")
    
    if unmount(mount_point):
        rprint("[green]✅ Unmount riuscito[/green]")
    else:
        rprint("[red]❌ Errore durante unmount[/red]")


@mount_app.command("profiles")
def show_mount_profiles():
    """Mostra profili mount con dettagli storage e performance"""
    rprint("[blue]📋 Profili Mount Disponibili[/blue]")
    
    from .rclone import list_mount_profiles
    
    table = Table(title="Profili Mount")
    table.add_column("Profilo", style="cyan", width=12)
    table.add_column("Caso d'uso", style="white", width=25)
    table.add_column("Storage Locale", style="green", width=18)
    table.add_column("Sync", style="yellow", width=20)
    
    profiles = list_mount_profiles()
    for name, info in profiles.items():
        table.add_row(
            name,
            info['use_case'],
            info['storage'],
            info['sync']
        )
    
    console.print(table)
    
    rprint("\n[bold]💡 Raccomandazioni:[/bold]")
    rprint("[green]🔄 WRITES PROFILE (DEFAULT RACCOMANDATO):[/green]")
    rprint("   ✅ Sync bidirezionale completo")
    rprint("   ✅ File modificati localmente caricati su Nextcloud")
    rprint("   ✅ Modifiche client Nextcloud sincronizzate localmente")
    rprint("   ✅ Cache persistente max 2GB (LRU cleanup)")
    rprint("   ⚠️  Storage: max 2GB (controllo LRU)")
    
    rprint("\n[yellow]⚡ MINIMAL PROFILE:[/yellow]")
    rprint("   ✅ Cache intelligente (max 1GB)")
    rprint("   ✅ Auto-cleanup automatico")
    rprint("   ❌ Read-only (nessun upload)")
    rprint("   ⚠️  Storage limitato")
    
    rprint("\n[cyan]🌐 HOSTING PROFILE:[/cyan]")
    rprint("   ✅ Zero storage VPS utilizzato")
    rprint("   ✅ File serviti on-demand")
    rprint("   ❌ Read-only (nessun upload)")
    rprint("   ⚠️  Performance dipende da rete")
    
    rprint("\n[bold]Esempi comando:[/bold]")
    rprint("# Sync bidirezionale completo (DEFAULT)")
    rprint("[green]nextcloud-wrapper mount mount cliente1 /mnt/nextcloud --profile writes[/green]")
    rprint("\n# Cache intelligente limitata")  
    rprint("[green]nextcloud-wrapper mount mount cliente1 /mnt/nextcloud --profile minimal[/green]")
    rprint("\n# Web hosting puro (zero storage)")
    rprint("[green]nextcloud-wrapper mount mount cliente1 /var/www/html --profile hosting[/green]")


@mount_app.command("list")
def list_mounts():
    """Lista remote configurati con status"""
    rprint("[blue]📋 Remote rclone configurati[/blue]")
    
    remotes = list_remotes()
    if remotes:
        table = Table(title="Remote RClone")
        table.add_column("Nome", style="cyan")
        table.add_column("Status", style="white")
        
        for remote in remotes:
            status = "🟢 Online" if check_connectivity(remote) else "🔴 Offline"
            table.add_row(remote, status)
            
        console.print(table)
    else:
        rprint("[yellow]Nessun remote configurato[/yellow]")


@mount_app.command("storage-calc")
def calculate_storage_usage(
    profile: str = typer.Argument(help="Profilo mount (hosting/minimal/writes)"),
    daily_files: int = typer.Option(100, help="File acceduti al giorno"),
    avg_size_mb: float = typer.Option(1.0, help="Dimensione media file (MB)")
):
    """Calcola stima uso storage per un profilo"""
    rprint(f"[blue]📊 Calcolo storage per profilo: {profile}[/blue]")
    
    from .rclone import estimate_storage_usage
    usage = estimate_storage_usage(profile, daily_files, avg_size_mb)
    rprint(f"[green]💾 Storage stimato: {usage}[/green]")
    
    if profile == "writes":
        weekly_mb = daily_files * avg_size_mb * 0.7  # ~70% dei file viene cached
        rprint(f"\n[cyan]🔄 Profilo WRITES:[/cyan]")
        rprint(f"   • Cache attiva: ~{weekly_mb:.0f} MB medi")
        rprint("   • Cache persistente (cresce nel tempo)")
        rprint("   • Sync bidirezionale completo")
        rprint("   • Performance ottime dopo primo accesso")
    elif profile == "minimal":
        weekly_mb = daily_files * avg_size_mb * 0.3  # ~30% dei file viene cached
        rprint(f"\n[cyan]⚡ Profilo MINIMAL:[/cyan]")
        rprint(f"   • Cache attiva: ~{weekly_mb:.0f} MB medi")
        rprint("   • Auto-cleanup dopo 1 ora inattività")
        rprint("   • Limite massimo: 1GB")
        rprint("   • Read-only (nessun upload)")
    elif profile == "hosting":
        rprint("\n[cyan]🌐 Profilo HOSTING:[/cyan]")
        rprint("   • File non salvati localmente")
        rprint("   • Ogni richiesta = download da Nextcloud")
        rprint("   • Zero accumulo cache")
        rprint("   • Read-only sicuro")


# =================== COMANDI QUOTA ===================

@quota_app.command("set")
def set_quota(
    username: str = typer.Argument(help="Nome utente"),
    nextcloud_quota: str = typer.Argument(help="Quota Nextcloud (es. 100G, 50G)"),
    fs_percentage: float = typer.Option(0.02, "--fs-percentage", help="Percentuale filesystem (default: 2%)"),
    mount_profile: str = typer.Option("writes", help="Profilo mount (hosting/minimal/writes)"),
    path: str = typer.Option("/home", help="Path base per btrfs")
):
    """Imposta quota filesystem come percentuale della quota Nextcloud"""
    rprint(f"[blue]💾 Impostando quota NC {nextcloud_quota} → FS {fs_percentage:.1%} per {username}[/blue]")
    
    quota_manager = QuotaManager()
    if quota_manager.set_quota(username, nextcloud_quota, fs_percentage, path=path):
        # Calcola e mostra quota filesystem risultante
        nc_bytes = quota_manager._parse_size(nextcloud_quota)
        fs_bytes = int(nc_bytes * fs_percentage)
        fs_human = quota_manager._bytes_to_human(fs_bytes)
        rprint(f"[green]✅ Quota impostata: NC {nextcloud_quota} → FS {fs_human}[/green]")
    else:
        rprint("[red]❌ Errore impostazione quota[/red]")


@quota_app.command("show")
def show_quota(
    username: Optional[str] = typer.Argument(None, help="Nome utente (vuoto = tutti)")
):
    """Mostra quota utente/i"""
    if username:
        rprint(f"[blue]💾 Quota per {username}[/blue]")
        quota_manager = QuotaManager()
        info = quota_manager.get_quota(username)
        
        if info:
            table = Table(title=f"Quota {username}")
            table.add_column("Campo", style="cyan")
            table.add_column("Valore", style="white")
            
            for key, value in info.items():
                table.add_row(key.replace("_", " ").title(), str(value or "N/A"))
                
            console.print(table)
        else:
            rprint("[yellow]Nessuna quota trovata[/yellow]")
    else:
        rprint("[blue]💾 Tutte le quote[/blue]")
        quotas = list_all_quotas()
        
        if quotas:
            table = Table(title="Quote Utenti")
            table.add_column("Utente", style="cyan")
            table.add_column("Usato", style="white")
            table.add_column("Limite", style="white")
            table.add_column("Filesystem", style="white")
            
            for user, info in quotas.items():
                table.add_row(
                    user,
                    info.get("used", "N/A"),
                    info.get("soft_limit", "N/A"),
                    info.get("filesystem", "N/A")
                )
                
            console.print(table)
        else:
            rprint("[yellow]Nessuna quota trovata[/yellow]")


@quota_app.command("remove")
def remove_quota(
    username: str = typer.Argument(help="Nome utente")
):
    """Rimuove quota per utente"""
    rprint(f"[blue]💾 Rimuovendo quota per {username}[/blue]")
    
    quota_manager = QuotaManager()
    if quota_manager.remove_quota(username):
        rprint("[green]✅ Quota rimossa[/green]")
    else:
        rprint("[red]❌ Errore rimozione quota[/red]")


# =================== COMANDI SERVIZI ===================

@service_app.command("create-mount")
def create_mount_service(
    username: str = typer.Argument(help="Nome utente"),
    remote: str = typer.Argument(help="Nome remote"),
    mount_point: str = typer.Argument(help="Directory di mount"),
    user: bool = typer.Option(False, "--user", help="Servizio utente invece di system"),
    profile: str = typer.Option("writes", help="Profilo mount (hosting/minimal/writes)")
):
    """Crea servizio systemd per mount automatico con profilo"""
    rprint(f"[blue]⚙️  Creando servizio mount per {username} (profilo: {profile})[/blue]")
    
    # Mostra info profilo
    from .rclone import get_mount_profile_info
    profile_info = get_mount_profile_info(profile)
    if profile_info:
        rprint(f"[cyan]ℹ️  {profile_info['description']}[/cyan]")
    
    systemd_manager = SystemdManager()
    service_name = systemd_manager.create_mount_service(username, remote, mount_point, user, profile)
    
    if service_name:
        rprint(f"[green]✅ Servizio {service_name} creato con profilo {profile}[/green]")
        
        # Chiedi se abilitare subito
        enable = typer.confirm("Abilitare e avviare il servizio ora?")
        if enable:
            if systemd_manager.enable_service(service_name, user):
                rprint("[green]✅ Servizio abilitato e avviato[/green]")
            else:
                rprint("[red]❌ Errore abilitazione servizio[/red]")
    else:
        rprint("[red]❌ Errore creazione servizio[/red]")


@service_app.command("list")
def list_services():
    """Lista servizi nextcloud-wrapper"""
    rprint("[blue]⚙️  Servizi nextcloud-wrapper[/blue]")
    
    systemd_manager = SystemdManager()
    
    # Servizi system
    system_services = systemd_manager.list_nextcloud_services(user=False)
    if system_services:
        rprint("\n[bold]Servizi System:[/bold]")
        table = Table()
        table.add_column("Nome", style="cyan")
        table.add_column("Load", style="white")
        table.add_column("Active", style="white")
        table.add_column("Sub", style="white")
        table.add_column("Descrizione", style="white")
        
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
    user_services = systemd_manager.list_nextcloud_services(user=True)
    if user_services:
        rprint("\n[bold]Servizi User:[/bold]")
        table = Table()
        table.add_column("Nome", style="cyan")
        table.add_column("Load", style="white")
        table.add_column("Active", style="white")
        table.add_column("Sub", style="white")
        table.add_column("Descrizione", style="white")
        
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


@service_app.command("enable")
def enable_service_cmd(
    service_name: str = typer.Argument(help="Nome servizio"),
    user: bool = typer.Option(False, "--user", help="Servizio utente")
):
    """Abilita e avvia servizio"""
    rprint(f"[blue]⚙️  Abilitando servizio {service_name}[/blue]")
    
    systemd_manager = SystemdManager()
    if systemd_manager.enable_service(service_name, user):
        rprint("[green]✅ Servizio abilitato e avviato[/green]")
    else:
        rprint("[red]❌ Errore abilitazione servizio[/red]")


@service_app.command("disable")
def disable_service_cmd(
    service_name: str = typer.Argument(help="Nome servizio"),
    user: bool = typer.Option(False, "--user", help="Servizio utente")
):
    """Disabilita e ferma servizio"""
    rprint(f"[blue]⚙️  Disabilitando servizio {service_name}[/blue]")
    
    systemd_manager = SystemdManager()
    if systemd_manager.disable_service(service_name, user):
        rprint("[green]✅ Servizio disabilitato[/green]")
    else:
        rprint("[red]❌ Errore disabilitazione servizio[/red]")


# =================== COMANDI PRINCIPALI ===================

@app.command()
def config():
    """Mostra configurazione corrente"""
    rprint("[blue]⚙️  Configurazione attuale:[/blue]")
    
    try:
        base_url, admin_user, admin_pass = get_nc_config()
        
        table = Table(title="Configurazione Nextcloud")
        table.add_column("Variabile", style="cyan")
        table.add_column("Valore", style="white")
        
        table.add_row("NC_BASE_URL", base_url)
        table.add_row("NC_ADMIN_USER", admin_user)
        table.add_row("NC_ADMIN_PASS", "***" + admin_pass[-3:])
        
        console.print(table)
        
        # Verifica privilegi sudo
        has_sudo = check_sudo_privileges()
        rprint(f"[bold]Privilegi sudo:[/bold] {'✅ Disponibili' if has_sudo else '❌ Non disponibili'}")
        
        # Info rclone
        from .rclone import RCLONE_CONF
        rprint(f"[bold]Config rclone:[/bold] {RCLONE_CONF}")
        
        # Remotes configurati
        remotes = list_remotes()
        rprint(f"[bold]Remote rclone:[/bold] {len(remotes)} configurati")
        
    except Exception as e:
        rprint(f"[red]❌ Errore configurazione: {e}[/red]")


@app.command()
def setup(
    username: str = typer.Argument(help="Nome utente per setup completo"),
    password: str = typer.Argument(help="Password utente"),
    quota: Optional[str] = typer.Option("100G", help="Quota Nextcloud da assegnare"),
    fs_percentage: float = typer.Option(0.02, "--fs-percentage", help="Percentuale filesystem (default: 2%)"),
    subdomains: List[str] = typer.Option([], "--sub", help="Sottodomini"),
    auto_mount: bool = typer.Option(True, "--mount/--no-mount", help="Configura mount automatico"),
    mount_point: Optional[str] = typer.Option(None, help="Directory di mount custom")
):
    """Setup completo utente con tutte le funzionalità"""
    rprint(f"[bold blue]🚀 Setup completo per: {username}[/bold blue]")
    
    try:
        base_url, _, _ = get_nc_config()
        
        # 1. Crea utente completo
        rprint("[yellow]1️⃣ Creazione utente completo...[/yellow]")
        
        # Simula chiamata create_user con parametri  
        create_user(username, password, subdomains, quota=quota, fs_percentage=fs_percentage)
        
        # 2. Setup mount automatico
        if auto_mount:
            rprint("[yellow]2️⃣ Configurazione mount automatico...[/yellow]")
            
            mount_dir = mount_point or f"/mnt/nextcloud/{username}"
            ensure_dir(mount_dir)
            
            systemd_manager = SystemdManager()
            service_name = systemd_manager.create_mount_service(
                username, username, mount_dir, user=False
            )
            
            if systemd_manager.enable_service(service_name):
                rprint(f"[green]✅ Mount automatico configurato in {mount_dir}[/green]")
            else:
                rprint("[red]❌ Errore configurazione mount automatico[/red]")
        
        # 3. Setup ambiente utente
        rprint("[yellow]3️⃣ Setup ambiente utente...[/yellow]")
        systemd_manager = SystemdManager()
        if systemd_manager.setup_user_environment(username):
            rprint("[green]✅ Ambiente utente configurato[/green]")
        else:
            rprint("[red]❌ Errore setup ambiente utente[/red]")
        
        rprint(f"[bold green]🎉 Setup completo per {username} terminato![/bold green]")
        
        # Riepilogo
        rprint("\n[bold]📋 Riepilogo configurazione:[/bold]")
        rprint(f"• Utente Nextcloud: {username}")
        rprint(f"• Utente Linux: {username}")
        rprint(f"• Remote rclone: {username}")
        rprint(f"• Quota: {quota}")
        if auto_mount:
            rprint(f"• Mount automatico: {mount_dir}")
        if subdomains:
            rprint(f"• Sottodomini: {', '.join(subdomains)}")
        
    except Exception as e:
        rprint(f"[bold red]💥 Errore durante setup: {str(e)}[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    app()
