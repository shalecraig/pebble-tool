# Build System Architecture

The Pebble build system orchestrates compilation of C/JavaScript code for multiple ARM-based platforms using WAF and cross-compilation tools.

## Overview

**Core Components:**
- **WAF** - Python-based build system (from SDK)
- **ARM Toolchain** - arm-none-eabi-gcc cross-compiler
- **npm** - JavaScript dependency management
- **Package Creation** - .pbw bundle generation

## Build Command Flow

**File:** `pebble_tool/commands/sdk/project/build.py`

### BuildCommand Entry Point

**Function:** `BuildCommand.__call__()` (build.py:19-48)

```python
def __call__(self, args):
    super(BuildCommand, self).__call__(args)

    # Check for npm dependencies
    if len(self.project.dependencies) > 0:
        npm.invoke_npm(["install"])
        npm.invoke_npm(["dedupe"])

    # Prepare waf arguments
    waf = list(args.args)

    # Setup debug environment
    extra_env = {}
    if args.debug:
        extra_env['CFLAGS'] = '-O0'

    # Execute waf
    self._waf("configure", extra_env=extra_env, args=waf)
    self._waf("build", args=waf)
```

**Key Features:**
- `--debug` flag adds `-O0` (disables optimization)
- npm dependencies installed automatically
- Collects analytics (build time, source line counts)

## WAF Integration

**File:** `pebble_tool/commands/sdk/project/__init__.py`

### WAF Invocation

**Function:** `_waf()` (project/__init__.py:23-42)

```python
def _waf(self, command, extra_env=None, args=None):
    waf_path = os.path.join(sdk_path, 'pebble', 'waf')
    venv = os.path.join(sdk_path, '..', '.venv')

    # Environment setup
    env = os.environ.copy()
    env['PYTHONHOME'] = venv
    env['PYTHONPATH'] = ':'.join(sys.path)
    env['NODE_PATH'] = os.path.join(sdk_path, '..', 'node_modules')
    env['NOCLIMB'] = "1"  # Prevents waf from climbing parent dirs

    if extra_env:
        env.update(extra_env)

    # Execute waf
    subprocess.check_call(
        [os.path.join(venv, 'bin', 'python'), waf_path, command] + args,
        env=env
    )
```

**Environment Variables:**
- `PYTHONHOME` - Points to SDK venv
- `PYTHONPATH` - sys.path from current Python
- `NODE_PATH` - SDK node_modules directory
- `NOCLIMB` - Prevents directory traversal
- `CFLAGS` - Compiler flags (e.g., `-O0` for debug)

## WAF Configuration

**Template:** `pebble_tool/sdk/templates/app/wscript`

### Three Build Phases

1. **options(ctx)** - Load pebble_sdk tools
2. **configure(ctx)** - Configure build for each target platform
3. **build(ctx)** - Execute multi-platform build

### Build Phase Implementation

```python
def build(ctx):
    for platform in ctx.env.TARGET_PLATFORMS:
        ctx.env = ctx.all_envs[platform]
        ctx.set_group(ctx.env.PLATFORM_NAME)

        # Build app binary
        app_elf = f'{ctx.env.BUILD_DIR}/pebble-app.elf'
        ctx.pbl_build(source='src/c/**/*.c', target=app_elf, bin_type='app')

        # Optional: Build background worker
        if os.path.exists('worker_src'):
            worker_elf = f'{ctx.env.BUILD_DIR}/pebble-worker.elf'
            ctx.pbl_build(source='worker_src/c/**/*.c',
                         target=worker_elf, bin_type='worker')
```

## ARM Cross-Compiler Integration

### Toolchain Path Setup

**File:** `pebble_tool/sdk/__init__.py:37-42`

```python
def add_tools_to_path():
    os.environ['PATH'] = (
        f"{sdk_path}/toolchain/arm-none-eabi/bin:"
        f"{os.environ['PATH']}"
    )
```

### ARM Toolchain Tools

**Compilation:**
- `arm-none-eabi-gcc` - C compiler

**Analysis:**
- `arm-none-eabi-objdump` - Binary analysis
- `arm-none-eabi-readelf` - Symbol reading
- `arm-none-eabi-addr2line` - Stack trace decoding

**Debugging:**
- `arm-none-eabi-gdb` - GDB debugger

### Compiler Flags

