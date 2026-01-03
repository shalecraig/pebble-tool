# Project Management System

**File:** `pebble_tool/sdk/project.py`

The project management system handles detection, validation, and metadata parsing for Pebble projects.

## Overview

The system supports **two project formats**:
1. **NpmProject** - Modern package.json-based (SDK 3.x+)
2. **AppinfoProject** - Legacy appinfo.json-based (SDK 2.x)

And **three project types**:
1. **native** - C-based apps/watchfaces
2. **rocky** - Rocky.js JavaScript watchfaces
3. **package** - Reusable libraries

## Project Detection

### Factory Function

**Function:** `PebbleProject()` (project.py:16-22)

```python
def PebbleProject(project_dir=None):
    if project_dir is None:
        project_dir = os.getcwd()

    if NpmProject.should_process(project_dir):
        return NpmProject(project_dir)
    else:
        return AppinfoProject(project_dir)
```

### Detection Logic

**NpmProject Detection** (project.py:143-152):

```python
@classmethod
def should_process(cls, project_dir):
    package_json = os.path.join(project_dir, 'package.json')
    if not os.path.exists(package_json):
        return False
    try:
        with open(package_json) as f:
            return 'pebble' in json.load(f)
    except (IOError, ValueError):
        return False
```

**Criteria:**
- `package.json` exists
- Valid JSON
- Contains `'pebble'` key

**Fallback:** If npm detection fails → `AppinfoProject`

## AppinfoProject (Legacy)

**File:** `pebble_tool/sdk/project.py:73-119`

### Structure Validation

```python
def __init__(self, project_dir):
    self.project_dir = os.path.abspath(project_dir)
    self.check_project_directory(project_dir)
    self._parse_project()
    self._sanity_check()
```

**Requirements:**
- `src/` directory must exist
- Valid `appinfo.json` file

### Metadata Parsing

```python
# Core fields from appinfo
self.uuid = uuid.UUID(self.appinfo['uuid'])
self.short_name = self.appinfo['shortName']
self.long_name = self.appinfo['longName']
self.company_name = self.appinfo['companyName']
self.version = self.appinfo['versionLabel']
```

### Limitations

- No dependency management (`self.dependencies = {}`)
- Legacy format for SDK 2.x compatibility
- Requires project conversion for modern features

## NpmProject (Modern)

**File:** `pebble_tool/sdk/project.py:121-186`

### Structure Validation

```python
def __init__(self, project_dir):
    self.project_dir = os.path.abspath(project_dir)
    self.check_project_directory(project_dir)
    self._parse_project()
    self._sanity_check()
```

**Requirements:**
- `package.json` with `'pebble'` key
- Falls back to checking `src/` directory if file missing

### Metadata Parsing

```python
# Root-level npm fields
self.short_name = self.project_info['name']
self.company_name = self.project_info['author']
self.version = self.project_info['version']

# Pebble-specific from nested 'pebble' key
self.appinfo = self.project_info['pebble']
self.uuid = uuid.UUID(self.appinfo['uuid'])  # Not required for packages
self.long_name = self.appinfo.get('displayName', self.short_name)
```

### Dependency Management

```python
# Merge dependencies and devDependencies
deps = self.project_info.get('dependencies', {})
dev_deps = self.project_info.get('devDependencies', {})
self.dependencies = {**deps, **dev_deps}
```

**Advantages:**
- Full npm dependency support
- Standard Node.js tooling
- Special handling for `package` projectType
- Uses `displayName` with fallback

## Project Metadata Structure

### package.json (App)

**Template:** `pebble_tool/sdk/templates/app/package.json`

```json
{
  "name": "myapp",           // → short_name
  "author": "Developer",     // → company_name
  "version": "1.0.0",        // → version
  "pebble": {
    "displayName": "My App", // → long_name
    "uuid": "...",           // → uuid
    "sdkVersion": "3",       // → sdk_version
    "targetPlatforms": [...],// → target_platforms
    "messageKeys": [...],    // → message_keys
    "resources": {...}       // → resources
  }
}
```

### package.json (Rocky)

**Additional Fields:**

