# Changelog nextcloud-wrapper

## v1.0.0rc3 - 2025-10-04 - Architecture Cleanup

### ❌ Removed
- **cli_service.py** - Redundant systemctl wrapper removed
- **service_manager.py** - Unnecessary abstraction layer (file didn't exist)
- **3-layer wrapper antipattern**: CLI → service_manager → systemctl

### ✅ Improved
- **Integrated service management** - Service commands now available via `nextcloud-wrapper mount service`
- **Simplified architecture** - Direct systemctl calls instead of wrapper layers
- **Reduced complexity** - Eliminated redundant code and potential failure points
- **Better UX** - Service management logically grouped with mount operations

### 🔧 Migration Guide

**Before (removed)**:
```bash
nextcloud-wrapper service list
nextcloud-wrapper service enable ncwrap-rclone-user
nextcloud-wrapper service status ncwrap-rclone-user
```

**After (new location)**:
```bash
nextcloud-wrapper mount service list
nextcloud-wrapper mount service enable ncwrap-rclone-user
nextcloud-wrapper mount service status ncwrap-rclone-user
```

### 📊 Benefits
- **Simplified maintenance** - Less code to maintain and debug
- **Better performance** - Fewer abstraction layers
- **Logical grouping** - Service management with mount operations
- **Reduced dependencies** - Direct systemctl integration

### 🏗️ Architecture Changes

**Old Architecture**:
```
CLI (cli.py) 
├── cli_service.py → service_manager.py → systemctl
├── cli_mount.py → MountManager → systemctl
└── cli_user.py
```

**New Architecture (Simplified)**:
```
CLI (cli.py)
├── cli_mount.py 
│   ├── mount commands → MountManager → systemctl
│   └── service subcommands → systemctl (direct)
└── cli_user.py
```

---

## v1.0.0rc2 - Previous Release
- rclone Engine Semplificato
- 4 profili mount (hosting/minimal/writes/full)
- Gestione automatica spazio via rclone cache LRU
