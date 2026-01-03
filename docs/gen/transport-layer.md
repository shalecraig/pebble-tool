# Communication & Transport Layer

The transport layer provides flexible connectivity to Pebble devices and emulators through multiple connection types.

## Overview

The pebble-tool implements **5 different transport types**, each implemented as a configuration wrapper around libpebble2 transport classes.

## Transport Architecture

**Base Pattern:**
- Self-registering via metaclass
- Configuration wrappers around libpebble2 transports
- Automatic selection based on CLI args or environment variables
- Fallback hierarchy for automatic detection

## Transport Implementations

### 1. Serial Transport

**File:** `pebble_tool/commands/base.py:180-188`

```python
class PebbleTransportSerial(PebbleTransportConfiguration):
    transport_class = SerialTransport  # from libpebble2
    env_var = 'PEBBLE_BT_SERIAL'
    name = 'serial'
```

**Purpose:** Direct serial connection to Pebble watch
**Usage:** `--serial /dev/ttyUSB0` or `PEBBLE_BT_SERIAL=/dev/ttyUSB0`
**Connection:** Path to serial device

### 2. Phone Transport (WebSocket)

**File:** `pebble_tool/commands/base.py:190-211`

```python
class PebbleTransportPhone(PebbleTransportConfiguration):
    transport_class = WebsocketTransport
    name = 'phone'

    @classmethod
    def _connect_args(cls, args):
        phone, = super(PebbleTransportPhone, cls)._connect_args(args)
        parts = phone.split(':')
        ip = parts[0]
        port = int(parts[1]) if len(parts) == 2 else 9000
        return (f"ws://{ip}:{port}/",)
```

**Purpose:** Connect via phone's developer connection
**Usage:** `--phone 192.168.1.100` or `--phone 192.168.1.100:9000`
**Default Port:** 9000
**Protocol:** WebSocket to phone app

### 3. QEMU Transport

**File:** `pebble_tool/commands/base.py:213-234`

```python
class PebbleTransportQemu(PebbleTransportConfiguration):
    transport_class = QemuTransport
    name = 'qemu'

    @classmethod
    def _connect_args(cls, args):
        phone, = super(PebbleTransportQemu, cls)._connect_args(args)
        parts = phone.split(':')
        ip = parts[0]
        port = int(parts[1]) if len(parts) == 2 else 12344
        return (ip, port,)
```

**Purpose:** Direct connection to standalone QEMU instance
**Usage:** `--qemu localhost:12344`
**Default:** localhost:12344
**Protocol:** Raw TCP connection

### 4. CloudPebble Transport

**File:** `pebble_tool/sdk/cloudpebble.py`

```python
class CloudPebbleTransport(WebsocketTransport):
    def __init__(self):
        super(CloudPebbleTransport, self).__init__(None)
        self._phone_connected = False

    def connect(self):
        account = get_default_account()
        if not account.is_logged_in:
            raise ToolError("You must be logged in to use CloudPebble connection.")

        self.ws = websocket.create_connection(CP_TRANSPORT_HOST)
        self._authenticate()
        self._wait_for_phone()
        self._phone_connected = True
```

**Proxy Host:** `wss://cloudpebble-proxy.repebble.com/tool`

**Authentication Flow:**
1. Send `WebSocketProxyAuthenticationRequest` with OAuth token
2. Wait for `WebSocketProxyAuthenticationResponse`
3. Validate success status
4. Wait for `WebSocketProxyConnectionStatusUpdate` (Connected)

**Usage:** `--cloudpebble`
**Requires:** GitHub OAuth login (`pebble login`)

### 5. Emulator Transport (Managed)

**File:** `pebble_tool/sdk/emulator.py:95-493`

```python
class ManagedEmulatorTransport(WebsocketTransport):
    def __init__(self, platform, version=None, vnc_enabled=False):
        self.platform = platform
        self.version = version
        self.vnc_enabled = vnc_enabled
        self._find_ports()
        super().__init__(f'ws://localhost:{self.pypkjs_port}/')
```

**Process Management:**
- Spawns QEMU process (runs actual watch firmware)
- Spawns pypkjs process (JavaScript phone simulator)
- Spawns websockify process (VNC web proxy, optional)

**State Persistence:** `/tmp/pb-emulator.json`

**Usage:** `--emulator basalt` or auto-detected if emulator running

## Transport Selection Flow

**File:** `pebble_tool/commands/base.py:108-125`

```python
def _connect(self, args):
    self._set_debugging(args.v)

    # Iterate through valid connection handlers
    for handler_impl in self.valid_connection_handlers():
        if handler_impl.is_selected(args):
            break
    else:
        # Fallback to running emulator if available
        if PebbleTransportEmulator.get_running_emulators():
            handler_impl = PebbleTransportEmulator
        else:
            raise ToolError("No pebble connection specified.")

    transport = handler_impl.get_transport(args)
    connection = PebbleConnection(transport, **self._get_debug_args())
    connection.connect()
    connection.run_async()
    handler_impl.post_connect(connection)
    return connection
```

