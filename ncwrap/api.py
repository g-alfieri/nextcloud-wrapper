"""
API Nextcloud - gestione utenti e cartelle via OCS e WebDAV
"""
import os
import requests
from typing import Tuple, List, Optional
from .utils import validate_domain, run_with_retry
import time
import random


def make_request_with_retry(method: str, url: str, max_retries: int = 3, 
                           delay_base: float = 2.0, **kwargs) -> requests.Response:
    """
    Fa richieste HTTP con retry automatico per rate limiting
    
    Args:
        method: Metodo HTTP (GET, POST, etc.)
        url: URL della richiesta
        max_retries: Numero massimo retry
        delay_base: Delay base in secondi
        **kwargs: Parametri aggiuntivi per requests
        
    Returns:
        Response object
        
    Raises:
        requests.RequestException: Se tutti i tentativi falliscono
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            response = requests.request(method, url, **kwargs)
            
            # Se è 429 (Too Many Requests), retry con backoff
            if response.status_code == 429:
                if attempt < max_retries:
                    delay = delay_base * (2 ** attempt)  # Backoff esponenziale
                    jitter = random.uniform(0.1, 0.3) * delay  # Jitter per evitare thundering herd
                    total_delay = delay + jitter
                    
                    print(f"⏳ Rate limit (429), attesa {total_delay:.1f}s (tentativo {attempt + 1}/{max_retries + 1})")
                    time.sleep(total_delay)
                    continue
            
            # Per altri errori HTTP temporanei
            elif response.status_code in [502, 503, 504]:  # Bad Gateway, Service Unavailable, Gateway Timeout
                if attempt < max_retries:
                    delay = delay_base * (1.5 ** attempt)
                    print(f"⏳ Errore server ({response.status_code}), retry in {delay:.1f}s")
                    time.sleep(delay)
                    continue
            
            # Risposta ricevuta (anche se con errore HTTP)
            return response
            
        except (requests.Timeout, requests.ConnectionError) as e:
            last_exception = e
            if attempt < max_retries:
                delay = delay_base * (1.5 ** attempt)
                print(f"⏳ Errore rete, retry in {delay:.1f}s (tentativo {attempt + 1}/{max_retries + 1})")
                time.sleep(delay)
                continue
            break
            
        except Exception as e:
            last_exception = e
            break
    
    # Se arriviamo qui, tutti i tentativi sono falliti
    if last_exception:
        raise last_exception
    else:
        # Fallback: se per qualche motivo non abbiamo un'eccezione ma siamo qui
        raise requests.RequestException("Tutti i tentativi di richiesta sono falliti")


def get_nc_config() -> Tuple[str, str, str]:
    """Recupera configurazione Nextcloud dalle variabili d'ambiente"""
    # Prova a caricare file .env se le variabili non sono già impostate
    base_url = os.environ.get("NC_BASE_URL")
    admin_user = os.environ.get("NC_ADMIN_USER")
    admin_pass = os.environ.get("NC_ADMIN_PASS")
    
    # Se mancano variabili, prova a caricare da file .env
    if not all([base_url, admin_user, admin_pass]):
        from .utils import find_and_load_env
        if find_and_load_env():
            # Riprova dopo aver caricato il file .env
            base_url = os.environ.get("NC_BASE_URL")
            admin_user = os.environ.get("NC_ADMIN_USER")
            admin_pass = os.environ.get("NC_ADMIN_PASS")
    
    if not all([base_url, admin_user, admin_pass]):
        missing_vars = []
        if not base_url:
            missing_vars.append("NC_BASE_URL")
        if not admin_user:
            missing_vars.append("NC_ADMIN_USER")
        if not admin_pass:
            missing_vars.append("NC_ADMIN_PASS")
            
        error_msg = f"Variabili d'ambiente mancanti: {', '.join(missing_vars)}"
        error_msg += "\n\n💡 Soluzioni:"
        error_msg += "\n1. Crea file .env nella directory corrente con:"
        error_msg += "\n   NC_BASE_URL=https://your-nextcloud.example.com"
        error_msg += "\n   NC_ADMIN_USER=admin"
        error_msg += "\n   NC_ADMIN_PASS='your_password'"
        error_msg += "\n\n2. Oppure imposta le variabili d'ambiente:"
        error_msg += "\n   export NC_BASE_URL='https://your-nextcloud.example.com'"
        error_msg += "\n   export NC_ADMIN_USER='admin'"
        error_msg += "\n   export NC_ADMIN_PASS='your_password'"
        
        raise ValueError(error_msg)
    
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


