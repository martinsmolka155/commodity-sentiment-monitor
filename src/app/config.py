from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY: str = os.environ.get("GROQ_API_KEY", "")
OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
SLACK_WEBHOOK_URL: str = os.environ.get("SLACK_WEBHOOK_URL", "")

WHISPER_MODEL: str = "whisper-large-v3-turbo"
LLM_MODEL: str = os.environ.get("LLM_MODEL", "gpt-4o-mini")
LLM_PROVIDER: str = os.environ.get("LLM_PROVIDER", "openai")  # "openai" or "groq"

CHUNK_DURATION_SECONDS: int = int(os.environ.get("CHUNK_DURATION", "10"))
SAMPLE_RATE: int = 16000
AUDIO_CHANNELS: int = 1
FILE_MODE_REALTIME: bool = os.environ.get("FILE_MODE_REALTIME", "false").lower() == "true"

INPUT_FILE: str = os.environ.get("INPUT_FILE", "fixtures/sample_stream.mp4")
STREAM_URL: str = os.environ.get("STREAM_URL", "")
CHUNKS_DIR: str = "/tmp/chunks"

COST_LOG_PATH: str = "costs.jsonl"

STT_LANGUAGE: str = os.environ.get("STT_LANGUAGE", "en")
ENABLE_DIARIZATION: bool = os.environ.get("ENABLE_DIARIZATION", "true").lower() == "true"

MAX_RETRIES: int = 3
RETRY_BASE_DELAY: float = 1.0
EVAL_THROTTLE_SEC: float = float(os.environ.get("EVAL_THROTTLE_SEC", "0"))
