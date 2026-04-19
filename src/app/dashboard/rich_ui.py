"""Rich terminal dashboard for displaying commodity signals."""
from __future__ import annotations

import asyncio
from collections import deque
from datetime import timedelta

from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from app.models import Signal

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


def _build_table(signals: deque[Signal], status: str) -> Layout:
    """Build a Rich Layout with signal table and status bar."""
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
        Layout(Text(f" {status}", style="dim italic"), name="status", size=1),
    )
    return layout


class Dashboard:
    """Real-time Rich dashboard consuming signals from an asyncio queue."""

    def __init__(self, signal_queue: asyncio.Queue) -> None:
        self._queue = signal_queue
        self._signals: deque[Signal] = deque(maxlen=MAX_ROWS)
        self._status: str = "Starting pipeline..."
        self._live: Live | None = None

    def set_status(self, status: str) -> None:
        """Update the status line (called from workers)."""
        self._status = status
        if self._live:
            self._live.update(_build_table(self._signals, self._status))

    async def run(self) -> None:
        """Run the dashboard, refreshing on each new signal."""
        with Live(_build_table(self._signals, self._status), refresh_per_second=2) as live:
            self._live = live
            while True:
                signal = await self._queue.get()
                if signal is None:
                    self._status = "Pipeline finished."
                    live.update(_build_table(self._signals, self._status))
                    break
                self._signals.appendleft(signal)
                self._status = f"Signal: {signal.commodity} {signal.direction} ({signal.confidence:.0%})"
                live.update(_build_table(self._signals, self._status))
