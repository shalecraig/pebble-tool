# SDK Management System

**File:** `pebble_tool/sdk/manager.py`

The SDK management system handles installation, activation, and version management of Pebble SDKs.

## Architecture Overview

The SDK management is centered around the `SDKManager` class with a global singleton instance created at `pebble_tool/sdk/__init__.py:25`.

## SDK Directory Structure

**Location:** `~/.pebble-sdk/SDKs/` (Linux) or `~/Library/Application Support/Pebble SDK/SDKs/` (macOS)

**Layout:**
```
~/.pebble-sdk/
├── SDKs/
│   ├── 4.5/                    # SDK version directory
│   │   ├── sdk-core/           # Core SDK files
│   │   │   ├── manifest.json   # SDK metadata
│   │   │   ├── requirements.txt
│   │   │   ├── package.json
│   │   │   └── pebble/
│   │   │       ├── waf
│   │   │       ├── common/
│   │   │       └── {platform}/ # aplite, basalt, chalk, etc.
│   │   ├── toolchain/          # ARM toolchain
│   │   │   └── arm-none-eabi/
│   │   ├── .venv/              # Python virtual environment
│   │   ├── node_modules/       # JS dependencies
│   │   └── package.json
│   ├── current -> 4.5/         # Symlink to active SDK
│   └── tintin/                 # Development SDK (optional)
└── settings.json               # Global config
```

## Remote SDK Discovery

**Function:** `list_remote_sdks()` (manager.py:85-87)

- **Download Server:** `https://sdk.core.store`
- **Channel Support:** Allows switching between stable/beta channels
- **API Endpoint:** `/v1/files/sdk-core?channel={channel}`

## Local SDK Discovery

**Function:** `list_local_sdks()` (manager.py:60-80)

**Algorithm:**
1. Scan all directories in SDK folder
2. Skip symlinks (avoids counting 'current' symlink)
3. Look for `sdk-core/manifest.json` in each directory
4. Parse and collect valid SDK manifests
5. Return list of SDK metadata dictionaries

## SDK Installation Flow

### Main Entry Points

**CLI Command:** `pebble_tool/commands/sdk/manage.py:98-109`

**Decision Tree:**
1. If `--tintin <path>`: Create development SDK from source
2. If version starts with `http://` or `https://`: Download from URL
3. If version is a file path: Install from local tarball
4. Otherwise: Install from official repository

### Remote Installation Process

**Function:** `install_remote_sdk(version)` (manager.py:240-250)

**Steps:**
1. Fetch SDK metadata from server
2. Validate response and check for duplicates
3. Validate system requirements
4. Show EULA license prompt
5. Download and install from URL

### Core Installation Logic

**Function:** `_install_from_handle(f)` (manager.py:169-217)

**Detailed Steps:**

1. **Extract and Validate Tarball**
   - Read manifest before extraction
   - Calculate installation path
   - Check for existing installation

2. **Security Validation**
   - Prevents path traversal attacks
   - Validates version number doesn't escape SDK directory

3. **Requirements Check**
   - Ensures system meets SDK requirements

4. **Extract SDK Files**
   - Creates version directory
   - Extracts all SDK files

5. **Create Python Virtual Environment**
   ```python
   venv_path = os.path.join(path, ".venv")
   subprocess.check_call([sys.executable, "-m", "venv", venv_path])
   subprocess.check_call([os.path.join(venv_path, "bin", "python"),
                         "-m", "pip", "install", "-r",
                         os.path.join(path, "sdk-core", "requirements.txt")])
   ```

6. **Install JavaScript Dependencies**
   - Copies package.json to SDK root
   - Creates node_modules directory
   - Runs `npm install`

7. **Activate SDK**
   - Automatically makes newly installed SDK active via symlink

8. **Install ARM Toolchain**
   - Downloads platform-specific toolchain (mac/linux)
   - URL pattern: `{DOWNLOAD_SERVER}/releases/{version}/toolchain-{platform}.tar.gz`

## SDK Activation Mechanism

**Function:** `set_current_sdk(version)` (manager.py:264-273)

