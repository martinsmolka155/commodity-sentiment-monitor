"""Rich terminal dashboard for displaying commodity signals."""
from __future__ import annotations

import asyncio
from collections import deque
from datetime import timedelta

from rich.console import Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from app.models import Signal, Transcript

MAX_ROWS = 20

DIRECTION_ICONS = {
    "bullish": Text("▲ BULL", style="bold green"),
    "bearish": Text("▼ BEAR", style="bold red"),
    "neutral": Text("● NEUT", style="dim"),
}

TIMEFRAME_LABELS = {
    "short_term": "Short",
    "medium_term": "Medium",
}


def _confidence_bar(confidence: float) -> Text:
    """Render a confidence value as a colored bar."""
    filled = int(confidence * 10)
    bar = "█" * filled + "░" * (10 - filled)
    if confidence >= 0.8:
        style = "bold green"
    elif confidence >= 0.5:
        style = "yellow"
    else:
        style = "red"
    return Text(f"{bar} {confidence:.0%}", style=style)


def _format_time(seconds: float) -> str:
    """Format seconds offset as HH:MM:SS."""
    return str(timedelta(seconds=int(seconds)))


def _format_latency(seconds: float | None) -> str:
    """Format latency in seconds for the status panel."""
    if seconds is None:
        return "—"
    return f"{seconds:.1f}s"


def _build_status_panel(
    status: str,
    processed_chunks: int,
    zero_signal_chunks: int,
    last_chunk_id: str,
    last_transcript_preview: str,
    last_stt_latency: float | None,
    last_llm_latency: float | None,
) -> Panel:
    """Build the bottom status panel with runtime telemetry."""
    lines = [
        Text(f"Status: {status}", style="dim italic"),
        Text(
            f"Chunks processed: {processed_chunks} | Zero-signal chunks: {zero_signal_chunks}",
            style="dim",
        ),
        Text(
            "Last latencies: "
            f"STT {_format_latency(last_stt_latency)} | "
            f"LLM {_format_latency(last_llm_latency)}",
            style="dim",
        ),
        Text(f"Last chunk: {last_chunk_id}", style="dim"),
        Text(f"Last transcript: {last_transcript_preview}", style="dim"),
    ]
    return Panel(Group(*lines), border_style="grey37")


def _build_table(
    signals: deque[Signal],
    status: str,
    processed_chunks: int,
    zero_signal_chunks: int,
    last_chunk_id: str,
    last_transcript_preview: str,
    last_stt_latency: float | None,
    last_llm_latency: float | None,
) -> Layout:
    """Build a Rich Layout with signal table and runtime status panel."""
    table = Table(
        show_lines=False,
        expand=True,
        title_style="bold white on dark_red",
    )
    table.add_column("Time", style="cyan", width=10)
    table.add_column("Commodity", style="bold", width=16)
    table.add_column("Dir", width=8)
    table.add_column("Conf", width=16)
    table.add_column("Entities", width=30)
    table.add_column("Rationale", ratio=1)

    for signal in signals:
        # Format entities
        entities_parts: list[str] = []
        if signal.mentioned_entities.persons:
            entities_parts.append("👤 " + ", ".join(signal.mentioned_entities.persons[:2]))
        if signal.mentioned_entities.organizations:
            entities_parts.append("🏛 " + ", ".join(signal.mentioned_entities.organizations[:2]))
        if signal.mentioned_entities.indicators:
            entities_parts.append("📊 " + ", ".join(signal.mentioned_entities.indicators[:2]))
        entities_str = "\n".join(entities_parts) if entities_parts else "—"

        table.add_row(
            _format_time(signal.source_timestamp_start),
            signal.commodity.replace("_", " ").title(),
            DIRECTION_ICONS.get(signal.direction, Text(signal.direction)),
            _confidence_bar(signal.confidence),
            entities_str,
            signal.rationale[:60] + ("…" if len(signal.rationale) > 60 else ""),
        )

    if not signals:
        table.add_row("—", "Waiting for signals…", "", "", "", "")

    layout = Layout()
    layout.split_column(
        Layout(Panel(table, title="🔥 Commodity Sentiment Monitor", border_style="red"), name="main"),
        Layout(
            _build_status_panel(
                status,
                processed_chunks,
                zero_signal_chunks,
                last_chunk_id,
                last_transcript_preview,
                last_stt_latency,
                last_llm_latency,
            ),
            name="status",
            size=6,
        ),
    )
    return layout


class Dashboard:
    """Real-time Rich dashboard consuming signals from an asyncio queue."""

    def __init__(self, signal_queue: asyncio.Queue) -> None:
        self._queue = signal_queue
        self._signals: deque[Signal] = deque(maxlen=MAX_ROWS)
        self._status: str = "Starting pipeline..."
        self._live: Live | None = None
        self._processed_chunks = 0
        self._zero_signal_chunks = 0
        self._last_chunk_id = "—"
        self._last_transcript_preview = "—"
        self._last_stt_latency: float | None = None
        self._last_llm_latency: float | None = None

    def _render(self) -> Layout:
        return _build_table(
            self._signals,
            self._status,
            self._processed_chunks,
            self._zero_signal_chunks,
            self._last_chunk_id,
            self._last_transcript_preview,
            self._last_stt_latency,
            self._last_llm_latency,
        )

    @staticmethod
    def _preview_text(transcript: Transcript) -> str:
        text = " ".join(transcript.text.split())
        if not text:
            return "—"
        return text[:140] + ("…" if len(text) > 140 else "")

    def record_stt_result(self, transcript: Transcript, stt_latency: float) -> None:
        """Record transcript-level telemetry after STT completes."""
        self._last_chunk_id = transcript.chunk_id
        self._last_transcript_preview = self._preview_text(transcript)
        self._last_stt_latency = stt_latency
        if self._live:
            self._live.update(self._render())

    def set_status(self, status: str) -> None:
        """Update the status line (called from workers)."""
        self._status = status
        if self._live:
            self._live.update(self._render())

    def record_scoring_result(
        self,
        transcript: Transcript,
        signals: list[Signal],
        llm_latency: float,
    ) -> None:
        """Record chunk-level dashboard telemetry after scoring."""
        self._processed_chunks += 1
        if not signals:
            self._zero_signal_chunks += 1

        self._last_chunk_id = transcript.chunk_id
        self._last_transcript_preview = self._preview_text(transcript)
        self._last_llm_latency = llm_latency

        if signals:
            top = max(signals, key=lambda s: s.confidence)
            self._status = (
                f"Signal in {transcript.chunk_id}: {top.commodity} "
                f"{top.direction} ({top.confidence:.0%})"
            )
        else:
            self._status = (
                f"No signal in {transcript.chunk_id} "
                f"({self._zero_signal_chunks}/{self._processed_chunks} empty)"
            )

        if self._live:
            self._live.update(self._render())

    async def run(self) -> None:
        """Run the dashboard, refreshing on each new signal."""
        with Live(self._render(), refresh_per_second=2) as live:
            self._live = live
            while True:
                signal = await self._queue.get()
                if signal is None:
                    self._status = "Pipeline finished."
                    live.update(self._render())
                    break
                self._signals.appendleft(signal)
                self._status = f"Signal: {signal.commodity} {signal.direction} ({signal.confidence:.0%})"
                live.update(self._render())