```json
{
  "pebble": {
    "main": {
      "rockyjs": "src/rocky/index.js",
      "pkjs": "src/pkjs/index.js"
    },
    "projectType": "rocky"
  }
}
```

### package.json (Package/Library)

```json
{
  "files": ["dist.zip"],
  "keywords": ["pebble-package"],
  "pebble": {
    "projectType": "package"  // NO uuid field!
  }
}
```

## Project Types

### Type Detection

```python
self.project_type = self.appinfo.get('projectType', 'native')
```

**Default:** `'native'` if not specified

### Type Validation

```python
if self.project_type not in ('native', 'package', 'rocky'):
    if self.project_type == 'pebblejs':
        raise InvalidProjectException("Pebble.js is not part of the SDK...")
    else:
        raise InvalidProjectException(f"Unsupported project type '{self.project_type}'")
```

### Type Characteristics

#### native (C-based apps)

**Build:** Compiles C code to ARM binary
**Structure:**
```
src/c/           # C source files
worker_src/c/    # Optional background worker
resources/       # Images, fonts, etc.
```

**Binary:** `pebble-app.elf` per platform
**JS Support:** Optional PebbleKit JS in `src/pkjs/`

**wscript:** `pebble_tool/sdk/templates/app/wscript`

#### rocky (Rocky.js watchfaces)

**Build:** JavaScript-only, no C compilation
**Structure:**
```
src/rocky/index.js  # Watch-side Rocky.js
src/pkjs/index.js   # Phone-side PebbleKit JS
```

**Binary:** `bin_type='rocky'`
**No C code:** Pure JS watchface framework

**wscript:** `pebble_tool/sdk/templates/rocky/wscript`

#### package (Libraries)

**Build:** Creates distributable library
**Structure:**
```
src/c/       # C source
include/     # Headers
src/js/      # Optional JavaScript
```

**Binary:** Static library per platform
**Output:** `dist.zip` for npm distribution
**No UUID:** Packages don't need app UUIDs

**wscript:** `pebble_tool/sdk/templates/lib/wscript`

## SDK Version Compatibility

### Version Constant

```python
SDK_VERSION = "3"
```

### Validation Logic

```python
if self.sdk_version == '2.9':
    if sdk_version() != '2.9':
        raise OutdatedProjectException(
            "This project is outdated (try 'pebble convert-project')"
        )
elif self.sdk_version != SDK_VERSION:
    raise PebbleProjectException(
        f"Invalid sdkVersion '{self.sdk_version}' in package.json. "
        f"Latest supported: '{SDK_VERSION}'"
    )
```

**Special Case:** SDK 2.9 projects require exact SDK match
**Default:** Projects without `sdkVersion` default to `2`

## Project Structure Requirements

### Common Requirements

- `src/` directory must exist
- `wscript` file for build configuration
- Valid project metadata (package.json OR appinfo.json)

### Native App Structure

```
project/
├── src/
│   ├── c/
│   │   └── main.c
│   └── pkjs/           # Optional
│       └── index.js
├── worker_src/         # Optional
│   └── c/
│       └── worker.c
├── resources/          # Optional
├── package.json
└── wscript
```

### Rocky Watchface Structure

```
project/
├── src/
│   ├── rocky/
│   │   └── index.js
│   └── pkjs/
│       └── index.js
├── package.json
└── wscript
```

### Package/Library Structure

```
project/
├── src/
│   ├── c/
│   │   └── lib.c
│   └── js/             # Optional
│       └── index.js
├── include/
│   └── lib.h
├── package.json
└── wscript
```

## Outdated Project Detection

**Function:** `_sanity_check()` (project.py:48-51)

```python
if os.path.islink(os.path.join(self.project_dir, 'pebble_app.ld')) \
        or os.path.exists(os.path.join(self.project_dir, 'resources/src/resource_map.json')) \
        or not os.path.exists(os.path.join(self.project_dir, 'wscript')):
    raise OutdatedProjectException("This project is very outdated...")
```

**Indicators:**
- `pebble_app.ld` symlink (SDK 1.x)
- `resources/src/resource_map.json` (SDK 2.x)
- Missing `wscript` file

