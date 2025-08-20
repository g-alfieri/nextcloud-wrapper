#!/bin/bash
# migrate-to-v0.2.0.sh - Script di migrazione da v0.1.0 a v0.2.0

echo "🔄 Migrazione Nextcloud Wrapper v0.1.0 → v0.2.0"
echo "=============================================="

# Backup configurazioni esistenti
echo ""
echo "1️⃣ Backup configurazioni esistenti..."
BACKUP_DIR="$HOME/.config/ncwrap/backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"

if [ -f "$HOME/.config/ncwrap/rclone.conf" ]; then
    cp "$HOME/.config/ncwrap/rclone.conf" "$BACKUP_DIR/"
    echo "✅ Backup rclone.conf → $BACKUP_DIR/"
else
    echo "ℹ️  Nessuna configurazione rclone trovata"
fi

# Lista remote esistenti
echo ""
echo "2️⃣ Analisi remote esistenti..."
EXISTING_REMOTES=()
if [ -f "$HOME/.config/ncwrap/rclone.conf" ]; then
    while IFS= read -r line; do
        if [[ $line =~ ^\[(.+)\]$ ]]; then
            remote_name="${BASH_REMATCH[1]}"
            EXISTING_REMOTES+=("$remote_name")
        fi
    done < "$HOME/.config/ncwrap/rclone.conf"
    
    echo "Remote trovati: ${#EXISTING_REMOTES[@]}"
    for remote in "${EXISTING_REMOTES[@]}"; do
        echo "  - $remote"
    done
else
    echo "ℹ️  Nessun remote configurato"
fi

# Migrazione mount options
echo ""
echo "3️⃣ Migrazione opzioni mount..."

# Trova servizi systemd nextcloud esistenti
EXISTING_SERVICES=($(systemctl list-unit-files "nextcloud-mount-*" --no-pager 2>/dev/null | grep "nextcloud-mount" | awk '{print $1}' | sed 's/.service$//'))

