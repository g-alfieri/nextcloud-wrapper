#!/bin/bash
# fix-env-crlf.sh - Fix terminatori Windows nei file .env

echo "🔧 Fix terminatori Windows nei file .env"

# Lista file da controllare
ENV_FILES=(
    ".env"
    ".env.example" 
    "/etc/nextcloud-wrapper/.env"
)

for env_file in "${ENV_FILES[@]}"; do
    if [ -f "$env_file" ]; then
        echo "Convertendo: $env_file"
        
        # Backup
        cp "$env_file" "$env_file.backup.$(date +%s)" 2>/dev/null
        
        # Converti CRLF -> LF
        sed -i 's/\r$//' "$env_file"
        
        echo "✅ $env_file convertito"
    else
        echo "ℹ️ $env_file non trovato"
    fi
done

echo "✅ Conversione terminatori completata"
echo "💡 I file backup sono stati creati con timestamp"