**Process:**
- **Symlink Path:** `~/.pebble-sdk/SDKs/current`
- **Target:** Points to versioned SDK directory
- **Atomic Switch:** Removes old symlink, creates new one

**Usage:**
```python
# Returns active SDK path or auto-installs latest
path = sdk_manager.current_path
```

## ARM Toolchain Installation

**Platform Detection:**
```python
platform_name = "mac" if platform.system() == "Darwin" else "linux"
```

**Download URL Pattern:**
```
https://sdk.core.store/releases/{version}/toolchain-{platform}.tar.gz
```

**Installation Process:**
1. Extract toolchain tarball
2. Security checks (path traversal)
3. Flatten directory structure (remove wrapper dir)
4. Add to PATH via `add_tools_to_path()`

**Final Structure:**
```
~/.pebble-sdk/SDKs/4.5/toolchain/
└── arm-none-eabi/
    ├── bin/           # Cross-compilation tools
    ├── lib/
    ├── include/
    └── ...
```

## Python Virtual Environment

**Purpose:** Each SDK has isolated Python dependencies to avoid conflicts between SDK versions.

**Creation:**
```python
venv_path = os.path.join(path, ".venv")
subprocess.check_call([sys.executable, "-m", "venv", venv_path])
subprocess.check_call([os.path.join(venv_path, "bin", "python"),
                      "-m", "pip", "install", "-r",
                      os.path.join(path, "sdk-core", "requirements.txt")])
```

## Version Tracking and Compatibility

### Version Parsing

**File:** `pebble_tool/util/versions.py`

**Function:** `version_to_key(version)` (versions.py:8-24)

**Version Examples:**
- `"4.5"` → `(4, 5, 0, 0, 0, "")`
- `"4.5-beta1"` → `(4, 5, 0, -2, 1, "")`
- `"4.5.1-rc2"` → `(4, 5, 1, -1, 2, "")`

**Suffix Mapping:**
- `dp` (Developer Preview): -3
- `beta`: -2
- `rc` (Release Candidate): -1
- Stable: 0

### Requirements System

**Class:** `Requirements` (pebble_tool/sdk/requirements.py:17-35)

**Supported Requirements:**
1. `pebble-tool` - Tool version check
2. `pypkjs` - JavaScript runtime version
3. `qemu` - QEMU emulator version

**Example Requirements:**
```json
{
    "requirements": [
        "pebble-tool>=4.5",
        "qemu>=2.7.0"
    ]
}
```

## SDK Update/Upgrade Mechanism

**Background Update Checker:** `pebble_tool/util/updates.py:22-60`

**Features:**
- Runs in background thread (daemon=True)
- Checks once per 24 hours
- Caches results in `~/.pebble-sdk/settings.json`
- Non-blocking startup
- Prints notification at program exit

**Update Check Flow:**
1. Check cache timestamp
2. If > 24 hours, fetch latest version from server
3. Compare with current version using semantic versioning
4. Cache result and schedule notification

## Command Examples

```bash
# List available SDKs
pebble sdk list

# Install specific version
pebble sdk install 4.5

# Install from URL
pebble sdk install https://example.com/sdk.tar.gz

# Activate different SDK
pebble sdk activate 4.3

# Uninstall SDK
pebble sdk uninstall 4.3
```

## Key Decision Points

1. **Platform Detection** - macOS vs Linux determines toolchain download
2. **SDK Source** - URL/file/version string determines installation method
3. **Auto-Install Latest** - No SDK installed triggers automatic latest install
4. **Automatic Activation** - New install activates immediately
5. **Requirements Validation** - Fails fast before extraction if incompatible
6. **Update Notifications** - Only if new version > current version

## Error Handling

**Cleanup on Failure:**
```python
try:
    # ... installation steps ...
except Exception:
    if path is not None and os.path.exists(path):
        shutil.rmtree(path)  # Remove partial install
    raise
```

## Smart Uninstall

When uninstalling active SDK:
1. Removes SDK directory
2. Gets list of remaining SDKs
3. Sorts by semantic version (newest first)
4. Activates newest remaining SDK
5. If no SDKs remain, removes 'current' symlink
