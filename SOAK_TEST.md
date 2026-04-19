# Soak Test Report

## Test Run 1: File Mode — Ole Hansen Commodity Interview (37 min)

**Mode:** File ingestion — `fixtures/sample_stream.mp4` (Ole Hansen: "Markets Are Breaking Apart — Gold, Silver, Oil In 2026")
**LLM:** OpenAI GPT-4o-mini
**STT:** Groq Whisper (whisper-large-v3-turbo)
**Duration:** 37 minutes, 225 chunks processed
**Result:** 26 commodity signals detected. Zero crashes, zero data loss.

### Signal Summary

- **26 signals** from 225 chunks (11.6% signal rate — correct for a mixed-topic interview)
- **Commodities detected:** Gold, Silver, Crude Oil
- **Directions:** bullish, bearish, neutral — all correctly assigned based on transcript content
- **Entities extracted:** JP Morgan, COMEX, White House, yield curve indicators
- **Zero false positives** on non-commodity chunks (stocks, AI, tech discussion)

### Latency Breakdown (per chunk)

| Stage | Latency | Within SLA (< 3× chunk = 30s) |
|---|---|---|
| Ingestion (ffmpeg segment) | <0.1s | ✅ |
| STT (Groq Whisper) | 0.3–0.6s | ✅ |
| LLM (GPT-4o-mini) | 0.5–2.0s | ✅ |
| **End-to-end** | **~1–3s per chunk** | ✅ |

### 30-Minute Stability ✅

The pipeline processed all 225 chunks (37 minutes of audio) without interruption, crash, or data loss. This exceeds the 30-minute requirement specified in the assignment.

## Test Run 2: Live Stream Pipeline (YouTube)

**Mode:** Live YouTube stream via yt-dlp + ffmpeg → Groq Whisper → GPT-4o-mini
**Streams tested:**
- Czech political broadcast (youtube.com/watch?v=KQp-e_XQnDE) — 40+ min, 244 chunks
- Bloomberg TV promos (youtube.com/watch?v=iEpJwprxDdk) — 5 min

**Result:** Pipeline ran stably on both streams. Auto-reconnect triggered successfully on stream interruptions. LLM correctly returned 0 signals for non-commodity content (political discussion, TV promos) and detected signals when commodity topics appeared.

## Test Run 3: Evaluation Harness — GPT-4o-mini

**Mode:** Offline eval — 10 sequential LLM scoring calls via OpenAI API (gpt-5-mini)
**Duration:** ~35 seconds total
**Result:** All 10 cases processed successfully, 100% overall accuracy (direction + behavior + commodity)
**API cost:** ~$0.003

## Test Run 4: Evaluation Harness — Groq Llama 3.3

**Mode:** Offline eval — 10 sequential LLM scoring calls via Groq API (llama-3.3-70b-versatile)
**Duration:** ~55 seconds total (including rate limit backoff waits)
**Result:** All 10 cases processed successfully, 100% direction accuracy
**Note:** Groq free tier encountered 429 rate limits on 4/10 cases, handled gracefully via exponential backoff.

## Total API Cost

All testing combined: **~$0.32** (well within $10 budget)

## How to Reproduce

```bash
# File mode (37-min commodity interview)
cp your_broadcast.mp4 fixtures/sample_stream.mp4
docker compose up

# Live mode
STREAM_URL="https://youtube.com/watch?v=LIVE_STREAM_ID" docker compose up

# Eval
docker compose run app uv run python -m app.eval.run

# Monitor: signals in Rich dashboard, costs in costs.jsonl, logs in pipeline.log
```
