#!/bin/bash
# Setup completo Miniconda + Nextcloud Wrapper v0.3.0

set -e

# Colori
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }

echo "🐍 Nextcloud Wrapper v0.3.0 - Miniconda Setup"
echo "=============================================="

# Verifica se siamo nella directory corretta
if [[ ! -f "environment.yml" ]]; then
    log_error "File environment.yml non trovato!"
    log_info "Esegui questo script dalla directory del progetto nextcloud-wrapper"
    exit 1
fi

# Funzione per installare Miniconda
install_miniconda() {
    local install_dir="$1"
    
    log_info "Installando Miniconda in $install_dir..."
    
    # Download Miniconda
    local miniconda_url="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"
    local installer="/tmp/miniconda_installer.sh"
    
    if command -v wget &> /dev/null; then
        wget -q -O "$installer" "$miniconda_url"
    elif command -v curl &> /dev/null; then
        curl -s -o "$installer" "$miniconda_url"
    else
        log_error "wget o curl richiesti per download Miniconda"
        return 1
    fi
    
    # Installa Miniconda
    chmod +x "$installer"
    bash "$installer" -b -p "$install_dir"
    
    # Cleanup
    rm -f "$installer"
    
    log_success "Miniconda installato in $install_dir"
}

# Funzione per rilevare o installare Conda
setup_conda() {
    log_info "Rilevamento Conda/Miniconda..."
    
    # Cerca installazioni esistenti
    local conda_paths=(
        "$HOME/miniconda3/bin/conda"
        "$HOME/anaconda3/bin/conda"
        "/opt/miniconda3/bin/conda"
        "/opt/anaconda3/bin/conda"
        "$(which conda 2>/dev/null || true)"
        "$(which mamba 2>/dev/null || true)"
    )
    
    for conda_path in "${conda_paths[@]}"; do
        if [[ -x "$conda_path" ]]; then
            log_success "Conda trovato: $conda_path"
            CONDA_EXE="$conda_path"
            return 0
        fi
    done
    
    # Nessuna installazione trovata - installa Miniconda
    log_warning "Conda non trovato - installazione automatica Miniconda"
    
    local install_dir="$HOME/miniconda3"
    if [[ "$EUID" -eq 0 ]]; then
        install_dir="/opt/miniconda3"
    fi
    
    if install_miniconda "$install_dir"; then
        CONDA_EXE="$install_dir/bin/conda"
        
        # Inizializza conda per la shell corrente
        eval "$($CONDA_EXE shell.bash hook)"
        
        log_success "Miniconda installato e inizializzato"
        return 0
    else
        log_error "Errore installazione Miniconda"
        return 1
    fi
}

# Funzione per creare environment
create_environment() {
    log_info "Creando environment nextcloud-wrapper..."
    
    # Verifica se environment esiste già
    if $CONDA_EXE env list | grep -q "nextcloud-wrapper"; then
        log_warning "Environment nextcloud-wrapper già esistente"
        
        read -p "Vuoi ricrearlo? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "Rimuovendo environment esistente..."
            $CONDA_EXE env remove -n nextcloud-wrapper -y
        else
            log_info "Usando environment esistente"
            return 0
        fi
    fi
    
    # Crea environment da file yml
    log_info "Creando environment da environment.yml..."
    $CONDA_EXE env create -f environment.yml
    
    log_success "Environment nextcloud-wrapper creato"
}

# Funzione per installare il package
install_package() {
    log_info "Installando nextcloud-wrapper in modalità development..."
    
    # Attiva environment
    eval "$($CONDA_EXE shell.bash hook)"
    conda activate nextcloud-wrapper
    
    # Installa package in modalità development
    pip install -e .
    
    log_success "Package nextcloud-wrapper installato"
}

# Funzione per creare wrapper scripts
create_wrappers() {
    log_info "Creando script wrapper..."
    
    # Attiva environment e crea wrapper tramite CLI
    eval "$($CONDA_EXE shell.bash hook)"
    conda activate nextcloud-wrapper
    
    python -m ncwrap.cli venv create-wrappers
    
    log_success "Script wrapper creati"
}

# Funzione per setup auto-attivazione
setup_auto_activation() {
    log_info "Configurando auto-attivazione..."
    
    # Attiva environment e configura auto-attivazione
    eval "$($CONDA_EXE shell.bash hook)"
    conda activate nextcloud-wrapper
    
    python -m ncwrap.cli venv setup-auto-activation
    
    log_success "Auto-attivazione configurata"
}

# Funzione per installare wrapper SystemD
install_systemd_wrapper() {
    if [[ "$EUID" -eq 0 ]]; then
        log_info "Installando wrapper SystemD globale..."
        
        eval "$($CONDA_EXE shell.bash hook)"
        conda activate nextcloud-wrapper
        
        python -m ncwrap.cli venv install-wrapper
        
        log_success "Wrapper SystemD installato"
    else
        log_warning "Privilegi root necessari per wrapper SystemD"
        log_info "Esegui manualmente: sudo nextcloud-wrapper venv install-wrapper"
    fi
}

