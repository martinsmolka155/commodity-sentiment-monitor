"""Evaluation harness: loads eval cases, runs scorer, computes accuracy."""
from __future__ import annotations

import json
import logging
import sys
import time
from collections import Counter
from pathlib import Path

from app.config import EVAL_THROTTLE_SEC
from app.llm.scorer import score_transcript
from app.models import EvalCase, Transcript

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)

EVAL_CASES_PATH = Path("fixtures/eval_cases.json")
EVAL_REPORT_PATH = Path("eval_report.md")

PLACEHOLDER_PREFIX = "[PLACEHOLDER"


def load_eval_cases() -> list[EvalCase]:
    """Load eval cases from JSON fixture."""
    raw = json.loads(EVAL_CASES_PATH.read_text())
    return [EvalCase(**case) for case in raw]


def _make_transcript(case: EvalCase) -> Transcript:
    """Wrap eval case transcript text into a Transcript object."""
    return Transcript(
        chunk_id=f"eval_{case.id}",
        chunk_start_seconds=0.0,
        text=case.transcript,
        words=[],
        language="en",
    )


def run_eval() -> None:
    """Run evaluation over all non-placeholder cases and generate report."""
    cases = load_eval_cases()

    # Filter out placeholder cases
    active_cases = [c for c in cases if not c.transcript.startswith(PLACEHOLDER_PREFIX)]

    if not active_cases:
        logger.warning("All eval cases are placeholders. See docs/eval_setup.md to add real transcripts.")
        _write_placeholder_report(cases)
        return

    logger.info("Running eval on %d/%d cases", len(active_cases), len(cases))

    results: list[dict] = []
    correct = 0
    total = 0
    direction_correct = 0
    behavior_correct = 0
    commodity_correct = 0
    commodity_total = 0
    confusion: Counter = Counter()

    for i, case in enumerate(active_cases):
        logger.info("Evaluating: %s (%d/%d)", case.id, i + 1, len(active_cases))
        transcript = _make_transcript(case)
        signals = score_transcript(transcript)
        if i < len(active_cases) - 1 and EVAL_THROTTLE_SEC > 0:
            time.sleep(EVAL_THROTTLE_SEC)

        # Determine predicted direction
        top_confidence: float | None = None
        if not signals:
            predicted_behavior = "empty"
            predicted_direction = "neutral"
            predicted_commodity = None
        else:
            top_signal = max(signals, key=lambda s: s.confidence)
            predicted_behavior = "neutral_signal" if top_signal.direction == "neutral" else "directional"
            predicted_direction = top_signal.direction
            predicted_commodity = top_signal.commodity
            top_confidence = top_signal.confidence

        is_behavior_correct = predicted_behavior == case.expected_behavior
        is_direction_correct = predicted_direction == case.expected_direction
        if case.expected_commodity is None:
            is_commodity_correct = predicted_commodity is None
        else:
            commodity_total += 1
            is_commodity_correct = predicted_commodity == case.expected_commodity

        if is_behavior_correct:
            behavior_correct += 1
        if is_direction_correct:
            direction_correct += 1
        if case.expected_commodity is not None and is_commodity_correct:
            commodity_correct += 1

        is_correct = is_behavior_correct and is_direction_correct and is_commodity_correct
        if is_correct:
            correct += 1
        total += 1

        confusion[(case.expected_direction, predicted_direction)] += 1

        # Collect extracted entities from all signals
        all_persons: list[str] = []
        all_indicators: list[str] = []
        all_orgs: list[str] = []
        for s in signals:
            all_persons.extend(s.mentioned_entities.persons)
            all_indicators.extend(s.mentioned_entities.indicators)
            all_orgs.extend(s.mentioned_entities.organizations)

        results.append({
            "id": case.id,
            "expected_behavior": case.expected_behavior,
            "predicted_behavior": predicted_behavior,
            "expected_direction": case.expected_direction,
            "predicted_direction": predicted_direction,
            "expected_commodity": case.expected_commodity,
            "predicted_commodity": predicted_commodity,
            "behavior_correct": is_behavior_correct,
            "direction_correct": is_direction_correct,
            "commodity_correct": is_commodity_correct,
            "correct": is_correct,
            "num_signals": len(signals),
            "top_confidence": top_confidence,
            "persons": list(set(all_persons)),
            "indicators": list(set(all_indicators)),
            "organizations": list(set(all_orgs)),
            "notes": case.notes,
        })

    accuracy = correct / total if total > 0 else 0.0
    direction_accuracy = direction_correct / total if total > 0 else 0.0
    behavior_accuracy = behavior_correct / total if total > 0 else 0.0
    commodity_accuracy = commodity_correct / commodity_total if commodity_total > 0 else 0.0

    # Generate report
    _write_report(
        results,
        accuracy,
        direction_accuracy,
        behavior_accuracy,
        commodity_accuracy,
        confusion,
        len(cases),
        len(active_cases),
        commodity_total,
    )
    logger.info("Eval complete. Accuracy: %.1f%% (%d/%d)", accuracy * 100, correct, total)
    logger.info("Report written to %s", EVAL_REPORT_PATH)


