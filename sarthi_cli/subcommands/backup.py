"""``sarthi backup`` subcommand parser.

Extracted verbatim from ``sarthi_cli/main.py:main()`` (god-file Phase 2).
Handler injected to avoid importing ``main``.
"""

from __future__ import annotations

from typing import Callable


def build_backup_parser(subparsers, *, cmd_backup: Callable) -> None:
    """Attach the ``backup`` subcommand to ``subparsers``."""
    # =========================================================================
    # backup command
    # =========================================================================
    backup_parser = subparsers.add_parser(
        "backup",
        help="Back up Sarthi home directory to a zip file",
        description="Create a zip archive of your entire Sarthi configuration, "
        "skills, sessions, and data (excludes the sarthi-agent codebase). "
        "Use --quick for a fast snapshot of just critical state files.",
    )
    backup_parser.add_argument(
        "-o",
        "--output",
        help="Output path for the zip file (default: ~/sarthi-backup-<timestamp>.zip)",
    )
    backup_parser.add_argument(
        "-q",
        "--quick",
        action="store_true",
        help="Quick snapshot: only critical state files (config, state.db, .env, auth, cron)",
    )
    backup_parser.add_argument(
        "-l", "--label", help="Label for the snapshot (only used with --quick)"
    )
    backup_parser.set_defaults(func=cmd_backup)
