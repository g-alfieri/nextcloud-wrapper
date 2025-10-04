#!/usr/bin/env python3
"""
Script per identificare e rimuovere servizi nextcloud-wrapper obsoleti
"""
import subprocess
import sys
import json
from pathlib import Path
from typing import Dict, List, Set
from rich.console import Console
from rich.table import Table
from rich import print as rprint
from rich.prompt import Confirm

console = Console()

class ObsoleteServiceCleaner:
    """Gestore pulizia servizi obsoleti nextcloud-wrapper"""
    
    def __init__(self):
        self.system_dir = Path("/etc/systemd/system")
        self.user_dir = Path.home() / ".config/systemd/user"
        
        # Pattern servizi nextcloud noti
        self.known_patterns = {
            "webdav-home-*": "Mount WebDAV home directory",
            "nextcloud-wrapper-*": "Servizi nextcloud-wrapper generici", 
            "nextcloud-sync-*": "Servizi sync",
            "nextcloud-monitor-*": "Servizi monitoring",
            "nextcloud-backup-*": "Servizi backup (obsoleti)",
            "rclone-mount-*": "Mount rclone (possibili duplicati)",
        }
        
        # Servizi che sicuramente sono obsoleti
        self.definitely_obsolete = {
            "nextcloud-backup-",  # Backup ora gestito esternamente
            "nextcloud-old-",     # Pattern vecchi
            "webdav-legacy-",     # WebDAV legacy
        }
        
    def run_cmd(self, cmd: List[str], check: bool = True) -> str:
        """Esegue comando e ritorna output"""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=check)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            if not check:
                return ""
            raise RuntimeError(f"Comando fallito: {' '.join(cmd)}\nErrore: {e.stderr}")

    def discover_all_nextcloud_services(self) -> Dict[str, List[Dict]]:
        """Scopre tutti i servizi nextcloud presenti nel sistema"""
        services = {"system": [], "user": []}
        
        # Servizi system
        try:
            cmd = ["systemctl", "list-units", "--all", "nextcloud-*", "webdav-*", "rclone-*", "--no-pager", "--no-legend"]
            output = self.run_cmd(cmd, check=False)
            
            for line in output.split('\n'):
                if line.strip() and any(pattern in line for pattern in ["nextcloud-", "webdav-", "rclone-"]):
                    parts = line.split()
                    if len(parts) >= 4:
                        service_name = parts[0].replace('.service', '')
                        services["system"].append({
                            "name": service_name,
                            "load": parts[1], 
                            "active": parts[2],
                            "sub": parts[3],
                            "description": " ".join(parts[4:]) if len(parts) > 4 else "",
                            "file_exists": self._check_service_file_exists(service_name, user=False)
                        })
        except Exception as e:
            console.print(f"[yellow]Warning: Errore lettura servizi system: {e}[/yellow]")

        # Servizi user  
        try:
            cmd = ["systemctl", "--user", "list-units", "--all", "nextcloud-*", "webdav-*", "rclone-*", "--no-pager", "--no-legend"]
            output = self.run_cmd(cmd, check=False)
            
            for line in output.split('\n'):
                if line.strip() and any(pattern in line for pattern in ["nextcloud-", "webdav-", "rclone-"]):
                    parts = line.split()
                    if len(parts) >= 4:
                        service_name = parts[0].replace('.service', '')
                        services["user"].append({
                            "name": service_name,
                            "load": parts[1],
                            "active": parts[2], 
                            "sub": parts[3],
                            "description": " ".join(parts[4:]) if len(parts) > 4 else "",
                            "file_exists": self._check_service_file_exists(service_name, user=True)
                        })
        except Exception as e:
            console.print(f"[yellow]Warning: Errore lettura servizi user: {e}[/yellow]")
            
        return services

    def _check_service_file_exists(self, service_name: str, user: bool = False) -> bool:
        """Verifica se il file del servizio esiste"""
        service_dir = self.user_dir if user else self.system_dir
        service_file = service_dir / f"{service_name}.service"
        return service_file.exists()

    def analyze_services(self, services: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
        """Analizza i servizi per identificare quelli obsoleti"""
        analysis = {
            "definitely_obsolete": [],
            "probably_obsolete": [],
            "orphaned_files": [],
            "active_important": [],
            "unknown": []
        }
        
        # Analizza servizi system e user
        for service_type in ["system", "user"]:
            for service in services[service_type]:
                service_name = service["name"]
                is_user = service_type == "user"
                
                # Aggiungi tipo per riferimento
                service["type"] = service_type
                
                # 1. Sicuramente obsoleti (pattern noti)
                if any(obsolete in service_name for obsolete in self.definitely_obsolete):
                    analysis["definitely_obsolete"].append(service)
                    continue
                
                # 2. Probabilmente obsoleti (non attivi + load error)
                elif (service["active"] == "failed" or 
                      service["load"] == "not-found" or
                      service["sub"] == "failed" or
                      not service["file_exists"]):
                    analysis["probably_obsolete"].append(service)
                    continue
                    
                # 3. Attivi e importanti
                elif service["active"] == "active" and service["load"] == "loaded":
                    analysis["active_important"].append(service)
                    continue
                    
                # 4. Sconosciuti - richiedono valutazione manuale
                else:
                    analysis["unknown"].append(service)
        
        # 5. Trova file orfani (file esistenti senza servizio attivo)
        analysis["orphaned_files"] = self._find_orphaned_service_files()
        
        return analysis

    def _find_orphaned_service_files(self) -> List[Dict]:
        """Trova file di servizio orfani (senza servizio corrispondente)"""
        orphaned = []
        
        # Controlla directory system
        if self.system_dir.exists():
            for service_file in self.system_dir.glob("nextcloud-*.service"):
                service_name = service_file.stem
                try:
                    # Verifica se systemd conosce questo servizio
                    cmd = ["systemctl", "status", service_name, "--no-pager"]
                    output = self.run_cmd(cmd, check=False)
                    
                    if "could not be found" in output.lower() or "not loaded" in output.lower():
                        orphaned.append({
                            "name": service_name,
                            "file": str(service_file),
                            "type": "system",
                            "size": service_file.stat().st_size
                        })
                except Exception:
                    pass
        
        # Controlla directory user
        if self.user_dir.exists():
            for service_file in self.user_dir.glob("nextcloud-*.service"):
                service_name = service_file.stem
                try:
                    cmd = ["systemctl", "--user", "status", service_name, "--no-pager"]
                    output = self.run_cmd(cmd, check=False)
                    
                    if "could not be found" in output.lower() or "not loaded" in output.lower():
                        orphaned.append({
                            "name": service_name,
                            "file": str(service_file),
                            "type": "user", 
                            "size": service_file.stat().st_size
                        })
                except Exception:
                    pass
        
        return orphaned

    def display_analysis(self, analysis: Dict[str, List[Dict]]):
        """Mostra risultati analisi in modo leggibile"""
        
        console.print("\n[bold blue]🔍 ANALISI SERVIZI NEXTCLOUD-WRAPPER[/bold blue]\n")
        
        # Servizi sicuramente obsoleti
        if analysis["definitely_obsolete"]:
            table = Table(title="❌ Servizi Sicuramente Obsoleti", show_header=True)
            table.add_column("Nome", style="red")
            table.add_column("Tipo", style="yellow")
            table.add_column("Status", style="white")
            table.add_column("Motivo", style="cyan")
            
            for service in analysis["definitely_obsolete"]:
                reason = "Pattern obsoleto noto"
                table.add_row(
                    service["name"], 
                    service["type"],
                    f"{service['active']}/{service['sub']}",
                    reason
                )
            console.print(table)
            console.print()
        
        # Servizi probabilmente obsoleti
        if analysis["probably_obsolete"]:
            table = Table(title="⚠️ Servizi Probabilmente Obsoleti", show_header=True)
            table.add_column("Nome", style="yellow")
            table.add_column("Tipo", style="yellow")
            table.add_column("Load", style="white")
            table.add_column("Active", style="white") 
            table.add_column("Sub", style="white")
            table.add_column("File Esiste", style="cyan")
            
            for service in analysis["probably_obsolete"]:
                table.add_row(
                    service["name"],
                    service["type"],
                    service["load"],
                    service["active"],
                    service["sub"],
                    "✅" if service["file_exists"] else "❌"
                )
            console.print(table)
            console.print()
        
        # File orfani
        if analysis["orphaned_files"]:
            table = Table(title="👻 File di Servizio Orfani", show_header=True)
            table.add_column("Nome", style="magenta")
            table.add_column("Tipo", style="yellow")
            table.add_column("File", style="white")
            table.add_column("Dimensione", style="cyan")
            
            for orphan in analysis["orphaned_files"]:
                table.add_row(
                    orphan["name"],
                    orphan["type"], 
                    orphan["file"],
                    f"{orphan['size']} bytes"
                )
            console.print(table)
            console.print()
            
        # Servizi attivi importanti
        if analysis["active_important"]:
            table = Table(title="✅ Servizi Attivi e Funzionanti", show_header=True)
            table.add_column("Nome", style="green")
            table.add_column("Tipo", style="yellow")
            table.add_column("Status", style="white")
            table.add_column("Descrizione", style="cyan")
            
            for service in analysis["active_important"]:
                table.add_row(
                    service["name"],
                    service["type"],
                    f"{service['active']}/{service['sub']}", 
                    service["description"][:50] + "..." if len(service["description"]) > 50 else service["description"]
                )
            console.print(table)
            console.print()
        
        # Servizi sconosciuti
        if analysis["unknown"]:
            table = Table(title="❓ Servizi da Valutare Manualmente", show_header=True)
            table.add_column("Nome", style="white")
            table.add_column("Tipo", style="yellow")
            table.add_column("Load", style="white")
            table.add_column("Active", style="white")
            table.add_column("Sub", style="white")
            
            for service in analysis["unknown"]:
                table.add_row(
                    service["name"],
                    service["type"],
                    service["load"], 
                    service["active"],
                    service["sub"]
                )
            console.print(table)
            console.print()

    def cleanup_obsolete_services(self, analysis: Dict[str, List[Dict]], dry_run: bool = True):
        """Rimuove servizi obsoleti"""
        
        services_to_remove = []
        services_to_remove.extend(analysis["definitely_obsolete"])
        
        if analysis["probably_obsolete"]:
            console.print("[yellow]Servizi probabilmente obsoleti trovati.[/yellow]")
            if Confirm.ask("Vuoi includerli nella pulizia?"):
                services_to_remove.extend(analysis["probably_obsolete"])
        
        files_to_remove = analysis["orphaned_files"]
        
        if not services_to_remove and not files_to_remove:
            console.print("[green]✅ Nessun servizio obsoleto da rimuovere![/green]")
            return
        
        if dry_run:
            console.print(f"\n[yellow]🔍 MODALITÀ DRY-RUN - Operazioni che verrebbero eseguite:[/yellow]\n")
        else:
            console.print(f"\n[red]🗑️ RIMOZIONE IN CORSO:[/red]\n")
        
        removed_count = 0
        failed_count = 0
        
        # Rimuovi servizi
        for service in services_to_remove:
            service_name = service["name"]
            is_user = service["type"] == "user"
            
            if dry_run:
                console.print(f"[yellow]Would remove service: {service_name} ({'user' if is_user else 'system'})[/yellow]")
            else:
                try:
                    # Stop e disable servizio
                    stop_cmd = ["systemctl"]
                    if is_user:
                        stop_cmd.append("--user")
                    stop_cmd.extend(["disable", "--now", f"{service_name}.service"])
                    
                    self.run_cmd(stop_cmd, check=False)
                    
                    # Rimuovi file servizio
                    service_dir = self.user_dir if is_user else self.system_dir
                    service_file = service_dir / f"{service_name}.service"
                    timer_file = service_dir / f"{service_name}.timer"
                    
                    if service_file.exists():
                        service_file.unlink()
                        console.print(f"[green]✅ Rimosso: {service_file}[/green]")
                    
                    if timer_file.exists():
                        timer_file.unlink()
                        console.print(f"[green]✅ Rimosso: {timer_file}[/green]")
                    
                    removed_count += 1
                    
                except Exception as e:
                    console.print(f"[red]❌ Errore rimozione {service_name}: {e}[/red]")
                    failed_count += 1
        
        # Rimuovi file orfani
        for orphan in files_to_remove:
            if dry_run:
                console.print(f"[yellow]Would remove orphaned file: {orphan['file']}[/yellow]")
            else:
                try:
                    Path(orphan["file"]).unlink()
                    console.print(f"[green]✅ Rimosso file orfano: {orphan['file']}[/green]")
                    removed_count += 1
                except Exception as e:
                    console.print(f"[red]❌ Errore rimozione file {orphan['file']}: {e}[/red]")
                    failed_count += 1
        
        if not dry_run:
            # Reload systemd
            try:
                self.run_cmd(["systemctl", "daemon-reload"])
                console.print("[cyan]🔄 SystemD configuration reloaded[/cyan]")
            except Exception as e:
                console.print(f"[yellow]Warning: Errore reload systemd: {e}[/yellow]")
            
            console.print(f"\n[bold green]✅ Pulizia completata![/bold green]")
            console.print(f"[green]Rimossi: {removed_count}[/green]")
            if failed_count > 0:
                console.print(f"[red]Falliti: {failed_count}[/red]")

def main():
    """Funzione principale"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Pulizia servizi nextcloud-wrapper obsoleti")
    parser.add_argument("--dry-run", action="store_true", help="Mostra operazioni senza eseguirle")
    parser.add_argument("--auto", action="store_true", help="Rimuovi automaticamente servizi sicuramente obsoleti")
    
    args = parser.parse_args()
    
    cleaner = ObsoleteServiceCleaner()
    
    console.print("[bold blue]🔧 NEXTCLOUD-WRAPPER - Pulizia Servizi Obsoleti[/bold blue]\n")
    
    # Scopri tutti i servizi
    console.print("🔍 Scansione servizi in corso...")
    services = cleaner.discover_all_nextcloud_services()
    
    # Analizza servizi
    console.print("📊 Analisi servizi...")
    analysis = cleaner.analyze_services(services)
    
    # Mostra risultati
    cleaner.display_analysis(analysis)
    
    # Statistiche finali
    total_obsolete = len(analysis["definitely_obsolete"]) + len(analysis["probably_obsolete"])
    total_orphaned = len(analysis["orphaned_files"])
    total_active = len(analysis["active_important"])
    
    console.print(f"\n[bold]📈 RIEPILOGO:[/bold]")
    console.print(f"[red]Obsoleti: {total_obsolete}[/red]")
    console.print(f"[magenta]File orfani: {total_orphaned}[/magenta]") 
    console.print(f"[green]Attivi: {total_active}[/green]")
    console.print(f"[yellow]Da valutare: {len(analysis['unknown'])}[/yellow]")
    
    # Rimozione
    if total_obsolete > 0 or total_orphaned > 0:
        if args.auto:
            cleaner.cleanup_obsolete_services(analysis, dry_run=args.dry_run)
        else:
            if Confirm.ask("\nVuoi procedere con la pulizia?"):
                dry_run = args.dry_run if args.dry_run else not Confirm.ask("Eseguire la rimozione? (No = dry-run)")
                cleaner.cleanup_obsolete_services(analysis, dry_run=dry_run)
    else:
        console.print("\n[green]✅ Sistema pulito - nessuna azione necessaria![/green]")

if __name__ == "__main__":
    main()