"""Parametrized tests over eval_cases.json.

Tests require a live LLM API connection. Run with:
    pytest -m api tests/test_scorer.py

Skipped by default in CI (no API key for the configured provider).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.models import EvalCase, Transcript

EVAL_CASES_PATH = Path("fixtures/eval_cases.json")
PLACEHOLDER_PREFIX = "[PLACEHOLDER"

_provider = os.environ.get("LLM_PROVIDER", "openai")
_has_api_key = (
    bool(os.environ.get("OPENAI_API_KEY")) if _provider == "openai"
    else bool(os.environ.get("GROQ_API_KEY")) if _provider == "groq"
    else False
)


def _load_cases() -> list[EvalCase]:
    raw = json.loads(EVAL_CASES_PATH.read_text())
    return [EvalCase(**case) for case in raw]


def _active_cases() -> list[EvalCase]:
    return [c for c in _load_cases() if not c.transcript.startswith(PLACEHOLDER_PREFIX)]


def _make_transcript(case: EvalCase) -> Transcript:
    return Transcript(
        chunk_id=f"test_{case.id}",
        chunk_start_seconds=0.0,
        text=case.transcript,
        words=[],
        language="en",
    )


@pytest.mark.skipif(not _has_api_key, reason="No API key set for configured provider")
@pytest.mark.skipif(not _active_cases(), reason="All eval cases are placeholders")
@pytest.mark.api
@pytest.mark.parametrize(
    "case",
    _active_cases(),
    ids=[c.id for c in _active_cases()],
)
def test_scorer_direction(case: EvalCase) -> None:
    """Test behavior, direction, and commodity for each eval case."""
    from app.llm.scorer import score_transcript

    transcript = _make_transcript(case)
    signals = score_transcript(transcript)

    if case.expected_behavior == "empty":
        assert signals == [], f"Expected empty result but got {len(signals)} signal(s)"
        return

    assert signals, f"Expected {case.expected_behavior} but got no signals"
    top = max(signals, key=lambda s: s.confidence)
    assert top.direction == case.expected_direction, (
        f"Expected {case.expected_direction} but got {top.direction}"
    )
    if case.expected_commodity is not None:
        assert top.commodity == case.expected_commodity, (
            f"Expected {case.expected_commodity} but got {top.commodity}"
        )


# ---------------------------------------------------------------------------
# Offline tests — no API required
# ---------------------------------------------------------------------------

def test_eval_cases_valid_structure() -> None:
    """Verify eval_cases.json has valid structure and all required fields."""
    cases = _load_cases()
    assert len(cases) >= 10, f"Expected at least 10 eval cases, got {len(cases)}"

    for case in cases:
        assert case.id, "Case must have an id"
        assert case.transcript, "Case must have a transcript"
        assert case.expected_behavior in ("empty", "neutral_signal", "directional")
        assert case.expected_direction in ("bullish", "bearish", "neutral")
        assert case.notes, "Case must have notes"


def test_eval_cases_no_placeholders() -> None:
    """Verify all eval cases have real transcripts (not placeholders)."""
    cases = _load_cases()
    placeholders = [c for c in cases if c.transcript.startswith(PLACEHOLDER_PREFIX)]
    assert not placeholders, (
        f"Found {len(placeholders)} placeholder cases: {[c.id for c in placeholders]}"
    )


def test_eval_cases_direction_coverage() -> None:
    """Verify eval cases cover all three directions."""
    cases = _load_cases()
    directions = {c.expected_direction for c in cases}
    assert "bullish" in directions, "Missing bullish test case"
    assert "bearish" in directions, "Missing bearish test case"
    assert "neutral" in directions, "Missing neutral test case"


def test_eval_cases_commodity_coverage() -> None:
    """Verify eval cases cover multiple commodities."""
    cases = _load_cases()
    commodities = {c.expected_commodity for c in cases if c.expected_commodity}
    assert len(commodities) >= 5, f"Expected at least 5 commodities, got {len(commodities)}: {commodities}"
