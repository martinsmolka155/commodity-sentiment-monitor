"""Pause-based speaker segmentation proxy using word-level timestamps from Whisper.

Detects speaker changes by identifying significant pauses between words.
In broadcast settings (interviews, press conferences), pauses > 1.5s typically
indicate a speaker change. This is a lightweight heuristic that assigns
alternating speaker labels after pause boundaries; it does not perform true
speaker identification. For production use, replace with pyannote-audio or a
cloud diarization API (Deepgram, AssemblyAI).
"""
from __future__ import annotations

import logging

from app.models import SpeakerSegment, Transcript, Word

logger = logging.getLogger(__name__)

# Pause threshold in seconds — gaps longer than this trigger a speaker change
PAUSE_THRESHOLD = 1.5

# Minimum words in a segment to be considered valid
MIN_SEGMENT_WORDS = 2


def detect_speaker_segments(words: list[Word]) -> list[SpeakerSegment]:
    """Segment words into pause-delimited turns based on inter-word pauses.

    Returns a list of SpeakerSegments with alternating placeholder speaker labels.
    """
    if not words:
        return []

    segments: list[SpeakerSegment] = []
    current_speaker_idx = 0
    current_words: list[Word] = [words[0]]

    for i in range(1, len(words)):
        gap = words[i].start - words[i - 1].end

        if gap >= PAUSE_THRESHOLD and len(current_words) >= MIN_SEGMENT_WORDS:
            # Pause boundary detected; treat it as a speaker-turn proxy.
            segments.append(_build_segment(current_words, current_speaker_idx))
            current_speaker_idx += 1
            current_words = [words[i]]
        else:
            current_words.append(words[i])

    # Final segment
    if current_words:
        segments.append(_build_segment(current_words, current_speaker_idx))

    # Normalize speaker IDs — merge consecutive same-length segments that are
    # likely the same speaker (heuristic: reuse IDs for alternating pattern)
    if len(segments) > 1:
        segments = _assign_alternating_speakers(segments)

    logger.info(
        "Pause segmentation: %d words → %d segments, %d labels",
        len(words),
        len(segments),
        len({s.speaker for s in segments}),
    )
    return segments


def _build_segment(words: list[Word], speaker_idx: int) -> SpeakerSegment:
    """Build a SpeakerSegment from a list of words."""
    text = " ".join(w.text for w in words)
    return SpeakerSegment(
        speaker=f"SPEAKER_{speaker_idx}",
        start=words[0].start,
        end=words[-1].end,
        text=text,
    )


def _assign_alternating_speakers(segments: list[SpeakerSegment]) -> list[SpeakerSegment]:
    """Reassign speaker labels assuming an alternating A/B pattern.

    In most broadcast scenarios (interview, press conference Q&A),
    there are 2-3 speakers alternating. This assigns placeholder labels
    SPEAKER_0, SPEAKER_1, etc. by cycling through detected pause boundaries.
    """
    for i, seg in enumerate(segments):
        # Simple alternating pattern for 2 speakers
        speaker_id = i % 2
        segments[i] = seg.model_copy(update={"speaker": f"SPEAKER_{speaker_id}"})
    return segments


def enrich_transcript(transcript: Transcript) -> Transcript:
    """Add pause-based speaker segmentation info to a transcript."""
    if not transcript.words:
        return transcript

    segments = detect_speaker_segments(transcript.words)

    # Tag individual words with their speaker
    enriched_words: list[Word] = []
    seg_idx = 0
    for word in transcript.words:
        speaker = None
        while seg_idx < len(segments):
            seg = segments[seg_idx]
            if word.start >= seg.start and word.end <= seg.end + 0.1:
                speaker = seg.speaker
                break
            elif word.start > seg.end:
                seg_idx += 1
            else:
                speaker = segments[seg_idx].speaker if seg_idx < len(segments) else None
                break
        enriched_words.append(word.model_copy(update={"speaker": speaker}))

    return transcript.model_copy(update={
        "words": enriched_words,
        "speaker_segments": segments,
    })
