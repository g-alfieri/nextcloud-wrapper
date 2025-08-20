"""
CLI per nextcloud-wrapper - gestione utenti, cartelle e sincronizzazione
"""
import typer
import sys
from typing import List, Optional
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from .api import (
    create_nc_user, 
    dav_probe, 
    ensure_tree, 
    check_user_exists,
    list_directory,
    get_nc_config
)
from .system import (
    create_linux_user, 
    sync_passwords, 
    get_user_info,
    check_sudo_privileges,
    user_exists
)

app = typer.Typer(
    name="nextcloud-wrapper",
    help="Wrapper per gestione utenti e cartelle Nextcloud + Linux"
)
console = Console()


@app.command()
def crea_utente(
    dominio: str = typer.Argument(help="Dominio/username (es. casacialde.com)"),
    password: str = typer.Argument(help="Password utente"),
    subdomini: List[str] = typer.Option([], "--sub", help="Sottodomini da creare"),
    skip_linux: bool = typer.Option(False, "--skip-linux", help="Non creare utente Linux"),
    skip_test: bool = typer.Option(False, "--skip-test", help="Non testare login WebDAV")
):
    """
    Crea nuovo utente completo: Nextcloud + Linux + struttura cartelle
    """
    rprint(f"[bold blue]🚀 Creazione utente: {dominio}[/bold blue]")
    
    try:
        # Verifica configurazione
        get_nc_config()
        
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
        
        # Mostra risultati creazione cartelle
        for path, status in results.items():
            if status == 201:
                rprint(f"[green]✅ Creata: {path}[/green]")
            elif status == 405:
                rprint(f"[yellow]📁 Già esistente: {path}[/yellow]")
            else:
                rprint(f"[red]❌ Errore {status}: {path}[/red]")
        
        # 4. Crea utente Linux (opzionale)
        if not skip_linux:
            rprint("[yellow]🐧 Creando utente Linux...[/yellow]")
            if user_exists(dominio):
                rprint(f"[yellow]⚠️  Utente Linux {dominio} già esistente[/yellow]")
            else:
                if create_linux_user(dominio, password):
                    rprint("[green]✅ Utente Linux creato[/green]")
                else:
                    rprint("[red]❌ Errore creazione utente Linux[/red]")
        
        rprint(f"[bold green]🎉 Utente {dominio} configurato con successo![/bold green]")
        
    except Exception as e:
        rprint(f"[bold red]💥 Errore: {str(e)}[/bold red]")
        sys.exit(1)


@app.command()
def test_login(
    utente: str = typer.Argument(help="Username da testare"),
    password: str = typer.Argument(help="Password da testare")
):
    """
    Testa login WebDAV di un utente
    """
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


@app.command()
def cambia_password(
    utente: str = typer.Argument(help="Username"),
    nuova_password: str = typer.Argument(help="Nuova password"),
    solo_nextcloud: bool = typer.Option(False, "--nc-only", help="Solo Nextcloud, non Linux")
):
    """
    Cambia password utente (Nextcloud + Linux sincronizzati)
    """
    rprint(f"[blue]🔑 Aggiornamento password per: {utente}[/blue]")
    
    try:
        if solo_nextcloud:
            from .api import set_nc_password
            set_nc_password(utente, nuova_password)
            rprint("[green]✅ Password Nextcloud aggiornata[/green]")
        else:
            # Verifica privilegi sudo
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


@app.command()
def lista_cartelle(
    utente: str = typer.Argument(help="Username"),
    password: str = typer.Argument(help="Password"),
    percorso: str = typer.Option("", "--path", help="Percorso da listare (default: root)")
):
    """
    Lista contenuto cartelle utente via WebDAV
    """
    rprint(f"[blue]📁 Listando cartelle per: {utente} (path: /{percorso})[/blue]")
    
    try:
        status_code, xml_response = list_directory(utente, password, percorso)
        
        if status_code in (200, 207):
            rprint("[green]✅ Lista recuperata[/green]")
            # Parsing semplificato del XML (per demo)
            if "<d:displayname>" in xml_response:
                rprint("\n[bold]Cartelle trovate:[/bold]")
                lines = xml_response.split('\n')
                for line in lines:
                    if '<d:displayname>' in line:
                        folder_name = line.strip().replace('<d:displayname>', '').replace('</d:displayname>', '')
                        if folder_name and folder_name != utente:  # Skip root
                            rprint(f"  📁 {folder_name}")
            else:
                rprint("[yellow]Nessuna cartella trovata o formato imprevisto[/yellow]")
        else:
            rprint(f"[red]❌ Errore {status_code}[/red]")
            
    except Exception as e:
        rprint(f"[red]💥 Errore: {str(e)}[/red]")
        sys.exit(1)


@app.command()
def info_utente(
    utente: str = typer.Argument(help="Username da verificare")
):
    """
    Mostra informazioni su utente Nextcloud e Linux
    """
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


@app.command()
def config():
    """
    Mostra configurazione corrente
    """
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
        
    except Exception as e:
        rprint(f"[red]❌ Errore configurazione: {e}[/red]")


if __name__ == "__main__":
    app()