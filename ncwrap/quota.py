"""
Gestione quote filesystem e utenti per Nextcloud Wrapper v0.3.0
"""
import subprocess
import re
import json
import os
from pathlib import Path
from typing import Dict, Optional, Tuple, List
from .utils import run, parse_size_to_bytes, bytes_to_human, get_filesystem_type


class QuotaManager:
    """Gestore unified per quote filesystem"""
    
    def __init__(self):
        self.fs_type = self._detect_filesystem_type()
        self.quota_config = self._load_quota_config()
    
    def _load_quota_config(self) -> Dict:
        """Carica configurazione quote da environment"""
        return {
            "default_fs_percentage": float(os.environ.get("NC_DEFAULT_FS_PERCENTAGE", "0.02")),
            "btrfs_subvolume_path": os.environ.get("NC_BTRFS_SUBVOLUME_PATH", "/home"),
            "posix_filesystem": os.environ.get("NC_POSIX_FILESYSTEM", "/"),
            "enable_auto_cleanup": os.environ.get("NC_ENABLE_AUTO_CLEANUP", "true").lower() == "true",
            "quota_warning_threshold": float(os.environ.get("NC_QUOTA_WARNING_THRESHOLD", "0.8")),
            "quota_critical_threshold": float(os.environ.get("NC_QUOTA_CRITICAL_THRESHOLD", "0.95"))
        }
    
    def _detect_filesystem_type(self, path: str = "/home") -> str:
        """Rileva tipo filesystem"""
        return get_filesystem_type(path)
    
    def set_quota(self, username: str, soft_limit: str, hard_limit: str = None, 
                  path: str = "/home") -> bool:
        """
        Imposta quota per un utente
        
        Args:
            username: Nome utente
            soft_limit: Limite soft (es. "1G", "500M")
            hard_limit: Limite hard (opzionale, default = soft_limit * 1.1)
            path: Path per btrfs subvolume
            
        Returns:
            True se quota impostata con successo
        """
        if not hard_limit:
            # Hard limit = 110% del soft limit
            size_bytes = parse_size_to_bytes(soft_limit)
            hard_bytes = int(size_bytes * 1.1)
            hard_limit = bytes_to_human(hard_bytes)
        
        fs_type = self._detect_filesystem_type(path)
        
        if fs_type == "btrfs":
            return self._set_btrfs_quota(f"{path}/{username}", soft_limit)
        elif fs_type in ["ext4", "ext3", "xfs"]:
            return self._set_posix_quota(username, soft_limit, hard_limit)
        else:
            print(f"Filesystem {fs_type} non supportato per quote")
            return False
    
    def _set_btrfs_quota(self, subvolume_path: str, size: str) -> bool:
        """Imposta quota BTRFS su subvolume"""
        try:
            # Assicurati che il path esista
            if not os.path.exists(subvolume_path):
                # Crea subvolume se non esiste
                parent_path = os.path.dirname(subvolume_path)
                subvol_name = os.path.basename(subvolume_path)
                
                run([
                    "btrfs", "subvolume", "create", 
                    os.path.join(parent_path, subvol_name)
                ])
            
            # Abilita quota se non attiva
            try:
                run(["btrfs", "quota", "enable", subvolume_path], check=False)
            except:
                pass
            
            # Crea qgroup se non esiste
            run([
                "btrfs", "qgroup", "create", "1/0", subvolume_path
            ], check=False)
            
            # Converti formato size per BTRFS (che accetta solo bytes o formato specifico)
            size_bytes = parse_size_to_bytes(size)
            btrfs_size = str(size_bytes)  # BTRFS vuole solo il numero di bytes
            
            # Imposta limite
            run([
                "btrfs", "qgroup", "limit", btrfs_size, subvolume_path
            ])
            
            print(f"✅ Quota BTRFS impostata: {subvolume_path} = {size} ({btrfs_size} bytes)")
            return True
            
        except RuntimeError as e:
            print(f"❌ Errore quota BTRFS: {e}")
            return False
    
    def _set_posix_quota(self, username: str, soft_limit: str, hard_limit: str) -> bool:
        """Imposta quota POSIX (ext4/xfs)"""
        try:
            # Verifica che quota siano abilitate
            self.setup_quota_system()
            
            # Converte in KB
            soft_kb = parse_size_to_bytes(soft_limit) // 1024
            hard_kb = parse_size_to_bytes(hard_limit) // 1024
            
            # setquota -u username soft_blocks hard_blocks soft_inodes hard_inodes filesystem
            filesystem = self.quota_config["posix_filesystem"]
            run([
                "setquota", "-u", username,
                str(soft_kb), str(hard_kb),
                "0", "0",  # inode limits (0 = unlimited)
                filesystem
            ])
            
            print(f"✅ Quota POSIX impostata: {username} = {soft_limit}")
            return True
            
        except RuntimeError as e:
            print(f"❌ Errore quota POSIX: {e}")
            return False
    
    def get_quota(self, username: str, path: str = "/home") -> Optional[Dict]:
        """
        Recupera informazioni quota utente
        
        Returns:
            Dict con used, soft_limit, hard_limit o None se errore
        """
        fs_type = self._detect_filesystem_type(path)
        
        if fs_type == "btrfs":
            return self._get_btrfs_quota(f"{path}/{username}")
        elif fs_type in ["ext4", "ext3", "xfs"]:
            return self._get_posix_quota(username)
        else:
            return None
    
    def _get_btrfs_quota(self, subvolume_path: str) -> Optional[Dict]:
        """Recupera quota BTRFS"""
        try:
            output = run([
                "btrfs", "qgroup", "show", "-p", "-c", subvolume_path
            ])
            
            # Parsing output btrfs qgroup show
            for line in output.split('\n'):
                if '1/0' in line:
                    parts = line.split()
                    if len(parts) >= 3:
                        used_bytes = int(parts[1]) if parts[1] != '-' else 0
                        limit_bytes = int(parts[2]) if parts[2] != 'none' and parts[2] != '-' else None
                        
                        result = {
                            "used": bytes_to_human(used_bytes),
                            "used_bytes": used_bytes,
                            "filesystem": "btrfs",
                            "path": subvolume_path
                        }
                        
                        if limit_bytes:
                            result["limit"] = bytes_to_human(limit_bytes)
                            result["limit_bytes"] = limit_bytes
                            result["usage_percent"] = (used_bytes / limit_bytes) * 100 if limit_bytes > 0 else 0
                        
                        return result
        except:
            pass
        return None
    
    def _get_posix_quota(self, username: str) -> Optional[Dict]:
        """Recupera quota POSIX"""
        try:
            output = run(["quota", "-u", username])
            
            # Parsing output quota
            for line in output.split('\n'):
                if username in line and '/dev/' in line:
                    parts = line.split()
                    if len(parts) >= 6:
                        used_kb = int(parts[1]) if parts[1] != '0' else 0
                        soft_kb = int(parts[2]) if parts[2] != '0' else None
                        hard_kb = int(parts[3]) if parts[3] != '0' else None
                        
                        result = {
                            "used": bytes_to_human(used_kb * 1024),
                            "used_bytes": used_kb * 1024,
                            "filesystem": "posix"
                        }
                        
                        if soft_kb:
                            result["soft_limit"] = bytes_to_human(soft_kb * 1024)
                            result["soft_limit_bytes"] = soft_kb * 1024
                        
                        if hard_kb:
                            result["hard_limit"] = bytes_to_human(hard_kb * 1024)
                            result["hard_limit_bytes"] = hard_kb * 1024
                            result["usage_percent"] = (used_kb / hard_kb) * 100 if hard_kb > 0 else 0
                        
                        return result
        except:
            pass
        return None
    
    def remove_quota(self, username: str, path: str = "/home") -> bool:
        """Rimuove quota per un utente"""
        fs_type = self._detect_filesystem_type(path)
        
        if fs_type == "btrfs":
            return self._remove_btrfs_quota(f"{path}/{username}")
        elif fs_type in ["ext4", "ext3", "xfs"]:
            return self._remove_posix_quota(username)
        else:
            return False
    
    def _remove_btrfs_quota(self, subvolume_path: str) -> bool:
        """Rimuove quota BTRFS"""
        try:
            run(["btrfs", "qgroup", "destroy", "1/0", subvolume_path])
            print(f"✅ Quota BTRFS rimossa: {subvolume_path}")
            return True
        except:
            return False
    
    def _remove_posix_quota(self, username: str) -> bool:
        """Rimuove quota POSIX"""
        try:
            filesystem = self.quota_config["posix_filesystem"]
            run(["setquota", "-u", username, "0", "0", "0", "0", filesystem])
            print(f"✅ Quota POSIX rimossa: {username}")
            return True
        except:
            return False
    
    def get_filesystem_usage(self, path: str = "/home") -> Optional[Dict]:
        """Recupera informazioni uso filesystem"""
        try:
            output = run(["df", "-h", path])
            lines = output.strip().split('\n')
            
            if len(lines) >= 2:
                parts = lines[1].split()
                if len(parts) >= 6:
                    return {
                        "filesystem": parts[0],
                        "total": parts[1],
                        "used": parts[2],
                        "available": parts[3],
                        "use_percent": parts[4],
                        "mount_point": parts[5]
                    }
        except:
            pass
        return None
    
    def setup_quota_system(self, filesystem_root: str = "/") -> bool:
        """
        Inizializza sistema quote se non attivo
        
        Args:
            filesystem_root: Root filesystem (di solito "/")
            
        Returns:
            True se quota system pronto
        """
        try:
            # Test se quote sono già attive
            run(["quotaon", "-p", filesystem_root], check=False)
            return True
        except:
            try:
                print("🔧 Inizializzazione sistema quote...")
                
                # Check filesystem
                run(["quotacheck", "-cum", filesystem_root])
                
                # Attiva quote
                run(["quotaon", filesystem_root])
                
                print("✅ Sistema quote attivato")
                return True
            except RuntimeError as e:
                print(f"❌ Errore setup quota system: {e}")
                return False
    
    def get_quota_status(self, username: str) -> Dict:
        """
        Ottiene status dettagliato quota utente
        
        Args:
            username: Nome utente
            
        Returns:
            Dict con status e raccomandazioni
        """
        quota_info = self.get_quota(username)
        
        if not quota_info:
            return {"status": "no_quota", "message": "Nessuna quota configurata"}
        
        usage_percent = quota_info.get("usage_percent", 0)
        warning_threshold = self.quota_config["quota_warning_threshold"] * 100
        critical_threshold = self.quota_config["quota_critical_threshold"] * 100
        
        if usage_percent >= critical_threshold:
            status = "critical"
            message = f"Quota quasi esaurita ({usage_percent:.1f}%)"
            recommendations = ["Eliminare file non necessari", "Aumentare quota", "Archiviare dati"]
        elif usage_percent >= warning_threshold:
            status = "warning"
            message = f"Quota in avvicinamento al limite ({usage_percent:.1f}%)"
            recommendations = ["Monitorare uso spazio", "Pianificare pulizia file"]
        else:
            status = "ok"
            message = f"Quota sotto controllo ({usage_percent:.1f}%)"
            recommendations = []
        
        return {
            "status": status,
            "message": message,
            "usage_percent": usage_percent,
            "recommendations": recommendations,
            "quota_info": quota_info
        }
    
    def cleanup_user_files(self, username: str, dry_run: bool = True) -> Dict:
        """
        Pulizia automatica file temporanei utente
        
        Args:
            username: Nome utente
            dry_run: Solo simulazione (non eliminare file)
            
        Returns:
            Dict con risultati pulizia
        """
        if not self.quota_config["enable_auto_cleanup"]:
            return {"error": "Auto-cleanup disabilitato"}
        
        user_home = f"/home/{username}"
        if not os.path.exists(user_home):
            return {"error": f"Home directory non trovata: {user_home}"}
        
        cleanup_paths = [
            "*.tmp",
            "*.temp",
            ".cache/*",
            ".thumbnails/*",
            "Downloads/*.part",
            "Downloads/*.tmp"
        ]
        
        results = {
            "files_found": 0,
            "space_freed": 0,
            "errors": [],
            "cleaned_paths": []
        }
        
        import glob
        from .utils import get_directory_size
        
        for pattern in cleanup_paths:
            try:
                full_pattern = os.path.join(user_home, pattern)
                matches = glob.glob(full_pattern, recursive=True)
                
                for file_path in matches:
                    try:
                        if os.path.isfile(file_path):
                            file_size = os.path.getsize(file_path)
                            results["files_found"] += 1
                            results["space_freed"] += file_size
                            
                            if not dry_run:
                                os.unlink(file_path)
                                results["cleaned_paths"].append(file_path)
                        elif os.path.isdir(file_path):
                            dir_size = get_directory_size(file_path)
                            results["files_found"] += 1
                            results["space_freed"] += dir_size
                            
                            if not dry_run:
                                import shutil
                                shutil.rmtree(file_path)
                                results["cleaned_paths"].append(file_path)
                    except Exception as e:
                        results["errors"].append(f"{file_path}: {str(e)}")
                        
            except Exception as e:
                results["errors"].append(f"Pattern {pattern}: {str(e)}")
        
        results["space_freed_human"] = bytes_to_human(results["space_freed"])
        return results
    
    def analyze_quota_trends(self, username: str) -> Dict:
        """
        Analizza trend uso quota nel tempo
        
        Args:
            username: Nome utente
            
        Returns:
            Dict con analisi trend
        """
        # In una implementazione completa, questo leggerebbe da un log storico
        # Per ora restituisce solo lo stato attuale
        quota_info = self.get_quota(username)
        
        if not quota_info:
            return {"error": "Nessuna quota configurata"}
        
        # Simulazione trend (in produzione leggerebbe da database/log)
        current_usage = quota_info.get("usage_percent", 0)
        
        # Stima molto semplificata del trend
        if current_usage > 80:
            trend = "increasing_fast"
            prediction = "Quota esaurita entro 7 giorni"
        elif current_usage > 50:
            trend = "increasing"
            prediction = "Quota esaurita entro 30 giorni"
        else:
            trend = "stable"
            prediction = "Uso quota stabile"
        
        return {
            "current_usage": current_usage,
            "trend": trend,
            "prediction": prediction,
            "recommendations": self._get_trend_recommendations(trend, current_usage)
        }
    
    def _get_trend_recommendations(self, trend: str, usage: float) -> List[str]:
        """Genera raccomandazioni basate su trend"""
        recommendations = []
        
        if trend == "increasing_fast":
            recommendations.extend([
                "Pulizia immediata file temporanei",
                "Archiviazione dati vecchi",
                "Aumento quota urgente"
            ])
        elif trend == "increasing":
            recommendations.extend([
                "Monitoraggio più frequente",
                "Pianificazione pulizia settimanale",
                "Valutazione aumento quota"
            ])
        else:
            recommendations.append("Continua monitoraggio normale")
        
        return recommendations


