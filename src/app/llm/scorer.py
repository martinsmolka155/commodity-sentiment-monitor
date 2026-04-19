"""LLM-based commodity signal scorer — supports OpenAI and Groq."""
from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from typing import TypeVar

from app.config import (
    GROQ_API_KEY,
    LLM_MODEL,
    LLM_PROVIDER,
    MAX_RETRIES,
    OPENAI_API_KEY,
    RETRY_BASE_DELAY,
)
from app.cost.tracker import log_cost
from app.llm.prompts import FEW_SHOT_MESSAGES_FUNCTION, SYSTEM_PROMPT, TOOL_SCHEMA_OPENAI
from app.models import Signal, Transcript

logger = logging.getLogger(__name__)
T = TypeVar("T")


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def _normalize_loose(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", text.lower())).strip()


def _quote_supported_by_transcript(quote: str, transcript_text: str) -> bool:
    normalized_transcript = _normalize_whitespace(transcript_text)
    normalized_quote = _normalize_whitespace(quote)
    if normalized_quote in normalized_transcript:
        return True

    loose_transcript = _normalize_loose(transcript_text)
    loose_quote = _normalize_loose(quote)
    if loose_quote and loose_quote in loose_transcript:
        return True

    fragments = [
        _normalize_loose(fragment)
        for fragment in re.split(r"\.\.\.|…", quote)
        if _normalize_loose(fragment)
    ]
    if len(fragments) > 1:
        start = 0
        for fragment in fragments:
            position = loose_transcript.find(fragment, start)
            if position == -1:
                return False
            start = position + len(fragment)
        return True

    return False


def _build_user_message(transcript: Transcript) -> str:
    if transcript.speaker_segments:
        speaker_text = "\n".join(
            f"[{seg.speaker}] {seg.text}" for seg in transcript.speaker_segments
        )
    else:
        speaker_text = transcript.text

    return (
        f"Analyze this transcript segment (chunk_id={transcript.chunk_id}, "
        f"starts at {transcript.chunk_start_seconds:.1f}s):\n\n"
        f'"{speaker_text}"'
    )


def _request_with_backoff(
    provider_name: str,
    request_fn: Callable[[], T],
) -> T:
    """Retry transient provider errors with exponential backoff."""
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            return request_fn()
        except Exception as e:
            last_error = e
            delay = RETRY_BASE_DELAY * (2 ** attempt)
            logger.warning(
                "%s error (attempt %d/%d): %s. Retrying in %.1fs",
                provider_name,
                attempt + 1,
                MAX_RETRIES,
                e,
                delay,
            )
            if attempt < MAX_RETRIES - 1:
                time.sleep(delay)
    raise RuntimeError(f"{provider_name} failed after {MAX_RETRIES} retries") from last_error


def _extract_signals(raw_signals: list[dict], transcript: Transcript) -> list[Signal]:
    from app.config import CHUNK_DURATION_SECONDS
    from app.models import MentionedEntities

    if transcript.words:
        chunk_end = max(w.end for w in transcript.words)
    else:
        chunk_end = transcript.chunk_start_seconds + CHUNK_DURATION_SECONDS

    signals: list[Signal] = []
    for raw in raw_signals:
        if not isinstance(raw, dict):
            logger.warning("LLM returned signal as %s, skipping: %s", type(raw).__name__, str(raw)[:100])
            continue
        raw.setdefault("source_chunk_id", transcript.chunk_id)
        raw.setdefault("source_timestamp_start", transcript.chunk_start_seconds)
        raw.setdefault("source_timestamp_end", chunk_end)
        quote = raw.get("raw_quote")
        if not isinstance(quote, str) or not quote.strip():
            logger.warning("Signal missing raw_quote, skipping: %s", raw)
            continue
        if not _quote_supported_by_transcript(quote, transcript.text):
            logger.warning(
                "Signal rejected: raw_quote not found verbatim in transcript. Quote: %r",
                quote[:100],
            )
            continue
        entities = raw.get("mentioned_entities")
        if entities is None:
            raw["mentioned_entities"] = MentionedEntities()
        elif isinstance(entities, dict):
            raw["mentioned_entities"] = MentionedEntities(**entities)
        try:
            signals.append(Signal(**raw))
        except Exception as e:
            logger.warning("Invalid signal from LLM, skipping: %s — %s", raw, e)
    return signals


# ---------------------------------------------------------------------------
# OpenAI backend (GPT-4o-mini)
# ---------------------------------------------------------------------------

# GPT-4o-mini pricing (per million tokens)
_OPENAI_INPUT_COST_PER_M = 0.15
_OPENAI_OUTPUT_COST_PER_M = 0.60


def _score_openai(transcript: Transcript) -> list[Signal]:
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)
    user_message = _build_user_message(transcript)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *FEW_SHOT_MESSAGES_FUNCTION,  # same OpenAI-compatible format
        {"role": "user", "content": user_message},
    ]

    response = _request_with_backoff(
        "OpenAI",
        lambda: client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            tools=[TOOL_SCHEMA_OPENAI],
            tool_choice={"type": "function", "function": {"name": "report_signals"}},
            max_tokens=2048,
            temperature=0.0,
            top_p=1.0,
        ),
    )

    input_tokens = response.usage.prompt_tokens or 0
    output_tokens = response.usage.completion_tokens or 0
    cost = (input_tokens * _OPENAI_INPUT_COST_PER_M + output_tokens * _OPENAI_OUTPUT_COST_PER_M) / 1_000_000
    log_cost("openai", input_tokens + output_tokens, cost, {
        "chunk": transcript.chunk_id,
        "model": LLM_MODEL,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    })

    signals: list[Signal] = []
    choice = response.choices[0]
    if choice.message.tool_calls:
        for tool_call in choice.message.tool_calls:
            if tool_call.function.name == "report_signals":
                data = json.loads(tool_call.function.arguments)
                signals = _extract_signals(data.get("signals", []), transcript)

    logger.info("Chunk %s: %d signals, %d+%d tokens, $%.6f (%s)",
                transcript.chunk_id, len(signals), input_tokens, output_tokens, cost, LLM_MODEL)
    return signals


