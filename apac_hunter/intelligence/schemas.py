from __future__ import annotations
"""
Pydantic schemas for validating structured outputs from LLM calls.

Each schema corresponds to a specific LLM response shape. Use the
`parse_llm_json` helper to safely parse raw LLM text and validate it
against the appropriate schema — it handles markdown fences, logging,
and returns None on failure rather than raising.
"""
import json
import logging
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

log = logging.getLogger(__name__)


# ── Parsing helper ────────────────────────────────────────────────────────────

def parse_llm_json(raw_text: str, schema: type[BaseModel], context: str = "") -> BaseModel | None:
    """
    Strip markdown fences, parse JSON, and validate against `schema`.

    Returns a validated model instance, or None if parsing/validation fails.
    Logs a warning with the raw text so failures are diagnosable.
    """
    text = raw_text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        # parts[1] is the block content; may start with "json\n"
        text = parts[1].lstrip("json").strip() if len(parts) > 1 else text
    text = text.rstrip("```").strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        log.warning(
            "LLM JSON parse failure%s: %s\nRaw text (first 500 chars):\n%s",
            f" [{context}]" if context else "",
            exc,
            raw_text[:500],
        )
        return None

    try:
        return schema.model_validate(data)
    except Exception as exc:
        log.warning(
            "LLM schema validation failure%s: %s\nParsed data: %s",
            f" [{context}]" if context else "",
            exc,
            data,
        )
        return None


# ── Classifier output ─────────────────────────────────────────────────────────

class ClassifiedTrigger(BaseModel):
    """Output schema for classify_filing / classify_batch items."""
    relevant: bool

    # Only present when relevant=True
    individual_name: str | None = None
    company: str | None = None
    country: str | None = None
    trigger_type: str | None = None
    tier: int | None = Field(default=None, ge=1, le=3)
    headline: str | None = None
    significance: str | None = None
    urgency_score: int | None = Field(default=None, ge=1, le=10)
    wealth_score: int | None = Field(default=None, ge=1, le=10)
    confidence: Literal["High", "Medium", "Low"] | None = None
    estimated_net_worth_notes: str | None = None

    @model_validator(mode="after")
    def check_required_when_relevant(self) -> "ClassifiedTrigger":
        if self.relevant and not self.individual_name:
            raise ValueError("individual_name is required when relevant=True")
        return self

    def to_trigger_dict(self, source_filing: dict) -> dict:
        """Merge filing metadata back onto this validated trigger."""
        return {
            **self.model_dump(exclude_none=True),
            "source": source_filing.get("source", ""),
            "source_url": source_filing.get("url", ""),
            "event_date": source_filing.get("date", ""),
            "raw_content": source_filing.get("content", ""),
        }


# ── Brief generator output ────────────────────────────────────────────────────

class BriefContent(BaseModel):
    """Output schema for generate_brief."""
    individual_profile: str
    event_summary: str
    wealth_control_analysis: str
    network_signal: str = ""
    behavioural_signals: str
    iconiq_value_prop: str
    suggested_conversation: str
    key_facts: list[str] = Field(default_factory=list)
    why_this_matters: list[str] = Field(default_factory=list)

    @field_validator("individual_profile", "event_summary", "wealth_control_analysis",
                     "network_signal", "behavioural_signals", "iconiq_value_prop",
                     "suggested_conversation", mode="before")
    @classmethod
    def coerce_none_to_empty(cls, v):
        """LLM occasionally returns null for optional narrative fields."""
        return v if v is not None else ""

    @field_validator("key_facts", "why_this_matters", mode="before")
    @classmethod
    def coerce_string_list(cls, v):
        if v is None:
            return []
        if isinstance(v, list):
            return [str(i) for i in v if i]
        return []


# ── Access scorer output ──────────────────────────────────────────────────────

class AccessPathway(BaseModel):
    type: str
    description: str
    strength: Literal["Strong", "Medium", "Weak"]


class AccessScore(BaseModel):
    """Output schema for score_access."""
    access_score: int = Field(ge=1, le=10)
    pathways: list[AccessPathway] = []
    linkedin_search_prompt: str = ""
    notes: str = ""

    @field_validator("access_score", mode="before")
    @classmethod
    def clamp_score(cls, v):
        try:
            return max(1, min(10, int(v)))
        except (TypeError, ValueError):
            return 2  # safe default


# ── Research dossier output ───────────────────────────────────────────────────

class ResearchDossier(BaseModel):
    """Output schema for research_individual."""
    confirmed_identity: str = "Unknown"
    net_worth_estimate: str = "Unknown"
    wealth_composition: str = "Unknown"
    family_background: str = "Unknown"
    board_roles: str = "Unknown"
    known_investments: str = "Unknown"
    advisors_and_bankers: str = "Unknown"
    public_profile: str = "Unknown"
    recent_news: str = "Unknown"
    research_confidence: Literal["High", "Medium", "Low"] = "Low"
    gaps: str = ""

    @field_validator("research_confidence", mode="before")
    @classmethod
    def normalise_confidence(cls, v):
        if isinstance(v, str) and v.title() in ("High", "Medium", "Low"):
            return v.title()
        return "Low"