# Funzioni di convenienza per backward compatibility e API semplificata
def setup_quota_for_user(username: str, nextcloud_quota: str, fs_percentage: float = 0.02) -> bool:
    """
    Setup quota utente con logica corretta: filesystem = nextcloud * percentage
    
    Args:
        username: Nome utente
        nextcloud_quota: Quota Nextcloud (es. "100G")
        fs_percentage: Percentuale filesystem (default: 2%)
        
    Returns:
        True se setup completato
    """
    try:
        # Calcola quota filesystem
        nc_bytes = parse_size_to_bytes(nextcloud_quota)
        fs_bytes = int(nc_bytes * fs_percentage)
        fs_quota = bytes_to_human(fs_bytes)
        
        print(f"📊 Setup quota: NC {nextcloud_quota} → FS {fs_quota} ({fs_percentage:.1%})")
        
        # Imposta quota Nextcloud
        from .api import set_nc_quota
        try:
            # Converte formato per Nextcloud (spazi tra numero e unità)
            # Nextcloud accetta formati come "100 GB", "50 MB", "1 TB"
            if nextcloud_quota.endswith('G'):
                nc_quota_formatted = nextcloud_quota.replace('G', ' GB')
            elif nextcloud_quota.endswith('M'):
                nc_quota_formatted = nextcloud_quota.replace('M', ' MB')
            elif nextcloud_quota.endswith('T'):
                nc_quota_formatted = nextcloud_quota.replace('T', ' TB')
            elif nextcloud_quota.endswith('K'):
                nc_quota_formatted = nextcloud_quota.replace('K', ' KB')
            else:
                nc_quota_formatted = nextcloud_quota  # Assume già formato corretto
                
            set_nc_quota(username, nc_quota_formatted)
            print(f"✅ Quota Nextcloud: {nc_quota_formatted}")
        except Exception as e:
            print(f"⚠️ Avviso quota Nextcloud: {e}")
        
        # Imposta quota filesystem
        quota_manager = QuotaManager()
        
        try:
            # Prova a impostare quota filesystem
            if quota_manager.set_quota(username, fs_quota):
                print(f"✅ Quota filesystem: {fs_quota}")
                return True
            else:
                print(f"⚠️ Quota filesystem non supportata su questo sistema")
                print(f"📊 Quota impostata solo su Nextcloud: {nc_quota_formatted}")
                return True  # Considera successo parziale
        except Exception as e:
            print(f"⚠️ Errore quota filesystem: {e}")
            print(f"📊 Quota impostata solo su Nextcloud: {nc_quota_formatted}")
            return True  # Fallback: almeno quota Nextcloud funziona
            
    except Exception as e:
        print(f"❌ Errore setup quota: {e}")
        return False