**Selection Priority:**
1. Explicitly specified transport via CLI args
2. Environment variable (e.g., `PEBBLE_PHONE`, `PEBBLE_EMULATOR`)
3. Auto-detect running emulator
4. Error if nothing found

## Self-Registration Pattern

**File:** `pebble_tool/commands/base.py:136-140`

```python
class SelfRegisteringTransportConfiguration(type):
    def __init__(cls, name, bases, dct):
        if hasattr(cls, 'name') and cls.name is not None:
            PebbleCommand.register_connection_handler(cls)
            super().__init__(name, bases, dct)
```

All transport configurations automatically register via metaclass.

## libpebble2 Integration

### PebbleConnection Wrapper

**Creation:**
```python
connection = PebbleConnection(transport, **self._get_debug_args())
connection.connect()
connection.run_async()
handler_impl.post_connect(connection)
```

**Debug Arguments:**
```python
def _get_debug_args(self):
    args = {}
    if self._verbosity >= 3:
        args['log_packet_level'] = logging.DEBUG
    if self._verbosity >= 4:
        args['log_protocol_level'] = logging.DEBUG
    return args
```

### Protocol Messages

**System Messages:**
- `TimeMessage`, `SetUTC` - Time synchronization
- `PingPong`, `Ping`, `Pong` - Connectivity testing

**App Messages:**
- `AppRunState`, `AppRunStateRequest`, `AppRunStateStart` - App lifecycle
- `AppLogMessage`, `AppLogShippingControl` - Log streaming

**WebSocket-Specific:**
- `WebSocketInstallBundle`, `WebSocketInstallStatus` - App installation
- `WebSocketTimelinePin`, `InsertPin`, `DeletePin` - Timeline management
- `WebSocketPhoneAppLog` - Phone-side JavaScript logs

**QEMU Protocol:**
- `QemuAccel`, `QemuBattery`, `QemuCompass`, `QemuTap` - Sensor simulation

### Post-Connection Setup

**File:** `pebble_tool/commands/base.py:288-295`

```python
@classmethod
def post_connect(cls, connection):
    # Set timezone for firmware 3+
    if connection.firmware_version.major >= 3:
        ts = time.time()
        tz_offset = -time.altzone if time.localtime(ts).tm_isdst else -time.timezone
        tz_offset_minutes = tz_offset // 60
        tz_name = f"UTC{tz_offset_minutes / 60:+d}"
        connection.send_packet(TimeMessage(message=SetUTC(...)))
```

## Message Passing

### Sending Messages

**Direct Packet Send:**
```python
connection.send_packet(packet)
```

**With Target (WebSocket):**
```python
connection.send_packet(packet, target=MessageTargetPhone())
```

**Send and Wait:**
```python
response = connection.send_and_read(request_packet, ResponseType, timeout=5)
```

**Example - Ping:**
```python
cookie = random.randint(1, 0xFFFFFFFF)
pong = self.pebble.send_and_read(
    PingPong(cookie=cookie, message=Ping(idle=False)),
    PingPong
)
```

**Example - Timeline Pin:**
```python
self.pebble.transport.send_packet(
    WebSocketTimelinePin(data=InsertPin(json=json.dumps(pin))),
    target=MessageTargetPhone()
)
result = self.pebble.read_transport_message(
    MessageTargetPhone,
    WebSocketTimelineResponse
).status
```

### Receiving Messages

**Endpoint Registration:**
```python
self.handles.append(
    pebble.register_endpoint(AppLogMessage, self.handle_watch_log)
)
self.handles.append(
    pebble.register_transport_endpoint(
        MessageTargetPhone,
        WebSocketPhoneAppLog,
        self.handle_phone_log
    )
)
```

**Handler Callbacks:**
```python
def handle_watch_log(self, packet):
    assert isinstance(packet, AppLogMessage)
    print(f"[{datetime.now():%H:%M:%S}] {packet.filename}:{packet.line_number}> {packet.message}")
```

## App Installation

**File:** `pebble_tool/commands/install.py`

### Installation Entry Point

```python
class ToolAppInstaller:
    def install(self):
        if isinstance(self.pebble.transport, WebsocketTransport):
            self._install_via_websocket(self.pebble, self.pbw)
        else:
            self._install_via_serial(self.pebble, self.pbw)
```

### Serial Installation

```python
def _install_via_serial(self, pebble, pbw):
    installer = AppInstaller(pebble, pbw)  # libpebble2 service
    self.progress_bar.maxval = installer.total_size
    self.progress_bar.start()
    installer.register_handler("progress", self._handle_pp_progress)
    installer.install()
    self.progress_bar.finish()
```

**Process:**
- Chunks PBW file
- Sends via PutBytes protocol
- Progress callbacks for UI

### WebSocket Installation

