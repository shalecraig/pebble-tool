# Pebble Tool - Architecture Overview

**Total Codebase:** ~3,526 lines of Python code across 40+ modules

## Project Type and Purpose

Pebble Tool is a Python-based command-line SDK for developing Pebble smartwatch applications and watchfaces. It's the modern Python 3 successor to the original Pebble SDK, providing developers with tools to create, build, test, and deploy Pebble applications.

## Main Entry Points

### Primary Entry Point
- **File:** `/pebble.py` (executable wrapper)
- **Main Function:** `pebble_tool/__init__.py:run_tool()`
- **Installed Command:** `pebble` (defined in pyproject.toml as console script)

### Command Registration System
The tool uses a **metaclass-based self-registering command system**:
- **Base Class:** `BaseCommand` with `SelfRegisteringCommand` metaclass
- **Location:** `pebble_tool/commands/base.py`
- Commands automatically register themselves when imported
- Uses argparse for argument parsing and subcommand routing

## Key Subsystems

### 1. SDK Management (`pebble_tool/sdk/`)
**Purpose:** Manages SDK versions, installation, and configuration

**Key Features:**
- Downloads SDK from `https://sdk.core.store`
- Manages multiple SDK versions with symlink-based activation
- Installs ARM toolchain per platform (Linux/Mac)
- Creates Python virtual environments per SDK
- Handles npm dependencies for JavaScript support

### 2. Emulator Management (`pebble_tool/sdk/emulator.py`)
**Purpose:** Manages QEMU-based Pebble emulator instances

**Key Components:**
- `ManagedEmulatorTransport` - Spawns and manages QEMU + pypkjs processes
- Supports 6 Pebble platforms: aplite, basalt, chalk, diorite, emery, flint
- VNC support via websockify for remote/web-based access
- Persistent storage per platform/SDK version
- Process lifecycle management (spawn, monitor, kill)

**Emulator Stack:**
- **QEMU**: Hardware emulation (custom pebble-qemu binary)
- **pypkjs**: JavaScript runtime (PebbleKit JS)
- **websockify**: Optional VNC-over-WebSocket proxy

### 3. Project Management (`pebble_tool/sdk/project.py`)
**Purpose:** Project structure and metadata handling

**Supported Project Types:**
- **NpmProject**: Modern package.json-based projects
- **AppinfoProject**: Legacy appinfo.json-based projects
- **Project Types**: native (C), rocky (Rocky.js), package (libraries)

### 4. Build System (`pebble_tool/commands/sdk/project/`)
**Purpose:** Compiles Pebble applications

**Build Process:**
- Uses **waf** (Python-based build system) from SDK
- Invokes ARM cross-compiler (arm-none-eabi-gcc)
- Handles multi-platform builds
- npm integration for JavaScript dependencies

### 5. Communication/Transport Layer (`pebble_tool/commands/base.py`)
**Purpose:** Connects to Pebble devices and emulators

**Transport Implementations:**
- `PebbleTransportSerial` - Direct serial/USB connection
- `PebbleTransportPhone` - WebSocket via Pebble mobile app
- `PebbleTransportQemu` - Direct QEMU connection
- `PebbleTransportEmulator` - Managed emulator (QEMU + pypkjs)
- `PebbleTransportCloudPebble` - Cloud proxy connection

### 6. Device Interaction Commands (`pebble_tool/commands/`)
**Available Commands (38 total):**

**SDK Management:**
- `sdk install/uninstall/activate/list` - SDK version management

**Project Creation:**
- `new-project` - Create new app/watchface
- `new-package` - Create reusable library

**Build & Deploy:**
- `build` - Compile project
- `clean` - Clean build artifacts
- `install` - Install app to device/emulator

**Device Operations:**
- `logs` - View app logs
- `screenshot` - Capture screen
- `ping` - Test connectivity
- `data-logging` - Access sensor data
- `timeline` - Manage timeline pins

**Emulator Control:**
- `kill/wipe/status` - Emulator lifecycle
- `emu-accel/battery/compass/tap` - Simulate sensors
- `emu-control` - Web-based control interface

**Account:**
- `login/logout` - GitHub OAuth authentication

### 7. Utilities (`pebble_tool/util/`)
**Supporting Infrastructure:**
- `analytics.py` - Usage tracking (currently disabled)
- `browser.py` - Web browser control for config pages
- `config.py` - Persistent configuration storage
- `logs.py` - Log formatting and display
- `npm.py` - npm command wrapper
- `updates.py` - Check for tool updates

### 8. Template System (`pebble_tool/sdk/templates/`)
**Project Templates:**
- `app/` - C application templates
- `rocky/` - Rocky.js templates
- `lib/` - Library package templates
- `templates.json` - Template definitions

## Technology Stack

### Programming Languages
- **Primary:** Python 3.9-3.13
- **Target:** C (for Pebble apps), JavaScript (Rocky.js/PebbleKit JS)

### Core Dependencies
**Pebble-Specific:**
- `libpebble2>=0.0.29` - Pebble communication protocol
- `pypkjs>=2.0.0` - JavaScript runtime for emulator

**External Tools/Dependencies:**
- **QEMU (qemu-pebble)** - Custom Pebble hardware emulator
- **ARM Toolchain** - arm-none-eabi-gcc cross-compiler
- **Node.js/npm** - For JavaScript dependencies

## Data Directories

**Linux:** `~/.pebble-sdk/`
**macOS:** `~/Library/Application Support/Pebble SDK/`

**Structure:**
```
~/.pebble-sdk/
├── SDKs/
│   ├── current -> 4.5/  (symlink)
│   └── 4.5/
│       ├── sdk-core/
│       ├── toolchain/
│       └── .venv/
├── oauth/               (authentication)
└── settings.json        (configuration)
```

## Architectural Patterns

1. **Plugin Architecture** - Self-registering commands via metaclasses
2. **Strategy Pattern** - Multiple transport implementations
3. **Factory Pattern** - Project type detection and instantiation
4. **Singleton Pattern** - Shared SDK manager, analytics tracker
5. **Template Method** - Base command classes with hooks
6. **Observer Pattern** - Progress callbacks for installations

## Key Architectural Decisions

1. **Python 3 Migration** - Modernized from Python 2
2. **Modular SDK Management** - Separate download vs bundled SDK
3. **Multi-Transport Support** - Flexible device/emulator connectivity
4. **Two-Process Emulator** - QEMU + pypkjs for complete emulation
5. **OAuth via GitHub** - Simplified authentication flow
6. **Per-SDK Isolation** - Virtual environments prevent conflicts