## Project Conversion

**File:** `pebble_tool/commands/sdk/project/convert.py`

### Conversion Flow

**Function:** `__call__()` (convert.py:20-32)

```python
def __call__(self, args):
    super().__call__(args)
    try:
        if not isinstance(self.project, NpmProject):
            self._convert_to_npm()
            print("Converted to package.json format.")
        else:
            print("No conversion required")
    except OutdatedProjectException:
        self._convert_project()           # SDK 2.x upgrade
        super(PblProjectConverter, self).__call__(args)
        self._convert_to_npm()           # Then convert to npm
```

### appinfo.json → package.json

**Function:** `_convert_to_npm()` (convert.py:34-69)

**Metadata Mapping:**

```python
new_info = {
    'name': self.project.short_name,
    'author': self.project.company_name,
    'version': self.project.version + '.0',  # Append '.0' for semver
    'private': True,
    'keywords': ['pebble-app'],
    'pebble': {
        'sdkVersion': self.project.sdk_version,
        'targetPlatforms': self.project.target_platforms,
        'enableMultiJS': self.project.enable_multi_js,
        'capabilities': self.project.capabilities,
        'projectType': self.project.project_type,
        'displayName': self.project.long_name,
        'uuid': str(self.project.uuid),
        'watchapp': {
            'watchface': self.project.is_watchface,
            'hiddenApp': self.project.is_hidden,
            'onlyShownOnCommunication': self.project.is_shown_only_on_communication,
        },
        'resources': self.project.resources,
        'messageKeys': self.project.message_keys,
    }
}
```

**Safety Measures:**
- Backs up existing `package.json` to `package.json~`
- Merges with existing package.json if present
- Deletes `appinfo.json` after successful conversion
- Adds `node_modules/` to `.gitignore`

### SDK 2.x → 3.x Conversion

**Function:** `_convert_project()` (convert.py:83-100)

**Process:**
1. Backup old wscript → `wscript.backup`
2. Update appinfo.json with SDK 3 fields:
   - Sets `targetPlatforms` to all available platforms
   - Sets `sdkVersion` to `"3"`
3. Copy new SDK 3 wscript from templates
4. Run `pebble clean` to clear old build artifacts

## Project Initialization Flow

```
PebbleProject(dir)
    │
    ├─→ NpmProject.should_process(dir)
    │       │
    │       ├─→ Check package.json exists
    │       ├─→ Parse JSON
    │       └─→ Check 'pebble' key exists
    │
    ├─[YES]→ return NpmProject(dir)
    │           │
    │           ├─→ check_project_directory()
    │           ├─→ _parse_project()
    │           │       └─→ Parse package.json
    │           └─→ _sanity_check()
    │                   └─→ Validate project_type, SDK version
    │
    └─[NO]─→ return AppinfoProject(dir)
                │
                ├─→ check_project_directory()
                ├─→ _parse_project()
                │       └─→ Parse appinfo.json
                └─→ _sanity_check()
                        └─→ Check for outdated markers
```

## Command Examples

```bash
# Create new app project
pebble new-project myapp

# Create Rocky.js watchface
pebble new-project mywatchface --rocky

# Create library package
pebble new-package mylib

# Convert legacy project to npm format
pebble convert-project

# Check project validity
pebble build  # Validates project during build
```

## Key Features

- **Dual Format Support** - Modern npm and legacy appinfo
- **Automatic Detection** - Smart project type detection
- **Conversion Tools** - Upgrade from SDK 2.x to 3.x
- **Validation** - Comprehensive sanity checks
- **Type Safety** - Explicit project type validation
- **Dependency Management** - Full npm integration
- **Flexible Metadata** - Package-specific handling (no UUID for libs)

## Summary

The project management system provides:
- **Format Detection** - Automatic npm vs appinfo
- **Type Support** - native, rocky, package projects
- **Validation** - Structure and metadata checks
- **Conversion** - SDK 2.x → 3.x, appinfo → package.json
- **Compatibility** - Handles both legacy and modern formats
- **Dependency Tracking** - npm integration for modern projects
