# Evaluation Setup Guide

The evaluation harness in `src/app/eval/run.py` tests the LLM scorer against a set of labeled transcript excerpts. The file `fixtures/eval_cases.json` ships with **10 ready-to-use eval cases** covering bullish, bearish, neutral, and empty behaviors across multiple commodities.

## Running the Evaluation

```bash
# Locally (default scorer: OpenAI)
OPENAI_API_KEY=your_key uv run python -m app.eval.run

# Or with Groq as scorer
LLM_PROVIDER=groq GROQ_API_KEY=your_key uv run python -m app.eval.run

# In Docker
docker compose run app uv run python -m app.eval.run
```

The results will be written to `eval_report.md` in the project root.

## Running Tests

```bash
# Offline tests (no API key needed) — validates eval case structure
uv run pytest tests/test_scorer.py -k "not test_scorer_direction"

# Full tests (requires API key for the configured provider) — runs scorer against all eval cases
OPENAI_API_KEY=your_key uv run pytest -m api tests/test_scorer.py
```

## Eval Cases

The 10 included cases cover:

| Case | Expected Behavior | Commodity | Expected Direction | Scenario |
|---|---|---|---|---|
| case_01_opec_cut | directional | crude_oil_brent | bullish | OPEC+ production cut |
| case_02_fed_hawkish | directional | gold | bearish | Fed rate hike signal |
| case_03_fed_dovish | directional | gold | bullish | Fed rate cut signal |
| case_04_usda_crop_damage | directional | wheat | bullish | Drought / crop damage |
| case_05_iran_sanctions | directional | crude_oil_brent | bullish | Oil export sanctions |
| case_06_china_demand_weak | directional | copper | bearish | Weak China PMI |
| case_07_warm_winter | directional | natural_gas | bearish | Mild winter forecast |
| case_08_silver_industrial | directional | silver | bullish | Solar panel demand |
| case_09_neutral_chitchat | empty | — | neutral | Non-commodity small talk |
| case_10_ambiguous | neutral_signal | crude_oil_brent | neutral | Mixed/contradictory signals |

## Customizing Eval Cases

To add or replace cases, edit `fixtures/eval_cases.json`. Each entry must match:

```json
{
  "id": "case_XX_description",
  "transcript": "2–5 sentences of financial commentary",
  "expected_behavior": "directional",
  "expected_commodity": "crude_oil_wti",
  "expected_direction": "bullish",
  "notes": "Brief explanation of the expected outcome"
}
```

Use `expected_behavior="empty"` when the scorer should return no signals. Use `expected_behavior="neutral_signal"` when the scorer should return a commodity-specific neutral signal for mixed evidence.

## Suggested Sources for Additional Cases

- **OPEC** — https://www.opec.org/opec_web/en/press_room.htm
- **Federal Reserve** — https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
- **USDA WASDE** — https://www.usda.gov/oce/commodity/wasde
- **US State Dept** — https://www.state.gov/press-releases/
- **Bloomberg / CNBC** — Search YouTube for specific commodity topics

## Evaluation Metrics

The harness computes:
- **Overall accuracy** — behavior + direction + commodity all match expected output
- **Direction accuracy** — percentage of cases where predicted direction matches expected
- **Behavior accuracy** — whether the scorer correctly returns `empty`, `neutral_signal`, or `directional`
- **Commodity accuracy** — percentage of non-empty cases where the predicted commodity matches expected
- **Confusion matrix** — bullish/bearish/neutral classification breakdown
- **Top misclassifications** — the 3 worst errors with case details
