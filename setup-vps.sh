#!/bin/bash
# setup-vps.sh - Setup completo per VPS con Miniconda

echo "🚀 Setup Nextcloud Wrapper su VPS con Miniconda"
echo "==============================================="

# Verifica di essere root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Questo script deve essere eseguito come root"
    exit 1
fi

# Verifica ambiente conda
if [ "$CONDA_DEFAULT_ENV" != "nextcloud-wrapper" ]; then
    echo "⚠️  ATTENZIONE: Assicurati di essere nell'ambiente 'nextcloud-wrapper'"
    echo "Esegui: conda activate nextcloud-wrapper"
    echo ""
    read -p "Continuare comunque? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Directory di lavoro
PROJECT_DIR="/root/src/nextcloud-wrapper"
cd "$PROJECT_DIR" || {
    echo "❌ Directory $PROJECT_DIR non trovata"
    exit 1
}

echo "📍 Working directory: $(pwd)"
echo "🐍 Python: $(which python)"
echo "🐍 Conda env: $CONDA_DEFAULT_ENV"

# 1. Installa dipendenze sistema se necessarie
echo ""
echo "1️⃣ Verifica dipendenze sistema..."

# RClone
if ! command -v rclone >/dev/null; then
    echo "📦 Installando rclone..."
    curl https://rclone.org/install.sh | bash
else
    echo "✅ rclone già installato: $(rclone version | head -1)"
fi

# Quota tools
if ! command -v quota >/dev/null; then
    echo "📦 Installando quota tools..."
    if command -v yum >/dev/null; then
        yum install -y quota
    elif command -v apt >/dev/null; then
        apt update && apt install -y quota
    else
        echo "⚠️  Installare manualmente quota tools"
    fi
else
    echo "✅ quota tools disponibili"
fi

# FUSE
if ! command -v fusermount >/dev/null; then
    echo "📦 Installando FUSE..."
    if command -v yum >/dev/null; then
        yum install -y fuse
    elif command -v apt >/dev/null; then
        apt update && apt install -y fuse
    fi
else
    echo "✅ FUSE disponibile"
fi

# 2. Setup ambiente Python
echo ""
echo "2️⃣ Setup ambiente Python..."

# Aggiorna pip
pip install --upgrade pip setuptools wheel

# Installa dipendenze
echo "📦 Installando dipendenze Python..."
pip install typer[all]>=0.9.0 requests>=2.28.0 rich>=13.0.0 click>=8.0.0

# Installa package in modalità development
echo "📦 Installando nextcloud-wrapper in modalità development..."
pip install -e .

# 3. Verifica installazione
echo ""
echo "3️⃣ Verifica installazione..."
if command -v nextcloud-wrapper >/dev/null; then
    echo "✅ nextcloud-wrapper installato: $(which nextcloud-wrapper)"
    nextcloud-wrapper --help | head -5
else
    echo "❌ nextcloud-wrapper non installato correttamente"
    exit 1
fi

# 4. Setup configurazione
echo ""
echo "4️⃣ Setup configurazione..."

# Crea directory config
mkdir -p ~/.config/ncwrap
mkdir -p /var/log
mkdir -p /mnt/nextcloud

# Crea .env se non esiste
if [ ! -f .env ]; then
    echo "📝 Creando file .env..."
    cat > .env << 'EOF'
# === NEXTCLOUD WRAPPER CONFIGURATION ===

# Nextcloud server settings (MODIFICA QUESTI!)
NC_BASE_URL=https://your-nextcloud.domain.com
NC_ADMIN_USER=admin
NC_ADMIN_PASS=your_admin_password_here

# Default settings ottimizzati per VPS
NC_DEFAULT_FS_PERCENTAGE=0.02
NC_DEFAULT_QUOTA=100G
NC_MOUNT_BASE_DIR=/mnt/nextcloud

# Service settings
NC_SERVICE_USER=root
NC_AUTO_ENABLE_SERVICES=true

# Performance settings
RCLONE_MOUNT_OPTIONS="--vfs-cache-mode writes --vfs-cache-max-size 2G --buffer-size 64M"

# Logging
NC_LOG_LEVEL=INFO
NC_LOG_FILE=/var/log/nextcloud-wrapper.log

# Security
NC_REQUIRE_SSL=true
NC_VERIFY_SSL=true
NC_API_TIMEOUT=30
EOF
    echo "✅ File .env creato"
    echo "⚠️  IMPORTANTE: Modifica .env con le tue configurazioni!"
