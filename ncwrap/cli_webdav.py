"""
CLI WebDAV - Gestione mount WebDAV
"""
import typer
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from .webdav import WebDAVMountManager
from .api import test_webdav_connectivity, test_webdav_login, list_webdav_directory, get_nc_config
from .utils import check_sudo_privileges, is_mounted, bytes_to_human, get_directory_size, get_available_space

webdav_app = typer.Typer(help="Gestione mount WebDAV")
console = Console()


@webdav_app.command("mount")
def webdav_mount(
    username: str = typer.Argument(help="Nome utente"),
    password: str = typer.Argument(help="Password"),
    mount_point: str = typer.Option(None, help="Directory mount (default: /home/username)"),
    auto_service: bool = typer.Option(True, "--service/--no-service", help="Crea servizio systemd")
):
    """Monta WebDAV Nextcloud in directory"""
    if not mount_point:
        mount_point = f"/home/{username}"
    
    rprint(f"[blue]🔗 Mount WebDAV {username} → {mount_point}[/blue]")
    
    if not check_sudo_privileges():
        rprint("[red]❌ Privilegi sudo richiesti[/red]")
        sys.exit(1)
    
    try:
        webdav_manager = WebDAVMountManager()
        
        # Installa e configura davfs2
        if not webdav_manager.install_davfs2():
            sys.exit(1)
        
        if not webdav_manager.configure_davfs2():
            sys.exit(1)
        
        # Mount WebDAV
        if webdav_manager.mount_webdav_home(username, password, mount_point):
            rprint(f"[green]✅ WebDAV montato: {mount_point}[/green]")
            
            # Crea servizio automatico
            if auto_service:
                try:
                    service_name = webdav_manager.create_systemd_service(username, password, mount_point)
                    if webdav_manager.enable_service(service_name):
                        rprint(f"[green]✅ Servizio automatico: {service_name}[/green]")
                except Exception as e:
                    rprint(f"[yellow]⚠️ Avviso servizio: {e}[/yellow]")
        else:
            rprint("[red]❌ Errore mount WebDAV[/red]")
            sys.exit(1)
            
    except Exception as e:
        rprint(f"[red]❌ Errore: {e}[/red]")
        sys.exit(1)


@webdav_app.command("unmount")
def webdav_unmount(
    mount_point: str = typer.Argument(help="Directory da smontare")
):
    """Smonta WebDAV"""
    rprint(f"[blue]📁 Smontando WebDAV: {mount_point}[/blue]")
    
    if not check_sudo_privileges():
        rprint("[red]❌ Privilegi sudo richiesti[/red]")
        sys.exit(1)
    
    try:
        webdav_manager = WebDAVMountManager()
        if webdav_manager.unmount_webdav(mount_point):
            rprint("[green]✅ WebDAV smontato[/green]")
        else:
            rprint("[red]❌ Errore unmount[/red]")
            
    except Exception as e:
        rprint(f"[red]❌ Errore: {e}[/red]")


@webdav_app.command("status")
def webdav_status():
    """Mostra status di tutti i mount WebDAV"""
    rprint("[blue]📊 Status mount WebDAV[/blue]")
    
    webdav_manager = WebDAVMountManager()
    mounts = webdav_manager.list_webdav_mounts()
    
    if mounts:
        table = Table(title="Mount WebDAV")
        table.add_column("URL", style="blue")
        table.add_column("Mount Point", style="cyan")
        table.add_column("Options", style="white")
        table.add_column("Status", style="green")
        
        for mount in mounts:
            # Verifica se mount è ancora attivo
            mount_point = mount.get("mountpoint", "")
            status = "🟢 Attivo" if is_mounted(mount_point) else "🔴 Inattivo"
            
            table.add_row(
                mount.get("url", ""),
                mount_point,
                mount.get("options", ""),
                status
            )
            
        console.print(table)
    else:
        rprint("[yellow]Nessun mount WebDAV trovato[/yellow]")