**Normal Build:**
- Default optimization (likely -Os or -O2, set in SDK's waf tools)
- Architecture flags based on platform:
  - Cortex-M3 for aplite
  - Cortex-M4 for basalt/chalk/diorite/emery/flint

**Debug Build:**
```python
if args.debug:
    extra_env['CFLAGS'] = '-O0'  # No optimization
```

## Multi-Platform Build Handling

### Platform Configuration

**Supported Platforms:** aplite, basalt, chalk, diorite, emery, flint

**Defined in:** `pebble_tool/sdk/project.py:107, 163`

```python
self.target_platforms = appinfo.get('targetPlatforms', get_pebble_platforms())
```

### Build Process Per Platform

**wscript Implementation (lines 32-47):**

```python
for platform in ctx.env.TARGET_PLATFORMS:
    ctx.env = ctx.all_envs[platform]  # Switch environment
    ctx.set_group(ctx.env.PLATFORM_NAME)

    # Build for this platform
    app_elf = f'{ctx.env.BUILD_DIR}/pebble-app.elf'
    ctx.pbl_build(source='src/c/**/*.c', target=app_elf, bin_type='app')
```

### Output Structure

```
build/
├── aplite/
│   ├── pebble-app.elf
│   └── pebble-worker.elf (optional)
├── basalt/
│   ├── pebble-app.elf
│   └── pebble-worker.elf (optional)
├── chalk/
│   ├── pebble-app.elf
│   └── pebble-worker.elf (optional)
├── myapp.pbw (final package)
├── pebble-js-app.js (bundled JS)
└── pebble-js-app.js.map (source map)
```

## npm Integration

**File:** `pebble_tool/util/npm.py`

### npm Commands

**Installation:**
```python
if len(self.project.dependencies) > 0:
    npm.invoke_npm(["install"])    # Install dependencies
    npm.invoke_npm(["dedupe"])     # Deduplicate packages
```

### npm.py Implementation

**Functions:**
- `check_npm()` (lines 12-19) - Validates npm ≥ 3.0.0
- `invoke_npm()` (lines 22-24) - Executes npm commands
- `sanity_check()` (lines 27-35) - Detects nested dependency conflicts

### JavaScript Sources

**Included in bundle (wscript:51-54):**

```python
ctx.pbl_bundle(
    js=ctx.path.ant_glob([
        'src/pkjs/**/*.js',      # PebbleKit JS files
        'src/pkjs/**/*.json',    # Configuration
        'src/common/**/*.js'     # Shared JS code
    ]),
    js_entry_file='src/pkjs/index.js'
)
```

## Package Creation (.pbw)

### Bundle Structure

**The .pbw file is a ZIP archive containing:**

1. `manifest.json` - App metadata (UUID, version, platforms)
2. `{platform}/pebble-app.bin` - Compiled app for each platform
3. `{platform}/pebble-worker.bin` - Background worker (if exists)
4. `pebble-js-app.js` - Bundled JavaScript code
5. `appinfo.json` - Legacy app information
6. `resources/` - Images, fonts, other assets

### Bundle Creation (wscript:49-54)

```python
ctx.set_group('bundle')
ctx.pbl_bundle(
    binaries=[
        {'platform': 'basalt', 'app_elf': '...', 'worker_elf': '...'},
        # ... for each platform
    ],
    js=ctx.path.ant_glob(['src/pkjs/**/*.js', ...]),
    js_entry_file='src/pkjs/index.js'
)
```

### Installation Path

**File:** `pebble_tool/commands/install.py:77`

```python
self.pbw = pbw or f'build/{os.path.basename(os.getcwd())}.pbw'
# Example: build/myapp.pbw
```

## Binary Size Analysis

**File:** `pebble_tool/commands/sdk/project/analyse_size.py`

### AnalyseSizeCommand

**Function:** `__call__()` (analyse_size.py:14-51)

```python
def __call__(self, args):
    # Add ARM tools to path
    self.add_arm_tools_to_path()

    # Import SDK's binutils module
    sys.path.append(os.path.join(sdk_path(), 'pebble', 'common', 'tools'))
    import binutils

    # Analyze each platform
    for platform in project.target_platforms:
        elf_path = f'build/{platform}/pebble-app.elf'
        sections = binutils.analyze_elf(elf_path, 'bdt', use_fast_nm=True)

        # Print section breakdown
        for s in sections.values():
            s.pprint(args.summary, args.verbose)
```

### Output Sections

- `.text` - Code section (executable instructions)
- `.data` - Initialized data
- `.bss` - Uninitialized data
- Per-symbol breakdown (when verbose)

### Usage Examples

```bash
pebble analyze-size                    # All platforms
pebble analyze-size --summary          # Summary only
pebble analyze-size --verbose          # Per-symbol breakdown
pebble analyze-size build/basalt/pebble-app.elf  # Specific ELF
```

## Debug Support (GDB)

**File:** `pebble_tool/commands/sdk/project/debug.py`

### GDB Integration Flow

**Function:** `GdbCommand.__call__()` (debug.py:22-167)

**Steps:**
1. Verify emulator connection
2. Ensure correct app is running (auto-launch/install if needed)
3. Setup GDB environment (platform, SDK version, GDB port)
4. Load debugging symbols:
   - Firmware ELF: `sdk/{version}/pebble/{platform}/qemu/{platform}_sdk_debug.elf`
   - App ELF: `build/{platform}/pebble-app.elf`
   - Worker ELF: `build/{platform}/pebble-worker.elf` (optional)
5. Calculate symbol offsets (using arm-none-eabi-objdump)
6. Generate GDB commands
7. Launch arm-none-eabi-gdb

### Symbol Loading

**Function:** `_get_symbol_command()` (debug.py:56-67)

```python
def _get_symbol_command(self, elf, base_addr_expr):
    offsets = self._find_app_section_offsets(elf)

    command = [
        'add-symbol-file', f'"{elf}"',
        f'{base_addr_expr}+{offsets[".text"]:#x}'
    ]

    # Add all other sections (.data, .bss, etc)
    for section, offset in offsets.items():
        if section != '.text':
            command.append(f'-s {section} {base_addr_expr}+{offset:#x}')
```

### Crash Handling

**File:** `pebble_tool/util/logs.py:147-195`

The log printer automatically decodes crashes:

1. Detect crash pattern: `App fault! {UUID} PC: {addr} LR: {addr}`
2. Match UUID to current project
3. Find ELF file: `build/{platform}/pebble-{app|worker}.elf`
4. Decode addresses using `arm-none-eabi-addr2line`
5. Display file:line information

## Complete Build Flow

```
User runs: pebble build

1. BuildCommand invoked
   ├── Check npm dependencies → npm install && npm dedupe
   │
2. Setup environment
   ├── Load PebbleProject (parse package.json/appinfo.json)
   ├── Add ARM toolchain to PATH
   └── Fix Python 3 environment
   │
3. Execute waf configure
   ├── Load pebble_sdk waf tool
   ├── Create build environments for each target platform
   │   └── Set platform-specific: compiler, flags, paths
   │
4. Execute waf build
   ├── For each platform in TARGET_PLATFORMS:
   │   ├── Switch to platform environment
   │   ├── Compile C sources with arm-none-eabi-gcc
   │   │   ├── App: src/c/**/*.c → build/{platform}/pebble-app.elf
   │   │   └── Worker: worker_src/c/**/*.c → build/{platform}/pebble-worker.elf
   │   │
   ├── Bundle JavaScript (if exists)
   │   ├── Process src/pkjs/**/*.js
   │   └── Create pebble-js-app.js + source map
   │   │
   └── Create .pbw package
       ├── Collect all platform binaries
       ├── Create manifest.json
       ├── Add JavaScript bundle
       ├── Add resources
       └── ZIP → build/{projectname}.pbw
   │
5. Post analytics
   └── Track build time, success/failure, line counts
```

## Command Examples

```bash
# Build project
pebble build

# Build with debug symbols (no optimization)
pebble build --debug

# Clean build artifacts
pebble clean

# Analyze binary size
pebble analyze-size

# Debug with GDB
pebble gdb

# Pass custom arguments to waf
pebble build -- --verbose
```

## Key Features

- **Multi-platform** - Builds for all target platforms in single command
- **Cross-compilation** - ARM Cortex-M3/M4 from x86/x64 hosts
- **JavaScript bundling** - Integrates npm dependencies
- **Debug support** - GDB integration with symbol loading
- **Size analysis** - Detailed memory usage breakdown
- **Crash decoding** - Automatic symbolication of crashes
