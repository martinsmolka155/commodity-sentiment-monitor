"""Entry point: wires up the ingestion → STT → LLM → dashboard pipeline."""
from __future__ import annotations

import asyncio
import logging
import sys
import time
from pathlib import Path

from app.config import ENABLE_DIARIZATION, INPUT_FILE, STREAM_URL
from app.cost.tracker import total_cost
from app.dashboard.rich_ui import Dashboard
from app.diarization.pause_based import enrich_transcript
from app.ingestion.file_stream import produce_chunks
from app.ingestion.live_stream import produce_chunks_live
from app.llm.scorer import score_transcript
from app.notifications.slack import send_signal_alert, should_notify
from app.sentinel import SENTINEL
from app.stt.groq_whisper import transcribe_chunk

LOG_FILE = "pipeline.log"


def _setup_logging() -> None:
    """Configure logging to file only (keeps terminal clean for Rich dashboard)."""
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Remove any existing handlers
    root.handlers.clear()
    # File handler only
    fh = logging.FileHandler(LOG_FILE, mode="w")
    fh.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s"))
    root.addHandler(fh)
    # Also log to stderr if not a TTY (e.g. Docker without tty, CI)
    if not sys.stderr.isatty():
        sh = logging.StreamHandler(sys.stderr)
        sh.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s"))
        root.addHandler(sh)


logger = logging.getLogger(__name__)


async def stt_worker(
    chunk_queue: asyncio.Queue,
    transcript_queue: asyncio.Queue,
    dashboard: Dashboard,
) -> None:
    """Consume WAV chunk paths, transcribe via Groq, produce Transcripts."""
    while True:
        dashboard.set_status("Waiting for next audio chunk...")
        item = await chunk_queue.get()
        if item is SENTINEL:
            await transcript_queue.put(SENTINEL)
            break
        chunk_path, chunk_start = item
        dashboard.set_status(f"Transcribing {Path(chunk_path).name}...")
        try:
            t0 = time.monotonic()
            transcript = await asyncio.to_thread(transcribe_chunk, chunk_path, chunk_start)
            stt_latency = time.monotonic() - t0
            if ENABLE_DIARIZATION:
                transcript = enrich_transcript(transcript)
            dashboard.record_stt_result(transcript, stt_latency)
            await transcript_queue.put(transcript)
            logger.info("STT done: %s (%d words, %.1fs latency)", transcript.chunk_id, len(transcript.words), stt_latency)
        except Exception:
            logger.exception("STT failed for %s", chunk_path)


async def llm_worker(
    transcript_queue: asyncio.Queue,
    signal_queue: asyncio.Queue,
    dashboard: Dashboard,
) -> None:
    """Consume Transcripts, score via LLM, produce Signals."""
    while True:
        transcript = await transcript_queue.get()
        if transcript is SENTINEL:
            await signal_queue.put(None)
            break
        dashboard.set_status(f"Scoring {transcript.chunk_id}...")
        try:
            t0 = time.monotonic()
            signals = await asyncio.to_thread(score_transcript, transcript)
            llm_latency = time.monotonic() - t0
            dashboard.record_scoring_result(transcript, signals, llm_latency)
            for signal in signals:
                await signal_queue.put(signal)
                if should_notify(signal):
                    await asyncio.to_thread(send_signal_alert, signal)
            logger.info("LLM done: %s → %d signals (%.1fs latency)", transcript.chunk_id, len(signals), llm_latency)
        except Exception:
            logger.exception("LLM scoring failed for %s", transcript.chunk_id)


async def run_pipeline() -> None:
    """Wire up and run the full pipeline."""
    _setup_logging()

    # Determine ingestion mode
    if STREAM_URL:
        logger.info("Starting LIVE stream pipeline: %s", STREAM_URL)
        ingestion_mode = "live"
    else:
        if not Path(INPUT_FILE).exists():
            logger.error("Input file not found: %s", INPUT_FILE)
            print(
                f"Error: {INPUT_FILE} not found.\n\n"
                "Either:\n"
                "  1. Place an MP4 file:  cp your_file.mp4 fixtures/sample_stream.mp4\n"
                "  2. Use a live stream:  STREAM_URL=https://youtube.com/watch?v=... uv run python -m app.main"
            )
            return
        logger.info("Starting FILE pipeline: %s", INPUT_FILE)
        ingestion_mode = "file"

    chunk_queue: asyncio.Queue = asyncio.Queue(maxsize=5)
    transcript_queue: asyncio.Queue = asyncio.Queue(maxsize=5)
    signal_queue: asyncio.Queue = asyncio.Queue(maxsize=50)

    dashboard = Dashboard(signal_queue)

    # Select ingestion worker based on mode
    if ingestion_mode == "live":
        dashboard.set_status(f"Connecting to stream: {STREAM_URL[:60]}...")
        ingestion_task = asyncio.create_task(
            produce_chunks_live(chunk_queue, STREAM_URL), name="ingestion-live"
        )
    else:
        dashboard.set_status(f"Splitting {Path(INPUT_FILE).name} into chunks...")
        ingestion_task = asyncio.create_task(
            produce_chunks(chunk_queue), name="ingestion-file"
        )

    tasks = [
        ingestion_task,
        asyncio.create_task(stt_worker(chunk_queue, transcript_queue, dashboard), name="stt"),
        asyncio.create_task(llm_worker(transcript_queue, signal_queue, dashboard), name="llm"),
        asyncio.create_task(dashboard.run(), name="dashboard"),
    ]

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        logger.info("Pipeline cancelled, shutting down gracefully")
        for t in tasks:
            t.cancel()
    finally:
        cost = total_cost()
        logger.info("Pipeline finished. Total API cost: $%.4f", cost)


def main() -> None:
    """CLI entry point."""
    try:
        asyncio.run(run_pipeline())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