@webdav_app.command("test")
def webdav_test(
    username: str = typer.Argument(help="Nome utente"),
    password: str = typer.Argument(help="Password")
):
    """Testa connettività WebDAV senza mount"""
    rprint(f"[blue]🧪 Test connettività WebDAV per {username}[/blue]")
    
    try:
        if test_webdav_connectivity(username, password):
            rprint("[green]✅ Connettività WebDAV OK[/green]")
            
            # Test dettagliato
            status_code, response = test_webdav_login(username, password)
            rprint(f"[cyan]Status Code: {status_code}[/cyan]")
            
            # Lista directory root
            list_status, xml_content = list_webdav_directory(username, password)
            if list_status in (200, 207):
                rprint("[green]✅ Listing directory OK[/green]")
            else:
                rprint(f"[yellow]⚠️ Listing status: {list_status}[/yellow]")
        else:
            rprint("[red]❌ Test connettività fallito[/red]")
            
    except Exception as e:
        rprint(f"[red]❌ Errore test: {e}[/red]")


@webdav_app.command("install")
def install_davfs2():
    """Installa e configura davfs2"""
    rprint("[blue]📦 Installazione e configurazione davfs2[/blue]")
    
    if not check_sudo_privileges():
        rprint("[red]❌ Privilegi sudo richiesti[/red]")
        sys.exit(1)
    
    try:
        webdav_manager = WebDAVMountManager()
        
        if webdav_manager.install_davfs2():
            rprint("[green]✅ davfs2 installato[/green]")
        else:
            rprint("[red]❌ Errore installazione davfs2[/red]")
            sys.exit(1)
        
        if webdav_manager.configure_davfs2():
            rprint("[green]✅ davfs2 configurato[/green]")
        else:
            rprint("[red]❌ Errore configurazione davfs2[/red]")
            
    except Exception as e:
        rprint(f"[red]❌ Errore: {e}[/red]")


@webdav_app.command("config")
def show_webdav_config():
    """Mostra configurazione davfs2 corrente"""
    rprint("[blue]⚙️ Configurazione davfs2[/blue]")
    
    try:
        from pathlib import Path
        
        # File configurazione davfs2
        davfs_conf = Path("/etc/davfs2/davfs2.conf")
        secrets_file = Path("/etc/davfs2/secrets")
        
        if davfs_conf.exists():
            rprint(f"[green]✅ Configurazione: {davfs_conf}[/green]")
        else:
            rprint(f"[red]❌ File configurazione non trovato: {davfs_conf}[/red]")
        
        if secrets_file.exists():
            rprint(f"[green]✅ File secrets: {secrets_file}[/green]")
        else:
            rprint(f"[red]❌ File secrets non trovato: {secrets_file}[/red]")
        
        # Mostra cache directory
        cache_dir = Path("/var/cache/davfs2")
        if cache_dir.exists():
            rprint(f"[green]✅ Cache directory: {cache_dir}[/green]")
        else:
            rprint(f"[yellow]⚠️ Cache directory non trovata: {cache_dir}[/yellow]")
        
    except Exception as e:
        rprint(f"[red]❌ Errore: {e}[/red]")


