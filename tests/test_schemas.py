"""
Tests for LLM output schemas and the parse_llm_json helper.
These run without any external API calls.
"""
import pytest
from pydantic import ValidationError

from apac_hunter.intelligence.schemas import (
    ClassifiedTrigger,
    BriefContent,
    AccessScore,
    AccessPathway,
    ResearchDossier,
    parse_llm_json,
)


# ── parse_llm_json ─────────────────────────────────────────────────────────────

class TestParseLlmJson:
    def test_clean_json(self):
        raw = '{"relevant": false}'
        result = parse_llm_json(raw, ClassifiedTrigger)
        assert result is not None
        assert result.relevant is False

    def test_strips_markdown_fence(self):
        raw = '```json\n{"relevant": false}\n```'
        result = parse_llm_json(raw, ClassifiedTrigger)
        assert result is not None

    def test_strips_fence_no_lang(self):
        raw = '```\n{"relevant": false}\n```'
        result = parse_llm_json(raw, ClassifiedTrigger)
        assert result is not None

    def test_invalid_json_returns_none(self):
        result = parse_llm_json("not json at all", ClassifiedTrigger)
        assert result is None

    def test_schema_mismatch_returns_none(self):
        # relevant=true but missing required individual_name
        raw = '{"relevant": true, "company": "Acme"}'
        result = parse_llm_json(raw, ClassifiedTrigger)
        assert result is None

    def test_empty_string_returns_none(self):
        result = parse_llm_json("", ClassifiedTrigger)
        assert result is None


# ── ClassifiedTrigger ──────────────────────────────────────────────────────────

class TestClassifiedTrigger:
    def test_not_relevant(self):
        t = ClassifiedTrigger(relevant=False)
        assert not t.relevant

    def test_relevant_requires_name(self):
        with pytest.raises(ValidationError):
            ClassifiedTrigger(relevant=True, company="Acme")

    def test_tier_clamps(self):
        with pytest.raises(ValidationError):
            ClassifiedTrigger(relevant=False, tier=5)

    def test_score_clamps(self):
        with pytest.raises(ValidationError):
            ClassifiedTrigger(relevant=False, urgency_score=11)

    def test_to_trigger_dict_merges_filing(self):
        t = ClassifiedTrigger(
            relevant=True,
            individual_name="Jane Doe",
            company="Acme",
            country="Singapore",
            trigger_type="IPO liquidity event",
            tier=1,
            headline="Test",
            significance="High",
            urgency_score=8,
            wealth_score=7,
            confidence="High",
        )
        filing = {"source": "SGX", "url": "https://example.com", "date": "2026-01-01", "content": "abc"}
        d = t.to_trigger_dict(filing)
        assert d["individual_name"] == "Jane Doe"
        assert d["source"] == "SGX"
        assert d["source_url"] == "https://example.com"
        assert d["event_date"] == "2026-01-01"

    def test_confidence_values(self):
        for conf in ("High", "Medium", "Low"):
            t = ClassifiedTrigger(relevant=False, confidence=conf)
            assert t.confidence == conf

    def test_invalid_confidence_rejected(self):
        with pytest.raises(ValidationError):
            ClassifiedTrigger(relevant=False, confidence="Unknown")


# ── BriefContent ──────────────────────────────────────────────────────────────

class TestBriefContent:
    def test_valid(self):
        b = BriefContent(
            individual_profile="Profile",
            event_summary="Summary",
            wealth_control_analysis="Analysis",
            access_pathways="Pathways",
            behavioural_signals="Signals",
            iconiq_value_prop="Value",
            suggested_conversation="Conversation",
        )
        assert b.individual_profile == "Profile"

    def test_none_coerced_to_empty_string(self):
        b = BriefContent(
            individual_profile=None,
            event_summary="Summary",
            wealth_control_analysis="Analysis",
            access_pathways="Pathways",
            behavioural_signals=None,
            iconiq_value_prop="Value",
            suggested_conversation="Conversation",
        )
        assert b.individual_profile == ""
        assert b.behavioural_signals == ""

    def test_missing_field_raises(self):
        with pytest.raises(ValidationError):
            BriefContent(individual_profile="x")  # missing required fields


# ── AccessScore ───────────────────────────────────────────────────────────────

class TestAccessScore:
    def test_valid(self):
        a = AccessScore(access_score=7, pathways=[], linkedin_search_prompt="search", notes="note")
        assert a.access_score == 7

    def test_clamps_score(self):
        a = AccessScore(access_score=15)  # validator clamps to 10
        assert a.access_score == 10

    def test_clamps_score_low(self):
        a = AccessScore(access_score=-5)  # clamps to 1
        assert a.access_score == 1

    def test_pathway_strength_validated(self):
        with pytest.raises(ValidationError):
            AccessPathway(type="board", description="desc", strength="Meh")

    def test_defaults(self):
        a = AccessScore(access_score=5)
        assert a.pathways == []
        assert a.linkedin_search_prompt == ""


# ── ResearchDossier ───────────────────────────────────────────────────────────

class TestResearchDossier:
    def test_defaults(self):
        d = ResearchDossier()
        assert d.confirmed_identity == "Unknown"
        assert d.research_confidence == "Low"

    def test_confidence_normalised(self):
        d = ResearchDossier(research_confidence="high")
        assert d.research_confidence == "High"

    def test_invalid_confidence_falls_back(self):
        d = ResearchDossier(research_confidence="very high")
        assert d.research_confidence == "Low"

    def test_model_dump_round_trip(self):
        d = ResearchDossier(
            confirmed_identity="Jane Doe",
            net_worth_estimate="$500M",
            research_confidence="High",
        )
        dumped = d.model_dump()
        assert dumped["confirmed_identity"] == "Jane Doe"
        assert dumped["research_confidence"] == "High"
