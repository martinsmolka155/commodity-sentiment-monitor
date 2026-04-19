# Soak Test Report

## Test Run 1: Evaluation Harness — GPT-4o-mini (2026-04-19)

**Mode:** Offline eval — 10 sequential LLM scoring calls via OpenAI API (gpt-4o-mini)
**Duration:** ~35 seconds total
**Result:** All 10 cases processed successfully, 100% direction accuracy

### Key Observations

- All 10 transcripts scored correctly: 5 bullish, 3 bearish, 2 neutral
- Entity extraction (persons, indicators, organizations) worked on all cases
- Zero crashes, zero data loss, zero unhandled exceptions
- Total API cost: ~$0.003 (GPT-4o-mini)
- Average LLM latency: 0.5–0.6s per chunk (well under 3× chunk duration SLA)

## Test Run 2: Live Stream Pipeline (2026-04-19)

**Mode:** Live YouTube stream via yt-dlp + ffmpeg → Groq Whisper → GPT-4o-mini
**Stream:** Czech political broadcast (youtube.com/watch?v=KQp-e_XQnDE)
**Duration:** ~3 minutes continuous operation (16+ chunks processed)
**Result:** Pipeline ran stably. LLM correctly returned 0 signals for non-commodity content.

### Latency Breakdown (per chunk)

| Stage | Latency | Within SLA |
|---|---|---|
| Ingestion (ffmpeg segment) | real-time (10s chunks) | ✅ |
| STT (Groq Whisper) | 0.3s | ✅ (< 30s = 3× chunk) |
| LLM (GPT-4o-mini) | 0.5–0.6s | ✅ |
| **End-to-end** | **~1s per chunk** | ✅ |

## Test Run 3: Evaluation Harness — Groq Llama 3.3 (2026-04-19)

**Mode:** Offline eval — 10 sequential LLM scoring calls via Groq API (llama-3.3-70b-versatile)
**Duration:** ~55 seconds total (including rate limit backoff waits)
**Result:** All 10 cases processed successfully, 100% direction accuracy
**Note:** Groq free tier encountered 429 rate limits on 4/10 cases, handled gracefully via exponential backoff.

## 30-Minute Stability Design

The pipeline is designed for continuous 30+ minute operation:

1. **File mode:** ffmpeg segments the entire input file upfront, then feeds chunks with `asyncio.sleep(10)` between them. A 30-minute MP4 produces ~180 chunks. Each chunk is processed independently — a failure on one chunk does not affect the next.

2. **Live mode:** yt-dlp resolves the stream URL, ffmpeg reads the HLS/m3u8 directly and segments into WAV chunks in real time. `produce_chunks_live()` includes auto-reconnect with exponential backoff (up to 3 retries) on stream failure.

3. **API resilience:** All API calls (Groq STT, OpenAI LLM) include retry with exponential backoff. The pipeline successfully navigated rate limit events without interruption.

### How to Run a Full 30-Minute Test

```bash
# File mode
cp your_30min_broadcast.mp4 fixtures/sample_stream.mp4
docker compose up

# Live mode
STREAM_URL="https://youtube.com/watch?v=LIVE_STREAM_ID" docker compose up

# Monitor: signals in Rich dashboard, costs in costs.jsonl, logs in pipeline.log
```
