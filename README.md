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

### Guidelines Sviluppo

- **Quote Logic**: sempre usare `filesystem = nextcloud * percentage`
- **RClone Options**: preferire `writes` invece di `full` per vfs-cache
- **CLI Design**: sotto-comandi logici (`user`, `mount`, `quota`, `service`)
- **Error Handling**: sempre gestire errori con messaggi utili
- **Testing**: testare su btrfs, ext4, xfs

## Testing

### Test Suite Completo
```bash
# Test setup base
nextcloud-wrapper setup test-user.com 'TestPass123!' --quota 10G --fs-percentage 0.1

# Verifica tutto funzioni
nextcloud-wrapper user info test-user.com
nextcloud-wrapper quota show test-user.com  # Dovrebbe mostrare ~1GB filesystem
nextcloud-wrapper mount list
nextcloud-wrapper service list

# Cleanup
nextcloud-wrapper service disable nextcloud-mount-test-user
sudo userdel -r test-user.com
```

### Test Performance
```bash
# Test mount performance
time nextcloud-wrapper mount mount test-user /mnt/test

# Test sync performance
time nextcloud-wrapper mount sync /tmp/testdata test-user:/backup --dry-run

# Test quota enforcement
dd if=/dev/zero of=/home/test-user/bigfile bs=1M count=1100  # Dovrebbe fallire se quota 1GB
```

### Test Multi-Filesystem
```bash
# Test su ext4
nextcloud-wrapper quota set user1 100G --fs-percentage 0.02

# Test su btrfs (se disponibile)
sudo btrfs subvolume create /home/user2
nextcloud-wrapper quota set user2 100G --fs-percentage 0.02
```

## Deployment Produzione

### Requisiti Sistema
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y rclone quota quotatool python3-pip fuse

# CentOS/RHEL
sudo yum install -y rclone quota python3-pip fuse

# Arch Linux
sudo pacman -S rclone quota python-pip fuse
```

### Setup Produzione
```bash
# 1. Clone e installa
git clone <repo-url>
cd nextcloud-wrapper
pip install -e .

# 2. Configura variabili
echo 'export NC_BASE_URL="https://your-nextcloud.com"' >> ~/.bashrc
echo 'export NC_ADMIN_USER="admin"' >> ~/.bashrc
echo 'export NC_ADMIN_PASS="your-admin-pass"' >> ~/.bashrc
source ~/.bashrc

# 3. Setup quota system
sudo quotacheck -cum /
sudo quotaon /

# 4. Test configurazione
nextcloud-wrapper config
```

### Automazione Cron
```bash
# Sync automatici ogni ora
echo "0 * * * * /usr/local/bin/nextcloud-wrapper mount sync /var/backups remote:/backup" | crontab -

# Cleanup cache giornaliero
echo "0 2 * * * find /tmp -name 'rclone-*' -mtime +1 -delete" | crontab -

# Report quote settimanale
echo "0 9 * * 1 /usr/local/bin/nextcloud-wrapper quota show | mail -s 'Weekly Quota Report' admin@domain.com" | crontab -
```

## Sicurezza

### Best Practices
1. **Password Strong**: sempre usare password complesse (12+ caratteri)
2. **Sudo Limitato**: configurare sudo passwordless solo per comandi necessari
3. **Mount Security**: usare `--allow-other` solo se necessario
4. **Log Monitoring**: monitorare `/var/log/rclone-*.log`
5. **Quota Enforcement**: sempre impostare quote per prevenire disk full

### Configurazione Sudo Sicura
```bash
# /etc/sudoers.d/nextcloud-wrapper
www-data ALL=(root) NOPASSWD: /usr/bin/useradd, /usr/bin/userdel, /usr/bin/chpasswd
www-data ALL=(root) NOPASSWD: /usr/bin/setquota, /usr/bin/quota
www-data ALL=(root) NOPASSWD: /usr/bin/systemctl enable nextcloud-*
www-data ALL=(root) NOPASSWD: /usr/bin/systemctl disable nextcloud-*
```

## Monitoring

### Metriche Chiave
```bash
# Spazio utenti
nextcloud-wrapper quota show | grep -E "(Used|Limit)"