# ---------------------------------------------------------------------------
# Groq (OpenAI-compatible) backend
# ---------------------------------------------------------------------------

def _score_groq(transcript: Transcript) -> list[Signal]:
    from groq import Groq

    client = Groq(api_key=GROQ_API_KEY, max_retries=0)
    user_message = _build_user_message(transcript)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *FEW_SHOT_MESSAGES_FUNCTION,
        {"role": "user", "content": user_message},
    ]

    response = _request_with_backoff(
        "Groq LLM",
        lambda: client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            tools=[TOOL_SCHEMA_OPENAI],
            tool_choice={"type": "function", "function": {"name": "report_signals"}},
            max_tokens=2048,
            temperature=0.0,
            top_p=1.0,
        ),
    )

    input_tokens = response.usage.prompt_tokens or 0
    output_tokens = response.usage.completion_tokens or 0
    log_cost("groq_llm", input_tokens + output_tokens, 0.0, {
        "chunk": transcript.chunk_id,
        "model": LLM_MODEL,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    })

    signals: list[Signal] = []
    choice = response.choices[0]
    if choice.message.tool_calls:
        for tool_call in choice.message.tool_calls:
            if tool_call.function.name == "report_signals":
                data = json.loads(tool_call.function.arguments)
                signals = _extract_signals(data.get("signals", []), transcript)

    logger.info("Chunk %s: %d signals, %d+%d tokens (groq/%s)",
                transcript.chunk_id, len(signals), input_tokens, output_tokens, LLM_MODEL)
    return signals

def score_transcript(transcript: Transcript) -> list[Signal]:
    """Score a transcript using the configured LLM provider."""
    logger.info("Scoring chunk %s (%d chars) via %s/%s",
                transcript.chunk_id, len(transcript.text), LLM_PROVIDER, LLM_MODEL)

    if LLM_PROVIDER == "groq":
        return _score_groq(transcript)
    if LLM_PROVIDER == "openai":
        return _score_openai(transcript)
    raise ValueError(f"Unsupported LLM_PROVIDER={LLM_PROVIDER!r}. Expected 'openai' or 'groq'.")