def _write_report(
    results: list[dict],
    accuracy: float,
    direction_accuracy: float,
    behavior_accuracy: float,
    commodity_accuracy: float,
    confusion: Counter,
    total_cases: int,
    active_cases: int,
    commodity_total: int,
) -> None:
    """Write evaluation report as Markdown."""
    lines = [
        "# Evaluation Report",
        "",
        f"**Cases evaluated:** {active_cases}/{total_cases}",
        f"**Overall accuracy:** {accuracy:.1%} ({sum(1 for r in results if r['correct'])}/{active_cases})",
        f"**Direction accuracy:** {direction_accuracy:.1%} ({sum(1 for r in results if r['direction_correct'])}/{active_cases})",
        f"**Behavior accuracy:** {behavior_accuracy:.1%} ({sum(1 for r in results if r['behavior_correct'])}/{active_cases})",
        f"**Commodity accuracy:** {commodity_accuracy:.1%} ({sum(1 for r in results if r['commodity_correct'] and r['expected_commodity'] is not None)}/{commodity_total})",
        "",
        "## Results",
        "",
        "| Case | Exp. Behavior | Pred. Behavior | Exp. Commodity | Pred. Commodity | Exp. Direction | Pred. Direction | Match | Confidence | Signals |",
        "|------|---------------|----------------|----------------|-----------------|----------------|-----------------|-------|------------|---------|",
    ]

    for r in results:
        match = "✅" if r["correct"] else "❌"
        conf = f"{r['top_confidence']:.2f}" if r["top_confidence"] is not None else "—"
        lines.append(
            f"| {r['id']} | {r['expected_behavior']} | {r['predicted_behavior']} | "
            f"{r['expected_commodity'] or '—'} | {r['predicted_commodity'] or '—'} | "
            f"{r['expected_direction']} | {r['predicted_direction']} | {match} | {conf} | {r['num_signals']} |"
        )

    lines.extend(["", "## Confusion Matrix", ""])
    directions = ["bullish", "bearish", "neutral"]
    lines.append("| Expected \\ Predicted | " + " | ".join(directions) + " |")
    lines.append("|---|" + "|".join(["---"] * len(directions)) + "|")
    for expected in directions:
        row = [str(confusion.get((expected, pred), 0)) for pred in directions]
        lines.append(f"| {expected} | " + " | ".join(row) + " |")

    # Top misclassifications
    misses = [r for r in results if not r["correct"]]
    if misses:
        lines.extend(["", "## Top Misclassifications", ""])
        for r in misses[:3]:
            lines.append(f"- **{r['id']}**: expected {r['expected_direction']}, "
                         f"got {r['predicted_direction']}. Notes: {r['notes']}")

    # Extracted entities summary
    lines.extend(["", "## Extracted Entities", ""])
    lines.append("| Case | Persons | Indicators | Organizations |")
    lines.append("|------|---------|------------|---------------|")
    for r in results:
        persons = ", ".join(r.get("persons", [])) or "—"
        indicators = ", ".join(r.get("indicators", [])[:3]) or "—"
        orgs = ", ".join(r.get("organizations", [])) or "—"
        lines.append(f"| {r['id']} | {persons} | {indicators} | {orgs} |")

    # Error analysis
    lines.extend(["", "## Error Analysis", ""])
    if not misses:
        lines.append("No misclassifications in this run. Behavior, direction, and commodity labels all matched ground truth.")
        lines.append("")
        lines.append("### Expected Failure Modes")
        lines.append("")
        lines.append("While the current eval achieves 100% accuracy, the following scenarios are expected to be challenging in production:")
        lines.append("")
        lines.append("1. **Mixed signals** — Transcripts containing both bullish and bearish factors for the same commodity (e.g., supply cuts + demand weakness). The model must weigh competing signals and may default to neutral when a directional call is warranted.")
        lines.append("2. **Weak/implicit context** — Indirect macro references (e.g., 'the dollar is strengthening') that imply commodity impact without naming a specific commodity. Requires economic reasoning beyond surface-level keyword matching.")
        lines.append("3. **STT transcription errors** — Whisper may mishear commodity names, numbers, or proper nouns (e.g., 'Brent' → 'Brett'), leading to missed or incorrect entity extraction.")
        lines.append("4. **Neutral vs. weak signal boundary** — Low-confidence signals (0.3–0.5) where the transcript hints at a direction but lacks conviction. The calibration threshold between 'report as weak signal' and 'classify as neutral' is subjective.")
        lines.append("5. **Multi-commodity interactions** — A single statement may affect multiple commodities in different directions (e.g., 'trade war escalation' → bearish copper, bullish gold). The model must correctly decompose these.")
    else:
        lines.append(f"**{len(misses)} misclassification(s)** out of {active_cases} cases.")
        lines.append("")
        for r in misses:
            lines.append(f"- **{r['id']}**: Expected {r['expected_direction']}, predicted {r['predicted_direction']}. "
                         f"The model may have {'over-detected a signal' if r['expected_direction'] == 'neutral' else 'missed the directional cue'}. "
                         f"Notes: {r['notes']}")

    # Recommendations
    lines.extend(["", "## Recommendations for Improvement", ""])
    lines.append("1. **Expand eval dataset** — Add 50+ cases from real broadcast recordings to test edge cases (mixed signals, implicit macro, multi-language).")
    lines.append("2. **Confidence calibration** — Apply Platt scaling or isotonic regression on accumulated predictions to improve confidence score reliability.")
    lines.append("3. **STT error injection** — Test scorer robustness by introducing realistic transcription errors (typos, homophones, dropped words).")
    lines.append("4. **Cross-model validation** — Periodically compare the primary scorer against a second model family to catch prompt drift and single-model bias.")
    lines.append("5. **Temporal context** — Feed previous chunk summaries to the scorer so it can track evolving narratives across a broadcast.")

    lines.append("")
    EVAL_REPORT_PATH.write_text("\n".join(lines))


def _write_placeholder_report(cases: list[EvalCase]) -> None:
    """Write a report noting that all cases are placeholders."""
    lines = [
        "# Evaluation Report",
        "",
        f"**Total cases:** {len(cases)}",
        "**Status:** All cases contain placeholder transcripts.",
        "",
        "To run a real evaluation, replace the placeholder transcripts in",
        "`fixtures/eval_cases.json` with real quotes from financial broadcasts.",
        "See `docs/eval_setup.md` for instructions.",
        "",
    ]
    EVAL_REPORT_PATH.write_text("\n".join(lines))
    logger.info("Placeholder report written to %s", EVAL_REPORT_PATH)


if __name__ == "__main__":
    run_eval()
