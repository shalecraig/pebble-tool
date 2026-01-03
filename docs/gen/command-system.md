# Command System Architecture

The Pebble Tool uses an elegant metaclass-based plugin architecture for command registration and routing.

## Overview

**Key Pattern:** Commands self-register simply by inheriting from `BaseCommand` and setting a `command` attribute.

**File:** `pebble_tool/commands/base.py`

## Metaclass-Based Self-Registration

### The Metaclass

```python
_CommandRegistry = []  # Global registry list

class SelfRegisteringCommand(type):
    def __init__(cls, name, bases, dct):
        if hasattr(cls, 'command') and cls.command is not None:
            _CommandRegistry.append(cls)  # Auto-registration!
        super(SelfRegisteringCommand, cls).__init__(name, bases, dct)
```

**How It Works:**
1. `SelfRegisteringCommand` is a metaclass (inherits from `type`)
2. When a class is defined using this metaclass, `__init__` runs during class creation
3. If the class has a `command` attribute that's not `None`, it's added to the registry
4. No manual registration needed!

### BaseCommand Integration

```python
class BaseCommand(with_metaclass(SelfRegisteringCommand)):
    command = None  # If None, won't be registered
    has_subcommands = False
```

**Usage:**
```python
class PingCommand(BaseCommand):
    command = 'ping'  # Automatically registers!

    def __call__(self, args):
        # Command implementation
        pass
```

## Command Registration Flow

### Module Import

**File:** `pebble_tool/__init__.py:27-34`

```python
from .commands.sdk import manage
from .commands.sdk.project import build
from .commands.base import register_children
from .commands import (install, logs, screenshot, timeline, emucontrol,
                      ping, account, repl, transcription_server, data_logging)
```

**Process:**
1. Importing modules causes class definitions to execute
2. Class definitions trigger metaclass `__init__`
3. Commands auto-register to `_CommandRegistry`

### Discovery and Registration

```python
def register_children(parser):
    subparsers = parser.add_subparsers(title="command")
    for command in _CommandRegistry:
        command.add_parser(subparsers)
```

## Command Hierarchy

```
SelfRegisteringCommand (metaclass)
    │
    └─> BaseCommand (abstract base)
            │
            ├─> PebbleCommand (device connection required)
            │      │
            │      ├─> PingCommand
            │      ├─> InstallCommand
            │      ├─> LogsCommand
            │      ├─> ScreenshotCommand
            │      └─> ... (emulator commands)
            │
            └─> SDKCommand (SDK operations)
                   │
                   ├─> NewProjectCommand
                   ├─> KillCommand
                   ├─> SDKManager (has subcommands)
                   │
                   └─> SDKProjectCommand (project-specific)
                          │
                          ├─> BuildCommand
                          ├─> CleanCommand
                          ├─> PackageManager
                          └─> AnalyseSizeCommand
```

## BaseCommand

**File:** `pebble_tool/commands/base.py:33-70`

### Key Methods

**1. add_parser() - Argparse Setup**
```python
@classmethod
def add_parser(cls, parser):
    parser = parser.add_parser(
        cls.command,
        parents=cls._shared_parser(),
        help=cls.__doc__,
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.set_defaults(func=lambda x: cls()(x))  # Routes to __call__
    return parser
```

**2. _shared_parser() - Common Arguments**
```python
@classmethod
def _shared_parser(cls):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('-v', action='count', default=0,
                       help="Degree of verbosity (use more v for more verbosity)")
    return parser
```

**3. __call__() - Execution**
```python
def __call__(self, args):
    self._set_debugging(args.v)
    post_event(self.command)
```

## PebbleCommand

**File:** `pebble_tool/commands/base.py:72-133`

Extends BaseCommand with Pebble device connection capabilities.

### Connection Handling

```python
def _connect(self, args):
    self._set_debugging(args.v)

    # Iterate through valid connection handlers
    for handler_impl in self.valid_connection_handlers():
        if handler_impl.is_selected(args):
            break
    else:
        # Fallback to running emulator
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

### Properties

```python
@property
def pebble(self):
    # Lazy connection - only connects when first accessed
    if self._pebble is None:
        self._pebble = self._connect(self._args)
    return self._pebble
```

## SDKCommand

**File:** `pebble_tool/commands/sdk/__init__.py:15-56`

Extends BaseCommand for SDK operations.

### Key Features

**SDK Path Resolution:**
```python
def get_sdk_path(self):
    if self.sdk is not None:
        return sdk_manager.path_for_sdk(self.sdk)
    return sdk_path()  # Returns active SDK
```

**ARM Tools:**
```python
def add_arm_tools_to_path(self):
    add_tools_to_path()  # Adds ARM toolchain to PATH
```

**Python Environment:**
```python
def _fix_python(self):
    # Ensures Python 3.8+ available
    pass
```

## SDKProjectCommand

**File:** `pebble_tool/commands/sdk/project/__init__.py:18-57`

Extends SDKCommand for project-specific operations.

### WAF Integration

```python
def _waf(self, command, extra_env=None, args=None):
    waf_path = os.path.join(sdk_path, 'pebble', 'waf')
    venv = os.path.join(sdk_path, '..', '.venv')

    env = os.environ.copy()
    env['PYTHONHOME'] = venv
    env['PYTHONPATH'] = ':'.join(sys.path)
    env['NODE_PATH'] = os.path.join(sdk_path, '..', 'node_modules')
    env['NOCLIMB'] = "1"

    if extra_env:
        env.update(extra_env)

    subprocess.check_call(
        [os.path.join(venv, 'bin', 'python'), waf_path, command] + args,
        env=env
    )
