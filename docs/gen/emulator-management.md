# Emulator Management System

**File:** `pebble_tool/sdk/emulator.py`

The emulator management system handles QEMU-based Pebble smartwatch emulation with a sophisticated multi-process architecture.

## Architecture Overview

The emulator consists of **three coordinated processes**:
1. **QEMU** - Hardware/firmware emulation
2. **pypkjs** - JavaScript runtime (PebbleKit JS)
3. **websockify** - VNC proxy (optional, for web-based display)

## ManagedEmulatorTransport

**Class:** `ManagedEmulatorTransport(WebsocketTransport)`

### Initialization Flow

**Function:** `__init__()` (emulator.py:96-102)

```python
def __init__(self, platform, version=None, vnc_enabled=False):
    self.platform = platform  # aplite, basalt, chalk, etc.
    self.version = version
    self.vnc_enabled = vnc_enabled
    self._find_ports()
    super().__init__(f'ws://localhost:{self.pypkjs_port}/')
```

## Port Management

### Dynamic Port Allocation

**Function:** `_choose_port()` (emulator.py:448-453)

```python
@classmethod
def _choose_port(cls):
    sock = socket.socket()
    sock.bind(('', 0))  # OS assigns random available port
    port = sock.getsockname()[1]
    sock.close()
    return port
```

### Port Discovery and Reuse

**Function:** `_find_ports()` (emulator.py:116-195)

**Process:**
1. Read `/tmp/pb-emulator.json` for existing processes
2. Verify QEMU process is alive
3. Check VNC state matches current request
4. Validate pypkjs dependency on QEMU
5. Allocate new ports if needed

**Port Types:**
- `qemu_port` - pypkjs communication (Pebble protocol)
- `qemu_serial_port` - Firmware boot logs
- `qemu_gdb_port` - GDB debugging
- `pypkjs_port` - WebSocket server
- `qemu_monitor_port` - QEMU monitor (not yet implemented)

## QEMU Process Management

### QEMU Command Construction

**Function:** `_spawn_qemu()` (emulator.py:248-329)

**Base Command:**
```python
command = [
    qemu_bin,  # Default: 'qemu-pebble' or $PEBBLE_QEMU_PATH
    "-rtc", "base=localtime",
    "-serial", "null",
    "-serial", f"tcp::{qemu_port},server,nowait",     # Protocol port
    "-serial", f"tcp::{qemu_serial_port},server",      # Serial console
    "-pflash", qemu_micro_flash,                       # Firmware flash
    "-gdb", f"tcp::{qemu_gdb_port},server,nowait",    # GDB debugging
]
```

### Platform-Specific Configurations

| Platform | Machine Type | CPU | Flash Type | Storage Arg |
|----------|--------------|-----|------------|-------------|
| aplite | pebble-bb2 | cortex-m3 | MTD block | -mtdblock |
| basalt | pebble-snowy-bb | cortex-m4 | Parallel flash | -pflash |
| chalk | pebble-s4-bb | cortex-m4 | Parallel flash | -pflash |
| diorite | pebble-silk-bb | cortex-m4 | MTD block | -mtdblock |
| emery | pebble-robert-bb / pebble-snowy-emery-bb | cortex-m4 | Parallel flash | -pflash |
| flint | pebble-silk-bb | cortex-m4 | MTD block | -mtdblock |

**Note:** Emery uses `pebble-snowy-emery-bb` for SDK >= 4.9

### VNC Integration

**Configuration:**
```python
if self.vnc_enabled:
    command.extend(["-L", sdk_path/toolchain/lib/pc-bios])
    command.extend(["-vnc", ":1"])
```

**Constraint:** Only ONE VNC instance can exist (display `:1` is unique)

### Boot Verification

**Function:** `_wait_for_qemu()` (emulator.py:331-357)

**Process:**
1. Connect to serial port (qemu_serial_port)
2. Wait up to 60 seconds
3. Look for boot messages: `<SDK Home>`, `<Launcher>`, or `Ready for communication`
4. Post analytics event on success/failure

## pypkjs Process Management