@webdav_app.command("space")
def check_webdav_space(
    username: str = typer.Argument(help="Nome utente"),
    mount_point: str = typer.Option(None, "--mount", help="Mount point da verificare (default: /home/username)"),
    detailed: bool = typer.Option(False, "--detailed", help="Mostra analisi dettagliata per cartella")
):
    """Verifica spazio utilizzato su WebDAV e mount point locale"""
    if not mount_point:
        mount_point = f"/home/{username}"
    
    rprint(f"[blue]📊 Verifica spazio WebDAV per: {username}[/blue]")
    
    try:
        # Verifica spazio mount point locale
        if is_mounted(mount_point):
            rprint(f"[green]✅ Mount point attivo: {mount_point}[/green]")
            
            # Spazio utilizzato localmente (mount WebDAV)
            local_used = get_directory_size(mount_point)
            local_available = get_available_space(mount_point)
            
            table = Table(title=f"Spazio WebDAV - {username}")
            table.add_column("Posizione", style="cyan")
            table.add_column("Spazio Utilizzato", style="white")
            table.add_column("Spazio Disponibile", style="white")
            table.add_column("Status", style="green")
            
            table.add_row(
                f"Mount locale\n{mount_point}",
                bytes_to_human(local_used),
                bytes_to_human(local_available),
                "🟢 WebDAV attivo"
            )
            
            console.print(table)
            
            # Analisi dettagliata se richiesta
            if detailed:
                rprint("\n[blue]📋 Analisi dettagliata per cartella:[/blue]")
                
                from pathlib import Path
                mount_path = Path(mount_point)
                
                folder_sizes = []
                try:
                    for item in mount_path.iterdir():
                        if item.is_dir() and not item.name.startswith('.'):
                            try:
                                dir_size = get_directory_size(str(item))
                                folder_sizes.append({
                                    "name": item.name,
                                    "size": dir_size
                                })
                            except:
                                continue
                    
                    # Ordina per dimensione decrescente
                    folder_sizes.sort(key=lambda x: x["size"], reverse=True)
                    
                    if folder_sizes:
                        folder_table = Table(title="Cartelle per Dimensione")
                        folder_table.add_column("Cartella", style="cyan")
                        folder_table.add_column("Dimensione", style="white")
                        folder_table.add_column("% del totale", style="yellow")
                        
                        for folder in folder_sizes[:10]:  # Top 10
                            percentage = (folder["size"] / local_used * 100) if local_used > 0 else 0
                            folder_table.add_row(
                                folder["name"],
                                bytes_to_human(folder["size"]),
                                f"{percentage:.1f}%"
                            )
                        
                        console.print(folder_table)
                    else:
                        rprint("[yellow]Nessuna cartella trovata per l'analisi[/yellow]")
                        
                except Exception as e:
                    rprint(f"[red]❌ Errore analisi cartelle: {e}[/red]")
        else:
            rprint(f"[red]❌ Mount point non attivo: {mount_point}[/red]")
            rprint(f"💡 Usa: nextcloud-wrapper webdav mount {username} <password>")
            
        # Test connettività WebDAV diretto (opzionale)
        rprint("\n[blue]🔍 Test connettività WebDAV diretta...[/blue]")
        
        base_url, _, _ = get_nc_config()
        webdav_url = f"{base_url}/remote.php/dav/files/{username}/"
        rprint(f"[cyan]URL WebDAV: {webdav_url}[/cyan]")
        
        # Nota: non possiamo testare senza password, quindi solo info
        rprint("[yellow]💡 Per test completo WebDAV usa: nextcloud-wrapper webdav test <username> <password>[/yellow]")
        
    except Exception as e:
        rprint(f"[red]💥 Errore verifica spazio: {str(e)}[/red]")
        sys.exit(1)


