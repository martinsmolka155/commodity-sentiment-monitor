"""Live stream ingestion: captures audio from a URL via yt-dlp + ffmpeg segmentation."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from app.config import CHUNK_DURATION_SECONDS, CHUNKS_DIR, MAX_RETRIES, RETRY_BASE_DELAY, SAMPLE_RATE
from app.sentinel import SENTINEL

logger = logging.getLogger(__name__)


async def _resolve_stream_url(url: str) -> str:
    """Use yt-dlp to resolve a page URL to a direct stream URL.

    For live streams, picks the lowest quality format (audio only or lowest muxed)
    to minimize bandwidth. Returns the direct URL that ffmpeg can consume.
    """
    # Try audio-only first, fall back to worst quality muxed
    for fmt in ("ba", "worst"):
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp", "--no-warnings", "-f", fmt, "--get-url", url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0 and stdout.strip():
            resolved = stdout.decode().strip().split("\n")[0]
            logger.info("Resolved stream URL (format=%s): %s...%s", fmt, resolved[:60], resolved[-30:])
            return resolved
        logger.debug("yt-dlp format %s failed: %s", fmt, stderr.decode()[:100])

    # If yt-dlp can't resolve, try the URL directly (might be a direct HLS/RTMP URL)
    logger.warning("yt-dlp could not resolve URL, trying direct: %s", url)
    return url


async def _wait_for_chunk(chunks_dir: Path, chunk_index: int, timeout: float = 60.0) -> Path | None:
    """Wait for a specific chunk file to appear on disk."""
    chunk_name = f"live_{chunk_index:04d}.wav"
    chunk_path = chunks_dir / chunk_name
    elapsed = 0.0
    interval = 0.5
    while elapsed < timeout:
        if chunk_path.exists() and chunk_path.stat().st_size > 0:
            # Give ffmpeg a brief flush window so the segment file is fully closed on disk.
            await asyncio.sleep(0.3)
            return chunk_path
        await asyncio.sleep(interval)
        elapsed += interval
    return None


async def produce_chunks_live(
    chunk_queue: asyncio.Queue,
    stream_url: str,
) -> None:
    """Capture a live stream URL and produce WAV chunks in real time.

    Uses yt-dlp to resolve the stream URL, then ffmpeg reads it directly
    (supporting HLS/m3u8, RTMP, and direct URLs). Audio is segmented
    into WAV chunks on disk.

    Implements auto-reconnect with exponential backoff on stream failure.
    """
    chunks_dir = Path(CHUNKS_DIR)
    chunks_dir.mkdir(parents=True, exist_ok=True)
    for old_chunk in chunks_dir.glob("live_*.wav"):
        old_chunk.unlink()

    chunk_index = 0
    consecutive_failures = 0

    while consecutive_failures < MAX_RETRIES:
        logger.info("Connecting to stream: %s (attempt %d)", stream_url, consecutive_failures + 1)

        # Resolve page URL to direct stream URL via yt-dlp
        direct_url = await _resolve_stream_url(stream_url)

        # ffmpeg reads the direct URL (HLS/m3u8) and segments into WAV
        output_pattern = str(chunks_dir / "live_%04d.wav")
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-i", direct_url,
            "-vn",  # discard video
            "-ar", str(SAMPLE_RATE),
            "-ac", "1",
            "-f", "segment",
            "-segment_time", str(CHUNK_DURATION_SECONDS),
            "-segment_start_number", str(chunk_index),
            output_pattern,
        ]

        proc = None
        try:
            proc = await asyncio.create_subprocess_exec(
                *ffmpeg_cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )

            logger.info("Stream connected, producing chunks from index %d", chunk_index)
            consecutive_failures = 0

            while proc.returncode is None:
                chunk_path = await _wait_for_chunk(chunks_dir, chunk_index, timeout=CHUNK_DURATION_SECONDS * 3)
                if chunk_path is None:
                    if proc.returncode is not None:
                        break
                    logger.warning("Timeout waiting for chunk %d; restarting stream reader", chunk_index)
                    if proc.returncode is None:
                        proc.kill()
                        await proc.wait()
                    consecutive_failures += 1
                    break

                chunk_start = chunk_index * CHUNK_DURATION_SECONDS
                logger.info("Live chunk %d (%.1fs): %s", chunk_index, chunk_start, chunk_path.name)
                await chunk_queue.put((str(chunk_path), chunk_start))
                chunk_index += 1

            await proc.wait()

            if proc.returncode == 0:
                logger.info("Stream ended normally")
                break
            else:
                stderr_data = await proc.stderr.read() if proc.stderr else b""
                logger.warning("ffmpeg exited %d: %s", proc.returncode, stderr_data.decode()[:300])
                consecutive_failures += 1

        except Exception as e:
            logger.exception("Stream error: %s", e)
            consecutive_failures += 1
            if proc and proc.returncode is None:
                proc.kill()

        if consecutive_failures < MAX_RETRIES:
            delay = RETRY_BASE_DELAY * (2 ** (consecutive_failures - 1))
            logger.info("Reconnecting in %.1fs (attempt %d/%d)", delay, consecutive_failures + 1, MAX_RETRIES)
            await asyncio.sleep(delay)

    if consecutive_failures >= MAX_RETRIES:
        logger.error("Stream failed after %d reconnection attempts", MAX_RETRIES)

    await chunk_queue.put(SENTINEL)
    logger.info("Live stream producer finished, sentinel sent")