### pypkjs Command Construction

**Function:** `_spawn_pypkjs()` (emulator.py:412-439)

```python
command = [
    sys.executable, "-m", "pypkjs",
    "--qemu", f"localhost:{qemu_port}",
    "--port", str(pypkjs_port),
    "--persist", get_sdk_persist_dir(platform, version),
    "--layout", sdk_path/pebble/platform/qemu/layouts.json,
    '--debug',
    '--oauth', account.bearer_token  # If logged in
]
```

### QEMU ↔ pypkjs Relationship

```
┌─────────────────┐      WebSocket      ┌──────────────────┐
│  pebble CLI /   │ ───────────────────> │     pypkjs       │
│  Browser Client │ <─────────────────── │  (WebSocket srv) │
└─────────────────┘                      └──────────────────┘
                                                  │
                                                  │ TCP (qemu_port)
                                                  │ Pebble Protocol
                                                  ↓
                                         ┌──────────────────┐
                                         │       QEMU       │
                                         │  (Firmware emu)  │
                                         └──────────────────┘
```

**Key Dependencies:**
- pypkjs CANNOT run without QEMU
- pypkjs acts as bridge between WebSocket clients and QEMU's TCP protocol
- When QEMU dies, pypkjs is killed

## websockify (VNC Proxy)

### websockify Command Construction

**Function:** `_spawn_websockify()` (emulator.py:392-410)

```python
command = [
    sys.executable, "-m", "websockify",
    '--heartbeat=30',     # Keep-alive every 30s
    '6080',               # Fixed WebSocket port
    'localhost:5901'      # VNC server (QEMU display :1)
]
```

### VNC Architecture

```
┌──────────────┐   WebSocket   ┌─────────────┐   VNC Protocol   ┌──────────┐
│ Web Browser  │ ────:6080──> │ websockify  │ ────:5901────> │   QEMU   │
│ (noVNC, etc) │ <─────────── │   (proxy)   │ <────────────  │ (VNC :1) │
└──────────────┘               └─────────────┘                 └──────────┘
```

## Persistent Storage

### Storage Hierarchy

**Base Directory:**
- Linux: `~/.pebble-sdk/{version}/{platform}/`
- macOS: `~/Library/Application Support/Pebble SDK/{version}/{platform}/`

### Storage Contents

1. **SPI Flash Image**
   - Path: `~/.pebble-sdk/{version}/{platform}/qemu_spi_flash.bin`
   - Decompressed from SDK's `qemu_spi_flash.bin.bz2` on first run
   - Persists installed apps, settings, data storage
   - Reused across emulator restarts

2. **pypkjs Persistent Data**
   - JavaScript localStorage
   - IndexedDB
   - App configuration

3. **Emulator State** (`/tmp/pb-emulator.json`)
   ```json
   {
     "platform_name": {
       "sdk_version": {
         "qemu": {"pid": int, "port": int, "serial": int, "gdb": int, "vnc": bool},
         "pypkjs": {"pid": int, "port": int},
         "websockify": {"pid": int},
         "version": "sdk_version"
       }
     }
   }
   ```

## Platform Support

### Supported Platforms

**Platforms:** aplite, basalt, chalk, diorite, emery, flint

| Platform | Display | Screen | Color | Release |
|----------|---------|--------|-------|---------|
| aplite | 144×168 | B&W | No | Pebble Classic |
| basalt | 144×168 | Color | 64-color | Pebble Time |
| chalk | 180×180 | Color (round) | 64-color | Pebble Time Round |
| diorite | 144×168 | B&W | No | Pebble 2 |
| emery | 200×228 | Color | 64-color | Pebble Time 2 |
| flint | 144×168 | B&W | No | Pebble 2 |

## Process Lifecycle

### Spawn Flow

**Function:** `_spawn_processes()` (emulator.py:196-223)

