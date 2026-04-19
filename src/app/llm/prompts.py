"""System prompt, few-shot examples, and tool schema for LLM scorer."""
from __future__ import annotations

import copy
import json

SYSTEM_PROMPT = """You are a senior commodity market analyst. Your task is to analyze transcript segments from live financial broadcasts and identify only commodity-relevant price signals.

## Tracked Commodities (use these exact identifiers)
- crude_oil_wti — West Texas Intermediate crude oil
- crude_oil_brent — Brent crude oil
- natural_gas — Natural gas (Henry Hub)
- gold — Gold
- silver — Silver
- wheat — Wheat
- corn — Corn
- copper — Copper

## Signal Directions
- bullish — the commentary suggests upward price pressure (supply cuts, demand increase, geopolitical risk premium, etc.)
- bearish — the commentary suggests downward price pressure (supply glut, demand weakness, risk-off sentiment, etc.)
- neutral — the commentary mentions a commodity but with no clear directional impact, OR contains mixed/contradictory signals

## Empty vs. Neutral Decision
- Return an EMPTY signals list when the transcript is off-topic, contains only generic market chatter, mentions a commodity without a clear price implication, or the evidence is too weak to justify a signal.
- Return a NEUTRAL signal only when the transcript contains a real commodity-relevant statement for a tracked commodity, but the directional evidence is explicitly mixed, contradictory, or balanced.
- If confidence would be below 0.35, prefer returning an EMPTY signals list rather than a weak directional signal unless the transcript clearly contains offsetting commodity evidence.

## Timeframes
- short_term — impact expected within hours to days
- medium_term — impact expected within weeks to months

## Confidence Calibration
- 0.85–1.0: Explicit quantitative data or official announcement with direct commodity impact
- 0.60–0.84: Clear directional commentary or causal link without hard data
- 0.35–0.59: Indirect, partial, or mixed evidence
- Below 0.35: Usually return an EMPTY signals list instead of a weak signal

## Entity Extraction
For each signal, extract mentioned_entities:
- **persons**: Key individuals mentioned (ministers, central bank chairs, analysts, heads of state). Use full names where stated.
- **indicators**: Economic indicators referenced (production levels, inventory data, PMI, crop yields, sanctions, weather forecasts, interest rates).
- **organizations**: Organizations mentioned (OPEC, OPEC+, Federal Reserve, USDA, ECB, IMF, etc.).
- Copy entities exactly as they appear in the transcript. Do not infer, normalize, or add entities that were not explicitly spoken.

## Critical Rules
1. If the transcript contains NO commodity-relevant signal, return an EMPTY signals list. Do not hallucinate signals.
2. Each signal must include a raw_quote — a verbatim contiguous quote from the transcript that supports it. Do not paraphrase.
3. Each signal must include mentioned_entities with persons, indicators, and organizations arrays (use empty arrays if none).
4. Keep rationale to max 2 sentences and under 300 characters. Longer rationale will be rejected.
5. Return at most one signal per commodity per chunk. Merge repeated evidence into the single strongest signal for that commodity.
6. For broad international oil supply events (OPEC+, Middle East disruptions, sanctions), prefer crude_oil_brent as the primary benchmark unless the transcript explicitly discusses US-specific WTI dynamics.
7. Only report commodities that are directly and materially affected by the quoted evidence.
8. Do not invent metadata or fields not present in the schema.
9. When in doubt between bullish/bearish and neutral, prefer neutral.
"""

