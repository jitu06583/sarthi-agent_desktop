"""Resolve SARTHI_HOME for standalone skill scripts.

Skill scripts may run outside the Sarthi process (system Python, nix env,
CI) where ``sarthi_constants`` is not importable.  This module provides the
same ``get_sarthi_home()`` contract without requiring it on ``sys.path``.

When ``sarthi_constants`` IS available it is used directly so profile
resolution and any future enhancements are picked up automatically.
"""

from __future__ import annotations

import os
from pathlib import Path

try:
    from sarthi_constants import get_sarthi_home as get_sarthi_home
except (ModuleNotFoundError, ImportError):

    def get_sarthi_home() -> Path:
        """Return the Sarthi home directory (default: ``~/.sarthi``)."""
        val = os.environ.get("SARTHI_HOME", "").strip()
        return Path(val) if val else Path.home() / ".sarthi"
