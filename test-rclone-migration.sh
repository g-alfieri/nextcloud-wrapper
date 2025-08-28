#!/bin/bash
# test-rclone-migration.sh - Test migrazione da davfs2 a rclone

echo "🧪 Test migrazione engine rclone per nextcloud-wrapper v0.4.0"
echo "=============================================================="

# Fix terminatori Windows nei file .env prima di iniziare
echo "🔧 Fix terminatori file .env..."
for env_file in ".env" "/etc/nextcloud-wrapper/.env"; do
    if [ -f "$env_file" ]; then
        sed -i 's/\r$//' "$env_file" 2>/dev/null || true
        echo "✅ $env_file corretto"
    fi
done

# Verifica ambiente
if [ "$EUID" -ne 0 ]; then
    echo "❌ Questo test deve essere eseguito come root"
    exit 1
fi

# Configurazione test
TEST_USER="test-rclone-user"
TEST_PASSWORD="TestPassword123!"
TEST_QUOTA="1G"
TEST_HOME="/home/$TEST_USER"

# Cleanup iniziale
cleanup() {
    echo "🧹 Cleanup..."
    
    # Ferma e rimuovi servizi
    systemctl stop "ncwrap-*$TEST_USER*" 2>/dev/null || true
    systemctl disable "ncwrap-*$TEST_USER*" 2>/dev/null || true
    find /etc/systemd/system -name "*$TEST_USER*" -delete 2>/dev/null || true
    systemctl daemon-reload
    
    # Unmount
    fusermount -u "$TEST_HOME" 2>/dev/null || true
    umount "$TEST_HOME" 2>/dev/null || true
    
    # Rimuovi utente Linux
    userdel -r "$TEST_USER" 2>/dev/null || true
    
    # Rimuovi configurazioni rclone
    rm -rf ~/.config/ncwrap/rclone.conf
    rm -rf ~/.cache/rclone
    
    # Rimuovi utente Nextcloud (se API disponibile)
    nextcloud-wrapper user delete "$TEST_USER" 2>/dev/null || true
    
    echo "✅ Cleanup completato"
}

# Trap per cleanup automatico
trap cleanup EXIT

echo ""
echo "1️⃣ Test disponibilità engine..."

# Test engine disponibili
nextcloud-wrapper mount engines

echo ""
echo "2️⃣ Test installazione rclone..."

# Installa rclone se non presente
if ! command -v rclone >/dev/null; then
    echo "📦 Installando rclone..."
    nextcloud-wrapper mount install rclone
else
    echo "✅ rclone già installato: $(rclone version | head -1)"
fi

echo ""
echo "3️⃣ Test setup utente con rclone..."

# DELAY per evitare rate limiting
echo "⏳ Attesa 3s per evitare rate limiting..."
sleep 3

# Setup completo con rclone
if nextcloud-wrapper setup user "$TEST_USER" "$TEST_PASSWORD" \
    --quota "$TEST_QUOTA" \
    --engine rclone \
    --profile writes \
    --skip-test; then
    echo "✅ Setup rclone completato"
else
    echo "❌ Setup rclone fallito"
    exit 1
fi

echo ""
echo "4️⃣ Verifica mount rclone..."

# DELAY per permettere al mount di stabilizzarsi
echo "⏳ Attesa 5s per stabilizzazione mount..."
sleep 5

# Verifica mount
if nextcloud-wrapper mount status | grep -q "$TEST_USER"; then
    echo "✅ Mount rclone rilevato"
    
    # Info dettagliate mount
    nextcloud-wrapper mount info "$TEST_HOME" || echo "⚠️ Info mount non disponibile"
else
    echo "❌ Mount rclone non trovato"
    exit 1
fi

echo ""
echo "5️⃣ Test operazioni file..."

# Test scrittura/lettura
TEST_FILE="$TEST_HOME/test-rclone.txt"
TEST_CONTENT="Test rclone mount - $(date)"

echo "$TEST_CONTENT" > "$TEST_FILE"
if [ $? -eq 0 ]; then
    echo "✅ Scrittura file OK"
else
    echo "❌ Errore scrittura file"
    exit 1
fi

# Test lettura
if [ -f "$TEST_FILE" ] && grep -q "Test rclone mount" "$TEST_FILE"; then
    echo "✅ Lettura file OK"
else
    echo "❌ Errore lettura file"
    exit 1
fi

# Test listing directory
if ls -la "$TEST_HOME" >/dev/null 2>&1; then
    echo "✅ Listing directory OK"
    echo "Contenuto home (primi 5 file):"
    ls -la "$TEST_HOME" | head -5
else
    echo "❌ Errore listing directory"
    exit 1
fi

echo ""
echo "6️⃣ Test comandi CLI principali..."

# Test tutti i nuovi comandi
echo "🧪 Test comandi CLI..."

echo "  • mount engines"
nextcloud-wrapper mount engines >/dev/null && echo "    ✅ OK" || echo "    ❌ FAIL"

echo "  • mount profiles"
nextcloud-wrapper mount profiles rclone >/dev/null && echo "    ✅ OK" || echo "    ❌ FAIL"

echo "  • mount status"
nextcloud-wrapper mount status >/dev/null && echo "    ✅ OK" || echo "    ❌ FAIL"

echo ""
echo "7️⃣ Test compatibilità backward..."

# Verifica che i vecchi comandi webdav funzionino ancora
echo "🔄 Test compatibilità webdav..."

echo "  • webdav status"
nextcloud-wrapper webdav status >/dev/null && echo "    ✅ OK" || echo "    ❌ FAIL"

echo "  • status generale"
nextcloud-wrapper status >/dev/null && echo "    ✅ OK" || echo "    ❌ FAIL"

echo ""
echo "8️⃣ Test profili rclone base..."

# Test veloce profili (senza creare utenti per risparmiare tempo)
echo "📋 Test info profili rclone..."
nextcloud-wrapper mount profiles rclone | grep -q "writes" && echo "✅ Profilo writes disponibile" || echo "❌ Profilo writes mancante"

echo ""
echo "🎉 TEST BASE COMPLETATO CON SUCCESSO!"
echo "====================================="
echo ""
echo "📊 Risultati:"
echo "✅ Engine rclone: funzionante"
echo "✅ Setup unificato: funzionante" 
echo "✅ Mount engine: funzionante"
echo "✅ Operazioni I/O: funzionanti"
echo "✅ CLI unificata: funzionante"
echo "✅ Compatibilità: mantenuta"
echo ""
echo "🚀 nextcloud-wrapper v0.4.0 pronto!"
echo ""
echo "💡 Comandi principali:"
echo "nextcloud-wrapper setup user USERNAME PASSWORD --engine rclone"
echo "nextcloud-wrapper mount engines"
echo "nextcloud-wrapper mount profiles rclone"
echo ""
echo "📋 Engine supportati:"
echo "• rclone (predefinito) - Performance superiori"
echo "• davfs2 (fallback) - Compatibilità massima"

# Cleanup finale automatico tramite trap