```python
def _install_via_websocket(self, pebble, pbw):
    with open(pbw, 'rb') as f:
        print("Installing app...")
        pebble.transport.send_packet(
            WebSocketInstallBundle(pbw=f.read()),
            target=MessageTargetPhone()
        )
        result = pebble.read_transport_message(
            MessageTargetPhone,
            WebSocketInstallStatus,
            timeout=300
        )
        if result.status != WebSocketInstallStatus.StatusCode.Success:
            raise ToolError("App install failed.")
```

**Differences:**
- Entire PBW sent as single message
- Phone/pypkjs handles unpacking
- 5-minute timeout for large apps
- Single response confirms success

### Fresh Install Feature

```python
def __call__(self, args):
    if args.fresh:
        self._kill_emulators()  # Kill all emulators first
    super(InstallCommand, self).__call__(args)
```

**Usage:** `pebble install --emulator basalt --fresh`

## Log Streaming

**File:** `pebble_tool/util/logs.py`

### Log Printer Initialization

```python
class PebbleLogPrinter:
    def __init__(self, pebble, force_colour=None):
        # Enable log shipping
        pebble.send_packet(AppLogShippingControl(enable=True))

        # Register handlers
        self.handles = []
        self.handles.append(
            pebble.register_endpoint(AppLogMessage, self.handle_watch_log)
        )
        self.handles.append(
            pebble.register_transport_endpoint(
                MessageTargetPhone,
                WebSocketPhoneAppLog,
                self.handle_phone_log
            )
        )
```

### Watch Log Handler

```python
def handle_watch_log(self, packet):
    self._print(packet, f"[{datetime.now():%H:%M:%S}] {packet.filename}:{packet.line_number}> {packet.message}")
    self._maybe_handle_crash(packet)
```

### JavaScript Log Handler

```python
def handle_phone_log(self, packet):
    logstr = self._sourcemap_translate_js_log(packet.payload)
    self._print(packet, f"[{datetime.now():%H:%M:%S}] pkjs> {logstr}")
```

**JavaScript Sourcemap Support:**
- Loads `build/pebble-js-app.js.map`
- Translates minified locations to original source
- Regex replacement of `pebble-js-app.js:line:col` references

### Crash Detection

```python
def _maybe_handle_crash(self, packet):
    result = re.search(r"(App|Worker) fault! {([0-9a-f-]{36})} PC: (\S+) LR: (\S+)", packet.message)
    if result:
        crash_uuid = uuid.UUID(result.group(2))
        # ... verify it's our app ...
        self._handle_crash(packet, result.group(1).lower(), result.group(3), result.group(4))
```

Automatically symbolicates crash addresses using `arm-none-eabi-addr2line`.

### Color Coding

```python
colour_scheme = OrderedDict([
    (255, Fore.CYAN),        # LOG_LEVEL_DEBUG_VERBOSE
    (200, Fore.MAGENTA),     # LOG_LEVEL_DEBUG
    (100, ""),               # LOG_LEVEL_INFO
    (50, Style.BRIGHT + Fore.RED),  # LOG_LEVEL_WARNING
    (1, Back.RED + Style.BRIGHT + Fore.WHITE),  # LOG_LEVEL_ERROR
    (0, None)                # LOG_LEVEL_ALWAYS
])
```

## Screenshot Capture

**File:** `pebble_tool/commands/screenshot.py`

### Capture Flow

```python
def __call__(self, args):
    screenshot = Screenshot(self.pebble)  # libpebble2 service
    screenshot.register_handler("progress", self._handle_progress)

    self.progress_bar.start()
    image = screenshot.grab_image()

    if not args.no_correction:
        image = self._correct_colours(image)  # Fix Pebble color palette
    image = self._roundify(image)  # Add alpha, round corners for Chalk
    if args.scale > 1:
        image = self._scale_image(image, args.scale)

    png.from_array(image, mode='RGBA;8').save(filename)
```

**Processing:**
- Color correction (64-color palette mapping)
- Roundification (circular display for Chalk)
- Scaling (nearest-neighbor interpolation)

## Connection Examples

```bash
# Serial connection
pebble logs --serial /dev/ttyUSB0

# Phone connection
pebble install --phone 192.168.1.100

# QEMU direct
pebble install --qemu localhost:12344

# CloudPebble proxy
pebble login
pebble logs --cloudpebble

# Emulator (auto-detected)
pebble install --emulator basalt
pebble logs  # Auto-connects to running emulator

# Emulator with VNC
pebble install --emulator basalt --vnc
```

## Summary

The transport layer provides:
- **Flexible Connectivity** - 5 transport types for different scenarios
- **Auto-Detection** - Smart fallback to running emulators
- **Protocol Abstraction** - Unified interface via libpebble2
- **Rich Features** - Installation, logging, screenshots, debugging
- **Dual Installation** - Optimized for serial vs WebSocket
- **Debug Support** - Packet/protocol logging, crash symbolication
