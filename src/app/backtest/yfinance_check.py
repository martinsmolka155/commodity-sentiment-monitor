"""Backtest signals against historical commodity prices via yfinance."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path

import yfinance as yf

from app.models import Signal

logger = logging.getLogger(__name__)

# Yahoo Finance tickers for tracked commodities
COMMODITY_TICKERS: dict[str, str] = {
    "crude_oil_wti": "CL=F",
    "crude_oil_brent": "BZ=F",
    "natural_gas": "NG=F",
    "gold": "GC=F",
    "silver": "SI=F",
    "wheat": "ZW=F",
    "corn": "ZC=F",
    "copper": "HG=F",
}

# How far ahead to check price movement
TIMEFRAME_DAYS = {
    "short_term": 3,
    "medium_term": 30,
}


def fetch_price_change(
    commodity: str,
    signal_date: datetime,
    timeframe: str,
) -> float | None:
    """Fetch the percentage price change for a commodity after a signal date.

    Returns percentage change (positive = price went up), or None if data unavailable.
    """
    ticker = COMMODITY_TICKERS.get(commodity)
    if not ticker:
        logger.warning("No ticker mapping for %s", commodity)
        return None

    days_ahead = TIMEFRAME_DAYS.get(timeframe, 3)
    start = signal_date - timedelta(days=1)
    end = signal_date + timedelta(days=days_ahead + 5)  # extra buffer for weekends

    try:
        data = yf.download(ticker, start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"), progress=False)
        if data.empty or len(data) < 2:
            logger.warning("No price data for %s (%s)", commodity, ticker)
            return None

        # Get close price on or after signal date
        signal_prices = data[data.index >= signal_date.strftime("%Y-%m-%d")]
        if signal_prices.empty:
            signal_prices = data  # fall back to all data

        close_col = "Close"
        if hasattr(signal_prices[close_col], "iloc"):
            start_price = float(signal_prices[close_col].iloc[0])
            end_price = float(signal_prices[close_col].iloc[-1])
        else:
            return None

        if start_price == 0:
            return None

        pct_change = ((end_price - start_price) / start_price) * 100
        return round(pct_change, 2)

    except Exception as e:
        logger.warning("yfinance error for %s: %s", commodity, e)
        return None


def backtest_signals(
    signals: list[Signal],
    signal_date: datetime,
) -> list[dict]:
    """Backtest a list of signals against historical prices.

    Args:
        signals: List of Signal objects to validate.
        signal_date: When the signals were generated.

    Returns:
        List of result dicts with signal info + actual price movement.
    """
    results: list[dict] = []

    for signal in signals:
        pct_change = fetch_price_change(signal.commodity, signal_date, signal.timeframe)

        if pct_change is None:
            verdict = "no_data"
        elif signal.direction == "bullish" and pct_change > 0:
            verdict = "correct"
        elif signal.direction == "bearish" and pct_change < 0:
            verdict = "correct"
        elif signal.direction == "neutral":
            verdict = "correct" if abs(pct_change) < 2.0 else "incorrect"
        else:
            verdict = "incorrect"

        results.append({
            "commodity": signal.commodity,
            "direction": signal.direction,
            "confidence": signal.confidence,
            "timeframe": signal.timeframe,
            "price_change_pct": pct_change,
            "verdict": verdict,
            "rationale": signal.rationale,
        })

        logger.info(
            "Backtest %s: predicted %s, actual %.2f%%, %s",
            signal.commodity, signal.direction, pct_change or 0, verdict,
        )

    return results


def backtest_report(results: list[dict], output_path: str = "backtest_report.md") -> None:
    """Generate a Markdown backtest report."""
    lines = [
        "# Backtest Report",
        "",
        "Comparison of predicted signal directions against actual price movements (via yfinance).",
        "",
        "| Commodity | Direction | Confidence | Price Δ% | Verdict |",
        "|---|---|---|---|---|",
    ]

    correct = 0
    total = 0
    for r in results:
        pct = f"{r['price_change_pct']:+.2f}%" if r["price_change_pct"] is not None else "N/A"
        icon = {"correct": "✅", "incorrect": "❌", "no_data": "⚠️"}.get(r["verdict"], "?")
        lines.append(
            f"| {r['commodity']} | {r['direction']} | {r['confidence']:.0%} | {pct} | {icon} {r['verdict']} |"
        )
        if r["verdict"] in ("correct", "incorrect"):
            total += 1
            if r["verdict"] == "correct":
                correct += 1

    accuracy = correct / total if total > 0 else 0
    lines.extend([
        "",
        f"**Accuracy:** {accuracy:.0%} ({correct}/{total} with data)",
        f"**No data:** {sum(1 for r in results if r['verdict'] == 'no_data')}",
        "",
    ])

    Path(output_path).write_text("\n".join(lines))
    logger.info("Backtest report written to %s", output_path)


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(sys.stderr)])
    print("Backtest module ready. Use backtest_signals() with Signal objects.")
