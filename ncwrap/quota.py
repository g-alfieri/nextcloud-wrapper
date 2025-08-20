"""
Gestione quote filesystem e utenti
"""
import subprocess
import re
import json
from pathlib import Path
from typing import Dict, Optional, Tuple
from .utils import run


class QuotaManager:
    """Gestore unified per quote filesystem"""
    
    def __init__(self):
        self.fs_type = self._detect_filesystem_type()
    
    def _detect_filesystem_type(self, path: str = "/home") -> str:
        """Rileva tipo filesystem"""
        try:
            output = run(["findmnt", "-n", "-o", "FSTYPE", path])
            return output.strip().lower()
        except:
            return "unknown"
    
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
            size_bytes = self._parse_size(soft_limit)
            hard_limit = f"{int(size_bytes * 1.1)}"
        
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
            # Crea qgroup se non esiste
            run([
                "btrfs", "qgroup", "create", "1/0", subvolume_path
            ], check=False)
            
            # Imposta limite
            run([
                "btrfs", "qgroup", "limit", size, subvolume_path
            ])
            return True
        except RuntimeError as e:
            print(f"Errore quota BTRFS: {e}")
            return False
    
    def _set_posix_quota(self, username: str, soft_limit: str, hard_limit: str) -> bool:
        """Imposta quota POSIX (ext4/xfs)"""
        try:
            # Converte in KB
            soft_kb = self._parse_size(soft_limit) // 1024
            hard_kb = self._parse_size(hard_limit) // 1024
            
            # setquota -u username soft_blocks hard_blocks soft_inodes hard_inodes filesystem
            run([
                "setquota", "-u", username,
                str(soft_kb), str(hard_kb),
                "0", "0",  # inode limits (0 = unlimited)
                "/"
            ])
            return True
        except RuntimeError as e:
            print(f"Errore quota POSIX: {e}")
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
                        return {
                            "used": self._bytes_to_human(int(parts[1])),
                            "soft_limit": self._bytes_to_human(int(parts[2])) if parts[2] != 'none' else None,
                            "hard_limit": self._bytes_to_human(int(parts[2])) if parts[2] != 'none' else None,
                            "filesystem": "btrfs"
                        }
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
                        return {
                            "used": f"{parts[1]}K",
                            "soft_limit": f"{parts[2]}K" if parts[2] != '0' else None,
                            "hard_limit": f"{parts[3]}K" if parts[3] != '0' else None,
                            "filesystem": "posix"
                        }
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
            return True
        except:
            return False
    
    def _remove_posix_quota(self, username: str) -> bool:
        """Rimuove quota POSIX"""
        try:
            run(["setquota", "-u", username, "0", "0", "0", "0", "/"])
            return True
        except:
            return False
    
    def _parse_size(self, size_str: str) -> int:
        """Converte stringa size in bytes (es. '1G' -> 1073741824)"""
        size_str = size_str.upper().strip()
        
        multipliers = {
            'B': 1,
            'K': 1024, 'KB': 1024,
            'M': 1024**2, 'MB': 1024**2,
            'G': 1024**3, 'GB': 1024**3,
            'T': 1024**4, 'TB': 1024**4
        }
        
        match = re.match(r'^(\d+(?:\.\d+)?)\s*([BKMGT]B?)$', size_str)
        if not match:
            raise ValueError(f"Formato size non valido: {size_str}")
        
        number, unit = match.groups()
        return int(float(number) * multipliers.get(unit, 1))
    
    def _bytes_to_human(self, bytes_val: int) -> str:
        """Converte bytes in formato human-readable"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_val < 1024.0:
                return f"{bytes_val:.1f}{unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.1f}PB"


# Backward compatibility functions
def set_btrfs_quota(path: str, size: str) -> bool:
    """Wrapper per compatibilità"""
    manager = QuotaManager()
    return manager._set_btrfs_quota(path, size)


def set_ext4_quota(user: str, size: str) -> bool:
    """Wrapper per compatibilità"""
    manager = QuotaManager()
    return manager._set_posix_quota(user, size, size)


def get_filesystem_usage(path: str = "/home") -> Optional[Dict]:
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


def setup_quota_system(filesystem_root: str = "/") -> bool:
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
        
        # Se arriviamo qui, le quote sono già attive
        return True
        
    except:
        try:
            # Prova ad attivare quote
            print("Tentativo attivazione quote...")
            
            # Check filesystem
            run(["quotacheck", "-cum", filesystem_root])
            
            # Attiva quote
            run(["quotaon", filesystem_root])
            
            return True
        except RuntimeError as e:
            print(f"Errore setup quota system: {e}")
            return False


def list_all_quotas() -> Dict[str, Dict]:
    """Lista tutte le quote utenti attive"""
    quotas = {}
    manager = QuotaManager()
    
    try:
        # Lista utenti sistema
        output = run(["cut", "-d:", "-f1", "/etc/passwd"])
        users = output.split('\n')
        
        for user in users:
            if user and not user.startswith('#'):
                quota_info = manager.get_quota(user.strip())
                if quota_info:
                    quotas[user.strip()] = quota_info
    except:
        pass
    
    return quotas