```

### Project Loading

```python
def __call__(self, args):
    super(SDKProjectCommand, self).__call__(args)
    try:
        self.project = PebbleProject()
    except OutdatedProjectException as e:
        post_event("sdk_outofdate_project_source")
        raise ToolError(str(e))
```

## Command Routing Flow

**Example:** `pebble ping`

1. **CLI Invocation**
   - User types `pebble ping`

2. **Entry Point** (`pebble.py:6-7`)
   ```python
   if __name__ == "__main__":
       pebble_tool.run_tool()
   ```

3. **Main Function** (`pebble_tool/__init__.py:52`)
   - Calls `register_children(parser)`
   - Adds all commands from `_CommandRegistry`

4. **Command Registration** (`base.py:47`)
   - `PingCommand.add_parser()` sets:
     ```python
     parser.set_defaults(func=lambda x: cls()(x))
     ```
   - Creates closure that instantiates class and calls it

5. **Argparse Execution** (`__init__.py:53-57`)
   ```python
   args = parser.parse_args(args)  # Parses 'ping'
   args.func(args)  # Calls the lambda: PingCommand()(args)
   ```

6. **Command Execution** (`ping.py:15-22`)
   ```python
   def __call__(self, args):
       super(PingCommand, self).__call__(args)  # Parent chain
       cookie = random.randint(1, 0xFFFFFFFF)
       pong = self.pebble.send_and_read(
           PingPong(cookie=cookie, message=Ping(idle=False)),
           PingPong
       )
   ```

7. **Parent Chain**
   - `PingCommand.__call__` → `PebbleCommand.__call__`
   - `PebbleCommand.__call__` establishes connection
   - Calls `super()` → `BaseCommand.__call__`
   - `BaseCommand.__call__` sets verbosity, posts analytics

## Nested Subcommands

**Example:** `pebble sdk install`

```python
class SDKManager(BaseCommand):
    command = 'sdk'
    has_subcommands = True

    @classmethod
    def add_parser(cls, parser):
        parser = super(SDKManager, cls).add_parser(parser)
        subparsers = parser.add_subparsers(title="subcommand")

        # Manually add subcommands
        list_parser = subparsers.add_parser("list", help="...")
        list_parser.set_defaults(sub_func=cls.do_list)

        install_parser = subparsers.add_parser("install", help="...")
        install_parser.set_defaults(sub_func=cls.do_install)

    def __call__(self, args):
        super(SDKManager, self).__call__(args)
        args.sub_func(args)  # Route to subcommand method
```

## Transport Configuration System

**Parallel Metaclass System:** `pebble_tool/commands/base.py:136-305`

```python
class SelfRegisteringTransportConfiguration(type):
    def __init__(cls, name, bases, dct):
        if hasattr(cls, 'name') and cls.name is not None:
            PebbleCommand.register_connection_handler(cls)

class PebbleTransportConfiguration(with_metaclass(...)):
    # Subclasses: Serial, Phone, Qemu, CloudPebble, Emulator
    pass
```

**Implementations:**
- `PebbleTransportSerial`
- `PebbleTransportPhone`
- `PebbleTransportQemu`
- `PebbleTransportCloudPebble`
- `PebbleTransportEmulator`

## Shared Functionality Summary

### BaseCommand
- Verbosity control
- Common arguments (`-v`)
- Parser setup
- Analytics posting

### PebbleCommand
- Connection management
- Transport auto-detection
- Debug arguments
- Lazy connection (`self.pebble` property)

### SDKCommand
- SDK path resolution
- Python environment setup
- ARM tools in PATH
- SDK version override (`--sdk`)

### SDKProjectCommand
- WAF integration
- Project loading
- Build orchestration
- Properties: `self.project`, `self.waf_path`

## Command Examples

**Simple Command:**
```python
class PingCommand(PebbleCommand):
    command = 'ping'
    """Test connection to Pebble"""

    def __call__(self, args):
        super().__call__(args)
        pong = self.pebble.send_and_read(
            PingPong(cookie=123, message=Ping(idle=False)),
            PingPong
        )
        print(f"Pong! (latency: {pong.latency}ms)")
```

**Project Command:**
```python
class BuildCommand(SDKProjectCommand):
    command = 'build'
    """Build the current project"""

    def __call__(self, args):
        super().__call__(args)

        # Install npm deps
        if self.project.dependencies:
            npm.invoke_npm(["install"])

        # Run waf
        self._waf("configure")
        self._waf("build")
```

**Subcommand Command:**
```python
class SDKManager(BaseCommand):
    command = 'sdk'
    has_subcommands = True

    @classmethod
    def add_parser(cls, parser):
        parser = super().add_parser(parser)
        subs = parser.add_subparsers(title="subcommand")
        subs.add_parser("list").set_defaults(sub_func=cls.do_list)
        subs.add_parser("install").set_defaults(sub_func=cls.do_install)

    def __call__(self, args):
        super().__call__(args)
        args.sub_func(args)

    @classmethod
    def do_list(cls, args):
        # Implementation
        pass

    @classmethod
    def do_install(cls, args):
        # Implementation
        pass
```

## Summary

The command system provides:
- **Automatic Registration** - Metaclass-based plugin architecture
- **Clean Hierarchy** - Each level adds specific capabilities
- **Flexible Routing** - From CLI to handler via argparse
- **Shared Functionality** - Connection, SDK, project management
- **Nested Commands** - Support for subcommand trees
- **Transport Abstraction** - Multiple connection types