else
    echo "ℹ️  File .env già esistente"
fi

# 5. Setup alias e shortcuts
echo ""
echo "5️⃣ Setup alias e shortcuts..."

# Backup .bashrc
cp ~/.bashrc ~/.bashrc.backup.$(date +%Y%m%d-%H%M%S)

# Aggiungi configurazione
if ! grep -q "NEXTCLOUD WRAPPER" ~/.bashrc; then
    cat >> ~/.bashrc << 'EOF'

# === NEXTCLOUD WRAPPER CONFIGURATION ===

# Funzione di attivazione rapida
nw-activate() {
    cd /root/src/nextcloud-wrapper
    conda activate nextcloud-wrapper 2>/dev/null
    if [ -f .env ]; then
        source .env
        echo "✅ Ambiente nextcloud-wrapper attivato"
    fi
}

# Auto-attivazione quando si entra nella directory
nextcloud_auto_activate() {
    if [[ "$PWD" == "/root/src/nextcloud-wrapper"* ]] && [[ "$CONDA_DEFAULT_ENV" != "nextcloud-wrapper" ]]; then
        conda activate nextcloud-wrapper 2>/dev/null
        if [ -f .env ]; then
            source .env 2>/dev/null
        fi
    fi
}

# Hook per cd
original_cd=$(declare -f cd)
cd() {
    if [ -n "$original_cd" ]; then
        eval "$original_cd"
    else
        builtin cd "$@"
    fi
    nextcloud_auto_activate
}

# Alias utili
alias nw='nextcloud-wrapper'
alias nw-activate='cd /root/src/nextcloud-wrapper && conda activate nextcloud-wrapper && source .env'
alias nw-config='nextcloud-wrapper config'
alias nw-status='echo "🔗 Remote:" && nextcloud-wrapper mount list && echo "" && echo "⚙️ Services:" && nextcloud-wrapper service list'
alias nw-logs='journalctl -u nextcloud-* --since "1 hour ago" --no-pager | tail -20'
alias nw-profiles='nextcloud-wrapper mount profiles'
alias nw-quota='nextcloud-wrapper quota show'

# === END NEXTCLOUD WRAPPER ===
EOF
    echo "✅ Configurazione aggiunta a ~/.bashrc"
else
    echo "ℹ️  Configurazione già presente in ~/.bashrc"
fi

# 6. Test configurazione
echo ""
echo "6️⃣ Test configurazione..."

# Source .env per test
if [ -f .env ]; then
    source .env
fi

# Test comandi base
echo "🧪 Test comandi base:"
nextcloud-wrapper mount profiles
echo ""
nextcloud-wrapper --version 2>/dev/null || echo "Package in development mode"

# 7. Setup permessi
echo ""
echo "7️⃣ Setup permessi..."

# Crea directory log se non esiste
touch /var/log/nextcloud-wrapper.log
chmod 644 /var/log/nextcloud-wrapper.log

# Permessi directory mount
chmod 755 /mnt/nextcloud

# 8. Mostra riepilogo
echo ""
echo "🎉 SETUP COMPLETATO!"
echo "==================="
echo ""
echo "📋 Configurazione attuale:"
echo "Directory progetto: $PROJECT_DIR"
echo "Python: $(which python)"
echo "nextcloud-wrapper: $(which nextcloud-wrapper)"
echo "Conda env: $CONDA_DEFAULT_ENV"
echo ""
echo "📝 Prossimi passi:"
echo "1. Ricarica bash: source ~/.bashrc"
echo "2. Modifica configurazioni: nano .env"
echo "3. Test configurazione: nextcloud-wrapper config"
echo "4. Setup primo utente: nextcloud-wrapper setup test.com password123"
echo ""
echo "🔧 Comandi rapidi:"
echo "nw                 # Alias per nextcloud-wrapper"
echo "nw-activate        # Attiva ambiente e carica .env"
echo "nw-config          # Verifica configurazione"
echo "nw-status          # Status mount e servizi"
echo "nw-profiles        # Mostra profili mount"
echo ""
echo "📁 File importanti:"
echo "Configurazione: $PROJECT_DIR/.env"
echo "Log: /var/log/nextcloud-wrapper.log"
echo "RClone config: ~/.config/ncwrap/rclone.conf"
echo ""
echo "🎯 Per iniziare subito:"
echo "1. source ~/.bashrc"
echo "2. nw-activate"
echo "3. nano .env  # Modifica con i tuoi dati Nextcloud"
echo "4. nw config  # Verifica tutto funzioni"
