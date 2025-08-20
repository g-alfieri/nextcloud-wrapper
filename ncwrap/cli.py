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
    create_remote: bool = typer.Option(True, "--remote/--no-remote", help="Crea remote rclone"),
    quota: Optional[str] = typer.Option(None, "--quota", help="Quota utente (es. 5G)")
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
        if create_remote:
            rprint("[yellow]🔗 Creando remote rclone...[/yellow]")
            if add_nextcloud_remote(dominio, base_url, dominio, password):
                rprint("[green]✅ Remote rclone creato[/green]")
            else:
                rprint("[red]❌ Errore creazione remote rclone[/red]")
        
        # 6. Imposta quota
        if quota and not skip_linux:
            rprint(f"[yellow]💾 Impostando quota {quota}...[/yellow]")
            quota_manager = QuotaManager()
            if quota_manager.set_quota(dominio, quota):
                rprint(f"[green]✅ Quota {quota} impostata[/green]")
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
    background: bool = typer.Option(True, "--daemon/--foreground", help="Esegui in background")
):
    """Monta remote rclone"""
    rprint(f"[blue]📁 Montando {remote} in {mount_point}[/blue]")
    
    if mount_remote(remote, mount_point, background):
        rprint("[green]✅ Mount riuscito[/green]")
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


@mount_app.command("list")
def list_mounts():
    """Lista remote configurati"""
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


@mount_app.command("sync")
def sync_cmd(
    source: str = typer.Argument(help="Directory/remote sorgente"),
    dest: str = typer.Argument(help="Directory/remote destinazione"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Solo simulazione"),
    delete: bool = typer.Option(False, "--delete", help="Elimina file extra in destinazione")
):
    """Sincronizza directory con rclone"""
    rprint(f"[blue]🔄 Sincronizzando {source} → {dest}[/blue]")
    
    if dry_run:
        rprint("[yellow]🔍 Modalità dry-run (simulazione)[/yellow]")
    
    if sync_directories(source, dest, dry_run, delete):
        rprint("[green]✅ Sincronizzazione completata[/green]")
    else:
        rprint("[red]❌ Errore durante sincronizzazione[/red]")


# =================== COMANDI QUOTA ===================

@quota_app.command("set")
def set_quota(
    username: str = typer.Argument(help="Nome utente"),
    size: str = typer.Argument(help="Dimensione quota (es. 5G, 1T)"),
    path: str = typer.Option("/home", help="Path base per btrfs")
):
    """Imposta quota per utente"""
    rprint(f"[blue]💾 Impostando quota {size} per {username}[/blue]")
    
    quota_manager = QuotaManager()
    if quota_manager.set_quota(username, size, path=path):
        rprint("[green]✅ Quota impostata con successo[/green]")
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
    user: bool = typer.Option(False, "--user", help="Servizio utente invece di system")
):
    """Crea servizio systemd per mount automatico"""
    rprint(f"[blue]⚙️  Creando servizio mount per {username}[/blue]")
    
    systemd_manager = SystemdManager()
    service_name = systemd_manager.create_mount_service(username, remote, mount_point, user)
    
    if service_name:
        rprint(f"[green]✅ Servizio {service_name} creato[/green]")
        
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
    quota: Optional[str] = typer.Option("5G", help="Quota da assegnare"),
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
        create_user(username, password, subdomains, quota=quota)
        
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
