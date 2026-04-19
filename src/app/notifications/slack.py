"""Slack webhook notifications for high-confidence signals."""
from __future__ import annotations

import json
import logging
import urllib.request
import urllib.error

from app.config import SLACK_WEBHOOK_URL
from app.models import Signal

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.8

DIRECTION_EMOJI = {
    "bullish": ":chart_with_upwards_trend:",
    "bearish": ":chart_with_downwards_trend:",
    "neutral": ":white_circle:",
}


def should_notify(signal: Signal) -> bool:
    """Check if a signal meets the notification threshold."""
    return bool(SLACK_WEBHOOK_URL) and signal.confidence >= CONFIDENCE_THRESHOLD


def send_signal_alert(signal: Signal) -> None:
    """Send a Slack webhook for a high-confidence signal."""
    if not SLACK_WEBHOOK_URL:
        return

    emoji = DIRECTION_EMOJI.get(signal.direction, ":question:")
    commodity = signal.commodity.replace("_", " ").title()

    text = (
        f"{emoji} *{commodity}* — {signal.direction.upper()} "
        f"(confidence: {signal.confidence:.0%})\n"
        f">{signal.rationale}\n"
        f"_Timeframe: {signal.timeframe.replace('_', ' ')} | "
        f"Quote: \"{signal.raw_quote[:100]}\"_"
    )

    payload = json.dumps({"text": text}).encode("utf-8")

    req = urllib.request.Request(
        SLACK_WEBHOOK_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            logger.info("Slack alert sent for %s (%s)", signal.commodity, resp.status)
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        logger.warning("Slack webhook failed: %s", e)
