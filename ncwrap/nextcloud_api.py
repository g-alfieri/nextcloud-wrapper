"""
Nextcloud API wrapper - gestione utenti e cartelle via OCS e WebDAV
"""
import os
import requests
from typing import Tuple, List


def get_nc_config() -> Tuple[str, str, str]:
    """Recupera configurazione Nextcloud dalle variabili d'ambiente"""
    base_url = os.environ.get("NC_BASE_URL")
    admin_user = os.environ.get("NC_ADMIN_USER")  
    admin_pass = os.environ.get("NC_ADMIN_PASS")
    
    if not all([base_url, admin_user, admin_pass]):
        raise ValueError(
            "Variabili d'ambiente mancanti: NC_BASE_URL, NC_ADMIN_USER, NC_ADMIN_PASS"
        )
    
    return base_url.rstrip("/"), admin_user, admin_pass


def nc_headers() -> dict:
    """Header richiesti per API OCS"""
    return {"OCS-APIRequest": "true"}


def create_nc_user(user_id: str, password: str) -> str:
    """
    Crea un nuovo utente in Nextcloud
    
    Args:
        user_id: Username dell'utente (es. casacialde.com)
        password: Password dell'utente
        
    Returns:
        Risposta XML/JSON del server
        
    Raises:
        requests.HTTPError: Se la richiesta fallisce
    """
    base_url, admin_user, admin_pass = get_nc_config()
    url = f"{base_url}/ocs/v1.php/cloud/users"
    
    response = requests.post(
        url,
        headers=nc_headers(),
        auth=(admin_user, admin_pass),
        data={"userid": user_id, "password": password},
        timeout=30,
    )
    response.raise_for_status()
    return response.text


def check_user_exists(user_id: str) -> bool:
    """
    Verifica se un utente esiste già in Nextcloud
    
    Args:
        user_id: Username da verificare
        
    Returns:
        True se l'utente esiste, False altrimenti
    """
    base_url, admin_user, admin_pass = get_nc_config()
    url = f"{base_url}/ocs/v1.php/cloud/users"
    
    try:
        response = requests.get(
            url,
            headers=nc_headers(),
            auth=(admin_user, admin_pass),
            params={"search": user_id},
            timeout=30,
        )
        response.raise_for_status()
        # Controllo semplificato - se user_id è nella risposta, esiste
        return user_id in response.text
    except requests.RequestException:
        return False


def dav_probe(user: str, password: str) -> Tuple[int, str]:
    """
    Test login dell'utente via WebDAV
    
    Args:
        user: Username
        password: Password
        
    Returns:
        Tupla (status_code, response_preview)
        Status 207 = successo, 401 = credenziali errate
    """
    base_url, _, _ = get_nc_config()
    url = f"{base_url}/remote.php/dav/files/{user}/"
    
    response = requests.request(
        "PROPFIND",
        url,
        auth=(user, password),
        headers={"Depth": "0"},
        timeout=30
    )
    return response.status_code, response.text[:500]


def mkcol(path: str, auth_user: str, auth_pass: str) -> int:
    """
    Crea una cartella via WebDAV
    
    Args:
        path: Percorso della cartella da creare
        auth_user: Username per autenticazione
        auth_pass: Password per autenticazione
        
    Returns:
        Status code (201 = creata, 405 = già esistente)
    """
    base_url, _, _ = get_nc_config()
    url = f"{base_url}/remote.php/dav/files/{auth_user}/{path.strip('/')}"
    
    response = requests.request(
        "MKCOL", 
        url, 
        auth=(auth_user, auth_pass), 
        timeout=30
    )
    return response.status_code


def ensure_tree(user: str, password: str, root_domain: str, subdomains: List[str]) -> dict:
    """
    Crea la struttura cartelle standard: /public, /logs, /backup + sottodomini
    
    Args:
        user: Username
        password: Password
        root_domain: Dominio principale (es. casacialde.com)
        subdomains: Lista sottodomini (es. ['spedizioni.casacialde.com'])
        
    Returns:
        Dict con risultati creazione cartelle
    """
    results = {}
    
    # Cartelle principali
    main_folders = ["public", "logs", "backup"]
    for folder in main_folders:
        status = mkcol(folder, user, password)
        results[folder] = status
    
    # Cartella dominio principale in /public
    main_domain_path = f"public/{root_domain}"
    results[main_domain_path] = mkcol(main_domain_path, user, password)
    
    # Cartelle sottodomini in /public  
    for subdomain in subdomains:
        subdomain_path = f"public/{subdomain}"
        results[subdomain_path] = mkcol(subdomain_path, user, password)
    
    return results


def set_nc_password(user_id: str, new_password: str) -> str:
    """
    Aggiorna password utente Nextcloud
    
    Args:
        user_id: Username
        new_password: Nuova password
        
    Returns:
        Risposta del server
        
    Raises:
        requests.HTTPError: Se la richiesta fallisce
    """
    base_url, admin_user, admin_pass = get_nc_config()
    url = f"{base_url}/ocs/v1.php/cloud/users/{user_id}"
    
    response = requests.put(
        url,
        headers=nc_headers(),
        auth=(admin_user, admin_pass),
        data={"key": "password", "value": new_password},
        timeout=30,
    )
    response.raise_for_status()
    return response.text


def list_directory(user: str, password: str, path: str = "") -> Tuple[int, str]:
    """
    Lista contenuto di una directory via WebDAV
    
    Args:
        user: Username
        password: Password  
        path: Percorso relativo (default: root)
        
    Returns:
        Tupla (status_code, xml_response)
    """
    base_url, _, _ = get_nc_config()
    url = f"{base_url}/remote.php/dav/files/{user}/{path.strip('/')}"
    
    response = requests.request(
        "PROPFIND",
        url,
        auth=(user, password),
        headers={"Depth": "1"},
        timeout=30
    )
    return response.status_code, response.text