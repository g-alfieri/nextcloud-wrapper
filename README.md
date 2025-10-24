# NextCloud Wrapper - rclone Engine Semplificato

> **Versione 1.0.0rc2** - Wrapper Python per gestire Nextcloud con rclone engine semplificato

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![rclone](https://img.shields.io/badge/rclone-Engine-green.svg)](https://rclone.org)
[![Version](https://img.shields.io/badge/Version-1.0.0rc2-orange.svg)]()

## 🚀 Quick Setup - Guida Rapida

### Prerequisiti
- Python 3.8 o superiore
- Git
- Sistema Linux/Unix (testato su Ubuntu/Debian)
- Privilegi sudo per creazione utenti Linux
- Istanza NextCloud accessibile

### 1. Clonazione e Setup Iniziale

```bash
# Clona il repository
git clone https://github.com/g-alfieri/nextcloud-wrapper.git
cd nextcloud-wrapper

# Setup ambiente Python (opzione 1: Miniconda - raccomandato)
./setup-miniconda.sh

# Setup ambiente Python (opzione 2: venv standard)
python -m venv nextcloud-wrapper-env
source nextcloud-wrapper-env/bin/activate  # Linux/macOS

# Installa dipendenze
pip install -r requirements.txt
pip install -e .
```

### 2. Configurazione Base

```bash
# Copia il template di configurazione
cp .env.example .env

# Modifica con i tuoi dati NextCloud
nano .env
```

**Configurazione Minima Richiesta (.env):**
```bash
# Configurazione NextCloud Instance
NC_BASE_URL=https://tuo-nextcloud.esempio.com
NC_ADMIN_USER=admin
NC_ADMIN_PASS=password_admin

# Profilo rclone predefinito
NC_DEFAULT_RCLONE_PROFILE=full
```

### 3. Primi Passi - Setup Utente Standard

```bash
# Verifica configurazione
nextcloud-wrapper config

# Setup rapido utente con profilo predefinito
nextcloud-wrapper setup quick nomedominio.com password123

# Oppure setup completo con opzioni
nextcloud-wrapper setup user nomedominio.com password123 \
  --quota 100G --profile full

# Verifica status
nextcloud-wrapper status
nextcloud-wrapper mount status
```

### 4. Verifica Funzionamento

```bash
# Lista utenti configurati
nextcloud-wrapper user list

# Informazioni dettagliate utente
nextcloud-wrapper user info nomedominio.com

# Status mount rclone
nextcloud-wrapper mount status

# Lista servizi systemd
nextcloud-wrapper mount service list
```

---

## 📋 Comandi CLI Disponibili

### Comandi Principali

```bash
nextcloud-wrapper --version          # Mostra versione
nextcloud-wrapper config             # Mostra configurazione
nextcloud-wrapper status             # Status generale sistema
```

### Setup e Configurazione

```bash
# Setup completo utente
nextcloud-wrapper setup user <username> <password> [opzioni]
  --quota <size>          # Quota NextCloud (es. 100G)
  --profile <profile>     # Profilo rclone (hosting/minimal/writes/full)
  --sub <domains>         # Sottodomini (es. www,blog,shop)
  --skip-linux           # Non creare utente Linux
  --skip-test            # Non testare connettività
  --service/--no-service # Crea/non creare servizio systemd
  --remount              # Forza remount se già esistente

# Setup rapido con predefiniti
nextcloud-wrapper setup quick <username> <password>

# Mostra profili disponibili
nextcloud-wrapper setup profiles

# Mostra configurazione setup
nextcloud-wrapper setup config
```

### Gestione Mount

```bash
# Lista profili mount disponibili
nextcloud-wrapper mount profiles

# Mount manuale utente
nextcloud-wrapper mount mount <username> <password> [opzioni]
  --mount-point <path>    # Directory mount (default: /home/username)
  --profile <profile>     # Profilo mount
  --service/--no-service # Crea servizio systemd
  --force                # Forza mount anche se directory non vuota
  --remount              # Forza remount se già montato

# Unmount directory
nextcloud-wrapper mount unmount <mount_point>

# Status mount attivi
nextcloud-wrapper mount status [--detailed]

# Informazioni mount specifico
nextcloud-wrapper mount info <mount_point> [--check-space]

# Test mount temporaneo
nextcloud-wrapper mount test <username> <password> [--profile <profile>]

# Setup completo mount + utente
nextcloud-wrapper mount setup <username> <password> [opzioni]

# Installa rclone
nextcloud-wrapper mount install [--configure/--no-configure]
```

### Gestione Utenti

```bash
# Lista tutti gli utenti
nextcloud-wrapper user list [--format table|json]

# Informazioni utente dettagliate
nextcloud-wrapper user info <username> [--include-stats]

# Mount rapido utente esistente
nextcloud-wrapper user mount <username> [--profile <profile>]

# Statistiche utilizzo utente
nextcloud-wrapper user stats <username> [--time-range 24h]
```

### Gestione Servizi SystemD

```bash
# Lista servizi nextcloud-wrapper
nextcloud-wrapper mount service list

# Status servizio specifico
nextcloud-wrapper mount service status <service_name> [--user]

# Abilita/avvia servizio
nextcloud-wrapper mount service enable <service_name> [--user]

# Disabilita/ferma servizio
nextcloud-wrapper mount service disable <service_name> [--user]

# Riavvia servizio
nextcloud-wrapper mount service restart <service_name> [--user]

# Mostra log servizio
nextcloud-wrapper mount service logs <service_name> [--user] [--lines 50] [--follow]

# Ricrea servizio per utente esistente
nextcloud-wrapper mount service recreate <username> [--password <pass>] [--profile <profile>] [--force]
```

### Ambiente Virtuale

```bash
# Setup virtual environment
nextcloud-wrapper venv setup [--python 3.8+]

# Attiva ambiente
nextcloud-wrapper venv activate

# Status ambiente
nextcloud-wrapper venv status
```

---

## 🎯 Profili rclone Disponibili

| Profilo | Cache | Sync | Uso | Performance |
|---------|-------|------|-----|-------------|
| **hosting** | 0 bytes (streaming) | Read-only | Web hosting, SFTP | Network dependent |
| **minimal** | Max 1GB, auto-cleanup | Read-only | Hosting leggero | Buona con cache |
| **writes** | Max 2GB, persistente | Bidirezionale | Sviluppo, editing | Ottima |
| **full** | Max 5GB, persistente | Bidirezionale | Uso completo | Migliore |

### Dettagli Profili

**hosting**: Zero cache locale, streaming puro per web server e CDN
- Ideale per: Apache/Nginx serving, accesso SFTP read-only
- Storage: 0 bytes, tutto in streaming
- Sync: Solo lettura, nessun upload

**minimal**: Cache temporanea con pulizia automatica
- Ideale per: Hosting con cache temporanea, accessi sporadici
- Storage: Max 1GB con auto-cleanup ogni ora
- Sync: Solo lettura, nessun upload

**writes**: Cache intelligente per file modificati
- Ideale per: Sviluppo, editing file, sync automatico modifiche
- Storage: Max 2GB persistente con cleanup LRU
- Sync: Bidirezionale completo

**full**: Cache completa per massime performance
- Ideale per: Uso intensivo, proxy filesystem completo
- Storage: Max 5GB persistente con cleanup LRU
- Sync: Bidirezionale completo

---

## 💡 Esempi d'Uso Pratici

### Setup Hosting Web
```bash
# Hosting con profilo ottimizzato e sottodomini
sudo nextcloud-wrapper setup user sito.com password123 \
  --profile hosting \
  --quota 500G \
  --sub www,blog,shop
```

### Setup Sviluppo
```bash
# Ambiente sviluppo con sync bidirezionale
sudo nextcloud-wrapper setup user dev.locale devpass456 \
  --profile writes \
  --quota 50G
```

### Setup Enterprise
```bash
# Configurazione enterprise con cache massima
sudo nextcloud-wrapper setup user azienda.com enterprisepass \
  --profile full \
  --quota 1T
```

### Test e Debug
```bash
# Test connettività e mount temporaneo
nextcloud-wrapper mount test utente.com password --profile minimal

# Ricrea servizio sistemd per utente esistente
sudo nextcloud-wrapper mount service recreate utente.com --profile full --force
```

---

## 🛠️ Installazione Dettagliata

### Opzione 1: Setup Automatizzato (Raccomandato)

```bash
git clone https://github.com/g-alfieri/nextcloud-wrapper.git
cd nextcloud-wrapper
./setup-miniconda.sh
# Segui le istruzioni per configurare .env
```

### Opzione 2: Python venv

```bash
python -m venv nextcloud-wrapper-env
source nextcloud-wrapper-env/bin/activate
pip install -r requirements.txt
pip install -e .
```

### Opzione 3: Conda Environment

```bash
conda env create -f environment.yml
conda activate nextcloud-wrapper
```

### Verifica Installazione

```bash
# Test importi Python
python test_import.py

# Test caricamento configurazione
python test_env_loading.py

# Test completo
./test-complete.sh
```

---

## 🚨 Risoluzione Problemi

### Problemi Comuni

**Errore "Privilegi sudo richiesti"**
```bash
# Assicurati di eseguire con sudo per operazioni di sistema
sudo nextcloud-wrapper setup user ...
```

**Errore "rclone non disponibile"**
```bash
# Installa rclone automaticamente
sudo nextcloud-wrapper mount install
```

**Problemi di line endings (Windows)**
```bash
# Fix automatico per file .env
./fix-env-crlf.sh
```

**Test connettività fallito**
```bash
# Verifica configurazione
nextcloud-wrapper config

# Test manuale connettività
nextcloud-wrapper mount test username password
```

### Debug e Diagnostica

```bash
# Test completo ambiente
./test-complete.sh

# Informazioni sistema
nextcloud-wrapper status

# Log servizi
nextcloud-wrapper mount service logs ncwrap-rclone-username --lines 100

# Status mount dettagliato
nextcloud-wrapper mount status --detailed
```

---

## 📂 Struttura Progetto

```
nextcloud-wrapper/
├── ncwrap/                 # Package principale
│   ├── cli.py             # CLI principale
│   ├── cli_setup.py       # Comandi setup
│   ├── cli_mount.py       # Comandi mount
│   ├── cli_user.py        # Comandi utente
│   ├── cli_venv.py        # Comandi ambiente virtuale
│   ├── api.py             # API NextCloud
│   ├── rclone.py          # Gestione rclone
│   ├── mount.py           # Logica mount
│   ├── system.py          # Operazioni sistema
│   ├── systemd.py         # Gestione servizi
│   └── utils.py           # Utility
├── .env.example           # Template configurazione
├── requirements.txt       # Dipendenze Python
├── setup-miniconda.sh     # Setup automatico
├── test-complete.sh       # Test completo
└── pyproject.toml         # Configurazione progetto
```

---

## 🔧 Configurazione Avanzata

### File .env Completo

```bash
# NextCloud Instance Configuration
NC_BASE_URL=https://cloud.esempio.com
NC_ADMIN_USER=admin
NC_ADMIN_PASS=password_admin
NC_API_TIMEOUT=30
NC_MAX_RETRIES=3

# rclone Configuration
NC_DEFAULT_RCLONE_PROFILE=full
NC_CACHE_DIR=/var/cache/nextcloud-wrapper
NC_LOG_LEVEL=INFO
NC_MAX_CONCURRENT_MOUNTS=50

# Virtual Environment
NC_VENV_NAME=nextcloud-wrapper
NC_AUTO_ACTIVATE=true
NC_PYTHON_VERSION=3.8+

# Security Settings
NC_SSL_VERIFY=true
NC_BACKUP_RETENTION_DAYS=30
NC_AUDIT_LOG_ENABLED=true
```

### Ottimizzazione Performance

- **hosting**: Per web server con accesso principalmente read-only
- **minimal**: Per uso sporadico con pulizia automatica cache
- **writes**: Per sviluppo con sync bidirezionale efficiente
- **full**: Per uso intensivo con cache massima

---

## 🏗️ Architettura Sistema

### Componenti Principali

- **CLI Layer**: Interfaccia utente con Typer + Rich
- **rclone Engine**: Unico engine per mount e sync
- **SystemD Integration**: Servizi automatici per mount persistenti
- **NextCloud API**: Gestione utenti e configurazione
- **Cache LRU**: Gestione automatica spazio cache

### Flusso Operazioni

1. **Setup**: Crea utente NextCloud + Linux + mount rclone
2. **Mount**: Configura remote rclone + mount con profilo specifico
3. **Service**: Crea servizio systemd per mount automatico
4. **Sync**: Gestione automatica sync bidirezionale
5. **Cache**: Cleanup automatico LRU basato su profilo

---

## 📞 Supporto e Contributi

**Repository**: [https://github.com/g-alfieri/nextcloud-wrapper](https://github.com/g-alfieri/nextcloud-wrapper)  
**Sviluppatore**: Giuseppe Alfieri  
**Versione**: 1.0.0rc2  
**Engine**: rclone Semplificato  

### Segnalazione Bug

Per segnalare problemi:
1. Esegui `./test-complete.sh` per diagnostica
2. Raccogli log con `nextcloud-wrapper mount service logs`
3. Apri issue su GitHub con log completi

---

**© 2025 Giuseppe Alfieri - NextCloud Wrapper rclone Engine**