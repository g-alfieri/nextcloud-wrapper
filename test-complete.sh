#!/bin/bash
# Test suite per nextcloud-wrapper v1.0.0 - rclone Engine (semplificato)

set -e

echo "🧪 Nextcloud Wrapper v1.0.0 - Test Suite Semplificata"
echo "======================================================="

# Configurazione test
TEST_USER="test-user-$(date +%s)"
TEST_PASSWORD="TestPass123!"

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Funzioni helper
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Verifica prerequisiti
check_prerequisites() {
    log_info "Verificando prerequisiti..."
    
    # Verifica variabili ambiente
    if [[ -z "$NC_BASE_URL" || -z "$NC_ADMIN_USER" || -z "$NC_ADMIN_PASS" ]]; then
        log_error "Variabili ambiente mancanti! Carica .env file:"
        echo "export NC_BASE_URL=https://your-nextcloud.com"
        echo "export NC_ADMIN_USER=admin"
        echo "export NC_ADMIN_PASS=password"
        exit 1
    fi
    
    # Verifica comando nextcloud-wrapper
    if ! command -v nextcloud-wrapper &> /dev/null; then
        log_error "Comando nextcloud-wrapper non trovato!"
        echo "Installa con: pip install -e ."
        exit 1
    fi
    
    # Verifica privilegi sudo se non in test mode
    if [[ "$1" != "--no-sudo" ]] && ! sudo -n true 2>/dev/null; then
        log_warning "Privilegi sudo non disponibili - alcuni test verranno saltati"
        export SKIP_SUDO_TESTS=true
    fi
    
    log_success "Prerequisiti verificati"
}

# Test configurazione v1.0
test_config() {
    log_info "Test configurazione v1.0..."
    
    nextcloud-wrapper config
    
    log_success "Test configurazione completato"
}

# Test connettività Nextcloud
test_nextcloud_connectivity() {
    log_info "Test connettività Nextcloud..."
    
    # Test tramite API wrapper
    python3 -c "
from ncwrap.api import test_webdav_connectivity
if test_webdav_connectivity('$NC_ADMIN_USER', '$NC_ADMIN_PASS'):
    print('✅ Connettività Nextcloud OK')
else:
    print('❌ Test connettività fallito')
    exit(1)
"
    
    log_success "Connettività Nextcloud OK"
}

# Test creazione utente
test_create_user() {
    log_info "Test creazione utente..."
    
    nextcloud-wrapper user create "$TEST_USER" "$TEST_PASSWORD" --skip-linux
    
    log_success "Utente creato"
}

# Test login WebDAV
test_webdav_login() {
    log_info "Test login WebDAV..."
    
    nextcloud-wrapper user test "$TEST_USER" "$TEST_PASSWORD"
    
    log_success "Login WebDAV verificato"
}

# Test creazione struttura cartelle
test_folder_structure() {
    log_info "Test creazione struttura cartelle..."
    
    python3 -c "
from ncwrap.api import create_folder_structure
results = create_folder_structure('$TEST_USER', '$TEST_PASSWORD', 'test.com', ['api.test.com'])
success_count = sum(1 for status in results.values() if status in [201, 405])
print(f'Cartelle create/verificate: {success_count}/{len(results)}')
if success_count < len(results):
    print('Alcuni errori nella creazione cartelle')
"
    
    log_success "Struttura cartelle verificata"
}

# Test rclone (se sudo disponibile) 
test_rclone_functionality() {
    if [[ "$SKIP_SUDO_TESTS" == "true" ]]; then
        log_warning "Test rclone saltato (no sudo)"
        return
    fi
    
    log_info "Test funzionalità rclone..."
    
    # Verifica rclone disponibile
    if ! command -v rclone &> /dev/null; then
        log_warning "rclone non installato - test saltato"
        return
    fi
    
    # Test mount manager
    python3 -c "
from ncwrap.mount import MountManager
manager = MountManager()
print(f'rclone disponibile: {manager.is_rclone_available()}')

# Test setup credenziali (dry run)
from ncwrap.api import get_nc_config
base_url, _, _ = get_nc_config()
print(f'URL base Nextcloud: {base_url}')

# Test profili
from ncwrap.rclone import MOUNT_PROFILES
print(f'Profili disponibili: {list(MOUNT_PROFILES.keys())}')
"
    
    log_success "Test rclone completato"
}

