# Commodity Sentiment Monitor — Technical Document

## 1. Architecture Overview

The system is a real-time pipeline that ingests audio from live streams or local files, transcribes speech, extracts commodity-relevant signals via LLM analysis, and displays results in a terminal dashboard.

```
┌──────────────┐  WAV chunks  ┌──────────────┐  Transcript   ┌──────────────┐  Signals    ┌─────────────┐
│ Ingestion    │─────────────▶│ Groq Whisper │──────────────▶│ LLM Scorer   │────────────▶│ Rich UI     │
│ yt-dlp+ffmpeg│  asyncio.Q   │ STT worker   │  asyncio.Q    │ tool_use     │  asyncio.Q  │ Live Table  │
└──────────────┘              └──────────────┘               └──────────────┘             └─────────────┘
       │                             │                              │                           │
  STREAM_URL                   word timestamps               Slack webhook              20 most recent
  or INPUT_FILE                + diarization                (conf ≥ 0.8)                  signals
```

### Component Responsibilities

| Component | Module | Responsibility |
|---|---|---|
| Ingestion | `ingestion/file_stream.py`, `ingestion/live_stream.py` | Accept URL or file, segment into WAV chunks, feed async queue |
| STT | `stt/groq_whisper.py` | Transcribe audio with word-level timestamps via Groq Whisper API |
| Diarization | `diarization/pause_based.py` | Segment transcript by speaker using pause detection |
| LLM Scorer | `llm/scorer.py`, `llm/prompts.py` | Extract commodity signals via structured tool calling |
| Dashboard | `dashboard/rich_ui.py` | Real-time terminal display of signals |
| Notifications | `notifications/slack.py` | Slack webhook alerts for high-confidence signals |
| Cost Tracker | `cost/tracker.py` | Append-only JSONL log of all API costs |
| Backtest | `backtest/yfinance_check.py` | Compare predictions against actual price movements |
| Evaluation | `eval/run.py` | Offline accuracy testing with labeled transcript fixtures |

### Data Flow

1. **Ingestion** produces `(chunk_path, chunk_start_seconds)` tuples into `chunk_queue`
2. **STT worker** consumes chunks, produces `Transcript` objects (with `Word` list and optional `SpeakerSegment` list) into `transcript_queue`
3. **LLM worker** consumes transcripts, produces `Signal` objects into `signal_queue`
4. **Dashboard** consumes signals and renders the live table
5. A `SENTINEL` (None) propagates through all queues to signal end-of-stream

## 2. Key Design Trade-offs

### Cloud API vs. Local Models

**Decision:** Cloud APIs for both STT (Groq Whisper) and LLM (OpenAI GPT-4o-mini / Groq Llama).

**Trade-off:** Adds network dependency and API rate limits, but eliminates GPU requirements, reduces Docker image size, and enables deployment on any machine. For a demo/evaluation context, API latency (~1-2s per chunk) is acceptable. For production with strict latency SLAs, local Whisper + GPU would be preferred.

### Single LLM Call vs. Multi-Step Pipeline

**Decision:** Entity extraction + impact scoring in one structured `tool_use` / function call.

**Trade-off:** A multi-step pipeline (NER → sentiment → scoring) would allow per-step optimization and caching, but adds latency, cost, and complexity. The single-call approach keeps latency under 3s per chunk and reduces cost by ~60% vs. two separate calls. The structured output schema guarantees valid JSON without post-processing.

### Direction vs. Intensity Representation

**Decision:** Represent expected market move strength indirectly via the `confidence` field rather than a separate `impact_strength` output.

**Trade-off:** The assignment asks for direction and intensity at a high level, but its required output schema explicitly requests `confidence` and does not require a separate magnitude field. In this implementation, `confidence` is therefore used as the practical proxy for intensity: higher confidence implies a stronger and clearer expected directional impact. A production variant could add an explicit impact magnitude label if downstream consumers need separate calibration for conviction vs. move size.

### Pause-Based Diarization vs. Neural Models

**Decision:** Heuristic pause-based speaker segmentation based on >1.5s pauses in word timestamps.

**Trade-off:** Neural diarization (pyannote-audio) would be significantly more accurate, especially for overlapping speech, but requires ~2GB of model downloads and GPU for real-time performance. The current implementation is only a lightweight proxy: it treats long pauses as turn boundaries and assigns alternating placeholder speaker labels. That is useful for cleaner transcript structure in interviews and briefings, but it does not perform true speaker identification.

### Groq Free Tier vs. Paid APIs

**Decision:** Default to Groq (Llama 3.3 70B + Whisper) on the free tier.

**Trade-off:** The Groq free tier has rate limits (~30 req/min for LLM) which limit throughput for high-volume streams. OpenAI provides a more stable default path for evaluation and demo use, while Groq remains a low-cost alternative. The architecture supports switching providers via a single environment variable.

## 3. Production Improvements

### Scalability

- **Horizontal worker scaling** — STT and LLM workers can be scaled independently. The `asyncio.Queue` interface would be replaced with a distributed queue (Redis Streams, Kafka) for multi-process/multi-node deployment.
- **Kubernetes deployment** — Each pipeline stage as a separate Deployment with HPA based on queue depth.
- **Chunk parallelism** — Process multiple chunks simultaneously rather than sequentially. Current architecture already supports this by increasing `maxsize` of queues and running multiple worker tasks.

