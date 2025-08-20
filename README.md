# Nextcloud Wrapper

Wrapper Python per gestire utenti Nextcloud, sincronizzazione con sistema Linux e creazione strutture cartelle automatiche.

## Caratteristiche

- ✅ Creazione utenti Nextcloud via API OCS
- ✅ Sincronizzazione utenti Linux con stesse credenziali  
- ✅ Creazione automatica struttura cartelle (`/public`, `/logs`, `/backup`)
- ✅ Gestione domini e sottodomini 
- ✅ Test login WebDAV
- ✅ Cambio password sincronizzato
- ✅ CLI intuitiva con Rich output

## Installazione

```bash
# Clona il repository
git clone <your-repo-url>
cd nextcloud-wrapper

# Installa in modalità sviluppo
pip install -e .

# Oppure installazione normale
pip install .
```

## Configurazione

Imposta le variabili d'ambiente per l'accesso admin Nextcloud:

```bash
export NC_BASE_URL="https://your-nextcloud.example.com"
export NC_ADMIN_USER="admin"
export NC_ADMIN_PASS="your_admin_password"
```

> **Nota**: Per la gestione utenti Linux sono richiesti privilegi sudo.

## Utilizzo CLI

### Visualizza configurazione
```bash
nextcloud-wrapper config
```

### Crea nuovo utente completo
```bash
# Utente base (dominio principale)
nextcloud-wrapper crea-utente casacialde.com 'SuperSegreta!123'

# Con sottodomini
nextcloud-wrapper crea-utente casacialde.com 'SuperSegreta!123' \
  --sub spedizioni.casacialde.com \
  --sub api.casacialde.com

# Solo Nextcloud (salta creazione utente Linux)
nextcloud-wrapper crea-utente casacialde.com 'SuperSegreta!123' --skip-linux
```

Questo comando:
1. Crea utente in Nextcloud
2. Testa login WebDAV 
3. Crea struttura cartelle:
   ```
   /public/
   ├── casacialde.com/
   ├── spedizioni.casacialde.com/
   └── api.casacialde.com/
   /logs/
   /backup/
   ```
4. Crea utente Linux corrispondente

### Test login
```bash
nextcloud-wrapper test-login casacialde.com 'SuperSegreta!123'
```

### Cambia password
```bash
# Sincronizza Nextcloud + Linux
nextcloud-wrapper cambia-password casacialde.com 'NuovaPassword456!'

# Solo Nextcloud
nextcloud-wrapper cambia-password casacialde.com 'NuovaPassword456!' --nc-only
```

### Lista cartelle utente
```bash
# Root directory
nextcloud-wrapper lista-cartelle casacialde.com 'SuperSegreta!123'

# Cartella specifica
nextcloud-wrapper lista-cartelle casacialde.com 'SuperSegreta!123' --path public
```

### Informazioni utente
```bash
nextcloud-wrapper info-utente casacialde.com
```

## Test e Verifica

### Test API Nextcloud manuale
```bash
# Verifica utente creato
curl -u admin:admin_password \
  -H "OCS-APIRequest: true" \
  "$NC_BASE_URL/ocs/v1.php/cloud/users?search=casacialde.com"

# Test WebDAV
curl -u casacialde.com:'SuperSegreta!123' \
  -X PROPFIND -H 'Depth: 0' \
  "$NC_BASE_URL/remote.php/dav/files/casacialde.com/"
```

### Verifica struttura cartelle
```bash
# Lista cartelle public
curl -u casacialde.com:'SuperSegreta!123' \
  -X PROPFIND -H 'Depth: 1' \
  "$NC_BASE_URL/remote.php/dav/files/casacialde.com/public/" | grep displayname
```

### Verifica utente Linux
```bash
# Info utente
id casacialde.com

# Test login (se SSH abilitato)
ssh casacialde.com@localhost
```

## Struttura del Progetto

```
ncwrap/
├── __init__.py
├── api.py          # API Nextcloud (OCS + WebDAV)
├── system.py       # Gestione utenti Linux
├── cli.py          # Interfaccia comando
├── quota.py        # Gestione quote (TODO)
├── rclone.py       # Integrazione rclone (TODO)
├── systemd.py      # Servizi systemd (TODO)
├── users.py        # Logica utenti avanzata (TODO)
└── utils.py        # Utility varie (TODO)
```

