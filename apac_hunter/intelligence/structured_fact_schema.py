from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any
import json


SCHEMA_VERSION = "0.1"


@dataclass
class StructuredFactPacket:
    source_type: str
    schema_version: str = SCHEMA_VERSION
    issuer: str | None = None
    company: str | None = None
    event_type: str | None = None
    event_date: str | None = None
    subject_name: str | None = None
    confidence: str = "Medium"
    facts: dict[str, Any] = field(default_factory=dict)
    assumptions: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


DEFAULT_EVENT_BRIEF_SCHEMA = {
    "subject": {
        "individual_name": None,
        "company": None,
        "region": None,
    },
    "event": {
        "trigger_type": None,
        "summary": None,
        "source_type": None,
        "event_date": None,
    },
    "structured_facts": {
        "schema_version": SCHEMA_VERSION,
        "packet": None,
    },
    "analyst_overrides": {
        "assumptions": [],
        "scenario_overrides": {},
    },
}