if [ ${#EXISTING_SERVICES[@]} -gt 0 ]; then
    echo "Servizi mount trovati: ${#EXISTING_SERVICES[@]}"
    
    for service in "${EXISTING_SERVICES[@]}"; do
        echo ""
        echo "Aggiornando servizio: $service"
        
        # Leggi configurazione esistente
        SERVICE_FILE="/etc/systemd/system/${service}.service"
        if [ -f "$SERVICE_FILE" ]; then
            # Backup servizio
            sudo cp "$SERVICE_FILE" "$BACKUP_DIR/${service}.service.backup"
            
            # Estrai info dal servizio esistente
            REMOTE_NAME=$(grep "rclone mount" "$SERVICE_FILE" | sed -n 's/.*rclone mount \([^:]*\):.*/\1/p')
            MOUNT_POINT=$(grep "rclone mount" "$SERVICE_FILE" | sed -n 's/.*rclone mount [^:]*:\/[[:space:]]*\([^[:space:]]*\).*/\1/p')
            
            if [ -n "$REMOTE_NAME" ] && [ -n "$MOUNT_POINT" ]; then
                echo "  Remote: $REMOTE_NAME"
                echo "  Mount point: $MOUNT_POINT"
                
                # Ferma servizio esistente
                echo "  Fermando servizio esistente..."
                sudo systemctl stop "$service" 2>/dev/null || true
                sudo systemctl disable "$service" 2>/dev/null || true
                
                # Crea nuovo servizio con opzioni v0.2.0
                echo "  Creando nuovo servizio con opzioni ottimizzate..."
                USERNAME=$(echo "$service" | sed 's/nextcloud-mount-//')
                
                if nextcloud-wrapper service create-mount "$USERNAME" "$REMOTE_NAME" "$MOUNT_POINT"; then
                    echo "  ✅ Servizio aggiornato con successo"
                    
                    # Abilita nuovo servizio
                    if nextcloud-wrapper service enable "nextcloud-mount-$USERNAME"; then
                        echo "  ✅ Servizio abilitato e avviato"
                    else
                        echo "  ⚠️  Errore abilitazione servizio"
                    fi
                else
                    echo "  ❌ Errore creazione nuovo servizio"
                    echo "  ℹ️  Ripristinando servizio originale..."
                    sudo systemctl enable "$service" 2>/dev/null || true
                    sudo systemctl start "$service" 2>/dev/null || true
                fi
            else
                echo "  ⚠️  Impossibile estrarre info dal servizio"
            fi
        fi
    done
else
    echo "ℹ️  Nessun servizio mount esistente trovato"
fi

# Verifica quote esistenti
echo ""
echo "4️⃣ Analisi quote esistenti..."

# Lista utenti con quota
USERS_WITH_QUOTA=()
if command -v quota >/dev/null; then
    while IFS= read -r line; do
        if [[ $line =~ ^([^[:space:]]+)[[:space:]] && ! $line =~ ^(root|daemon|bin|sys|sync|games|man|lp|mail|news|uucp|proxy|www-data|backup|list|irc|gnats|nobody|systemd|_apt)$ ]]; then
            user=$(echo "$line" | awk '{print $1}')
            if [ -n "$user" ] && id "$user" >/dev/null 2>&1; then
                USERS_WITH_QUOTA+=("$user")
            fi
        fi
    done < <(repquota -a 2>/dev/null | grep -v "^#\|^$\|Grace\|User\|Block\|--")
    
    if [ ${#USERS_WITH_QUOTA[@]} -gt 0 ]; then
        echo "Utenti con quota trovati: ${#USERS_WITH_QUOTA[@]}"
        for user in "${USERS_WITH_QUOTA[@]}"; do
            quota_info=$(quota -u "$user" 2>/dev/null | grep "^/dev" | awk '{print $2 "K utilizzati, limite " $3 "K"}')
            echo "  - $user: $quota_info"
        done
        
        echo ""
        echo "⚠️  ATTENZIONE: Quote Migration"
        echo "Le quote esistenti non verranno modificate automaticamente."
        echo "In v0.2.0 le quote seguono la logica: filesystem = nextcloud_quota * percentage"
        echo ""
        echo "Per ogni utente, dovrai:"
        echo "1. Determinare la quota Nextcloud desiderata"
        echo "2. Eseguire: nextcloud-wrapper quota set USERNAME NEXTCLOUD_QUOTA --fs-percentage 0.02"
        echo ""
        echo "Esempio per conversione manuale:"
        for user in "${USERS_WITH_QUOTA[@]}"; do
            current_quota=$(quota -u "$user" 2>/dev/null | grep "^/dev" | awk '{print $3}')
            if [ -n "$current_quota" ] && [ "$current_quota" != "0" ]; then
                # Calcola quota nextcloud equivalente (assume 2% default)
                nc_quota_kb=$((current_quota * 50))  # current / 0.02
                nc_quota_gb=$((nc_quota_kb / 1024 / 1024))
                echo "  nextcloud-wrapper quota set $user ${nc_quota_gb}G --fs-percentage 0.02"
            fi
        done
    else
        echo "ℹ️  Nessuna quota esistente trovata"
    fi
else
    echo "ℹ️  Comando quota non disponibile"
fi

# Test CLI v0.2.0
echo ""
echo "5️⃣ Test nuova CLI..."
if nextcloud-wrapper config >/dev/null 2>&1; then
    echo "✅ CLI v0.2.0 funzionante"
    echo ""
    echo "Nuovi comandi disponibili:"
    echo "  nextcloud-wrapper user create/info/test/passwd"
    echo "  nextcloud-wrapper mount add/mount/sync/list"
    echo "  nextcloud-wrapper quota set/show/remove"
    echo "  nextcloud-wrapper service create-mount/list/enable/disable"
    echo "  nextcloud-wrapper setup  # Setup completo one-shot"
else
    echo "❌ Errore CLI v0.2.0"
fi

# Summary e raccomandazioni
echo ""
echo "📋 Riepilogo Migrazione"
echo "====================="
echo ""
echo "✅ Completato:"
echo "  - Backup configurazioni in: $BACKUP_DIR"
if [ ${#EXISTING_SERVICES[@]} -gt 0 ]; then
    echo "  - Aggiornamento servizi mount (${#EXISTING_SERVICES[@]} servizi)"
fi
echo "  - Test CLI v0.2.0"
echo ""
echo "⚠️  Azioni manuali richieste:"
echo ""

if [ ${#USERS_WITH_QUOTA[@]} -gt 0 ]; then
    echo "1. QUOTE: Migra le quote alla nuova logica"
    echo "   Le quote attuali sono impostate direttamente sul filesystem."
    echo "   In v0.2.0 devi specificare la quota Nextcloud e la percentuale."
    echo ""
    echo "   Comandi di esempio:"
    for user in "${USERS_WITH_QUOTA[@]}"; do
        current_quota=$(quota -u "$user" 2>/dev/null | grep "^/dev" | awk '{print $3}')
        if [ -n "$current_quota" ] && [ "$current_quota" != "0" ]; then
            nc_quota_gb=$((current_quota / 1024 / 1024 * 50))  # Assume 2% ratio
            echo "   nextcloud-wrapper quota set $user ${nc_quota_gb}G --fs-percentage 0.02"
        fi
    done
    echo ""
fi

echo "2. PERFORMANCE: Verifica le nuove opzioni mount"
echo "   I servizi sono stati aggiornati per usare:"
echo "   - --vfs-cache-mode writes (invece di full)"
echo "   - --buffer-size 64M (invece di 256M)"
echo "   Monitora le performance e regola se necessario."
echo ""

echo "3. TEST: Verifica tutti i servizi"
echo "   systemctl status nextcloud-mount-*"
echo "   nextcloud-wrapper service list"
echo "   nextcloud-wrapper mount list"
echo ""

echo "📚 Documentazione:"
echo "   - README.md aggiornato con tutti i nuovi comandi"
echo "   - test-v0.2.0.sh per test completo"
echo ""

echo "🚀 Migrazione completata!"
echo "   Nextcloud Wrapper è ora v0.2.0 con tutte le nuove funzionalità."
