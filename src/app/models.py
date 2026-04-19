from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Commodity = Literal[
    "crude_oil_wti",
    "crude_oil_brent",
    "natural_gas",
    "gold",
    "silver",
    "wheat",
    "corn",
    "copper",
]
Direction = Literal["bullish", "bearish", "neutral"]
Timeframe = Literal["short_term", "medium_term"]
ExpectedBehavior = Literal["empty", "neutral_signal", "directional"]


class Word(BaseModel):
    text: str
    start: float
    end: float
    speaker: str | None = None


class SpeakerSegment(BaseModel):
    speaker: str
    start: float
    end: float
    text: str


class Transcript(BaseModel):
    chunk_id: str
    chunk_start_seconds: float
    text: str
    words: list[Word]
    language: str = "en"
    speaker_segments: list[SpeakerSegment] = Field(default_factory=list)


class MentionedEntities(BaseModel):
    """Entities explicitly mentioned in the transcript segment."""
    persons: list[str] = Field(default_factory=list, description="Key persons: ministers, central bank chairs, analysts")
    indicators: list[str] = Field(default_factory=list, description="Economic indicators: inventories, production, demand, sanctions, weather")
    organizations: list[str] = Field(default_factory=list, description="Organizations: OPEC, Fed, USDA, ECB")


class Signal(BaseModel):
    commodity: Commodity
    direction: Direction
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str = Field(max_length=300)
    timeframe: Timeframe
    mentioned_entities: MentionedEntities = Field(default_factory=MentionedEntities)
    source_chunk_id: str
    source_timestamp_start: float
    source_timestamp_end: float
    raw_quote: str


class EvalCase(BaseModel):
    id: str
    transcript: str
    expected_behavior: ExpectedBehavior
    expected_commodity: Commodity | None
    expected_direction: Direction
    notes: str