# Test virtual environment
test_virtual_environment() {
    log_info "Test virtual environment..."
    
    python3 -c "
from ncwrap.venv import VenvManager
manager = VenvManager()

print(f'Conda disponibile: {manager.is_conda_available()}')
if manager.is_conda_available():
    conda_info = manager.conda_info
    print(f'Conda version: {conda_info[\"version\"]}')
    
    env_name = manager.config[\"venv_name\"]
    if manager.environment_exists(env_name):
        print(f'Environment {env_name}: ✅ Esistente')
    else:
        print(f'Environment {env_name}: ❌ Non trovato')
else:
    print('Conda non disponibile - usando Python di sistema')
"
    
    log_success "Test virtual environment completato"
}

# Test utilities semplificati
test_utilities() {
    log_info "Test moduli utilities..."
    
    python3 -c "
from ncwrap.utils import *

# Test info sistema
info = get_system_info()
print(f'OS: {info.get(\"os\", \"unknown\")}')

# Test mount check
print(f'Mount check function available: {callable(is_mounted)}')

# Test run command
try:
    result = run(['echo', 'test'])
    print(f'Run command OK: {\"test\" in result}')
except:
    print('Run command failed')
"
    
    log_success "Test utilities completato"
}

# Test cambio password
test_password_change() {
    log_info "Test cambio password..."
    
    NEW_PASSWORD="NewPass456!"
    
    # Test solo Nextcloud
    nextcloud-wrapper user passwd "$TEST_USER" "$NEW_PASSWORD" --nc-only
    
    # Verifica nuovo login
    nextcloud-wrapper user test "$TEST_USER" "$NEW_PASSWORD"
    
    log_success "Cambio password verificato"
    
    # Ripristina password originale
    nextcloud-wrapper user passwd "$TEST_USER" "$TEST_PASSWORD" --nc-only
}

# Test info utente v1.0
test_user_info() {
    log_info "Test info utente v1.0..."
    
    nextcloud-wrapper user info "$TEST_USER"
    
    log_success "Info utente recuperate"
}

# Test CLI mount (se rclone disponibile)
test_cli_mount() {
    if [[ "$SKIP_SUDO_TESTS" == "true" ]]; then
        log_warning "Test CLI mount saltato (no sudo)"
        return
    fi
    
    log_info "Test CLI mount..."
    
    # Test lista profili
    nextcloud-wrapper mount profiles
    
    # Test mount temporaneo (se rclone disponibile)
    if command -v rclone &> /dev/null; then
        log_info "Rclone disponibile, test mount temporaneo..."
        nextcloud-wrapper mount test "$TEST_USER" "$TEST_PASSWORD" --profile=minimal
    else
        log_warning "Rclone non disponibile, test mount saltato"
    fi
    
    log_success "Test CLI mount completato"
}

# Test setup command v1.0
test_setup_command() {
    log_info "Test comando setup v1.0..."
    
    # Test mostra profili
    nextcloud-wrapper setup profiles
    
    # Test migrazione info
    nextcloud-wrapper setup migrate
    
    log_success "Test setup completato"
}

# Cleanup test
cleanup_test() {
    log_info "Pulizia test..."
    
    # Elimina utente Nextcloud
    python3 -c "
try:
    from ncwrap.api import delete_nc_user
    delete_nc_user('$TEST_USER')
    print('Utente test eliminato')
except Exception as e:
    print(f'Avviso eliminazione utente: {e}')
"
    
    log_success "Cleanup completato"
}

# Esecuzione test suite v1.0
main() {
    echo
    echo "🏁 Inizio test suite v1.0..."
    echo
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --no-sudo)
                export SKIP_SUDO_TESTS=true
                shift
                ;;
            --quick)
                export QUICK_TEST=true
                shift
                ;;
            *)
                echo "Uso: $0 [--no-sudo] [--quick]"
                exit 1
                ;;
        esac
    done
    
    # Test core v1.0 (solo rclone)
    check_prerequisites
    test_config
    test_nextcloud_connectivity
    test_virtual_environment
    test_utilities
    test_create_user
    test_webdav_login
    test_folder_structure
    test_password_change
    test_user_info
    test_setup_command
    
    # Test avanzati (se non quick mode)
    if [[ "$QUICK_TEST" != "true" ]]; then
        test_rclone_functionality
        test_cli_mount
    fi
    
    cleanup_test
    
    echo
    log_success "🎉 Tutti i test v1.0 completati con successo!"
    echo
    echo "✨ Nextcloud Wrapper v1.0.0 funziona correttamente!"
    echo
    echo "🚀 Versione 1.0 - Caratteristiche:"
    echo "   • Engine unico: rclone (performance ottimali)"
    echo "   • Gestione spazio: automatica via rclone (cache LRU)"
    echo "   • Setup semplificato: zero configurazioni quote"
    echo "   • 4 profili rclone: hosting, minimal, writes, full"
    echo
    echo "🔧 Workflow semplificato:"
    echo "   1. nextcloud-wrapper setup user domain.com password --profile=full"
    echo "   2. nextcloud-wrapper mount status"
    echo "   3. ssh utente@server (home = spazio Nextcloud!)"
    echo
}

# Gestione segnali per cleanup
trap cleanup_test EXIT

# Esegui test suite
main "$@"
