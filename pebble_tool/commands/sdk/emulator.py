
__author__ = 'katharine'

import errno
import os
import shutil
import signal

from libpebble2.communication import PebbleConnection
from libpebble2.exceptions import ConnectionError, TimeoutError
from libpebble2.protocol.apps import AppRunState, AppRunStateRequest

from ..base import BaseCommand, PebbleCommand
from pebble_tool.exceptions import InvalidProjectException
from pebble_tool.sdk import get_sdk_persist_dir, get_persist_dir, get_pebble_platforms
from pebble_tool.sdk.project import PebbleProject
import pebble_tool.sdk.emulator as emulator


class KillCommand(BaseCommand):
    """Kills running emulators, if any."""
    command = 'kill'

    def __call__(self, args):
        super(KillCommand, self).__call__(args)
        if args.force:
            s = signal.SIGKILL
        else:
            s = signal.SIGTERM

        info = emulator.get_all_emulator_info()
        for platform in list(info.values()):
            for version in list(platform.values()):
                self._kill_if_running(version['qemu']['pid'], s)
                self._kill_if_running(version['pypkjs']['pid'], s)
                if 'websockify' in version:
                    self._kill_if_running(version['websockify']['pid'], s)

    @classmethod
    def _kill_if_running(cls, pid, signal_number):
        try:
            os.kill(pid, signal_number)
        except OSError as e:
            if e.errno == errno.ESRCH:
                pass

    @classmethod
    def add_parser(cls, parser):
        parser = super(KillCommand, cls).add_parser(parser)
        parser.add_argument('--force', action='store_true', help="Send the processes SIGKILL")
        return parser


class WipeCommand(BaseCommand):
    """Wipes data for running emulators. By default, only clears data for the current SDK version."""
    command = 'wipe'

    def __call__(self, args):
        super(WipeCommand, self).__call__(args)
        if args.everything:
            shutil.rmtree(get_persist_dir())
        else:
            for platform in get_pebble_platforms():
                shutil.rmtree(get_sdk_persist_dir(platform))

    @classmethod
    def add_parser(cls, parser):
        parser = super(WipeCommand, cls).add_parser(parser)
        parser.add_argument('--everything', action='store_true',
                            help="Deletes all data from all versions. Also logs you out.")
        return parser


class StatusCommand(BaseCommand):
    """Shows the status of running emulators and installed apps."""
    command = 'status'

    def __call__(self, args):
        super(StatusCommand, self).__call__(args)

        all_info = emulator.get_all_emulator_info()

        if not all_info:
            print("No emulators have been started.")
            return

        found_any = False
        for platform, versions in all_info.items():
            for version, info in versions.items():
                found_any = True
                self._show_emulator_status(platform, version, info, args.verbose)

        if not found_any:
            print("No emulators have been started.")

    def _show_emulator_status(self, platform, version, info, verbose):
        """Display status for a single emulator instance."""
        qemu_pid = info.get('qemu', {}).get('pid')
        pypkjs_pid = info.get('pypkjs', {}).get('pid')

        qemu_alive = qemu_pid and emulator.ManagedEmulatorTransport._is_pid_running(qemu_pid)
        pypkjs_alive = pypkjs_pid and emulator.ManagedEmulatorTransport._is_pid_running(pypkjs_pid)

        print("\n=== Emulator: {} (SDK {}) ===".format(platform, version))

        # Process status
        if qemu_alive and pypkjs_alive:
            print("Status: RUNNING")
            print("  QEMU:   running (pid {})".format(qemu_pid))
            print("  pypkjs: running (pid {})".format(pypkjs_pid))
        elif qemu_alive and not pypkjs_alive:
            print("Status: DEGRADED (pypkjs not running)")
            print("  QEMU:   running (pid {})".format(qemu_pid))
            print("  pypkjs: NOT RUNNING (was pid {})".format(pypkjs_pid))
        elif not qemu_alive and pypkjs_alive:
            print("Status: DEGRADED (QEMU not running)")
            print("  QEMU:   NOT RUNNING (was pid {})".format(qemu_pid))
            print("  pypkjs: running (pid {})".format(pypkjs_pid))
        else:
            print("Status: STOPPED")
            print("  QEMU:   not running (was pid {})".format(qemu_pid))
            print("  pypkjs: not running (was pid {})".format(pypkjs_pid))
            return  # No point checking app status if emulator is stopped

        # VNC status
        if info.get('qemu', {}).get('vnc'):
            websockify_pid = info.get('websockify', {}).get('pid')
            if websockify_pid and emulator.ManagedEmulatorTransport._is_pid_running(websockify_pid):
                print("  VNC:    enabled (websockify pid {})".format(websockify_pid))
            else:
                print("  VNC:    enabled but websockify not running")

        # Try to get app status
        if qemu_alive and pypkjs_alive:
            self._show_app_status(info, verbose)

    def _show_app_status(self, info, verbose):
        """Query and display the currently running app status."""
        pypkjs_port = info.get('pypkjs', {}).get('port')
        if not pypkjs_port:
            print("  App:    unable to query (no pypkjs port)")
            return

        try:
            transport = emulator.WebsocketTransport('ws://localhost:{}/'.format(pypkjs_port))
            connection = PebbleConnection(transport)
            connection.connect()
            connection.run_async()

            # Query app run state
            try:
                response = connection.send_and_read(
                    AppRunState(data=AppRunStateRequest()),
                    AppRunState,
                    timeout=5
                )
                app_uuid = response.data.uuid

                # Check if this matches the current project
                project_match = self._check_project_match(app_uuid)

                if app_uuid:
                    uuid_str = str(app_uuid)
                    if project_match:
                        print("  App:    RUNNING ({} - current project)".format(uuid_str))
                    else:
                        print("  App:    RUNNING ({})".format(uuid_str))
                        if verbose:
                            print("          (not the current project)")
                else:
                    print("  App:    no app running (showing watchface)")

            except TimeoutError:
                print("  App:    UNRESPONSIVE (timed out querying app state)")
                if verbose:
                    print("          The app may be stuck in an infinite loop or crashed")
            finally:
                connection.disconnect()

        except ConnectionError as e:
            print("  App:    DISCONNECTED (could not connect to emulator)")
            if verbose:
                print("          Error: {}".format(str(e)))
        except Exception as e:
            print("  App:    UNKNOWN (error querying status)")
            if verbose:
                print("          Error: {}".format(str(e)))

    def _check_project_match(self, app_uuid):
        """Check if the running app matches the current project."""
        try:
            project = PebbleProject()
            return project.uuid == app_uuid
        except InvalidProjectException:
            return False

    @classmethod
    def add_parser(cls, parser):
        parser = super(StatusCommand, cls).add_parser(parser)
        parser.add_argument('--verbose', '-V', action='store_true',
                            help="Show more detailed status information")
        return parser
