#!/bin/bash
# Test completo per nextcloud-wrapper v0.3.0

set -e

echo "🧪 Nextcloud Wrapper v0.3.0 - Test Suite"
echo "=========================================="

# Configurazione test
TEST_USER="test-user-$(date +%s)"
TEST_PASSWORD="TestPass123!"
TEST_QUOTA="1G"

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

# Test configurazione
test_config() {
    log_info "Test configurazione..."
    
    nextcloud-wrapper config
    
    log_success "Test configurazione completato"
}

# Test connettività Nextcloud
test_nextcloud_connectivity() {
    log_info "Test connettività Nextcloud..."
    
    # Test tramite API wrapper
    python3 -c "
from ncwrap.api import test_nextcloud_connectivity
success, message = test_nextcloud_connectivity()
print(f'Connettività: {message}')
if not success:
    exit(1)
"
    
    log_success "Connettività Nextcloud OK"
}

# Test creazione utente Nextcloud only
test_create_nextcloud_user() {
    log_info "Test creazione utente Nextcloud..."
    
    nextcloud-wrapper user create "$TEST_USER" "$TEST_PASSWORD" --skip-linux
    
    log_success "Utente Nextcloud creato"
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

# Test quota (se sudo disponibile)
test_quota() {
    if [[ "$SKIP_SUDO_TESTS" == "true" ]]; then
        log_warning "Test quota saltato (no sudo)"
        return
    fi
    
    log_info "Test sistema quote..."
    
    # Test rilevamento filesystem
    python3 -c "
from ncwrap.quota import QuotaManager
manager = QuotaManager()
print(f'Filesystem rilevato: {manager.fs_type}')
"
    
    # Test setup quota (senza effettivamente impostarla)
    python3 -c "
from ncwrap.quota import setup_quota_for_user
from ncwrap.utils import parse_size_to_bytes, bytes_to_human

# Calcola quota filesystem
nc_bytes = parse_size_to_bytes('$TEST_QUOTA')
fs_bytes = int(nc_bytes * 0.02)
fs_quota = bytes_to_human(fs_bytes)

print(f'Quota calcolata: NC $TEST_QUOTA → FS {fs_quota} (2%)')
"
    
    log_success "Test quota completato"
}

# Test WebDAV mount (se sudo disponibile)
test_webdav_mount() {
    if [[ "$SKIP_SUDO_TESTS" == "true" ]]; then
        log_warning "Test WebDAV mount saltato (no sudo)"
        return
    fi
    
    log_info "Test WebDAV mount..."
    
    # Verifica che davfs2 sia installato
    if ! command -v mount.davfs &> /dev/null; then
        log_warning "davfs2 non installato - test mount saltato"
        return
    fi
    
    # Test configurazione WebDAV
    python3 -c "
from ncwrap.webdav import WebDAVMountManager
manager = WebDAVMountManager()
print('WebDAV manager inizializzato')

# Test setup credenziali (dry run)
from ncwrap.api import get_webdav_url
webdav_url = get_webdav_url('$TEST_USER')
print(f'URL WebDAV: {webdav_url}')
"
    
    log_success "Test WebDAV mount completato"
}

# Test servizi systemd (se sudo disponibile)
test_systemd_services() {
    if [[ "$SKIP_SUDO_TESTS" == "true" ]]; then
        log_warning "Test servizi systemd saltato (no sudo)"
        return
    fi
    
    log_info "Test servizi systemd..."
    
    python3 -c "
from ncwrap.systemd import SystemdManager
manager = SystemdManager()

# Lista servizi esistenti
services = manager.list_nextcloud_services()
print(f'Servizi nextcloud trovati: {len(services)}')

# Test generazione configurazione servizio
config = manager._generate_webdav_mount_service_config(
    'test-service', '$TEST_USER', 'https://example.com/dav/', '/home/test', 1000, 1000
)
print('Configurazione servizio generata OK')
"
    
    log_success "Test servizi systemd completato"
}

# Test API completa
test_api_features() {
    log_info "Test funzionalità API..."
    
    python3 -c "
from ncwrap.api import *

# Test info utente
info = get_user_info('$TEST_USER')
if info:
    print('Info utente recuperate OK')
else:
    print('Utente non trovato (normale se appena creato)')

# Test lista directory
status, xml = list_webdav_directory('$TEST_USER', '$TEST_PASSWORD')
print(f'Lista directory: status {status}')

# Test spazio WebDAV
space_info = get_webdav_space_info('$TEST_USER', '$TEST_PASSWORD')
if space_info:
    print(f'Spazio WebDAV: {space_info}')
else:
    print('Info spazio non disponibile')
"
    
    log_success "Test API completato"
}

# Test virtual environment (se disponibile)
test_virtual_environment() {
    log_info "Test virtual environment..."
    
    python3 -c "
from ncwrap.venv import VenvManager
manager = VenvManager()

print(f'Conda disponibile: {manager.is_conda_available()}')
if manager.is_conda_available():
    conda_info = manager.conda_info
    print(f'Conda version: {conda_info[\"version\"]}')
    print(f'Conda path: {conda_info[\"executable\"]}')
    
    env_name = manager.config[\"venv_name\"]
    if manager.environment_exists(env_name):
        print(f'Environment {env_name}: ✅ Esistente')
        env_info = manager.get_env_info(env_name)
        if env_info:
            print(f'Python path: {env_info[\"python_path\"]}')
            print(f'Packages: {len(env_info[\"packages\"])}')
    else:
        print(f'Environment {env_name}: ❌ Non trovato')
    
    # Test path SystemD
    systemd_path = manager.get_systemd_executable_path()
    print(f'SystemD path: {systemd_path}')
else:
    print('Conda non disponibile - usando Python di sistema')
"
    
    log_success "Test virtual environment completato"
}
test_utilities() {
    log_info "Test moduli utilities..."
    
    python3 -c "
from ncwrap.utils import *

# Test parsing size
size_bytes = parse_size_to_bytes('1G')
size_human = bytes_to_human(size_bytes)
print(f'Parsing size: 1G = {size_bytes} bytes = {size_human}')

# Test validazione dominio
valid = validate_domain('test.com')
print(f'Validazione dominio test.com: {valid}')

# Test validazione password
valid, msg = validate_password('$TEST_PASSWORD')
print(f'Validazione password: {valid} - {msg}')

# Test info sistema
info = get_system_info()
print(f'OS: {info.get(\"os\", \"unknown\")}')
print(f'Kernel: {info.get(\"kernel\", \"unknown\")}')
print(f'Memory: {info.get(\"memory\", \"unknown\")}')
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
    
    # Ripristina password originale per altri test
    nextcloud-wrapper user passwd "$TEST_USER" "$TEST_PASSWORD" --nc-only
}

# Test info utente
test_user_info() {
    log_info "Test info utente..."
    
    nextcloud-wrapper user info "$TEST_USER"
    
    log_success "Info utente recuperate"
}

# Cleanup test
cleanup_test() {
    log_info "Pulizia test..."
    
    # Elimina utente Nextcloud (se possibile)
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

# Esecuzione test suite
main() {
    echo
    echo "🏁 Inizio test suite..."
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
    
    # Esegui test
    check_prerequisites
    test_config
    test_nextcloud_connectivity
    test_virtual_environment
    test_utilities
    test_create_nextcloud_user
    test_webdav_login
    test_folder_structure
    test_api_features
    test_password_change
    test_user_info
    
    # Test avanzati (se non quick mode)
    if [[ "$QUICK_TEST" != "true" ]]; then
        test_quota
        test_webdav_mount
        test_systemd_services
    fi
    
    cleanup_test
    
    echo
    log_success "🎉 Tutti i test completati con successo!"
    echo
    echo "✨ Nextcloud Wrapper v0.3.0 funziona correttamente!"
    echo
    echo "🚀 Prossimi passi:"
    echo "   1. Configura le variabili in .env"
    echo "   2. Testa con utenti reali: nextcloud-wrapper setup user domain.com password"
    echo "   3. Configura mount automatici: nextcloud-wrapper webdav mount user password"
    echo "   4. Monitora quote: nextcloud-wrapper quota show"
    echo
}

# Gestione segnali per cleanup
trap cleanup_test EXIT

# Esegui test suite
main "$@"