# Status mount
systemctl list-units "nextcloud-mount-*" --no-pager

# Performance rclone
journalctl -u nextcloud-mount-* --since "1 hour ago" | grep -E "(ERROR|WARN)"
```

### Alerting Semplice
```bash
#!/bin/bash
# /usr/local/bin/nextcloud-check.sh

# Check mount failures
if systemctl list-units "nextcloud-mount-*" | grep -q failed; then
    echo "ALERT: Nextcloud mount failures detected" | mail -s "Mount Alert" admin@domain.com
fi

# Check quota near limits
nextcloud-wrapper quota show | awk '$3 > 90 {print "ALERT: User " $1 " quota " $3 "% full"}' | \
    mail -s "Quota Alert" admin@domain.com
```

## FAQ

### Q: Perché filesystem quota = 2% di Nextcloud quota?
**A**: La quota filesystem serve per cache, logs e temporanei. Il 2% è generalmente sufficiente. Per workload intensivi usa 3-5%.

### Q: Posso cambiare la percentuale dopo?
**A**: Sì! `nextcloud-wrapper quota set username 100G --fs-percentage 0.05`

### Q: Come backup delle configurazioni?
**A**: Le config sono in `~/.config/ncwrap/`. Fai backup di quella directory.

### Q: Supporta multi-server?
**A**: Al momento no, ma è nella roadmap v0.3.0

### Q: Posso usare LDAP invece di utenti locali?
**A**: Non ancora, ma pianificato per v0.3.0

### Q: Come debug mount lenti?
**A**: Verifica che usi `--vfs-cache-mode writes`. Se ancora lento, prova `minimal`.

### Q: Limite massimo utenti?
**A**: Teoricamente illimitato. In pratica dipende da RAM/CPU per i mount rclone.

## Licenza

MIT License - vedi `LICENSE` file per dettagli.

## Supporto

Per problemi o domande:
- 🐛 **Bug Reports**: GitHub Issues
- 💬 **Discussioni**: GitHub Discussions  
- 📧 **Email**: supporto tecnico
- 📖 **Docs**: Questo README + commenti nel codice

## Crediti

### Sviluppatori
- **Core Team**: Sviluppo architettura modulare
- **Community**: Bug reports e feature requests

### Tecnologie
- **[RClone](https://rclone.org/)**: Mount e sync cloud storage
- **[Typer](https://typer.tiangolo.com/)**: CLI moderna e intuitiva
- **[Rich](https://rich.readthedocs.io/)**: Output colorato e tabelle
- **[Requests](https://docs.python-requests.org/)**: HTTP client per API Nextcloud

---

## 🎉 Changelog v0.2.0

### ✅ Nuovo
- **CLI unificata** con sotto-comandi logici
- **Quote intelligenti** con logica corretta (filesystem = nextcloud * %)
- **RClone manager** completo con mount ottimizzati
- **SystemD automation** per servizi persistenti
- **Setup one-shot** per configurazione rapida
- **Performance ottimizzate** (vfs-cache-mode, buffer size)

### 🔧 Migliorato
- **Mount options**: `writes` invece di `full`, buffer 64M invece di 256M
- **Error handling**: messaggi più chiari e informativi
- **Documentazione**: README completo con esempi pratici
- **API consistency**: parametri uniformi tra funzioni

### 🐛 Corretto
- **Quota logic**: filesystem quota ora calcolata correttamente
- **Memory usage**: ridotto consumo RAM sui mount
- **CLI parameters**: parametri consistenti tra comandi
- **Edge cases**: gestione errori migliorata

### 📋 Deprecato
- `nextcloud_cli.py`: sostituito da `cli.py` unificata
- Parametri quota diretti: ora usa Nextcloud quota + percentuale
- Mount options pesanti: ora ottimizzate per default

---

**🚀 Nextcloud Wrapper v0.2.0 - Production Ready!**

*From MVP to Enterprise Solution in One Major Release*

## Licenza

MIT License - vedi `LICENSE` file per dettagli.

## Supporto

Per problemi o domande:
- Apri un issue su GitHub
- Controlla la documentazione API Nextcloud
- Verifica log Nextcloud in `/var/log/nextcloud/`