@webdav_app.command("compare")
def compare_webdav_space(
    username1: str = typer.Argument(help="Primo utente da confrontare"),
    username2: str = typer.Argument(help="Secondo utente da confrontare"),
    mount_base: str = typer.Option("/home", help="Directory base mount (default: /home)")
):
    """Confronta spazio utilizzato tra due utenti WebDAV"""
    rprint(f"[blue]⚖️ Confronto spazio WebDAV: {username1} vs {username2}[/blue]")
    
    try:
        users_data = []
        
        for username in [username1, username2]:
            mount_point = f"{mount_base}/{username}"
            
            if is_mounted(mount_point):
                used_space = get_directory_size(mount_point)
                available_space = get_available_space(mount_point)
                status = "🟢 Attivo"
            else:
                used_space = 0
                available_space = 0
                status = "🔴 Non montato"
            
            users_data.append({
                "username": username,
                "mount_point": mount_point,
                "used": used_space,
                "available": available_space,
                "status": status
            })
        
        # Tabella confronto
        table = Table(title="Confronto Spazio WebDAV")
        table.add_column("Utente", style="cyan")
        table.add_column("Mount Point", style="white")
        table.add_column("Spazio Utilizzato", style="white")
        table.add_column("Spazio Disponibile", style="white")
        table.add_column("Status", style="green")
        
        for data in users_data:
            table.add_row(
                data["username"],
                data["mount_point"],
                bytes_to_human(data["used"]),
                bytes_to_human(data["available"]),
                data["status"]
            )
        
        console.print(table)
        
        # Calcola differenza se entrambi sono montati
        if all(d["used"] > 0 for d in users_data):
            diff_bytes = abs(users_data[0]["used"] - users_data[1]["used"])
            bigger_user = users_data[0]["username"] if users_data[0]["used"] > users_data[1]["used"] else users_data[1]["username"]
            
            rprint(f"\n[bold]📊 Differenza di spazio:[/bold]")
            rprint(f"• {bigger_user} usa {bytes_to_human(diff_bytes)} in più")
            
            # Percentuale differenza
            total_space = users_data[0]["used"] + users_data[1]["used"]
            if total_space > 0:
                percentage = (diff_bytes / total_space) * 100
                rprint(f"• Differenza percentuale: {percentage:.1f}%")
        
    except Exception as e:
        rprint(f"[red]💥 Errore confronto: {str(e)}[/red]")
        sys.exit(1)


@webdav_app.command("df")
def webdav_disk_usage(
    mount_base: str = typer.Option("/home", help="Directory base mount (default: /home)")
):
    """Mostra uso disco per tutti i mount WebDAV (stile df -h)"""
    rprint("[blue]💽 Uso disco mount WebDAV[/blue]")
    
    try:
        webdav_manager = WebDAVMountManager()
        active_mounts = webdav_manager.list_webdav_mounts()
        
        if not active_mounts:
            rprint("[yellow]Nessun mount WebDAV attivo[/yellow]")
            return
        
        table = Table(title="Uso Disco WebDAV (df -h style)")
        table.add_column("URL WebDAV", style="blue")
        table.add_column("Mount Point", style="cyan")
        table.add_column("Utilizzato", style="white")
        table.add_column("Disponibile", style="white")
        table.add_column("Uso%", style="yellow")
        table.add_column("Status", style="green")
        
        total_used = 0
        total_available = 0
        
        for mount in active_mounts:
            mount_point = mount.get("mountpoint", "")
            url = mount.get("url", "")
            
            if is_mounted(mount_point):
                used_space = get_directory_size(mount_point)
                available_space = get_available_space(mount_point)
                total_space = used_space + available_space
                
                # Calcola percentuale uso
                if total_space > 0:
                    usage_percent = (used_space / total_space) * 100
                    usage_str = f"{usage_percent:.1f}%"
                else:
                    usage_str = "0.0%"
                
                status = "🟢 Attivo"
                total_used += used_space
                total_available += available_space
            else:
                used_space = 0
                available_space = 0
                usage_str = "N/A"
                status = "🔴 Inattivo"
            
            table.add_row(
                url[:50] + "..." if len(url) > 50 else url,
                mount_point,
                bytes_to_human(used_space),
                bytes_to_human(available_space),
                usage_str,
                status
            )
        
        console.print(table)
        
        # Riepilogo totale
        if total_used > 0 or total_available > 0:
            rprint(f"\n[bold]📊 Totale WebDAV:[/bold]")
            rprint(f"• Spazio utilizzato: {bytes_to_human(total_used)}")
            rprint(f"• Spazio disponibile: {bytes_to_human(total_available)}")
            
            grand_total = total_used + total_available
            if grand_total > 0:
                overall_usage = (total_used / grand_total) * 100
                rprint(f"• Uso complessivo: {overall_usage:.1f}%")
        
    except Exception as e:
        rprint(f"[red]💥 Errore uso disco: {str(e)}[/red]")
        sys.exit(1)