def get_quota_info(username: str) -> Optional[Dict]:
    """Wrapper semplice per ottenere info quota"""
    quota_manager = QuotaManager()
    return quota_manager.get_quota(username)


def list_all_user_quotas() -> Dict[str, Dict]:
    """Lista tutte le quote utenti attive"""
    quotas = {}
    quota_manager = QuotaManager()
    
    try:
        # Lista utenti sistema con home directory
        import pwd
        for user_entry in pwd.getpwall():
            username = user_entry.pw_name
            home_dir = user_entry.pw_dir
            
            # Salta utenti di sistema
            if user_entry.pw_uid < 1000 or not home_dir.startswith("/home/"):
                continue
            
            quota_info = quota_manager.get_quota(username)
            if quota_info:
                quotas[username] = quota_info
    except Exception as e:
        print(f"Errore listing quote: {e}")
    
    return quotas


def check_all_quotas() -> Dict:
    """Verifica tutte le quote e genera report"""
    all_quotas = list_all_user_quotas()
    
    report = {
        "total_users": len(all_quotas),
        "over_quota": [],
        "warnings": [],
        "ok": [],
        "total_used_bytes": 0,
        "total_limit_bytes": 0
    }
    
    quota_manager = QuotaManager()
    warning_threshold = quota_manager.quota_config["quota_warning_threshold"] * 100
    critical_threshold = quota_manager.quota_config["quota_critical_threshold"] * 100
    
    for username, quota_info in all_quotas.items():
        usage_percent = quota_info.get("usage_percent", 0)
        used_bytes = quota_info.get("used_bytes", 0)
        limit_bytes = quota_info.get("limit_bytes") or quota_info.get("hard_limit_bytes")
        
        report["total_used_bytes"] += used_bytes
        if limit_bytes:
            report["total_limit_bytes"] += limit_bytes
        
        if usage_percent >= critical_threshold:
            report["over_quota"].append({
                "username": username,
                "usage_percent": usage_percent,
                "quota_info": quota_info
            })
        elif usage_percent >= warning_threshold:
            report["warnings"].append({
                "username": username,
                "usage_percent": usage_percent,
                "quota_info": quota_info
            })
        else:
            report["ok"].append(username)
    
    # Converti totali in formato human
    report["total_used_human"] = bytes_to_human(report["total_used_bytes"])
    report["total_limit_human"] = bytes_to_human(report["total_limit_bytes"])
    
    return report


