# Pebble Tool - Claude Documentation

This document provides a brief overview of the Pebble Tool project. For detailed architectural information, see the documentation in `docs/gen/`.

## Project Overview

Pebble Tool is a Python-based CLI SDK for developing Pebble smartwatch applications and watchfaces. It's the modern Python 3 successor to the original Pebble SDK.

**Codebase:** ~3,526 lines of Python across 40+ modules

## Architecture

The tool consists of 8 major subsystems. For detailed information on each, see the corresponding documentation file:

1. **[SDK Management](docs/gen/sdk-management.md)** - Multi-version SDK isolation, ARM toolchains, Python virtual environments
2. **[Emulator Management](docs/gen/emulator-management.md)** - QEMU + pypkjs multi-process architecture
3. **[Build System](docs/gen/build-system.md)** - WAF-based compilation, multi-platform builds, npm integration
4. **[Transport Layer](docs/gen/transport-layer.md)** - Multiple connection types (Serial, Phone, QEMU, CloudPebble, Emulator)
5. **[Command System](docs/gen/command-system.md)** - Metaclass-based self-registering commands
6. **[Project Management](docs/gen/project-management.md)** - Dual format support (npm/appinfo), SDK compatibility
7. **[Authentication](docs/gen/authentication.md)** - GitHub OAuth 2.0 integration
8. **[Template System](docs/gen/template-system.md)** - Project scaffolding for apps, Rocky.js, and libraries

For a comprehensive overview of all subsystems, see [Architecture Overview](docs/gen/architecture-overview.md).

## Key Files

- `pebble_tool/commands/base.py` - Command registration system
- `pebble_tool/sdk/manager.py` - SDK installation and management
- `pebble_tool/sdk/emulator.py` - QEMU emulator integration
- `pebble_tool/sdk/project.py` - Project type detection and parsing

## Quick Reference

**Main entry point:** `pebble_tool/__init__.py:run_tool()`
**Command registration:** Metaclass-based auto-registration in `pebble_tool/commands/base.py`
**SDK directory:** `~/.pebble-sdk/` (Linux) or `~/Library/Application Support/Pebble SDK/` (macOS)

## Development Notes

All detailed architectural documentation is maintained in the `docs/gen/` directory. Each file provides in-depth analysis of a specific subsystem with code examples, file references, and implementation details.
