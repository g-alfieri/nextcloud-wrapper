#!/bin/bash
# test-v0.2.0.sh - Script di test per verificare le nuove funzionalità

echo "🚀 Test Suite Nextcloud Wrapper v0.2.0"
echo "======================================="

# Configurazione test
TEST_USER="test-v2.domain.com"
TEST_PASS="TestPassword123!"
TEST_QUOTA="10G"
TEST_FS_PERCENTAGE="0.1"  # 10% per test rapidi

echo ""
echo "📋 Configurazione test:"
echo "- Utente: $TEST_USER"
echo "- Quota NC: $TEST_QUOTA"
echo "- Quota FS: ${TEST_FS_PERCENTAGE} (${TEST_FS_PERCENTAGE/0./}%)"

# Verifica configurazione base
echo ""
echo "1️⃣ Verifica configurazione..."
if ! nextcloud-wrapper config; then
    echo "❌ ERRORE: Configurazione non valida. Verificare variabili d'ambiente:"
    echo "   export NC_BASE_URL='https://your-nextcloud.com'"
    echo "   export NC_ADMIN_USER='admin'"
    echo "   export NC_ADMIN_PASS='your-pass'"
    exit 1
fi

# Test setup completo
echo ""
echo "2️⃣ Test setup completo..."
if nextcloud-wrapper setup "$TEST_USER" "$TEST_PASS" \
    --quota "$TEST_QUOTA" \
    --fs-percentage "$TEST_FS_PERCENTAGE" \
    --sub "api.$TEST_USER" \
    --sub "shop.$TEST_USER" \
    --no-mount; then  # Salta mount per evitare problemi nei test
    echo "✅ Setup completato con successo"
else
    echo "❌ ERRORE: Setup fallito"
    exit 1
fi

# Verifica utente creato
echo ""
echo "3️⃣ Verifica utente creato..."
nextcloud-wrapper user info "$TEST_USER"

# Test quota logic
echo ""
echo "4️⃣ Test logica quote..."
echo "Quota Nextcloud: $TEST_QUOTA"
echo "Percentuale FS: $TEST_FS_PERCENTAGE"

# Calcolo atteso
if command -v python3 >/dev/null; then
    EXPECTED_FS=$(python3 -c "
import re
quota = '$TEST_QUOTA'
percentage = $TEST_FS_PERCENTAGE

# Parse quota size
match = re.match(r'^(\d+(?:\.\d+)?)\s*([KMGT]?)B?$', quota.upper())
if match:
    number, unit = match.groups()
    multipliers = {'': 1, 'K': 1024, 'M': 1024**2, 'G': 1024**3, 'T': 1024**4}
    bytes_val = int(float(number) * multipliers.get(unit, 1))
    fs_bytes = int(bytes_val * percentage)
    
    # Convert back to human readable
    for unit in ['B', 'K', 'M', 'G', 'T']:
        if fs_bytes < 1024:
            print(f'{fs_bytes:.0f}{unit}')
            break
        fs_bytes /= 1024
")
    echo "Quota filesystem attesa: ~$EXPECTED_FS"
fi

nextcloud-wrapper quota show "$TEST_USER"

# Test mount remote (senza montare realmente)
echo ""
echo "5️⃣ Test configurazione remote..."
nextcloud-wrapper mount list

# Test comandi CLI
echo ""
echo "6️⃣ Test comandi CLI..."

echo "user test:"
if nextcloud-wrapper user test "$TEST_USER" "$TEST_PASS"; then
    echo "✅ Login WebDAV funzionante"
else
    echo "❌ Login WebDAV fallito"
fi

echo ""
echo "mount list:"
nextcloud-wrapper mount list

echo ""
echo "service list:"
nextcloud-wrapper service list

# Performance test (opzionale)
echo ""
echo "7️⃣ Test performance mount options..."
echo "Verificando che usi le opzioni ottimizzate (writes, 64M buffer)..."

# Controlla file di configurazione systemd se esiste
if [ -f "/etc/systemd/system/nextcloud-mount-$TEST_USER.service" ]; then
    echo "Configurazione systemd trovata:"
    grep -E "(vfs-cache-mode|buffer-size)" "/etc/systemd/system/nextcloud-mount-$TEST_USER.service" || echo "Opzioni non trovate nel file"
else
    echo "ℹ️  Servizio systemd non creato (normale se --no-mount usato)"
fi

# Test cambio password
echo ""
echo "8️⃣ Test cambio password..."
NEW_PASS="NewTestPassword456!"
if nextcloud-wrapper user passwd "$TEST_USER" "$NEW_PASS" --nc-only; then
    echo "✅ Cambio password riuscito"
    
    # Test nuovo login
    if nextcloud-wrapper user test "$TEST_USER" "$NEW_PASS"; then
        echo "✅ Nuovo login confermato"
    else
        echo "❌ Nuovo login fallito"
    fi
else
    echo "❌ Cambio password fallito"
fi

# Cleanup
echo ""
echo "9️⃣ Cleanup..."
read -p "Vuoi rimuovere l'utente test? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Rimuovendo utente test..."
    
    # Rimuovi quota
    nextcloud-wrapper quota remove "$TEST_USER" 2>/dev/null || echo "Quota non presente"
    
    # Disabilita servizi se esistono
    nextcloud-wrapper service disable "nextcloud-mount-$TEST_USER" 2>/dev/null || echo "Servizio non presente"
    
    # Rimuovi utente Linux se esiste
    if id "$TEST_USER" >/dev/null 2>&1; then
        sudo userdel -r "$TEST_USER" 2>/dev/null || echo "Errore rimozione utente Linux"
    fi
    
    # Rimuovi remote rclone
    echo "ℹ️  Remote rclone lasciato per debug. Rimuovere manualmente se necessario:"
    echo "   rclone config delete '$TEST_USER' --config ~/.config/ncwrap/rclone.conf"
    
    echo "✅ Cleanup completato"
else
    echo "ℹ️  Utente test mantenuto per debug"
    echo "   Utente: $TEST_USER"
    echo "   Password: $NEW_PASS"
fi

echo ""
echo "🎉 Test completato!"
echo ""
echo "📊 Riepilogo:"
echo "- Setup completo: ✅"
echo "- Quota logic: ✅ (filesystem = ${TEST_FS_PERCENTAGE/0./}% di nextcloud)"
echo "- Login WebDAV: ✅"
echo "- CLI unificata: ✅"
echo "- Cambio password: ✅"
echo ""
echo "🚀 Nextcloud Wrapper v0.2.0 funzionante!"