## API Python

Oltre alla CLI, puoi usare le funzioni direttamente:

```python
from ncwrap.api import create_nc_user, dav_probe, ensure_tree
from ncwrap.system import create_linux_user, sync_passwords

# Crea utente Nextcloud
create_nc_user("test.com", "password123")

# Test login
status, response = dav_probe("test.com", "password123")
print(f"Login status: {status}")

# Crea struttura cartelle
results = ensure_tree(
    "test.com", 
    "password123", 
    "test.com", 
    ["api.test.com", "shop.test.com"]
)

# Utente Linux
create_linux_user("test.com", "password123")

# Sincronizza password
results = sync_passwords("test.com", "new_password")
```

## Esempi Completi

### Scenario 1: Setup dominio e-commerce
```bash
# Dominio principale + sottodomini
nextcloud-wrapper crea-utente ecommerce.it 'Secure123!' \
  --sub shop.ecommerce.it \
  --sub api.ecommerce.it \
  --sub admin.ecommerce.it

# Verifica struttura
nextcloud-wrapper lista-cartelle ecommerce.it 'Secure123!' --path public
```

### Scenario 2: Solo backup/storage
```bash
# Utente solo per storage (senza Linux)
nextcloud-wrapper crea-utente backup-server.com 'BackupPass456!' --skip-linux

# Test accesso
nextcloud-wrapper test-login backup-server.com 'BackupPass456!'
```

### Scenario 3: Cambio password di massa (script)
```bash
#!/bin/bash
DOMINI=("sito1.com" "sito2.com" "sito3.com")
NUOVA_PASS="NewSecurePass789!"

for dominio in "${DOMINI[@]}"; do
  echo "Aggiornando password per $dominio..."
  nextcloud-wrapper cambia-password "$dominio" "$NUOVA_PASS"
done
```

## Troubleshooting

### Errori comuni

1. **"Variabili d'ambiente mancanti"**
   ```bash
   # Verifica configurazione
   nextcloud-wrapper config
   
   # Imposta variabili se mancanti
   export NC_BASE_URL="https://your-nextcloud.com"
   export NC_ADMIN_USER="admin"  
   export NC_ADMIN_PASS="password"
   ```

2. **"Privilegi sudo richiesti"**
   ```bash
   # Verifica sudo
   sudo -n true && echo "OK" || echo "Sudo richiesto"
   
   # Esegui con sudo se necessario
   sudo -E nextcloud-wrapper crea-utente test.com password123
   ```

3. **"Login WebDAV fallito: HTTP 401"**
   - Verifica credenziali utente
   - Controlla che l'utente sia stato creato correttamente
   - Testa manualmente con curl

4. **"Errore creazione cartelle: HTTP 404"**
   - Verifica che l'utente abbia accesso WebDAV
   - Controlla URL base Nextcloud
   - Verifica permessi utente

### Debug mode
```bash
# Output verboso (TODO: implementare)
nextcloud-wrapper --verbose crea-utente test.com password123

# Test connettività
curl -I "$NC_BASE_URL/status.php"
```

## Limitazioni Attuali

- Gestione password unidirezionale (dal tool verso NC/Linux)
- Nessun webhook automatico per cambi password da interfaccia NC
- Richiede privilegi sudo per operazioni Linux
- Parsing XML WebDAV semplificato

## Roadmap

- [ ] Integrazione rclone per sync automatici
- [ ] Gestione quote utente avanzata  
- [ ] Webhook listeners per eventi Nextcloud
- [ ] Supporto backend LDAP/SSO
- [ ] Interfaccia web opzionale
- [ ] Docker container ready
- [ ] Unit tests completi

## Contribuire

1. Fork del repository
2. Crea branch feature (`git checkout -b feature/nuova-funzione`)
3. Commit modifiche (`git commit -am 'Aggiunge nuova funzione'`)
4. Push branch (`git push origin feature/nuova-funzione`)
5. Apri Pull Request

## Licenza

MIT License - vedi `LICENSE` file per dettagli.

## Supporto

Per problemi o domande:
- Apri un issue su GitHub
- Controlla la documentazione API Nextcloud
- Verifica log Nextcloud in `/var/log/nextcloud/`