def quota_maintenance() -> Dict:
    """Esegue manutenzione automatica quote"""
    quota_manager = QuotaManager()
    
    if not quota_manager.quota_config["enable_auto_cleanup"]:
        return {"message": "Manutenzione automatica disabilitata"}
    
    results = {
        "users_processed": 0,
        "space_freed": 0,
        "errors": []
    }
    
    # Trova utenti oltre soglia critica
    all_quotas = list_all_user_quotas()
    critical_threshold = quota_manager.quota_config["quota_critical_threshold"] * 100
    
    for username, quota_info in all_quotas.items():
        usage_percent = quota_info.get("usage_percent", 0)
        
        if usage_percent >= critical_threshold:
            print(f"🧹 Pulizia automatica per {username} ({usage_percent:.1f}%)")
            
            try:
                cleanup_results = quota_manager.cleanup_user_files(username, dry_run=False)
                results["users_processed"] += 1
                results["space_freed"] += cleanup_results.get("space_freed", 0)
                
                if cleanup_results.get("errors"):
                    results["errors"].extend(cleanup_results["errors"])
                
            except Exception as e:
                results["errors"].append(f"{username}: {str(e)}")
    
    results["space_freed_human"] = bytes_to_human(results["space_freed"])
    return results


# Backward compatibility aliases
set_btrfs_quota = lambda path, size: QuotaManager()._set_btrfs_quota(path, size)
set_ext4_quota = lambda user, size: QuotaManager()._set_posix_quota(user, size, size)
get_filesystem_usage = lambda path="/home": QuotaManager().get_filesystem_usage(path)
setup_quota_system = lambda: QuotaManager().setup_quota_system()
list_all_quotas = list_all_user_quotas  # Alias per compatibilità
