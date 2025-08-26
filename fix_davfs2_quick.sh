#!/bin/bash
# Fix rapido per certificati davfs2

echo "🔐 Fix rapido certificati davfs2"
echo "================================="

# 1. Crea directory certificati
echo "🔧 Creazione directory certificati..."
sudo mkdir -p /etc/davfs2/certs
sudo chmod 755 /etc/davfs2/certs

# 2. Scarica certificato server Nextcloud
echo "📥 Scaricamento certificato server..."
echo "" | openssl s_client -connect ncloud.charax.io:443 -servername ncloud.charax.io 2>/dev/null | openssl x509 > /tmp/nextcloud-cert.pem

if [ -s /tmp/nextcloud-cert.pem ]; then
    sudo cp /tmp/nextcloud-cert.pem /etc/davfs2/certs/nextcloud-server.crt
    sudo chmod 644 /etc/davfs2/certs/nextcloud-server.crt
    echo "✅ Certificato salvato"
else
    echo "❌ Errore download certificato"
fi

# 3. Aggiorna configurazione davfs2
echo "🔧 Aggiornamento configurazione..."
sudo tee /etc/davfs2/davfs2.conf > /dev/null << 'EOF'
# Configurazione davfs2 per Nextcloud
# Generata da nextcloud-wrapper fix

# Cache settings
cache_size 256
table_size 1024

# Timeouts (seconds)
connect_timeout 30
read_timeout 60

# Retry settings
retry 30
max_retry 300

# Cache directory
cache_dir /var/cache/davfs2
backup_dir lost+found

# Lock settings
use_locks 1
lock_timeout 1800

# Authentication - non chiedere interattivamente
ask_auth 0

# HTTP optimizations
use_expect100 0
if_match_bug 1
drop_weak_etags 1
n_cookies 0
precheck 1

# Upload settings
delay_upload 10
max_upload_attempts 15

# Directory refresh
dir_refresh 60
file_refresh 1

# Buffer size (KiB)
buf_size 16

# SSL Certificate (se necessario)
# trust_server_cert /etc/davfs2/certs/nextcloud-server.crt

# End of configuration
EOF

echo "✅ Configurazione aggiornata"

# 4. Fix permessi
echo "🔧 Correzione permessi..."
sudo chmod 644 /etc/davfs2/davfs2.conf
sudo chmod 600 /etc/davfs2/secrets 2>/dev/null || true

# 5. Test configurazione
echo "🧪 Test configurazione..."
if mount.davfs --help >/dev/null 2>&1; then
    echo "✅ mount.davfs funzionante"
else
    echo "❌ Problema con mount.davfs"
fi

echo ""
echo "🚀 Ora prova il mount:"
echo "sudo mount -t davfs https://ncloud.charax.io/remote.php/dav/files/charax.io/ /home/charax.io"
echo ""
echo "Se il mount fallisce ancora per certificati SSL, decommenta la riga trust_server_cert:"
echo "sudo sed -i 's/# trust_server_cert/trust_server_cert/' /etc/davfs2/davfs2.conf"