@webdav_app.command("cache")
def show_cache_info():
    """Mostra informazioni e stato della cache davfs2"""
    rprint("[blue]🖼️ Cache davfs2[/blue]")
    
    try:
        from pathlib import Path
        import os
        
        # Directory cache
        cache_dir = Path("/var/cache/davfs2")
        config_file = Path("/etc/davfs2/davfs2.conf")
        
        # Tabella informazioni configurazione
        config_table = Table(title="Configurazione Cache davfs2")
        config_table.add_column("Parametro", style="cyan")
        config_table.add_column("Valore Configurato", style="white")
        config_table.add_column("Descrizione", style="yellow")
        
        # Leggi configurazione se esiste
        cache_size = "Non trovato"
        table_size = "Non trovato"
        buf_size = "Non trovato"
        
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    config_content = f.read()
                
                import re
                # Estrai valori configurazione
                cache_match = re.search(r'^cache_size\s+(\d+)', config_content, re.MULTILINE)
                if cache_match:
                    cache_mb = int(cache_match.group(1))
                    cache_size = f"{cache_mb} MB ({cache_mb/1024:.1f} GB)"
                
                table_match = re.search(r'^table_size\s+(\d+)', config_content, re.MULTILINE)
                if table_match:
                    table_size = f"{table_match.group(1)} file"
                
                buf_match = re.search(r'^buf_size\s+(\d+)', config_content, re.MULTILINE)
                if buf_match:
                    buf_size = f"{buf_match.group(1)} KiB"
                    
            except Exception as e:
                rprint(f"[yellow]⚠️ Errore lettura config: {e}[/yellow]")
        
        config_table.add_row(
            "cache_size",
            cache_size,
            "Dimensione cache disco"
        )
        config_table.add_row(
            "table_size",
            table_size,
            "N. max file indicizzati"
        )
        config_table.add_row(
            "buf_size",
            buf_size,
            "Buffer I/O"
        )
        
        console.print(config_table)
        
        # Informazioni cache directory
        rprint("\n[blue]📋 Stato Cache Directory:[/blue]")
        
        if cache_dir.exists():
            # Calcola dimensione cache attuale
            total_size = 0
            file_count = 0
            
            try:
                for root, dirs, files in os.walk(cache_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            file_size = os.path.getsize(file_path)
                            total_size += file_size
                            file_count += 1
                        except:
                            continue
            except Exception as e:
                rprint(f"[red]❌ Errore calcolo dimensioni: {e}[/red]")
                return
            
            # Informazioni spazio
            try:
                stat = os.statvfs(str(cache_dir))
                available_space = stat.f_bavail * stat.f_frsize
            except:
                available_space = 0
            
            cache_table = Table(title="Stato Cache Attuale")
            cache_table.add_column("Metrica", style="cyan")
            cache_table.add_column("Valore", style="white")
            cache_table.add_column("Status", style="green")
            
            cache_table.add_row(
                "Directory cache",
                str(cache_dir),
                "🟢 Esistente"
            )
            
            cache_table.add_row(
                "Spazio utilizzato",
                bytes_to_human(total_size),
                "📊 Attuale"
            )
            
            cache_table.add_row(
                "File in cache",
                str(file_count),
                "📁 Conteggio"
            )
            
            cache_table.add_row(
                "Spazio disponibile",
                bytes_to_human(available_space),
                "💾 Filesystem"
            )
            
            # Calcola percentuale uso se conosciamo la config
            if cache_size != "Non trovato" and "MB" in cache_size:
                try:
                    configured_mb = int(re.search(r'(\d+)', cache_size).group(1))
                    configured_bytes = configured_mb * 1024 * 1024
                    usage_percent = (total_size / configured_bytes) * 100
                    
                    cache_table.add_row(
                        "Uso cache (%)",
                        f"{usage_percent:.1f}%",
                        "📈 Percentuale"
                    )
                except:
                    pass
            
            console.print(cache_table)
            
            # Avvisi e raccomandazioni
            if total_size > 5 * 1024 * 1024 * 1024:  # > 5GB
                rprint("\n[bold yellow]📊 Cache grande rilevata:[/bold yellow]")
                rprint(f"• La cache è {bytes_to_human(total_size)}")
                rprint(f"• Considera pulizia se le prestazioni sono lente")
                rprint(f"• Usa: nextcloud-wrapper webdav cleanup")
            
            if file_count > 10000:
                rprint("\n[bold cyan]🗄 Molti file in cache:[/bold cyan]")
                rprint(f"• {file_count:,} file indicizzati")
                rprint(f"• Prestazioni ottimali con cache grande")
            
        else:
            rprint(f"[red]❌ Directory cache non trovata: {cache_dir}[/red]")
            rprint("💡 Esegui: nextcloud-wrapper webdav install")
        
        # Suggerimenti ottimizzazione
        rprint("\n[bold blue]🚀 Suggerimenti ottimizzazione:[/bold blue]")
        rprint("• Cache 10GB ottima per uso intensivo")
        rprint("• 16k file indicizzati per prestazioni elevate")
        rprint("• Monitora spazio disco disponibile")
        rprint("• Pulizia periodica se cache cresce troppo")
        
    except Exception as e:
        rprint(f"[red]💥 Errore info cache: {str(e)}[/red]")
        sys.exit(1)


@webdav_app.command("reconfigure")
def reconfigure_davfs2(
    cache_gb: int = typer.Option(10, "--cache-gb", help="Dimensione cache in GB"),
    table_size: int = typer.Option(16384, "--table-size", help="Numero max file indicizzati"),
    buf_size: int = typer.Option(64, "--buf-size", help="Buffer I/O in KiB")
):
    """Riconfigura davfs2 con nuovi parametri ottimizzati"""
    rprint(f"[blue]⚙️ Riconfigurazione davfs2[/blue]")
    rprint(f"Cache: {cache_gb}GB, File indicizzati: {table_size:,}, Buffer: {buf_size}KiB")
    
    if not check_sudo_privileges():
        rprint("[red]❌ Privilegi sudo richiesti[/red]")
        sys.exit(1)
    
    try:
        # Aggiorna variabili ambiente temporanee per questa configurazione
        import os
        os.environ["NC_WEBDAV_CACHE_SIZE"] = str(cache_gb * 1024)  # Converti GB in MB
        os.environ["NC_WEBDAV_TABLE_SIZE"] = str(table_size)
        os.environ["NC_WEBDAV_BUF_SIZE"] = str(buf_size)
        
        webdav_manager = WebDAVMountManager()
        
        # Mostra configurazione attuale prima della modifica
        config_file = Path("/etc/davfs2/davfs2.conf")
        if config_file.exists():
            rprint("[yellow]📋 Configurazione attuale:[/yellow]")
            try:
                with open(config_file, 'r') as f:
                    config_content = f.read()
                
                import re
                current_cache = re.search(r'^cache_size\s+(\d+)', config_content, re.MULTILINE)
                current_table = re.search(r'^table_size\s+(\d+)', config_content, re.MULTILINE)
                current_buf = re.search(r'^buf_size\s+(\d+)', config_content, re.MULTILINE)
                
                if current_cache:
                    current_cache_gb = int(current_cache.group(1)) / 1024
                    rprint(f"• Cache attuale: {current_cache_gb:.1f}GB")
                if current_table:
                    rprint(f"• File indicizzati attuali: {current_table.group(1)}")
                if current_buf:
                    rprint(f"• Buffer attuale: {current_buf.group(1)}KiB")
                    
            except Exception as e:
                rprint(f"[yellow]⚠️ Errore lettura config attuale: {e}[/yellow]")
        
        # Verifica mount attivi prima della riconfigurazione
        active_mounts = webdav_manager.list_webdav_mounts()
        if active_mounts:
            rprint(f"[yellow]⚠️ {len(active_mounts)} mount WebDAV attivi rilevati[/yellow]")
            rprint("Questa operazione potrebbe richiedere il restart dei mount")
            
            from rich.prompt import Confirm
            if not Confirm.ask("Continuare con la riconfigurazione?"):
                rprint("[cyan]Operazione annullata[/cyan]")
                return
        
        # Applica nuova configurazione
        if webdav_manager.configure_davfs2():
            rprint(f"[green]✅ Configurazione davfs2 aggiornata[/green]")
            
            # Mostra nuova configurazione
            rprint(f"[bold green]🆕 Nuova configurazione:[/bold green]")
            rprint(f"• Cache: {cache_gb}GB ({cache_gb * 1024}MB)")
            rprint(f"• File indicizzati: {table_size:,}")
            rprint(f"• Buffer I/O: {buf_size}KiB")
            
            # Suggerimenti post-configurazione
            rprint(f"\n[bold blue]💡 Suggerimenti:[/bold blue]")
            
            if active_mounts:
                rprint("• Considera restart mount per applicare modifiche:")
                for mount in active_mounts:
                    mount_point = mount.get("mountpoint", "")
                    if mount_point:
                        # Estrai username dal mount point (assuming /home/username pattern)
                        import os
                        username = os.path.basename(mount_point)
                        rprint(f"  - nextcloud-wrapper webdav unmount {mount_point}")
                        rprint(f"  - nextcloud-wrapper webdav mount {username} <password>")
            
            rprint("• Monitora cache con: nextcloud-wrapper webdav cache")
            rprint("• Pulizia cache: nextcloud-wrapper webdav cleanup")
            rprint(f"• Cache ottimizzata per {table_size:,} file")
            
            # Verifica spazio disco necessario
            try:
                cache_dir = Path("/var/cache/davfs2")
                if cache_dir.exists():
                    import os
                    stat = os.statvfs(str(cache_dir))
                    available_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
                    
                    if available_gb < cache_gb:
                        rprint(f"\n[bold yellow]⚠️ Avviso spazio disco:[/bold yellow]")
                        rprint(f"• Spazio disponibile: {available_gb:.1f}GB")
                        rprint(f"• Cache configurata: {cache_gb}GB")
                        rprint(f"• Potrebbe non esserci abbastanza spazio")
                    else:
                        rprint(f"\n[green]✅ Spazio disco sufficiente: {available_gb:.1f}GB disponibili[/green]")
                        
            except Exception:
                rprint(f"\n[yellow]⚠️ Impossibile verificare spazio disco[/yellow]")
            
        else:
            rprint("[red]❌ Errore aggiornamento configurazione[/red]")
            sys.exit(1)
            
    except Exception as e:
        rprint(f"[red]💥 Errore riconfigurazione: {str(e)}[/red]")
        sys.exit(1)


@webdav_app.command("cleanup")
def cleanup_cache():
    """Pulisce cache davfs2"""
    rprint("[blue]🧹 Pulizia cache davfs2[/blue]")
    
    if not check_sudo_privileges():
        rprint("[red]❌ Privilegi sudo richiesti[/red]")
        sys.exit(1)
    
    try:
        from pathlib import Path
        import shutil
        
        cache_dir = Path("/var/cache/davfs2")
        if cache_dir.exists():
            # Calcola dimensione prima
            total_size = sum(f.stat().st_size for f in cache_dir.rglob('*') if f.is_file())
            
            if total_size > 0:
                from .utils import bytes_to_human
                rprint(f"[yellow]Cache corrente: {bytes_to_human(total_size)}[/yellow]")
                
                # Rimuovi file cache
                for item in cache_dir.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir() and item.name != "lost+found":
                        shutil.rmtree(item)
                
                rprint("[green]✅ Cache pulita[/green]")
            else:
                rprint("[yellow]Cache già vuota[/yellow]")
        else:
            rprint("[yellow]Directory cache non trovata[/yellow]")
            
    except Exception as e:
        rprint(f"[red]❌ Errore pulizia cache: {e}[/red]")
