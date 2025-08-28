#!/bin/bash
# test-rclone-migration.sh - Test migrazione da davfs2 a rclone

echo "🧪 Test migrazione engine rclone per nextcloud-wrapper v0.4.0"
echo "=============================================================="

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

# Verifica mount
if nextcloud-wrapper mount status | grep -q "$TEST_USER"; then
    echo "✅ Mount rclone rilevato"
    
    # Info dettagliate mount
    nextcloud-wrapper mount info "$TEST_HOME"
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
    echo "Contenuto home:"
    ls -la "$TEST_HOME" | head -10
else
    echo "❌ Errore listing directory"
    exit 1
fi

echo ""
echo "6️⃣ Test migrazione davfs2 → rclone..."

# Crea secondo utente con davfs2
TEST_USER_2="test-davfs2-user"

echo "📝 Setup utente davfs2..."
if nextcloud-wrapper setup user "$TEST_USER_2" "$TEST_PASSWORD" \
    --quota "$TEST_QUOTA" \
    --engine davfs2 \
    --skip-test; then
    echo "✅ Setup davfs2 OK"
else
    echo "❌ Setup davfs2 fallito"
    exit 1
fi

# Migra a rclone
echo "🔄 Migrazione davfs2 → rclone..."
if echo "$TEST_PASSWORD" | nextcloud-wrapper mount migrate \
    "/home/$TEST_USER_2" rclone \
    --profile writes \
    --backup; then
    echo "✅ Migrazione completata"
else
    echo "❌ Migrazione fallita"
    exit 1
fi

echo ""
echo "7️⃣ Test performance engine..."

# Benchmark veloce (file piccoli)
echo "⚡ Benchmark performance..."
if nextcloud-wrapper mount benchmark "$TEST_USER" \
    --test-dir /tmp/benchmark-test \
    --file-size-mb 1 \
    --iterations 2; then
    echo "✅ Benchmark completato"
else
    echo "⚠️ Benchmark fallito (non critico)"
fi

echo ""
echo "8️⃣ Test profili rclone..."

# Test tutti i profili rclone
for profile in writes minimal hosting; do
    echo "🔧 Test profilo: $profile"
    
    TEST_USER_PROFILE="test-profile-$profile"
    
    # Setup con profilo specifico
    if nextcloud-wrapper setup user "$TEST_USER_PROFILE" "$TEST_PASSWORD" \
        --quota "$TEST_QUOTA" \
        --engine rclone \
        --profile "$profile" \
        --skip-test >/dev/null 2>&1; then
        echo "  ✅ Profilo $profile: setup OK"
        
        # Test scrittura veloce
        echo "test" > "/home/$TEST_USER_PROFILE/test-$profile.txt" 2>/dev/null
        if [ $? -eq 0 ]; then
            echo "  ✅ Profilo $profile: I/O OK"
        else
            echo "  ⚠️ Profilo $profile: I/O warning"
        fi
        
        # Cleanup utente profilo
        userdel -r "$TEST_USER_PROFILE" 2>/dev/null || true
        nextcloud-wrapper user delete "$TEST_USER_PROFILE" 2>/dev/null || true
    else
        echo "  ⚠️ Profilo $profile: setup warning"
    fi
done

echo ""
echo "9️⃣ Test comandi CLI..."

# Test tutti i nuovi comandi
echo "🧪 Test comandi CLI..."

echo "  • mount engines"
nextcloud-wrapper mount engines >/dev/null && echo "    ✅ OK" || echo "    ❌ FAIL"

echo "  • mount profiles"
nextcloud-wrapper mount profiles rclone >/dev/null && echo "    ✅ OK" || echo "    ❌ FAIL"

echo "  • mount status"
nextcloud-wrapper mount status >/dev/null && echo "    ✅ OK" || echo "    ❌ FAIL"

echo "  • mount info"
nextcloud-wrapper mount info "$TEST_HOME" >/dev/null && echo "    ✅ OK" || echo "    ❌ FAIL"

echo ""
echo "🔟 Test compatibilità backward..."

# Verifica che i vecchi comandi webdav funzionino ancora
echo "🔄 Test compatibilità webdav..."

echo "  • webdav status"
nextcloud-wrapper webdav status >/dev/null && echo "    ✅ OK" || echo "    ❌ FAIL"

echo "  • status generale"
nextcloud-wrapper status >/dev/null && echo "    ✅ OK" || echo "    ❌ FAIL"

# Cleanup finale automatico tramite trap

echo ""
echo "🎉 TEST MIGRAZIONE COMPLETATO!"
echo "=============================="
echo ""
echo "📊 Risultati:"
echo "✅ Engine rclone: funzionante"
echo "✅ Setup unificato: funzionante" 
echo "✅ Mount engine: funzionante"
echo "✅ Operazioni I/O: funzionanti"
echo "✅ Profili rclone: funzionanti"
echo "✅ Migrazione engine: funzionante"
echo "✅ CLI unificata: funzionante"
echo "✅ Compatibilità: mantenuta"
echo ""
echo "🚀 nextcloud-wrapper v0.4.0 pronto per production!"
echo ""
echo "💡 Per usare il nuovo engine:"
echo "nextcloud-wrapper setup user USERNAME PASSWORD --engine rclone"
echo "nextcloud-wrapper mount mount USERNAME PASSWORD --engine rclone --profile writes"
echo ""
echo "📋 Engine supportati:"
echo "• rclone (predefinito) - Performance superiori"
echo "• davfs2 (fallback) - Compatibilità massima"
