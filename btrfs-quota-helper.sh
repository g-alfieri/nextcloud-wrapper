#!/bin/bash
# btrfs-quota-helper.sh - Gestione quote BTRFS per Nextcloud Wrapper

echo "📁 BTRFS Quota Helper per Nextcloud Wrapper"
echo "==========================================="

# Configurazione
BTRFS_BASE="/home"
SUBVOL_PREFIX="nextcloud-user"

# Funzioni helper
check_btrfs() {
    local path="$1"
    if ! btrfs filesystem show "$path" >/dev/null 2>&1; then
        echo "❌ $path non è un filesystem btrfs"
        return 1
    fi
    echo "✅ $path è filesystem btrfs"
    return 0
}

enable_quotas() {
    local path="$1"
    echo "🔧 Abilitando quote su $path..."
    
    # Abilita quote
    if btrfs quota enable "$path"; then
        echo "✅ Quote abilitate su $path"
        return 0
    else
        echo "❌ Errore abilitazione quote"
        return 1
    fi
}

create_user_subvolume() {
    local username="$1"
    local base_path="${2:-$BTRFS_BASE}"
    local subvol_path="$base_path/$username"
    
    echo "📁 Creando subvolume per utente: $username"
    
    # Verifica se esiste già come subvolume
    if btrfs subvolume show "$subvol_path" >/dev/null 2>&1; then
        echo "ℹ️  Subvolume $subvol_path già esistente"
        return 0
    fi
    
    # Se esiste come directory normale, fai backup
    if [ -d "$subvol_path" ]; then
        backup_path="${subvol_path}.backup.$(date +%s)"
        echo "📦 Backup directory esistente: $backup_path"
        mv "$subvol_path" "$backup_path"
    fi
    
    # Crea subvolume
    if btrfs subvolume create "$subvol_path"; then
        echo "✅ Subvolume creato: $subvol_path"
        
        # Imposta ownership se utente esiste
        if id "$username" >/dev/null 2>&1; then
            chown "$username:$username" "$subvol_path"
            echo "✅ Ownership impostato per $username"
        fi
        
        return 0
    else
        echo "❌ Errore creazione subvolume"
        return 1
    fi
}

set_subvolume_quota() {
    local username="$1"
    local quota_size="$2"
    local base_path="${3:-$BTRFS_BASE}"
    local subvol_path="$base_path/$username"
    
    echo "💾 Impostando quota $quota_size per $username"
    
    # Verifica subvolume esistente
    if ! btrfs subvolume show "$subvol_path" >/dev/null 2>&1; then
        echo "❌ Subvolume non trovato: $subvol_path"
        return 1
    fi
    
    # Ottieni ID subvolume
    local subvol_id=$(btrfs subvolume show "$subvol_path" | grep "Subvolume ID:" | awk '{print $3}')
    if [ -z "$subvol_id" ]; then
        echo "❌ Impossibile ottenere ID subvolume"
        return 1
    fi
    
    echo "📋 Subvolume ID: $subvol_id"
    
    # Crea qgroup se non esiste
    local qgroup_id="0/$subvol_id"
    btrfs qgroup create "$qgroup_id" "$base_path" 2>/dev/null || true
    
    # Imposta quota
    if btrfs qgroup limit "$quota_size" "$qgroup_id" "$base_path"; then
        echo "✅ Quota $quota_size impostata per $username (qgroup $qgroup_id)"
        return 0
    else
        echo "❌ Errore impostazione quota"
        return 1
    fi
}

show_quotas() {
    local base_path="${1:-$BTRFS_BASE}"
    
    echo "📊 Quote BTRFS su $base_path:"
    echo ""
    
    # Mostra qgroup con dettagli
    if btrfs qgroup show -p -c "$base_path" 2>/dev/null; then
        echo ""
        echo "📋 Legenda:"
        echo "   Qgroupid: ID del gruppo quota"
        echo "   Rfer: Spazio usato (referenced)"  
        echo "   Excl: Spazio esclusivo"
        echo "   Max_rfer: Limite quota"
    else
        echo "⚠️  Quote non abilitate o nessuna quota configurata"
    fi
}

list_subvolumes() {
    local base_path="${1:-$BTRFS_BASE}"
    
    echo "📁 Subvolume in $base_path:"
    echo ""
    
    # Lista subvolume
    btrfs subvolume list "$base_path" | while read line; do
        subvol_path=$(echo "$line" | awk '{print $NF}')
        subvol_id=$(echo "$line" | awk '{print $2}')
        
        # Cerca quote associate
        quota_info=$(btrfs qgroup show "$base_path" 2>/dev/null | grep "0/$subvol_id" | head -1)
        if [ -n "$quota_info" ]; then
            limit=$(echo "$quota_info" | awk '{print $4}')
            if [ "$limit" != "none" ] && [ "$limit" != "0" ]; then
                echo "📁 $subvol_path (ID: $subvol_id, Quota: $limit)"
            else
                echo "📁 $subvol_path (ID: $subvol_id, Nessuna quota)"
            fi
        else
            echo "📁 $subvol_path (ID: $subvol_id, Nessuna quota)"
        fi
    done
}

