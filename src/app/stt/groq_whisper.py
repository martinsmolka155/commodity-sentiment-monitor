"""Groq Whisper STT: transcribes WAV chunks via Groq API."""
from __future__ import annotations

import logging
import time
from pathlib import Path

from groq import Groq

from app.config import (
    GROQ_API_KEY,
    MAX_RETRIES,
    RETRY_BASE_DELAY,
    STT_LANGUAGE,
    WHISPER_MODEL,
)
from app.cost.tracker import log_cost
from app.models import Transcript, Word

logger = logging.getLogger(__name__)

# Groq Whisper pricing: $0.04 per audio hour
COST_PER_HOUR = 0.04

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=GROQ_API_KEY)
    return _client


def transcribe_chunk(chunk_path: str, chunk_start_seconds: float) -> Transcript:
    """Transcribe a single WAV chunk using Groq Whisper API with retry."""
    client = _get_client()
    path = Path(chunk_path)
    audio_bytes = path.read_bytes()

    logger.info("Transcribing %s (offset %.1fs)", path.name, chunk_start_seconds)

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.audio.transcriptions.create(
                file=(path.name, audio_bytes, "audio/wav"),
                model=WHISPER_MODEL,
                response_format="verbose_json",
                timestamp_granularities=["word"],
                language=STT_LANGUAGE,
            )
            break
        except Exception as e:
            last_error = e
            delay = RETRY_BASE_DELAY * (2 ** attempt)
            logger.warning(
                "Groq API error (attempt %d/%d): %s. Retrying in %.1fs",
                attempt + 1, MAX_RETRIES, e, delay,
            )
            time.sleep(delay)
    else:
        raise RuntimeError(f"Groq API failed after {MAX_RETRIES} retries") from last_error

    # Extract words with global timestamps
    words: list[Word] = []
    if hasattr(response, "words") and response.words:
        for w in response.words:
            # Groq may return Word objects or dicts depending on SDK version
            if isinstance(w, dict):
                word_text = w.get("word", "")
                word_start = w.get("start", 0.0)
                word_end = w.get("end", 0.0)
            else:
                word_text = w.word
                word_start = w.start
                word_end = w.end
            words.append(Word(
                text=word_text,
                start=chunk_start_seconds + word_start,
                end=chunk_start_seconds + word_end,
            ))

    # Log cost
    duration_hours = (response.duration or 10.0) / 3600.0
    cost = duration_hours * COST_PER_HOUR
    log_cost("groq_whisper", response.duration or 10.0, cost, {"chunk": path.name})

    chunk_id = path.stem
    transcript = Transcript(
        chunk_id=chunk_id,
        chunk_start_seconds=chunk_start_seconds,
        text=response.text or "",
        words=words,
        language=response.language or STT_LANGUAGE,
    )

    logger.info("Transcribed %s: %d words, %.1fs", chunk_id, len(words), response.duration or 0)
    return transcript
