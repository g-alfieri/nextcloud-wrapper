def setup_user_with_mount(username: str, password: str, quota: str = None,
                         profile: str = "full", remount: bool = False) -> bool:
    """
    Setup completo utente con rclone engine (v1.0.0rc2 semplificato)
    
    Args:
        username: Nome utente
        password: Password
        quota: Quota Nextcloud (es. "100G") - solo per info
        profile: Profilo rclone mount
        remount: Forza remount se già esistente
    
    Returns:
        True se setup completato
    """
    print(f"🚀 Setup completo per {username} (v1.0.0rc2 - rclone)")
    
    # Validazione profilo
    from .rclone import MOUNT_PROFILES
    if profile not in MOUNT_PROFILES:
        print(f"❌ Profilo non valido: {profile}")
        print(f"💡 Profili disponibili: {', '.join(MOUNT_PROFILES.keys())}")
        return False
    
    mount_manager = MountManager(MountEngine.RCLONE)
    
    # 1. Verifica e installa rclone
    available_engines = mount_manager.detect_available_engines()
    if not available_engines[MountEngine.RCLONE]:
        print("📦 Installando rclone...")
        if not mount_manager.install_engine(MountEngine.RCLONE):
            return False
    
    # 2. Configura rclone
    if not mount_manager.configure_engine(MountEngine.RCLONE):
        return False
    
    # 3. Crea utente Nextcloud se non esiste
    from .api import create_nc_user, check_user_exists
    if not check_user_exists(username):
        try:
            create_nc_user(username, password)
            print(f"✅ Utente Nextcloud creato: {username}")
        except Exception as e:
            print(f"❌ Errore creazione utente Nextcloud: {e}")
            return False
    else:
        print(f"ℹ️ Utente Nextcloud già esistente: {username}")
    
    # 4. Crea utente Linux se non esiste
    from .system import create_linux_user, user_exists
    if not user_exists(username):
        if create_linux_user(username, password, create_home=False):
            print(f"✅ Utente Linux creato: {username}")
        else:
            print(f"❌ Errore creazione utente Linux: {username}")
            return False
    else:
        print(f"ℹ️ Utente Linux già esistente: {username}")
    
    # 5. Mount con rclone (v1.0 - no fallback, solo rclone)
    home_path = f"/home/{username}"
    mount_result = mount_manager.mount_user_home(
        username=username,
        password=password, 
        home_path=home_path,
        engine=MountEngine.RCLONE,
        profile=profile,
        auto_fallback=False,  # v1.0: no fallback
        remount=remount
    )
    
    if not mount_result["success"]:
        print(f"❌ {mount_result['message']}")
        return False
    
    print(f"✅ Mount rclone riuscito")
    print(f"📊 Profilo: {mount_result.get('profile', profile)}")
    
    # 6. Gestione spazio v1.0 (automatica via rclone)
    profile_info = MOUNT_PROFILES.get(profile, {})
    if profile_info.get('storage'):
        print(f"💾 Cache rclone: {profile_info['storage']}")
    print("✅ Gestione spazio: automatica via rclone (cache LRU)")
    
    # 7. Crea servizio systemd rclone
    try:
        service_name = mount_manager.create_systemd_service(
            username, password, home_path, MountEngine.RCLONE, profile
        )
        
        # Abilita servizio
        from .utils import run
        run(["systemctl", "enable", "--now", f"{service_name}.service"], check=False)
        print(f"✅ Servizio systemd: {service_name}")
        
    except Exception as e:
        print(f"⚠️ Avviso servizio systemd: {e}")
    
    print(f"🎉 Setup completato per {username}")
    print(f"• Engine: rclone")
    print(f"• Profilo: {profile}")
    print(f"• Home directory: {home_path} → Nextcloud WebDAV")
    print(f"• Gestione spazio: automatica (cache LRU)")
    
    return True
