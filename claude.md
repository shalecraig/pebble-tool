# Pebble Tool - Claude Documentation

This document contains architectural information and development notes for the Pebble Tool project.

## Project Overview

Pebble Tool is a Python-based CLI SDK for developing Pebble smartwatch applications and watchfaces. It's the modern Python 3 successor to the original Pebble SDK.

## Architecture

The tool is organized into 8 major subsystems:

1. **SDK Management** - Multi-version SDK isolation, ARM toolchains, Python virtual environments
2. **Emulator Management** - QEMU + pypkjs multi-process architecture
3. **Build System** - WAF-based compilation, multi-platform builds, npm integration
4. **Transport Layer** - Multiple connection types (Serial, Phone, QEMU, CloudPebble, Emulator)
5. **Command System** - Metaclass-based self-registering commands
6. **Project Management** - Dual format support (npm/appinfo), SDK compatibility
7. **Authentication** - GitHub OAuth 2.0 integration
8. **Template System** - Project scaffolding for apps, Rocky.js, and libraries

## Key Files

- `/pebble_tool/commands/base.py` - Command registration system
- `/pebble_tool/sdk/manager.py` - SDK installation and management
- `/pebble_tool/sdk/emulator.py` - QEMU emulator integration
- `/pebble_tool/sdk/project.py` - Project type detection and parsing

## Development Notes

For detailed architectural analysis, see the `docs/gen/` directory.
