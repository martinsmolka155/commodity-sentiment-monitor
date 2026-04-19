"""Unit tests with mocked LLM — no API keys required."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.models import MentionedEntities, Signal, Transcript, Word


# ---------------------------------------------------------------------------
# Signal model validation
# ---------------------------------------------------------------------------

def test_signal_valid():
    s = Signal(
        commodity="gold",
        direction="bullish",
        confidence=0.85,
        rationale="Test rationale",
        timeframe="short_term",
        mentioned_entities=MentionedEntities(
            persons=["Powell"],
            indicators=["rate cut"],
            organizations=["Fed"],
        ),
        source_chunk_id="chunk_0001",
        source_timestamp_start=0.0,
        source_timestamp_end=10.0,
        raw_quote="test quote",
    )
    assert s.commodity == "gold"
    assert s.mentioned_entities.persons == ["Powell"]


def test_signal_confidence_bounds():
    with pytest.raises(Exception):
        Signal(
            commodity="gold", direction="bullish", confidence=1.5,
            rationale="x", timeframe="short_term",
            source_chunk_id="x", source_timestamp_start=0, source_timestamp_end=10,
            raw_quote="x",
        )

    with pytest.raises(Exception):
        Signal(
            commodity="gold", direction="bullish", confidence=-0.1,
            rationale="x", timeframe="short_term",
            source_chunk_id="x", source_timestamp_start=0, source_timestamp_end=10,
            raw_quote="x",
        )


def test_signal_invalid_commodity():
    with pytest.raises(Exception):
        Signal(
            commodity="bitcoin", direction="bullish", confidence=0.5,
            rationale="x", timeframe="short_term",
            source_chunk_id="x", source_timestamp_start=0, source_timestamp_end=10,
            raw_quote="x",
        )


def test_mentioned_entities_defaults():
    e = MentionedEntities()
    assert e.persons == []
    assert e.indicators == []
    assert e.organizations == []


# ---------------------------------------------------------------------------
# Extract signals from raw LLM output
# ---------------------------------------------------------------------------

def test_extract_signals_valid():
    from app.llm.scorer import _extract_signals

    transcript = Transcript(
        chunk_id="test_chunk",
        chunk_start_seconds=30.0,
        text="OPEC cuts production",
        words=[Word(text="OPEC", start=30.0, end=30.5), Word(text="cuts", start=30.6, end=31.0)],
    )

    raw = [
        {
            "commodity": "crude_oil_wti",
            "direction": "bullish",
            "confidence": 0.9,
            "rationale": "Production cut",
            "timeframe": "short_term",
            "mentioned_entities": {
                "persons": [],
                "indicators": ["production cut"],
                "organizations": ["OPEC"],
            },
            "raw_quote": "OPEC cuts production",
        }
    ]

    signals = _extract_signals(raw, transcript)
    assert len(signals) == 1
    assert signals[0].commodity == "crude_oil_wti"
    assert signals[0].source_chunk_id == "test_chunk"
    assert signals[0].source_timestamp_start == 30.0
    assert signals[0].source_timestamp_end == 31.0  # from word timestamps, not hardcoded +10
    assert signals[0].mentioned_entities.organizations == ["OPEC"]


def test_extract_signals_empty():
    from app.llm.scorer import _extract_signals

    transcript = Transcript(chunk_id="t", chunk_start_seconds=0, text="hello", words=[])
    signals = _extract_signals([], transcript)
    assert signals == []


def test_extract_signals_missing_entities():
    """LLM may omit mentioned_entities — should default to empty."""
    from app.llm.scorer import _extract_signals

    transcript = Transcript(chunk_id="t", chunk_start_seconds=0, text="test", words=[])
    raw = [
        {
            "commodity": "gold",
            "direction": "neutral",
            "confidence": 0.3,
            "rationale": "Weak hint",
            "timeframe": "short_term",
            "raw_quote": "test",
            # no mentioned_entities key
        }
    ]
    signals = _extract_signals(raw, transcript)
    assert len(signals) == 1
    assert signals[0].mentioned_entities.persons == []


def test_extract_signals_invalid_raw_quote_skipped():
    """Signals with hallucinated raw_quote should be rejected."""
    from app.llm.scorer import _extract_signals

    transcript = Transcript(chunk_id="t", chunk_start_seconds=0, text="gold rallied today", words=[])
    raw = [
        {
            "commodity": "gold",
            "direction": "bullish",
            "confidence": 0.8,
            "rationale": "Valid enough",
            "timeframe": "short_term",
            "raw_quote": "something the transcript never said",
        }
    ]
    signals = _extract_signals(raw, transcript)
    assert signals == []


def test_extract_signals_raw_quote_with_ellipsis_accepted():
    """Quote fragments joined by ellipsis should still validate if grounded in transcript."""
    from app.llm.scorer import _extract_signals

    transcript = Transcript(
        chunk_id="t",
        chunk_start_seconds=0,
        text=(
            "The State Department announced a new round of sanctions targeting Iran's oil export "
            "infrastructure. Officials say this could remove up to one million barrels per day "
            "from the global market."
        ),
        words=[],
    )
    raw = [
        {
            "commodity": "crude_oil_brent",
            "direction": "bullish",
            "confidence": 0.82,
            "rationale": "Supply disruption is bullish for Brent.",
            "timeframe": "short_term",
            "raw_quote": "a new round of sanctions targeting Iran's oil export infrastructure...could remove up to one million barrels per day",
        }
    ]
    signals = _extract_signals(raw, transcript)
    assert len(signals) == 1


def test_extract_signals_invalid_skipped():
    """Invalid signals should be skipped, not crash the pipeline."""
    from app.llm.scorer import _extract_signals

    transcript = Transcript(chunk_id="t", chunk_start_seconds=0, text="test", words=[])
    raw = [
        {"commodity": "invalid_commodity", "direction": "bullish", "confidence": 0.5},
        {
            "commodity": "gold", "direction": "bullish", "confidence": 0.8,
            "rationale": "Valid", "timeframe": "short_term", "raw_quote": "test",
        },
    ]
    signals = _extract_signals(raw, transcript)
    assert len(signals) == 1
    assert signals[0].commodity == "gold"


# ---------------------------------------------------------------------------
# Mocked scorer — OpenAI provider
# ---------------------------------------------------------------------------

def _mock_openai_response(signals_data: list[dict]) -> MagicMock:
    """Create a mock OpenAI chat completion response with tool calls."""
    tool_call = MagicMock()
    tool_call.function.name = "report_signals"
    tool_call.function.arguments = json.dumps({"signals": signals_data})

    choice = MagicMock()
    choice.message.tool_calls = [tool_call]

    usage = MagicMock()
    usage.prompt_tokens = 1500
    usage.completion_tokens = 200

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


@patch("app.llm.scorer.OPENAI_API_KEY", "test-key")
@patch("app.llm.scorer.LLM_MODEL", "gpt-5-mini")
def test_score_transcript_openai_mocked():
    from app.llm.scorer import _score_openai

    transcript = Transcript(
        chunk_id="mock_chunk",
        chunk_start_seconds=0.0,
        text="The Fed announced rate cuts today",
        words=[],
    )

    mock_response = _mock_openai_response([
        {
            "commodity": "gold",
            "direction": "bullish",
            "confidence": 0.85,
            "rationale": "Fed rate cuts weaken dollar, bullish for gold.",
            "timeframe": "medium_term",
            "mentioned_entities": {
                "persons": ["Fed Chair"],
                "indicators": ["rate cuts"],
                "organizations": ["Federal Reserve"],
            },
            "raw_quote": "The Fed announced rate cuts today",
        }
    ])

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch("openai.OpenAI", return_value=mock_client):
        signals = _score_openai(transcript)

    assert len(signals) == 1
    assert signals[0].commodity == "gold"
    assert signals[0].direction == "bullish"
    assert signals[0].mentioned_entities.persons == ["Fed Chair"]


@patch("app.llm.scorer.OPENAI_API_KEY", "test-key")
@patch("app.llm.scorer.LLM_MODEL", "gpt-5-mini")
def test_score_transcript_neutral_no_signals():
    from app.llm.scorer import _score_openai

    transcript = Transcript(
        chunk_id="neutral_chunk",
        chunk_start_seconds=0.0,
        text="Welcome back to the show, great weather today",
        words=[],
    )

    mock_response = _mock_openai_response([])

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch("openai.OpenAI", return_value=mock_client):
        signals = _score_openai(transcript)

    assert signals == []


# ---------------------------------------------------------------------------
# Prompt schema
# ---------------------------------------------------------------------------

def test_openai_tool_schema_is_strict_and_recursive():
    from app.llm.prompts import TOOL_SCHEMA_OPENAI

    def walk_objects(node: dict | list) -> list[dict]:
        objects: list[dict] = []
        if isinstance(node, dict):
            if node.get("type") == "object":
                objects.append(node)
            for value in node.values():
                if isinstance(value, (dict, list)):
                    objects.extend(walk_objects(value))
        elif isinstance(node, list):
            for item in node:
                if isinstance(item, (dict, list)):
                    objects.extend(walk_objects(item))
        return objects

    fn = TOOL_SCHEMA_OPENAI["function"]
    params = fn["parameters"]

    assert fn["strict"] is True
    assert "source_chunk_id" not in params["properties"]["signals"]["items"]["properties"]
    assert "source_timestamp_start" not in params["properties"]["signals"]["items"]["properties"]
    assert "source_timestamp_end" not in params["properties"]["signals"]["items"]["properties"]

    for obj in walk_objects(params):
        assert obj["additionalProperties"] is False
        assert set(obj["required"]) == set(obj["properties"].keys())


def test_score_transcript_invalid_provider_raises():
    from app.llm.scorer import score_transcript

    transcript = Transcript(chunk_id="x", chunk_start_seconds=0.0, text="test", words=[])
    with patch("app.llm.scorer.LLM_PROVIDER", "invalid-provider"):
        with pytest.raises(ValueError):
            score_transcript(transcript)


# ---------------------------------------------------------------------------
# Diarization
# ---------------------------------------------------------------------------

def test_diarization_speaker_change():
    from app.diarization.pause_based import detect_speaker_segments

    words = [
        Word(text="The", start=0.0, end=0.2),
        Word(text="Fed", start=0.3, end=0.5),
        Word(text="will", start=0.6, end=0.8),
        # 2s pause = speaker change
        Word(text="What", start=2.8, end=3.0),
        Word(text="about", start=3.1, end=3.3),
        Word(text="gold", start=3.4, end=3.6),
    ]

    segments = detect_speaker_segments(words)
    assert len(segments) == 2
    assert segments[0].speaker == "SPEAKER_0"
    assert segments[1].speaker == "SPEAKER_1"
    assert "Fed" in segments[0].text
    assert "gold" in segments[1].text


def test_diarization_no_pause():
    from app.diarization.pause_based import detect_speaker_segments

    words = [
        Word(text="Oil", start=0.0, end=0.3),
        Word(text="prices", start=0.4, end=0.7),
        Word(text="rose", start=0.8, end=1.0),
    ]

    segments = detect_speaker_segments(words)
    assert len(segments) == 1


def test_diarization_empty():
    from app.diarization.pause_based import detect_speaker_segments
    assert detect_speaker_segments([]) == []


# ---------------------------------------------------------------------------
# Slack notification logic
# ---------------------------------------------------------------------------

def test_slack_should_notify_high_confidence():
    from app.notifications.slack import should_notify

    s = Signal(
        commodity="gold", direction="bullish", confidence=0.9,
        rationale="x", timeframe="short_term",
        source_chunk_id="x", source_timestamp_start=0, source_timestamp_end=10,
        raw_quote="x",
    )
    with patch("app.notifications.slack.SLACK_WEBHOOK_URL", "https://hooks.slack.test"):
        assert should_notify(s) is True


def test_slack_should_not_notify_low_confidence():
    from app.notifications.slack import should_notify

    s = Signal(
        commodity="gold", direction="bullish", confidence=0.5,
        rationale="x", timeframe="short_term",
        source_chunk_id="x", source_timestamp_start=0, source_timestamp_end=10,
        raw_quote="x",
    )
    with patch("app.notifications.slack.SLACK_WEBHOOK_URL", "https://hooks.slack.test"):
        assert should_notify(s) is False


def test_slack_send_signal_alert_posts_payload():
    from app.notifications.slack import send_signal_alert

    signal = Signal(
        commodity="gold",
        direction="bullish",
        confidence=0.91,
        rationale="Gold should benefit from the move.",
        timeframe="short_term",
        source_chunk_id="x",
        source_timestamp_start=0,
        source_timestamp_end=10,
        raw_quote="gold rallied on the announcement",
    )

    response = MagicMock()
    response.status = 200
    context_manager = MagicMock()
    context_manager.__enter__.return_value = response

    with patch("app.notifications.slack.SLACK_WEBHOOK_URL", "https://hooks.slack.test"):
        with patch("urllib.request.urlopen", return_value=context_manager) as mock_urlopen:
            send_signal_alert(signal)

    request = mock_urlopen.call_args.args[0]
    assert request.full_url == "https://hooks.slack.test"
    payload = json.loads(request.data.decode("utf-8"))
    assert "Gold" in payload["text"]
    assert "BULLISH" in payload["text"]


# ---------------------------------------------------------------------------
# Cost tracker
# ---------------------------------------------------------------------------

def test_cost_tracker_logs_and_sums(tmp_path: Path):
    from app.cost import tracker

    log_path = tmp_path / "costs.jsonl"
    with patch.object(tracker, "_log_path", log_path):
        tracker.log_cost("openai", 100, 0.12, {"chunk": "a"})
        tracker.log_cost("groq_whisper", 10, 0.08)

        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 2
        assert tracker.total_cost() == pytest.approx(0.20)


# ---------------------------------------------------------------------------
# File ingestion
# ---------------------------------------------------------------------------

def test_file_stream_produce_chunks_fast_mode(tmp_path: Path):
    from app.ingestion import file_stream
    from app.sentinel import SENTINEL

    for i in range(2):
        (tmp_path / f"chunk_{i:04d}.wav").write_bytes(b"wav")

    async def fake_split_audio(input_file: str | None = None) -> Path:
        return tmp_path

    queue: asyncio.Queue = asyncio.Queue()

    with patch.object(file_stream, "split_audio", side_effect=fake_split_audio):
        with patch.object(file_stream, "FILE_MODE_REALTIME", False):
            with patch("app.ingestion.file_stream.asyncio.sleep", side_effect=AssertionError("sleep should not be called")):
                asyncio.run(file_stream.produce_chunks(queue))

    items = []
    while not queue.empty():
        items.append(queue.get_nowait())

    assert items[0][1] == 0
    assert items[1][1] == file_stream.CHUNK_DURATION_SECONDS
    assert items[-1] is SENTINEL


def test_file_stream_produce_chunks_realtime_mode_sleeps(tmp_path: Path):
    from app.ingestion import file_stream

    for i in range(2):
        (tmp_path / f"chunk_{i:04d}.wav").write_bytes(b"wav")

    async def fake_split_audio(input_file: str | None = None) -> Path:
        return tmp_path

    sleeps: list[int] = []

    async def fake_sleep(seconds: int) -> None:
        sleeps.append(seconds)

    queue: asyncio.Queue = asyncio.Queue()

    with patch.object(file_stream, "split_audio", side_effect=fake_split_audio):
        with patch.object(file_stream, "FILE_MODE_REALTIME", True):
            with patch("app.ingestion.file_stream.asyncio.sleep", side_effect=fake_sleep):
                asyncio.run(file_stream.produce_chunks(queue))

    assert sleeps == [file_stream.CHUNK_DURATION_SECONDS]


# ---------------------------------------------------------------------------
# Dashboard telemetry
# ---------------------------------------------------------------------------

def test_dashboard_records_zero_signal_chunk_preview():
    from app.dashboard.rich_ui import Dashboard

    dashboard = Dashboard(asyncio.Queue())
    transcript = Transcript(
        chunk_id="live_0001",
        chunk_start_seconds=10.0,
        text="Gold is being mentioned, but the speaker gives no clear directional signal right now.",
        words=[],
    )

    dashboard.record_stt_result(transcript, 1.23)
    dashboard.record_scoring_result(transcript, [], 0.67)

    assert dashboard._processed_chunks == 1
    assert dashboard._zero_signal_chunks == 1
    assert dashboard._last_chunk_id == "live_0001"
    assert "Gold is being mentioned" in dashboard._last_transcript_preview
    assert dashboard._last_stt_latency == pytest.approx(1.23)
    assert dashboard._last_llm_latency == pytest.approx(0.67)