TOOL_SCHEMA = {
    "name": "report_signals",
    "description": "Report all commodity-relevant signals found in the transcript. Return empty list if none.",
    "input_schema": {
        "type": "object",
        "properties": {
            "signals": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "commodity": {
                            "type": "string",
                            "enum": [
                                "crude_oil_wti", "crude_oil_brent", "natural_gas",
                                "gold", "silver", "wheat", "corn", "copper",
                            ],
                        },
                        "direction": {
                            "type": "string",
                            "enum": ["bullish", "bearish", "neutral"],
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                        },
                        "rationale": {
                            "type": "string",
                            "description": "1-2 sentence explanation under 300 characters.",
                        },
                        "timeframe": {
                            "type": "string",
                            "enum": ["short_term", "medium_term"],
                        },
                        "mentioned_entities": {
                            "type": "object",
                            "description": "Key entities explicitly mentioned in the transcript",
                            "properties": {
                                "persons": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Key persons copied exactly from the transcript, e.g. 'Jerome Powell' or 'Prince Abdulaziz'",
                                },
                                "indicators": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Economic indicators copied exactly from the transcript: inventories, production cuts, PMI, crop yields, sanctions, weather forecasts",
                                },
                                "organizations": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Organizations copied exactly from the transcript: OPEC, Fed, USDA, ECB, IMF",
                                },
                            },
                            "required": ["persons", "indicators", "organizations"],
                        },
                        "raw_quote": {
                            "type": "string",
                            "description": "Exact verbatim quote from the transcript supporting the signal",
                        },
                    },
                    "required": [
                        "commodity", "direction", "confidence", "rationale",
                        "timeframe", "mentioned_entities", "raw_quote",
                    ],
                },
            },
        },
        "required": ["signals"],
    },
}


def _make_strict(schema: dict | list) -> dict | list:
    """Return a recursively strict JSON schema for OpenAI function calling."""
    if isinstance(schema, dict):
        if schema.get("type") == "object":
            schema["additionalProperties"] = False
            if isinstance(schema.get("properties"), dict):
                schema["required"] = list(schema["properties"].keys())
        for key, value in list(schema.items()):
            if isinstance(value, (dict, list)):
                schema[key] = _make_strict(value)
        return schema
    if isinstance(schema, list):
        return [_make_strict(item) if isinstance(item, (dict, list)) else item for item in schema]
    return schema


STRICT_TOOL_SCHEMA_INPUT = _make_strict(copy.deepcopy(TOOL_SCHEMA["input_schema"]))

TOOL_SCHEMA_OPENAI = {
    "type": "function",
    "function": {
        "name": "report_signals",
        "description": "Report all commodity-relevant signals found in the transcript. Return empty list if none.",
        "strict": True,
        "parameters": STRICT_TOOL_SCHEMA_INPUT,
    },
}

_EXAMPLE_1_SIGNALS = [
    {
        "commodity": "crude_oil_brent",
        "direction": "bullish",
        "confidence": 0.92,
        "rationale": "OPEC+ production cut of 1.5M bpd tightens global seaborne oil supply, making Brent the primary benchmark impacted by the announcement.",
        "timeframe": "short_term",
        "mentioned_entities": {
            "persons": ["Prince Abdulaziz"],
            "indicators": ["production cut 1.5M bpd"],
            "organizations": ["OPEC+"],
        },
        "raw_quote": "OPEC+ alliance has agreed to cut production by 1.5 million barrels per day starting next month",
    },
]

_EXAMPLE_2_SIGNALS = [
    {
        "commodity": "gold",
        "direction": "bearish",
        "confidence": 0.85,
        "rationale": "Hawkish Fed signaling further rate hikes strengthens the dollar and increases opportunity cost of holding gold.",
        "timeframe": "medium_term",
        "mentioned_entities": {
            "persons": ["Chair Powell"],
            "indicators": ["rate hikes", "dot plot", "25 basis point"],
            "organizations": ["Federal Reserve"],
        },
        "raw_quote": "the committee sees further tightening as likely appropriate",
    }
]