def get_user_info(user_id: str) -> Optional[dict]:
    """
    Recupera informazioni dettagliate utente Nextcloud
    
    Args:
        user_id: Username
        
    Returns:
        Dict con info utente o None se non trovato
    """
    base_url, admin_user, admin_pass = get_nc_config()
    url = f"{base_url}/ocs/v1.php/cloud/users/{user_id}"
    
    try:
        response = requests.get(
            url,
            headers=nc_headers(),
            auth=(admin_user, admin_pass),
            timeout=30,
        )
        response.raise_for_status()
        
        # Parse XML semplificato (dovremmo usare xml.etree ma per ora ok)
        data = response.text
        info = {}
        
        # Estrai info base dal XML
        if "<enabled>true</enabled>" in data:
            info["enabled"] = True
        elif "<enabled>false</enabled>" in data:
            info["enabled"] = False
            
        if "<quota>" in data:
            quota_start = data.find("<quota>") + 7
            quota_end = data.find("</quota>")
            if quota_start > 6 and quota_end > quota_start:
                info["quota"] = data[quota_start:quota_end]
        
        return info if info else None
        
    except requests.RequestException:
        return None


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


def set_nc_quota(user_id: str, quota: str) -> str:
    """
    Imposta quota Nextcloud per utente
    
    Args:
        user_id: Username
        quota: Quota in formato Nextcloud (es. "100 GB")
        
    Returns:
        Risposta del server
    """
    base_url, admin_user, admin_pass = get_nc_config()
    url = f"{base_url}/ocs/v1.php/cloud/users/{user_id}"
    
    response = requests.put(
        url,
        headers=nc_headers(),
        auth=(admin_user, admin_pass),
        data={"key": "quota", "value": quota},
        timeout=30,
    )
    response.raise_for_status()
    return response.text


def delete_nc_user(user_id: str) -> str:
    """
    Elimina utente Nextcloud
    
    Args:
        user_id: Username da eliminare
        
    Returns:
        Risposta del server
    """
    base_url, admin_user, admin_pass = get_nc_config()
    url = f"{base_url}/ocs/v1.php/cloud/users/{user_id}"
    
    response = requests.delete(
        url,
        headers=nc_headers(),
        auth=(admin_user, admin_pass),
        timeout=30,
    )
    response.raise_for_status()
    return response.text


def get_webdav_url(user: str) -> str:
    """
    Genera URL WebDAV per un utente
    
    Args:
        user: Username
        
    Returns:
        URL WebDAV completo
    """
    base_url, _, _ = get_nc_config()
    return f"{base_url}/remote.php/dav/files/{user}/"


def test_webdav_connectivity(user: str, password: str) -> bool:
    """
    Test veloce connettività WebDAV
    
    Args:
        user: Username
        password: Password
        
    Returns:
        True se connessione funziona
    """
    try:
        status_code, _ = test_webdav_login(user, password)
        return status_code in (200, 207)
    except:
        return False


def test_webdav_login(user: str, password: str) -> Tuple[int, str]:
    """
    Test login dell'utente via WebDAV con retry automatico per rate limiting
    
    Args:
        user: Username
        password: Password
        
    Returns:
        Tupla (status_code, response_preview)
        Status 207 = successo, 401 = credenziali errate
    """
    webdav_url = get_webdav_url(user)
    
    try:
        response = make_request_with_retry(
            "PROPFIND",
            webdav_url,
            auth=(user, password),
            headers={"Depth": "0"},
            timeout=30,
            max_retries=3,
            delay_base=2.0
        )
        return response.status_code, response.text[:500]
    except Exception as e:
        print(f"❌ Errore test WebDAV: {e}")
        return 500, str(e)[:500]


