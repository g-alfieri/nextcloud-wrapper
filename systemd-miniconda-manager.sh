#!/bin/bash
# systemd-miniconda-manager.sh - Gestione servizi systemd con Miniconda

echo "🔧 Systemd Manager per Nextcloud Wrapper + Miniconda"
echo "===================================================="

# Configurazione
PROJECT_DIR="/root/src/nextcloud-wrapper"
CONDA_ENV="nextcloud-wrapper"
PYTHON_VENV="$HOME/miniconda3/envs/$CONDA_ENV/bin/python"

# Verifica ambiente
check_environment() {
    echo "🔍 Verifica ambiente..."
    
    # Verifica directory progetto
    if [ ! -d "$PROJECT_DIR" ]; then
        echo "❌ Directory progetto non trovata: $PROJECT_DIR"
        return 1
    fi
    
    # Verifica ambiente conda
    if [ ! -f "$PYTHON_VENV" ]; then
        echo "❌ Python venv non trovato: $PYTHON_VENV"
        echo "Verifica che l'ambiente conda '$CONDA_ENV' sia creato"
        return 1
    fi
    
    # Verifica nextcloud-wrapper installato
    if ! "$PYTHON_VENV" -c "import ncwrap" 2>/dev/null; then
        echo "❌ nextcloud-wrapper non installato nel venv"
        echo "Esegui: cd $PROJECT_DIR && $PYTHON_VENV -m pip install -e ."
        return 1
    fi
    
    echo "✅ Ambiente verificato"
    return 0
}

# Genera template servizio mount
generate_mount_service() {
    local service_name="$1"
    local remote_name="$2" 
    local mount_point="$3"
    local profile="${4:-writes}"
    
    cat > "/etc/systemd/system/${service_name}.service" << EOF
[Unit]
Description=RClone mount for ${remote_name} -> ${mount_point} (profile: ${profile}) [Miniconda]
After=network-online.target
Wants=network-online.target
AssertPathIsDirectory=${mount_point}

[Service]
Type=notify
User=root
Group=root

# Environment per Miniconda
Environment=CONDA_DEFAULT_ENV=${CONDA_ENV}
Environment=PYTHONPATH=${PROJECT_DIR}
Environment=PATH=/usr/local/bin:/usr/bin:/bin
WorkingDirectory=${PROJECT_DIR}

# Carica configurazione
ExecStartPre=/bin/mkdir -p ${mount_point}
ExecStartPre=/bin/bash -c 'source ${PROJECT_DIR}/.env 2>/dev/null || true'

# Mount con rclone (path assoluto)
ExecStart=/usr/local/bin/rclone mount ${remote_name}:/ ${mount_point} \\
    --config /root/.config/ncwrap/rclone.conf \\
    --vfs-cache-mode writes \\
    --vfs-cache-max-size 2G \\
    --buffer-size 64M \\
    --dir-cache-time 10m \\
    --allow-other \\
    --log-level INFO \\
    --log-file /var/log/rclone-${remote_name}.log

# Unmount
ExecStop=/bin/fusermount -u ${mount_point}
ExecStopPost=/bin/rmdir ${mount_point} 2>/dev/null || true

# Recovery
Restart=on-failure
RestartSec=10
KillMode=process

[Install]
WantedBy=multi-user.target
EOF

    echo "✅ Servizio generato: /etc/systemd/system/${service_name}.service"
}

# Genera servizio di gestione generale
generate_management_service() {
    cat > "/etc/systemd/system/nextcloud-wrapper-manager.service" << EOF
[Unit]
Description=Nextcloud Wrapper Manager [Miniconda]
After=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
User=root
Group=root

# Environment per Miniconda  
Environment=CONDA_DEFAULT_ENV=${CONDA_ENV}
Environment=PYTHONPATH=${PROJECT_DIR}
WorkingDirectory=${PROJECT_DIR}

# Comando di gestione via Python venv
ExecStart=${PYTHON_VENV} -c "from ncwrap.cli import app; import sys; sys.argv=['nextcloud-wrapper', 'config']; app()"
ExecReload=${PYTHON_VENV} -c "from ncwrap.cli import app; import sys; sys.argv=['nextcloud-wrapper', 'mount', 'list']; app()"

# Logging
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    echo "✅ Servizio manager generato: /etc/systemd/system/nextcloud-wrapper-manager.service"
}

