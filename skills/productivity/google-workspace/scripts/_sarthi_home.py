"""Resolve SARTHI_HOME for standalone skill scripts.

Skill scripts may run outside the Sarthi process (e.g. system Python,
nix env, CI) where ``sarthi_constants`` is not importable.  This module
provides the same ``get_sarthi_home()`` and ``display_sarthi_home()``
contracts as ``sarthi_constants`` without requiring it on ``sys.path``.

When ``sarthi_constants`` IS available it is used directly so that any
future enhancements (profile resolution, Docker detection, etc.) are
picked up automatically.  The fallback path replicates the core logic
from ``sarthi_constants.py`` using only the stdlib.

All scripts under ``google-workspace/scripts/`` should import from here
instead of duplicating the ``SARTHI_HOME = Path(os.getenv(...))`` pattern.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from sarthi_constants import display_sarthi_home as display_sarthi_home
    from sarthi_constants import get_sarthi_home as get_sarthi_home
except (ModuleNotFoundError, ImportError):

    def get_sarthi_home() -> Path:
        """Return the Sarthi home directory (default: ~/.sarthi).

        Mirrors ``sarthi_constants.get_sarthi_home()``."""
        val = os.environ.get("SARTHI_HOME", "").strip()
        return Path(val) if val else Path.home() / ".sarthi"

    def display_sarthi_home() -> str:
        """Return a user-friendly ``~/``-shortened display string.

        Mirrors ``sarthi_constants.display_sarthi_home()``."""
        home = get_sarthi_home()
        try:
            return "~/" + str(home.relative_to(Path.home()))
        except ValueError:
            return str(home)