def create_webdav_folder(path: str, auth_user: str, auth_pass: str) -> int:
    """
    Crea una cartella via WebDAV
    
    Args:
        path: Percorso della cartella da creare (relativo alla root utente)
        auth_user: Username per autenticazione
        auth_pass: Password per autenticazione
        
    Returns:
        Status code (201 = creata, 405 = già esistente, altro = errore)
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


def delete_webdav_item(path: str, auth_user: str, auth_pass: str) -> int:
    """
    Elimina file o cartella via WebDAV
    
    Args:
        path: Percorso dell'elemento da eliminare
        auth_user: Username per autenticazione
        auth_pass: Password per autenticazione
        
    Returns:
        Status code (204 = eliminato, 404 = non trovato)
    """
    base_url, _, _ = get_nc_config()
    url = f"{base_url}/remote.php/dav/files/{auth_user}/{path.strip('/')}"
    
    response = requests.delete(
        url, 
        auth=(auth_user, auth_pass), 
        timeout=30
    )
    return response.status_code


def list_webdav_directory(user: str, password: str, path: str = "") -> Tuple[int, str]:
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


def upload_file_webdav(local_path: str, remote_path: str, user: str, password: str) -> int:
    """
    Carica file via WebDAV
    
    Args:
        local_path: Percorso file locale
        remote_path: Percorso destinazione su Nextcloud
        user: Username
        password: Password
        
    Returns:
        Status code (201/204 = successo)
    """
    base_url, _, _ = get_nc_config()
    url = f"{base_url}/remote.php/dav/files/{user}/{remote_path.strip('/')}"
    
    try:
        with open(local_path, 'rb') as f:
            response = requests.put(
                url,
                data=f,
                auth=(user, password),
                timeout=60
            )
        return response.status_code
    except FileNotFoundError:
        return 404
    except Exception:
        return 500


def download_file_webdav(remote_path: str, local_path: str, user: str, password: str) -> int:
    """
    Scarica file via WebDAV
    
    Args:
        remote_path: Percorso file su Nextcloud
        local_path: Percorso destinazione locale
        user: Username
        password: Password
        
    Returns:
        Status code (200 = successo)
    """
    base_url, _, _ = get_nc_config()
    url = f"{base_url}/remote.php/dav/files/{user}/{remote_path.strip('/')}"
    
    try:
        response = requests.get(
            url,
            auth=(user, password),
            timeout=60,
            stream=True
        )
        
        if response.status_code == 200:
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        
        return response.status_code
    except Exception:
        return 500


def create_folder_structure(user: str, password: str, root_domain: str, subdomains: List[str]) -> dict:
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
    if not validate_domain(root_domain):
        raise ValueError(f"Dominio non valido: {root_domain}")
    
    for subdomain in subdomains:
        if not validate_domain(subdomain):
            raise ValueError(f"Sottodominio non valido: {subdomain}")
    
    results = {}
    
    # Lista tutte le cartelle da creare
    folders_to_create = [
        "public",
        "logs", 
        "backup",
        f"public/{root_domain}"
    ]
    
    # Aggiungi sottodomini
    for subdomain in subdomains:
        folders_to_create.append(f"public/{subdomain}")
    
    # Delay per rate limiting
    import time
    DELAY_BETWEEN_REQUESTS = 2  # 2 secondi tra richieste
    
    for folder in folders_to_create:
        try:
            # Delay per evitare rate limiting
            time.sleep(DELAY_BETWEEN_REQUESTS)
            
            status = create_webdav_folder(folder, user, password)
            results[folder] = status
            
            if status == 429:  # Rate limited
                print(f"⚠️ Rate limiting per {folder}, attesa più lunga...")
                time.sleep(10)  # Attesa più lunga
                
                # Riprova una volta
                status = create_webdav_folder(folder, user, password)
                results[folder] = status
                
        except Exception as e:
            print(f"❌ Errore creazione cartella {folder}: {e}")
            results[folder] = 500
    
    return results


def get_webdav_space_info(user: str, password: str) -> Optional[dict]:
    """
    Ottiene informazioni spazio WebDAV per utente
    
    Args:
        user: Username
        password: Password
        
    Returns:
        Dict con quota e spazio usato o None se errore
    """
    try:
        status_code, xml_response = list_webdav_directory(user, password, "")
        
        if status_code not in (200, 207):
            return None
        
        # Parse XML per trovare informazioni quota
        # Questo è un parsing semplificato - in produzione usare xml.etree
        info = {}
        
        if "<d:quota-available-bytes>" in xml_response:
            start = xml_response.find("<d:quota-available-bytes>") + 25
            end = xml_response.find("</d:quota-available-bytes>")
            if start > 24 and end > start:
                try:
                    available = int(xml_response[start:end])
                    info["available_bytes"] = available
                except:
                    pass
        
        if "<d:quota-used-bytes>" in xml_response:
            start = xml_response.find("<d:quota-used-bytes>") + 20
            end = xml_response.find("</d:quota-used-bytes>")
            if start > 19 and end > start:
                try:
                    used = int(xml_response[start:end])
                    info["used_bytes"] = used
                except:
                    pass
        
        # Calcola quota totale se abbiamo entrambi i valori
        if "available_bytes" in info and "used_bytes" in info:
            info["total_bytes"] = info["available_bytes"] + info["used_bytes"]
        
        return info if info else None
        
    except Exception:
        return None


def share_webdav_folder(path: str, user: str, password: str, share_type: str = "public") -> Optional[str]:
    """
    Condivide una cartella via API OCS
    
    Args:
        path: Percorso cartella da condividere
        user: Username proprietario
        password: Password utente
        share_type: Tipo condivisione ("public", "user", "group")
        
    Returns:
        URL di condivisione o None se errore
    """
    base_url, admin_user, admin_pass = get_nc_config()
    url = f"{base_url}/ocs/v2.php/apps/files_sharing/api/v1/shares"
    
    try:
        data = {
            "path": f"/{path.strip('/')}",
            "shareType": "3" if share_type == "public" else "0"  # 3=public, 0=user
        }
        
        response = requests.post(
            url,
            headers=nc_headers(),
            auth=(user, password),
            data=data,
            timeout=30
        )
        
        if response.status_code in (200, 201):
            # Parse XML per ottenere URL
            if "<url>" in response.text:
                start = response.text.find("<url>") + 5
                end = response.text.find("</url>")
                if start > 4 and end > start:
                    return response.text[start:end]
        
        return None
        
    except Exception:
        return None


def get_nextcloud_version() -> Optional[str]:
    """
    Ottiene versione Nextcloud server
    
    Returns:
        Stringa versione o None se errore
    """
    try:
        base_url, _, _ = get_nc_config()
        url = f"{base_url}/status.php"
        
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get("version")
        
        return None
        
    except Exception:
        return None


def test_nextcloud_connectivity() -> Tuple[bool, str]:
    """
    Test connettività server Nextcloud
    
    Returns:
        Tupla (successo, messaggio)
    """
    try:
        base_url, admin_user, admin_pass = get_nc_config()
        
        # Test status endpoint
        status_url = f"{base_url}/status.php"
        response = requests.get(status_url, timeout=10)
        
        if response.status_code != 200:
            return False, f"Status endpoint non raggiungibile: {response.status_code}"
        
        # Test autenticazione admin
        auth_url = f"{base_url}/ocs/v1.php/cloud/capabilities"
        response = requests.get(
            auth_url,
            headers=nc_headers(),
            auth=(admin_user, admin_pass),
            timeout=10
        )
        
        if response.status_code == 401:
            return False, "Credenziali admin non valide"
        elif response.status_code != 200:
            return False, f"API OCS non raggiungibile: {response.status_code}"
        
        # Ottieni versione
        version = get_nextcloud_version()
        return True, f"Connessione OK (Nextcloud {version or 'unknown'})"
        
    except requests.Timeout:
        return False, "Timeout connessione al server"
    except requests.ConnectionError:
        return False, "Impossibile raggiungere il server"
    except Exception as e:
        return False, f"Errore: {str(e)}"


def sync_user_quota(user_id: str, nextcloud_quota: str, filesystem_quota: str) -> dict:
    """
    Sincronizza quota utente tra Nextcloud e filesystem
    
    Args:
        user_id: Username
        nextcloud_quota: Quota Nextcloud (es. "100 GB")
        filesystem_quota: Quota filesystem (es. "2G")
        
    Returns:
        Dict con risultati operazioni
    """
    results = {
        "nextcloud": False,
        "filesystem": False,
        "errors": []
    }
    
    # Imposta quota Nextcloud
    try:
        set_nc_quota(user_id, nextcloud_quota)
        results["nextcloud"] = True
    except Exception as e:
        results["errors"].append(f"Nextcloud: {str(e)}")
    
    # Imposta quota filesystem
    try:
        from .quota import QuotaManager
        quota_manager = QuotaManager()
        if quota_manager.set_quota(user_id, filesystem_quota):
            results["filesystem"] = True
        else:
            results["errors"].append("Filesystem: errore impostazione quota")
    except Exception as e:
        results["errors"].append(f"Filesystem: {str(e)}")
    
    return results


# Alias per compatibilità con versioni precedenti
dav_probe = test_webdav_login
mkcol = create_webdav_folder
ensure_tree = create_folder_structure
list_directory = list_webdav_directory