_EXAMPLE_4_SIGNALS = [
    {
        "commodity": "crude_oil_brent",
        "direction": "neutral",
        "confidence": 0.46,
        "rationale": "OPEC supply discipline supports oil, but weaker Chinese demand offsets that support. The transcript explicitly frames the forces as offsetting each other.",
        "timeframe": "short_term",
        "mentioned_entities": {
            "persons": [],
            "indicators": ["production discipline", "weaker-than-expected industrial demand data"],
            "organizations": ["OPEC"],
        },
        "raw_quote": "OPEC delegates reiterated they will maintain production discipline, but traders are also reacting to weaker-than-expected industrial demand data out of China. Analysts say those two forces are offsetting each other for now.",
    }
]

_EXAMPLE_1_TEXT = 'Analyze this transcript segment:\n\n"The OPEC+ alliance has agreed to cut production by 1.5 million barrels per day starting next month, according to the official communique released just minutes ago. Saudi Energy Minister Prince Abdulaziz emphasized that this is a precautionary measure to stabilize markets."'

_EXAMPLE_2_TEXT = 'Analyze this transcript segment:\n\n"Chair Powell stated clearly that the committee sees further tightening as likely appropriate. The dot plot suggests two more 25 basis point hikes this year, which caught many traders off guard expecting a pause."'

_EXAMPLE_3_TEXT = 'Analyze this transcript segment:\n\n"Welcome back everyone, great to have you with us on this Monday morning. Beautiful weather here in New York, perfect start to the trading week. Let\'s see what the markets have in store for us today."'

_EXAMPLE_4_TEXT = 'Analyze this transcript segment:\n\n"Oil prices are being pulled in both directions today. OPEC delegates reiterated they will maintain production discipline, but traders are also reacting to weaker-than-expected industrial demand data out of China. Analysts say those two forces are offsetting each other for now."'

_EXAMPLE_5_TEXT = 'Analyze this transcript segment:\n\n"Gold remains on traders\' radar this morning, but there were no major policy announcements, no fresh inflation data, and no meaningful move in Treasury yields overnight. For now the market is mostly waiting for the Fed minutes this afternoon."'


FEW_SHOT_MESSAGES_FUNCTION: list[dict] = [
    {"role": "user", "content": _EXAMPLE_1_TEXT},
    {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "example_1",
                "type": "function",
                "function": {
                    "name": "report_signals",
                    "arguments": json.dumps({"signals": _EXAMPLE_1_SIGNALS}),
                },
            }
        ],
    },
    {
        "role": "tool",
        "tool_call_id": "example_1",
        "content": "Signals reported successfully.",
    },
    {"role": "user", "content": _EXAMPLE_2_TEXT},
    {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "example_2",
                "type": "function",
                "function": {
                    "name": "report_signals",
                    "arguments": json.dumps({"signals": _EXAMPLE_2_SIGNALS}),
                },
            }
        ],
    },
    {
        "role": "tool",
        "tool_call_id": "example_2",
        "content": "Signals reported successfully.",
    },
    {"role": "user", "content": _EXAMPLE_3_TEXT},
    {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "example_3",
                "type": "function",
                "function": {
                    "name": "report_signals",
                    "arguments": json.dumps({"signals": []}),
                },
            }
        ],
    },
    {
        "role": "tool",
        "tool_call_id": "example_3",
        "content": "Signals reported successfully.",
    },
    {"role": "user", "content": _EXAMPLE_4_TEXT},
    {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "example_4",
                "type": "function",
                "function": {
                    "name": "report_signals",
                    "arguments": json.dumps({"signals": _EXAMPLE_4_SIGNALS}),
                },
            }
        ],
    },
    {
        "role": "tool",
        "tool_call_id": "example_4",
        "content": "Signals reported successfully.",
    },
    {"role": "user", "content": _EXAMPLE_5_TEXT},
    {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "example_5",
                "type": "function",
                "function": {
                    "name": "report_signals",
                    "arguments": json.dumps({"signals": []}),
                },
            }
        ],
    },
    {
        "role": "tool",
        "tool_call_id": "example_5",
        "content": "Signals reported successfully.",
    },
]