remove_quota() {
    local username="$1"
    local base_path="${2:-$BTRFS_BASE}"
    local subvol_path="$base_path/$username"
    
    echo "🗑️  Rimuovendo quota per $username"
    
    # Ottieni ID subvolume
    if ! btrfs subvolume show "$subvol_path" >/dev/null 2>&1; then
        echo "❌ Subvolume non trovato: $subvol_path"
        return 1
    fi
    
    local subvol_id=$(btrfs subvolume show "$subvol_path" | grep "Subvolume ID:" | awk '{print $3}')
    local qgroup_id="0/$subvol_id"
    
    # Rimuovi limite
    if btrfs qgroup limit none "$qgroup_id" "$base_path"; then
        echo "✅ Quota rimossa per $username"
        return 0
    else
        echo "❌ Errore rimozione quota"
        return 1
    fi
}

# Menu interattivo
main_menu() {
    echo ""
    echo "Opzioni disponibili:"
    echo "1. Verifica filesystem BTRFS"
    echo "2. Abilita quote su filesystem" 
    echo "3. Crea subvolume utente"
    echo "4. Imposta quota subvolume"
    echo "5. Mostra tutte le quote"
    echo "6. Lista subvolume"
    echo "7. Rimuovi quota utente"
    echo "8. Setup completo utente"
    echo "9. Exit"
    echo ""
    read -p "Scegli opzione (1-9): " choice
    
    case $choice in
        1)
            read -p "Path filesystem: " path
            check_btrfs "${path:-$BTRFS_BASE}"
            ;;
        2)
            read -p "Path filesystem: " path
            enable_quotas "${path:-$BTRFS_BASE}"
            ;;
        3)
            read -p "Username: " username
            read -p "Base path [$BTRFS_BASE]: " path
            create_user_subvolume "$username" "${path:-$BTRFS_BASE}"
            ;;
        4)
            read -p "Username: " username
            read -p "Quota size (es. 1G): " quota
            read -p "Base path [$BTRFS_BASE]: " path
            set_subvolume_quota "$username" "$quota" "${path:-$BTRFS_BASE}"
            ;;
        5)
            read -p "Base path [$BTRFS_BASE]: " path
            show_quotas "${path:-$BTRFS_BASE}"
            ;;
        6)
            read -p "Base path [$BTRFS_BASE]: " path
            list_subvolumes "${path:-$BTRFS_BASE}"
            ;;
        7)
            read -p "Username: " username
            read -p "Base path [$BTRFS_BASE]: " path
            remove_quota "$username" "${path:-$BTRFS_BASE}"
            ;;
        8)
            read -p "Username: " username
            read -p "Quota size (es. 1G): " quota
            read -p "Base path [$BTRFS_BASE]: " path
            
            echo "🚀 Setup completo per $username..."
            create_user_subvolume "$username" "${path:-$BTRFS_BASE}" && \
            set_subvolume_quota "$username" "$quota" "${path:-$BTRFS_BASE}" && \
            echo "✅ Setup completato!"
            ;;
        9)
            echo "👋 Uscita"
            exit 0
            ;;
        *)
            echo "Opzione non valida"
            ;;
    esac
}

# Esecuzione script
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    if [ "$EUID" -ne 0 ]; then
        echo "❌ Questo script deve essere eseguito come root"
        exit 1
    fi
    
    # Se argomenti da comando, esegui direttamente
    if [ $# -gt 0 ]; then
        case $1 in
            "check")
                check_btrfs "${2:-$BTRFS_BASE}"
                ;;
            "enable")
                enable_quotas "${2:-$BTRFS_BASE}"
                ;;
            "create")
                if [ $# -lt 2 ]; then
                    echo "Uso: $0 create USERNAME [BASE_PATH]"
                    exit 1
                fi
                create_user_subvolume "$2" "${3:-$BTRFS_BASE}"
                ;;
            "quota")
                if [ $# -lt 3 ]; then
                    echo "Uso: $0 quota USERNAME SIZE [BASE_PATH]"
                    exit 1
                fi
                set_subvolume_quota "$2" "$3" "${4:-$BTRFS_BASE}"
                ;;
            "show")
                show_quotas "${2:-$BTRFS_BASE}"
                ;;
            "list")
                list_subvolumes "${2:-$BTRFS_BASE}"
                ;;
            "remove")
                if [ $# -lt 2 ]; then
                    echo "Uso: $0 remove USERNAME [BASE_PATH]"
                    exit 1
                fi
                remove_quota "$2" "${3:-$BTRFS_BASE}"
                ;;
            "setup")
                if [ $# -lt 3 ]; then
                    echo "Uso: $0 setup USERNAME QUOTA_SIZE [BASE_PATH]"
                    exit 1
                fi
                create_user_subvolume "$2" "${4:-$BTRFS_BASE}" && \
                set_subvolume_quota "$2" "$3" "${4:-$BTRFS_BASE}"
                ;;
            *)
                echo "Comandi: check|enable|create|quota|show|list|remove|setup"
                exit 1
                ;;
        esac
    else
        # Menu interattivo
        while true; do
            main_menu
            echo ""
            read -p "Continuare? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                break
            fi
        done
    fi
fi
