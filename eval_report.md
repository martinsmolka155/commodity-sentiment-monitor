# Evaluation Report

**Cases evaluated:** 10/10
**Overall accuracy:** 100.0% (10/10)
**Direction accuracy:** 100.0% (10/10)
**Behavior accuracy:** 100.0% (10/10)
**Commodity accuracy:** 100.0% (9/9)

## Results

| Case | Exp. Behavior | Pred. Behavior | Exp. Commodity | Pred. Commodity | Exp. Direction | Pred. Direction | Match | Confidence | Signals |
|------|---------------|----------------|----------------|-----------------|----------------|-----------------|-------|------------|---------|
| case_01_opec_cut | directional | directional | crude_oil_brent | crude_oil_brent | bullish | bullish | ✅ | 0.95 | 1 |
| case_02_fed_hawkish | directional | directional | gold | gold | bearish | bearish | ✅ | 0.85 | 1 |
| case_03_fed_dovish | directional | directional | gold | gold | bullish | bullish | ✅ | 0.85 | 1 |
| case_04_usda_crop_damage | directional | directional | wheat | wheat | bullish | bullish | ✅ | 0.88 | 1 |
| case_05_iran_sanctions | directional | directional | crude_oil_brent | crude_oil_brent | bullish | bullish | ✅ | 0.90 | 1 |
| case_06_china_demand_weak | directional | directional | copper | copper | bearish | bearish | ✅ | 0.88 | 1 |
| case_07_warm_winter | directional | directional | natural_gas | natural_gas | bearish | bearish | ✅ | 0.85 | 1 |
| case_08_silver_industrial | directional | directional | silver | silver | bullish | bullish | ✅ | 0.88 | 1 |
| case_09_neutral_chitchat | empty | empty | — | — | neutral | neutral | ✅ | — | 0 |
| case_10_ambiguous | neutral_signal | neutral_signal | crude_oil_brent | crude_oil_brent | neutral | neutral | ✅ | 0.55 | 1 |

## Confusion Matrix

| Expected \ Predicted | bullish | bearish | neutral |
|---|---|---|---|
| bullish | 5 | 0 | 0 |
| bearish | 0 | 3 | 0 |
| neutral | 0 | 0 | 2 |

## Extracted Entities

| Case | Persons | Indicators | Organizations |
|------|---------|------------|---------------|
| case_01_opec_cut | Saudi Arabia's energy minister | production cut 2 million barrels per day | OPEC+ |
| case_02_fed_hawkish | Chairman Powell | twenty five basis point, dot plot, rate hikes | Federal Reserve |
| case_03_fed_dovish | Chair | three rate cuts by year end | Federal Reserve |
| case_04_usda_crop_damage | — | ending stocks will fall to their lowest level in nine years, reduced projected yields by nearly eighteen percent | USDA |
| case_05_iran_sanctions | — | one million barrels per day | State Department |
| case_06_china_demand_weak | — | highest level since twenty twenty one, declining factory activity, copper inventories | — |
| case_07_warm_winter | — | fourteen percent above the five year average, natural gas storage levels, above average temperatures | National Weather Service |
| case_08_silver_industrial | — | industrial demand will exceed mining supply, global solar panel installations up forty two percent year over year | Silver Institute |
| case_09_neutral_chitchat | — | — | — |
| case_10_ambiguous | — | production discipline, US shale production hitting new records, disappointing demand from China | OPEC |

## Error Analysis

No misclassifications in this run. Behavior, direction, and commodity labels all matched ground truth.

### Expected Failure Modes

While the current eval achieves 100% accuracy, the following scenarios are expected to be challenging in production:

1. **Mixed signals** — Transcripts containing both bullish and bearish factors for the same commodity (e.g., supply cuts + demand weakness). The model must weigh competing signals and may default to neutral when a directional call is warranted.
2. **Weak/implicit context** — Indirect macro references (e.g., 'the dollar is strengthening') that imply commodity impact without naming a specific commodity. Requires economic reasoning beyond surface-level keyword matching.
3. **STT transcription errors** — Whisper may mishear commodity names, numbers, or proper nouns (e.g., 'Brent' → 'Brett'), leading to missed or incorrect entity extraction.
4. **Neutral vs. weak signal boundary** — Low-confidence signals (0.3–0.5) where the transcript hints at a direction but lacks conviction. The calibration threshold between 'report as weak signal' and 'classify as neutral' is subjective.
5. **Multi-commodity interactions** — A single statement may affect multiple commodities in different directions (e.g., 'trade war escalation' → bearish copper, bullish gold). The model must correctly decompose these.

## Recommendations for Improvement

1. **Expand eval dataset** — Add 50+ cases from real broadcast recordings to test edge cases (mixed signals, implicit macro, multi-language).
2. **Confidence calibration** — Apply Platt scaling or isotonic regression on accumulated predictions to improve confidence score reliability.
3. **STT error injection** — Test scorer robustness by introducing realistic transcription errors (typos, homophones, dropped words).
4. **Cross-model validation** — Periodically compare the primary scorer against a second model family to catch prompt drift and single-model bias.
5. **Temporal context** — Feed previous chunk summaries to the scorer so it can track evolving narratives across a broadcast.
