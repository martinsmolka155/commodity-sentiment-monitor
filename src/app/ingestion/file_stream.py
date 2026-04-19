"""File-based audio ingestion: splits MP4 into 10s WAV chunks via ffmpeg."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from app.config import (
    CHUNK_DURATION_SECONDS,
    CHUNKS_DIR,
    FILE_MODE_REALTIME,
    INPUT_FILE,
    MAX_RETRIES,
    SAMPLE_RATE,
)
from app.sentinel import SENTINEL

logger = logging.getLogger(__name__)


def _clean_chunks_dir(chunks_dir: Path) -> None:
    """Remove old chunk files from previous runs."""
    for old_chunk in chunks_dir.glob("chunk_*.wav"):
        old_chunk.unlink()
    logger.info("Cleaned old chunks from %s", chunks_dir)


async def split_audio(input_file: str | None = None) -> Path:
    """Run ffmpeg to segment the input file into WAV chunks with retry."""
    src = Path(input_file or INPUT_FILE)
    if not src.exists():
        raise FileNotFoundError(f"Input file not found: {src}")

    chunks_dir = Path(CHUNKS_DIR)
    chunks_dir.mkdir(parents=True, exist_ok=True)
    _clean_chunks_dir(chunks_dir)

    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-ar", str(SAMPLE_RATE),
        "-ac", "1",
        "-f", "segment",
        "-segment_time", str(CHUNK_DURATION_SECONDS),
        str(chunks_dir / "chunk_%04d.wav"),
    ]

    last_error: str = ""
    for attempt in range(MAX_RETRIES):
        logger.info("Splitting audio (attempt %d/%d): %s", attempt + 1, MAX_RETRIES, " ".join(cmd))
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode == 0:
            break
        last_error = stderr.decode()
        logger.warning("ffmpeg failed (attempt %d/%d): %s", attempt + 1, MAX_RETRIES, last_error)
        await asyncio.sleep(2 ** attempt)
    else:
        raise RuntimeError(f"ffmpeg failed after {MAX_RETRIES} retries: {last_error}")

    chunk_count = len(list(chunks_dir.glob("chunk_*.wav")))
    logger.info("Created %d chunks in %s", chunk_count, chunks_dir)
    return chunks_dir


async def produce_chunks(chunk_queue: asyncio.Queue, input_file: str | None = None) -> None:
    """Split audio and feed WAV chunk paths into the queue.

    By default file mode runs as fast as possible. Set FILE_MODE_REALTIME=true
    to simulate live timing between chunks for demos.
    """
    chunks_dir = await split_audio(input_file)

    chunk_files = sorted(chunks_dir.glob("chunk_*.wav"))
    if not chunk_files:
        raise RuntimeError(f"No chunks found in {chunks_dir}")

    for i, chunk_path in enumerate(chunk_files):
        chunk_start = i * CHUNK_DURATION_SECONDS
        logger.info("Producing chunk %d (%.1fs): %s", i, chunk_start, chunk_path.name)
        await chunk_queue.put((str(chunk_path), chunk_start))
        if FILE_MODE_REALTIME and i < len(chunk_files) - 1:
            await asyncio.sleep(CHUNK_DURATION_SECONDS)

    await chunk_queue.put(SENTINEL)
    logger.info("All chunks produced, sentinel sent")