# Funzione per configurare .env
setup_env_file() {
    log_info "Configurando file .env..."
    
    if [[ ! -f ".env" ]]; then
        if [[ -f ".env.example" ]]; then
            cp .env.example .env
            log_success "File .env creato da .env.example"
            log_warning "⚠️  IMPORTANTE: Modifica .env con le tue credenziali Nextcloud!"
            echo
            echo "Parametri da configurare:"
            echo "  • NC_BASE_URL=https://your-nextcloud.com"
            echo "  • NC_ADMIN_USER=admin"
            echo "  • NC_ADMIN_PASS=your_password"
            echo
        else
            log_warning "File .env.example non trovato"
        fi
    else
        log_info "File .env già esistente"
    fi
}

# Funzione per test finale
test_installation() {
    log_info "Test installazione..."
    
    # Attiva environment
    eval "$($CONDA_EXE shell.bash hook)"
    conda activate nextcloud-wrapper
    
    # Test import
    if python -c "import ncwrap; print(f'✅ nextcloud-wrapper v{ncwrap.__version__}')" 2>/dev/null; then
        log_success "Import test superato"
    else
        log_error "Import test fallito"
        return 1
    fi
    
    # Test CLI
    if python -m ncwrap.cli --version &>/dev/null; then
        log_success "CLI test superato"
    else
        log_error "CLI test fallito"
        return 1
    fi
    
    # Test wrapper script
    if [[ -f "$HOME/.local/bin/nextcloud-wrapper" ]]; then
        log_success "Wrapper script trovato"
    else
        log_warning "Wrapper script non trovato"
    fi
    
    log_success "Installazione testata con successo!"
}

# Funzione per mostrare informazioni finali
show_final_info() {
    echo
    log_success "🎉 Setup Miniconda completato con successo!"
    echo
    echo "📋 Riepilogo installazione:"
    echo "  • Conda: $CONDA_EXE"
    echo "  • Environment: nextcloud-wrapper"
    echo "  • Package: installato in modalità development"
    echo "  • Wrapper scripts: ~/.local/bin/nextcloud-wrapper"
    echo "  • Auto-attivazione: configurata"
    echo
    echo "🚀 Prossimi passi:"
    echo
    echo "1. Ricarica la shell:"
    echo "   source ~/.bashrc"
    echo
    echo "2. Attiva l'environment (automatico nella directory progetto):"
    echo "   conda activate nextcloud-wrapper"
    echo
    echo "3. Configura le credenziali in .env:"
    echo "   nano .env"
    echo
    echo "4. Testa la configurazione:"
    echo "   nextcloud-wrapper config"
    echo
    echo "5. Crea il tuo primo utente:"
    echo "   nextcloud-wrapper setup user domain.com password"
    echo
    echo "🔧 Comandi utili:"
    echo "  • nw config           # Alias breve per nextcloud-wrapper config"
    echo "  • nw status           # Status generale sistema"
    echo "  • nw venv status      # Status virtual environment"
    echo "  • nw venv test        # Test environment completo"
    echo
    echo "⚙️ Per servizi SystemD:"
    if [[ -f "/usr/local/bin/nextcloud-wrapper" ]]; then
        echo "  • Wrapper globale installato: /usr/local/bin/nextcloud-wrapper"
        echo "  • I servizi SystemD useranno automaticamente il virtual environment"
    else
        echo "  • Installa wrapper globale: sudo nextcloud-wrapper venv install-wrapper"
    fi
    echo
    echo "📖 Documentazione completa: README.md"
    echo "🐛 Issues/Support: https://github.com/your-repo/nextcloud-wrapper"
}

# Main execution
main() {
    echo
    
    # Parse arguments
    FORCE_REINSTALL=false
    SKIP_SYSTEMD=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --force)
                FORCE_REINSTALL=true
                shift
                ;;
            --skip-systemd)
                SKIP_SYSTEMD=true
                shift
                ;;
            --help|-h)
                echo "Uso: $0 [--force] [--skip-systemd]"
                echo
                echo "Opzioni:"
                echo "  --force        Forza reinstallazione environment esistente"
                echo "  --skip-systemd Salta installazione wrapper SystemD"
                echo "  --help         Mostra questo messaggio"
                exit 0
                ;;
            *)
                log_error "Opzione sconosciuta: $1"
                echo "Usa --help per vedere le opzioni disponibili"
                exit 1
                ;;
        esac
    done
    
    # Setup steps
    if ! setup_conda; then
        log_error "Setup Conda fallito"
        exit 1
    fi
    
    if ! create_environment; then
        log_error "Creazione environment fallita"
        exit 1
    fi
    
    if ! install_package; then
        log_error "Installazione package fallita"
        exit 1
    fi
    
    if ! create_wrappers; then
        log_warning "Creazione wrapper parzialmente fallita"
    fi
    
    if ! setup_auto_activation; then
        log_warning "Setup auto-attivazione parzialmente fallito"
    fi
    
    if [[ "$SKIP_SYSTEMD" != "true" ]]; then
        install_systemd_wrapper
    fi
    
    setup_env_file
    
    if ! test_installation; then
        log_error "Test installazione falliti"
        exit 1
    fi
    
    show_final_info
}

# Gestione segnali
trap 'log_error "Setup interrotto dall'\''utente"; exit 1' INT TERM

# Verifica prerequisiti
if [[ ! -d ".git" ]] && [[ ! -f "pyproject.toml" ]]; then
    log_error "Questo non sembra essere la directory del progetto nextcloud-wrapper"
    log_info "Assicurati di essere nella directory corretta con pyproject.toml"
    exit 1
fi

# Esegui setup
main "$@"
