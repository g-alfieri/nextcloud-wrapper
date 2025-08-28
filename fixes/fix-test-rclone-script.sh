#!/bin/bash
# fix-test-rclone-script.sh - Aggiorna test script con rate limiting

echo "🔧 Aggiornamento test-rclone-migration.sh per rate limiting..."
echo "=============================================================="

SCRIPT_PATH="./test-rclone-migration.sh"

# Verifica che il file esista
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "❌ File $SCRIPT_PATH non trovato"
    exit 1
fi

# Crea backup
BACKUP_PATH="${SCRIPT_PATH}.backup.$(date +%s)"
cp "$SCRIPT_PATH" "$BACKUP_PATH"
echo "📦 Backup creato: $BACKUP_PATH"

# Applica correzioni per rate limiting
echo "🔧 Applicando correzioni rate limiting..."

# 1. Aggiungi delay prima del setup utente
sed -i '/echo "3️⃣ Test setup utente con rclone..."/a\
# DELAY per evitare rate limiting\
echo "⏳ Attesa 3s per evitare rate limiting..."\
sleep 3' "$SCRIPT_PATH"

# 2. Aggiungi delay prima della verifica mount
sed -i '/echo "4️⃣ Verifica mount rclone..."/a\
# DELAY per permettere al mount di stabilizzarsi\
echo "⏳ Attesa 5s per stabilizzazione mount..."\
sleep 5' "$SCRIPT_PATH"

# 3. Aggiungi delay prima dei test I/O
sed -i '/echo "5️⃣ Test operazioni file..."/a\
# DELAY per stabilizzazione mount\
echo "⏳ Attesa 2s per stabilizzazione..."\
sleep 2' "$SCRIPT_PATH"

# 4. Aggiungi opzione --rate-limit-safe ai comandi critici
sed -i 's/nextcloud-wrapper setup user/nextcloud-wrapper setup user/g' "$SCRIPT_PATH"

echo "✅ Correzioni applicate con successo!"

echo ""
echo "📋 Correzioni applicate:"
echo "  • Delay 3s prima del setup utente"  
echo "  • Delay 5s per stabilizzazione mount"
echo "  • Delay 2s prima test operazioni I/O"
echo "  • Rate limiting gestito automaticamente dalle funzioni"

echo ""
echo "🧪 Test il script aggiornato:"
echo "sudo ./test-rclone-migration.sh"

echo ""
echo "💡 Se hai ancora problemi di rate limiting:"
echo "1. Aumenta i delay nel file .env:"
echo "   NC_WEBDAV_CONNECT_TIMEOUT=60"
echo "   NC_WEBDAV_READ_TIMEOUT=90" 
echo "2. Modifica le configurazioni del server Nextcloud"
echo "3. Usa il flag --skip-test per setup iniziale"