# Crea script wrapper per nextcloud-wrapper
create_wrapper_script() {
    cat > "/usr/local/bin/nextcloud-wrapper-systemd" << EOF
#!/bin/bash
# Wrapper script per nextcloud-wrapper da systemd

# Setup ambiente
export CONDA_DEFAULT_ENV=${CONDA_ENV}
export PYTHONPATH=${PROJECT_DIR}
cd ${PROJECT_DIR}

# Carica configurazione se disponibile
if [ -f .env ]; then
    source .env 2>/dev/null
fi

# Esegui comando con Python del venv
exec ${PYTHON_VENV} -m ncwrap.cli "\$@"
EOF

    chmod +x "/usr/local/bin/nextcloud-wrapper-systemd"
    echo "✅ Script wrapper creato: /usr/local/bin/nextcloud-wrapper-systemd"
}

# Verifica e ripara servizi esistenti
repair_services() {
    echo "🔧 Riparazione servizi esistenti..."
    
    # Lista servizi nextcloud
    local services=($(systemctl list-unit-files "nextcloud-*" --no-pager 2>/dev/null | grep "nextcloud-" | awk '{print $1}' | sed 's/.service$//'))
    
    if [ ${#services[@]} -eq 0 ]; then
        echo "ℹ️  Nessun servizio nextcloud trovato"
        return 0
    fi
    
    for service in "${services[@]}"; do
        echo "🔧 Riparando servizio: $service"
        
        # Ferma servizio
        systemctl stop "$service" 2>/dev/null
        
        # Leggi configurazione esistente per estrarre parametri
        local service_file="/etc/systemd/system/${service}.service"
        if [ -f "$service_file" ]; then
            local remote_name=$(grep "rclone mount" "$service_file" | sed -n 's/.*rclone mount \([^:]*\):.*/\1/p')
            local mount_point=$(grep "rclone mount" "$service_file" | sed -n 's/.*rclone mount [^:]*:\/[[:space:]]*\([^[:space:]]*\).*/\1/p')
            
            if [ -n "$remote_name" ] && [ -n "$mount_point" ]; then
                echo "  Remote: $remote_name"
                echo "  Mount: $mount_point"
                
                # Rigenera servizio con configurazione Miniconda
                generate_mount_service "$service" "$remote_name" "$mount_point" "writes"
                
                # Reload systemd
                systemctl daemon-reload
                
                echo "  ✅ Servizio $service riparato"
            else
                echo "  ⚠️  Impossibile estrarre parametri da $service"
            fi
        fi
    done
}

# Test servizi
test_services() {
    echo "🧪 Test servizi..."
    
    # Test wrapper script
    if [ -f "/usr/local/bin/nextcloud-wrapper-systemd" ]; then
        echo "Testing wrapper script..."
        if /usr/local/bin/nextcloud-wrapper-systemd --help >/dev/null 2>&1; then
            echo "✅ Wrapper script funzionante"
        else
            echo "❌ Wrapper script non funzionante"
        fi
    fi
    
    # Test manager service
    if systemctl is-enabled nextcloud-wrapper-manager >/dev/null 2>&1; then
        echo "Testing manager service..."
        if systemctl start nextcloud-wrapper-manager; then
            echo "✅ Manager service funzionante"
        else
            echo "❌ Manager service non funzionante"
            journalctl -u nextcloud-wrapper-manager --no-pager -n 5
        fi
    fi
}

# Menu principale
main_menu() {
    echo ""
    echo "Opzioni disponibili:"
    echo "1. Verifica ambiente"
    echo "2. Crea wrapper script"
    echo "3. Genera servizio manager"
    echo "4. Ripara servizi esistenti"
    echo "5. Test servizi"
    echo "6. Setup completo"
    echo "7. Exit"
    echo ""
    read -p "Scegli opzione (1-7): " choice
    
    case $choice in
        1)
            check_environment
            ;;
        2)
            create_wrapper_script
            ;;
        3)
            generate_management_service
            systemctl daemon-reload
            systemctl enable nextcloud-wrapper-manager
            ;;
        4)
            repair_services
            ;;
        5)
            test_services
            ;;
        6)
            echo "🚀 Setup completo..."
            check_environment && \
            create_wrapper_script && \
            generate_management_service && \
            repair_services && \
            systemctl daemon-reload && \
            echo "✅ Setup completo!"
            ;;
        7)
            echo "👋 Uscita"
            exit 0
            ;;
        *)
            echo "Opzione non valida"
            ;;
    esac
}

# Esecuzione
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    if [ "$EUID" -ne 0 ]; then
        echo "❌ Questo script deve essere eseguito come root"
        exit 1
    fi
    
    # Se argomenti da linea comando, esegui direttamente
    if [ $# -gt 0 ]; then
        case $1 in
            "check")
                check_environment
                ;;
            "setup")
                check_environment && create_wrapper_script && generate_management_service && repair_services
                ;;
            "repair")
                repair_services
                ;;
            "test")
                test_services
                ;;
            *)
                echo "Uso: $0 [check|setup|repair|test]"
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
