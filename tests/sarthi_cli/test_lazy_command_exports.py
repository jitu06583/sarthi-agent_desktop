"""The decomposed command modules stay lazy after `import sarthi_cli.main`.

The main.py decomposition re-exports the sessions/update/dashboard command
surface from sarthi_cli.main so argparse wiring and monkeypatches keep
resolving. Those re-exports must not import the modules eagerly: every
`sarthi` invocation (including `sarthi --version`) would pay for update_cmd's
dependency chain (jwt, click, ...) even when no subcommand runs.
"""

import subprocess
import sys
import textwrap

import sarthi_cli.main


def test_importing_main_does_not_import_command_modules():
    code = textwrap.dedent(
        """
        import sys
        import sarthi_cli.main  # noqa: F401
        loaded = [
            m
            for m in (
                "sarthi_cli.update_cmd",
                "sarthi_cli.sessions_cmd",
                "sarthi_cli.dashboard_procs",
            )
            if m in sys.modules
        ]
        assert not loaded, f"eagerly imported: {loaded}"
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr


def test_lazy_reexports_resolve_to_real_objects():
    import sarthi_cli.dashboard_procs
    import sarthi_cli.sessions_cmd
    import sarthi_cli.update_cmd

    assert sarthi_cli.main.cmd_sessions is sarthi_cli.sessions_cmd.cmd_sessions
    assert (
        sarthi_cli.main._cmd_update_impl is sarthi_cli.update_cmd._cmd_update_impl
    )
    assert (
        sarthi_cli.main._scan_dashboard_processes
        is sarthi_cli.dashboard_procs._scan_dashboard_processes
    )
    # Back-compat alias resolves to the kill helper.
    assert (
        sarthi_cli.main._warn_stale_dashboard_processes
        is sarthi_cli.dashboard_procs._kill_stale_dashboard_processes
    )


def test_lazy_reexports_accept_monkeypatch(monkeypatch):
    sentinel = object()
    monkeypatch.setattr("sarthi_cli.main._cmd_update_impl", sentinel)
    assert sarthi_cli.main._cmd_update_impl is sentinel
