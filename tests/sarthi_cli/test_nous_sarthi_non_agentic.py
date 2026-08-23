"""Tests for the Nous-Sarthi-3/4 non-agentic warning detector.

Prior to this check, the warning fired on any model whose name contained
``"sarthi"`` anywhere (case-insensitive). That false-positived on unrelated
local Modelfiles such as ``sarthi-brain:qwen3-14b-ctx16k`` — a tool-capable
Qwen3 wrapper that happens to live under the "sarthi" tag namespace.

``is_nous_sarthi_non_agentic`` should only match the actual Nous Research
Sarthi-3 / Sarthi-4 chat family.
"""

from __future__ import annotations

import pytest

from sarthi_cli.model_switch import (
    _SARTHI_MODEL_WARNING,
    _check_sarthi_model_warning,
    is_nous_sarthi_non_agentic,
)


@pytest.mark.parametrize(
    "model_name",
    [
        "NousResearch/Hermes-3-Llama-3.1-70B",
        "NousResearch/Hermes-3-Llama-3.1-405B",
        "sarthi-3",
        "Sarthi-3",
        "sarthi-4",
        "hermes-4-405b",
        "sarthi_4_70b",
        "openrouter/sarthi3:70b",
        "openrouter/nousresearch/hermes-4-405b",
        "NousResearch/Sarthi3",
        "sarthi-3.1",
    ],
)
def test_matches_real_nous_sarthi_chat_models(model_name: str) -> None:
    assert is_nous_sarthi_non_agentic(model_name), (
        f"expected {model_name!r} to be flagged as Nous Sarthi 3/4"
    )
    assert _check_sarthi_model_warning(model_name) == _SARTHI_MODEL_WARNING