### Monitoring & SLA

- **Prometheus metrics** — Expose: chunks_processed_total, transcription_latency_seconds, scoring_latency_seconds, signals_generated_total, api_cost_usd_total, queue_depth.
- **Alerting** — PagerDuty/OpsGenie alerts on: pipeline stall (no chunks processed for 5 minutes), API error rate > 10%, cost exceeding threshold.
- **SLA targets** — End-to-end latency from audio chunk to signal display: <15 seconds (current: ~5-8s). Uptime: 99.9% with automatic stream reconnection.
- **Health checks** — HTTP endpoint exposing pipeline status, last chunk timestamp, and queue depths for load balancer integration.

### Reliability

- **Persistent queue** — Replace in-memory `asyncio.Queue` with Redis or RabbitMQ for crash recovery. If the LLM worker crashes, unprocessed transcripts are not lost.
- **Exactly-once processing** — Chunk IDs enable deduplication. Each chunk is assigned a deterministic ID based on stream + offset, preventing reprocessing after restart.
- **Graceful shutdown** — On SIGTERM, stop accepting new chunks, drain in-flight work, flush cost log, then exit. Current implementation handles `CancelledError` but could be improved with a proper shutdown coordinator.

### Security

- **API key rotation** — Secrets should be managed via a vault (HashiCorp Vault, AWS Secrets Manager), not environment variables in production.
- **Network isolation** — Pipeline workers should run in a private subnet with egress-only access to API endpoints.
- **Input validation** — Stream URLs should be validated against an allowlist of trusted sources to prevent SSRF.
- **Audit logging** — All API calls and their costs are already logged to `costs.jsonl`. In production, this should go to a centralized logging system (ELK, Datadog).

### Accuracy

- **Confidence calibration** — Post-hoc calibration using Platt scaling or isotonic regression on historical prediction accuracy. Current confidence scores are uncalibrated LLM estimates.
- **Cross-model validation** — Periodically compare the primary scorer against a second model family and investigate persistent disagreements.
- **Streaming overlap** — Overlapping audio windows (e.g., 10s chunks with 5s overlap) to avoid cutting sentences at chunk boundaries, which can lose context.
- **Backtesting feedback loop** — Use yfinance backtest results to fine-tune prompt calibration thresholds.
- **spaCy prefilter / normalizer** — spaCy would likely help as a lightweight support layer rather than a core reasoning engine: prefilter obviously irrelevant chunks, normalize aliases (`Fed` → `Federal Reserve`, `WTI` → `crude_oil_wti`), and extract candidate entities before LLM scoring. This would reduce cost and noise, but would not by itself solve the harder economic reasoning cases.
- **RAG-lite grounding** — A small retrieval layer would likely improve the project more than full rule-based NLP. The most promising variant is not generic web retrieval, but a curated knowledge base plus recent chunk summaries: commodity/entity mappings, macro-to-commodity relationships, and short rolling context from previous chunks. This would help on implicit signals, mixed evidence, and multi-commodity interactions without replacing the existing scorer.

## 4. Evaluation Methodology

The evaluation harness tests the LLM scorer's ability to correctly classify commodity signals from transcript excerpts.

**Dataset:** 10 labeled cases covering 8 commodities, 3 directions (bullish/bearish/neutral), and 3 output behaviors (`empty`, `neutral_signal`, `directional`), with scenarios ranging from explicit quantitative announcements to ambiguous mixed signals.

**Metrics:**
- **Overall accuracy** — behavior + direction + commodity all match expected label
- **Direction accuracy** — percentage of cases where the top-confidence signal's direction matches the expected direction
- **Behavior accuracy** — whether the system correctly returns `empty`, `neutral_signal`, or `directional`
- **Commodity accuracy** — percentage of non-empty cases where the predicted commodity matches the expected commodity
- **Confusion matrix** — 3×3 matrix of expected vs. predicted directions
- **Error analysis** — top misclassifications with case details

**Limitations:**
- The eval dataset is small (10 cases). A production evaluation would require 100+ cases with inter-annotator agreement.
- Eval transcripts are representative of real broadcast scenarios but should be augmented with verbatim recordings to test STT error resilience.
- Neutral detection is inherently harder — the model must decide that a transcript has *no* signal, which requires different reasoning than extracting a signal.
- 100% accuracy on a small curated dataset does not guarantee production accuracy. Expected failure modes include mixed signals, implicit macro reasoning, and STT artifacts (see eval_report.md for detailed error analysis).

## 5. Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| Runtime | Python 3.12, asyncio | Native async support, rich ecosystem |
| Package manager | uv | Fast, deterministic, replaces pip+poetry |
| Audio processing | ffmpeg, yt-dlp | Industry standard, broad format/protocol support |
| STT | Groq Whisper API | Free tier, fast, word-level timestamps |
| LLM | OpenAI GPT-4o-mini (default) | Structured function calling, ~$0.04/h, no rate limit issues |
| LLM (alt) | Groq Llama 3.3 | Free tier alternative |
| Data models | Pydantic v2 | Runtime validation, JSON schema generation |
| Dashboard | Rich | Zero-dependency terminal UI, works over SSH |
| Container | Docker, docker-compose | Reproducible deployment |
| Testing | pytest | Parametrized eval tests, offline structural tests |
