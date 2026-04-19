# Evaluation Setup Guide

The evaluation harness in `src/app/eval/run.py` tests the LLM scorer against a set of labeled transcript excerpts. The file `fixtures/eval_cases.json` ships with **10 ready-to-use eval cases** covering bullish, bearish, and neutral scenarios across multiple commodities.

## Running the Evaluation

```bash
# Locally
GROQ_API_KEY=your_key uv run python -m app.eval.run

# In Docker
docker compose run app uv run python -m app.eval.run
```

The results will be written to `eval_report.md` in the project root.

## Running Tests

```bash
# Offline tests (no API key needed) — validates eval case structure
uv run pytest tests/test_scorer.py -k "not test_scorer_direction"

# Full tests (requires API key) — runs scorer against all eval cases
GROQ_API_KEY=your_key uv run pytest tests/test_scorer.py
```

## Eval Cases

The 10 included cases cover:

| Case | Commodity | Expected Direction | Scenario |
|---|---|---|---|
| case_01_opec_cut | crude_oil_wti | bullish | OPEC+ production cut |
| case_02_fed_hawkish | gold | bearish | Fed rate hike signal |
| case_03_fed_dovish | gold | bullish | Fed rate cut signal |
| case_04_usda_crop_damage | wheat | bullish | Drought / crop damage |
| case_05_iran_sanctions | crude_oil_brent | bullish | Oil export sanctions |
| case_06_china_demand_weak | copper | bearish | Weak China PMI |
| case_07_warm_winter | natural_gas | bearish | Mild winter forecast |
| case_08_silver_industrial | silver | bullish | Solar panel demand |
| case_09_neutral_chitchat | — | neutral | Non-commodity small talk |
| case_10_ambiguous | — | neutral | Mixed/contradictory signals |

## Customizing Eval Cases

To add or replace cases, edit `fixtures/eval_cases.json`. Each entry must match:

```json
{
  "id": "case_XX_description",
  "transcript": "2–5 sentences of financial commentary",
  "expected_commodity": "crude_oil_wti",
  "expected_direction": "bullish",
  "notes": "Brief explanation of the expected outcome"
}
```

Set `expected_commodity` to `null` for neutral/ambiguous cases where no specific commodity signal is expected.

## Suggested Sources for Additional Cases

- **OPEC** — https://www.opec.org/opec_web/en/press_room.htm
- **Federal Reserve** — https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
- **USDA WASDE** — https://www.usda.gov/oce/commodity/wasde
- **US State Dept** — https://www.state.gov/press-releases/
- **Bloomberg / CNBC** — Search YouTube for specific commodity topics

## Evaluation Metrics

The harness computes:
- **Direction accuracy** — percentage of cases where predicted direction matches expected
- **Confusion matrix** — bullish/bearish/neutral classification breakdown
- **Top misclassifications** — the 3 worst errors with case details