```python
def _spawn_processes(self):
    # 1. Determine SDK version
    if self.version is None:
        self.version = sdk_manager.get_current_sdk()

    # 2. Spawn QEMU (or reuse existing)
    if self.qemu_pid is None:
        self._spawn_qemu()

    # 3. Spawn pypkjs (or reuse existing)
    if self.pypkjs_pid is None:
        self._spawn_pypkjs()

    # 4. Spawn websockify if VNC enabled
    if self.vnc_enabled and self.websockify_pid is None:
        self._spawn_websockify()

    # 5. Save state to /tmp/pb-emulator.json
    self._save_state()
```

### Process Health Monitoring

**Function:** `_is_pid_running(pid)` (emulator.py:456-465)

```python
@classmethod
def _is_pid_running(cls, pid):
    try:
        os.kill(pid, 0)  # Signal 0 checks if process exists
    except OSError as e:
        if e.errno == 3:
            return False
    return True
```

### Kill Flow

**File:** `pebble_tool/commands/sdk/emulator.py:20-51`

**Kill Command:**
```python
signal = signal.SIGKILL if args.force else signal.SIGTERM

for platform in emulator_info:
    for version in platform:
        self._kill_if_running(version['qemu']['pid'], signal)
        self._kill_if_running(version['pypkjs']['pid'], signal)
        if 'websockify' in version:
            self._kill_if_running(version['websockify']['pid'], signal)
```

**Wipe Command:**
- Deletes `~/.pebble-sdk/{version}/{platform}/` (current SDK only)
- `--everything` flag deletes entire `~/.pebble-sdk/` directory

## Sensor Simulation

### Command-Line Simulation

**File:** `pebble_tool/commands/emucontrol.py`

**Accelerometer:**
```python
# Predefined motions
'tilt-left': [QemuAccelSample(x=-500, y=0, z=-900), ...]
'gravity+x': [QemuAccelSample(x=1000, y=0, z=0)]

# Send to QEMU
send_data_to_qemu(transport, QemuAccel(samples=samples))
```

**Compass:**
```python
# Convert degrees to QEMU units
heading = math.ceil(degrees % 360 * 0x10000 / 360)
send_data_to_qemu(transport, QemuCompass(heading=..., calibrated=...))
```

**Battery:**
```python
QemuBattery(percent=0-100, charging=bool)
```

**Tap:**
```python
QemuTap(axis=X/Y/Z, direction=+1/-1)
```

### Interactive Browser Control

**Command:** `pebble emu-control`

**Data Flow:**
```
┌────────────────────┐   DeviceMotion/     ┌─────────────────┐
│  Mobile Browser    │   Orientation API   │  sensors.js     │
│  (Phone sensors)   │ ─────────────────> │  (Conversion)   │
└────────────────────┘                     └─────────────────┘
                                                   │
                                                   │ WebSocket
                                                   ↓
┌─────────────────┐                      ┌──────────────────┐
│      QEMU       │ <──── Protocol ───── │     pypkjs       │
│  (Firmware)     │       0xb [type]     │   (WebSocket)    │
└─────────────────┘                      └──────────────────┘
```

## Environment Variables

**`PEBBLE_QEMU_PATH`** - Override QEMU binary path
**`DYLD_FALLBACK_LIBRARY_PATH`** - Apple Silicon dylib loading
**`PEBBLE_EMULATOR`** - Specify platform
**`PEBBLE_EMULATOR_VERSION`** - Specify SDK version

## Command Examples

```bash
# Start emulator for basalt platform
pebble install --emulator basalt

# Check emulator status
pebble emu status

# Kill all emulators
pebble kill

# Kill with force
pebble kill --force

# Wipe emulator data
pebble wipe

# Simulate accelerometer
pebble emu-accel tilt-left

# Simulate compass
pebble emu-compass 90

# Simulate battery
pebble emu-battery 50 --charging

# Launch web-based control
pebble emu-control
```

## Summary

The emulator management system provides:
- **Process Reuse** - Avoids slow startup times
- **Clean Lifecycle** - Prevents zombie processes
- **Multi-Platform** - Six Pebble hardware variants
- **Persistent State** - Apps survive emulator restart
- **Rich Simulation** - Sensors, battery, connectivity
- **Debug Support** - GDB integration, VNC display
