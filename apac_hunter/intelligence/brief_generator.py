from __future__ import annotations
import json
import logging
import os
import re
import anthropic
from dotenv import load_dotenv

from apac_hunter.intelligence.schemas import BriefContent, parse_llm_json

load_dotenv()

log = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def generate_brief(trigger: dict, research: dict | None = None) -> dict | None:
    """
    Takes a classified trigger event and a pre-brief research dossier.
    Produces a structured strategic brief dict, or None on failure.

    The returned dict includes a `source_context` key containing the
    raw filing content and research facts — used later for grounded Q&A.
    """
    research_section = ""
    if research:
        research_section = f"""
PRE-BRIEF RESEARCH DOSSIER:
Confirmed Identity: {research.get('confirmed_identity', 'Unknown')}
Net Worth Estimate: {research.get('net_worth_estimate', 'Unknown')}
Wealth Composition: {research.get('wealth_composition', 'Unknown')}
Family Background: {research.get('family_background', 'Unknown')}
Board Roles: {research.get('board_roles', 'Unknown')}
Known Investments: {research.get('known_investments', 'Unknown')}
Advisors & Bankers: {research.get('advisors_and_bankers', 'Unknown')}
Public Profile: {research.get('public_profile', 'Unknown')}
Recent News: {research.get('recent_news', 'Unknown')}
Research Confidence: {research.get('research_confidence', 'Unknown')}
Gaps: {research.get('gaps', 'Unknown')}
"""

    prompt = f"""You are a senior relationship manager at ICONIQ Capital, a wealth management firm serving ultra-high-net-worth founders and families. You write strategic briefs for internal use to help the team identify and approach new client opportunities.

Write a strategic brief for the following trigger event. Use the research dossier as your primary source of facts. Be analytical, direct, and honest. Do not pad thin signals.

TRIGGER EVENT:
Individual: {trigger.get('individual_name')}
Company: {trigger.get('company')}
Country: {trigger.get('country')}
Trigger Type: {trigger.get('trigger_type')}
Tier: {trigger.get('tier')}
Headline: {trigger.get('headline')}
Significance: {trigger.get('significance')}
Source: {trigger.get('source')} - {trigger.get('source_url')}
Event Date: {trigger.get('event_date')}
Confidence: {trigger.get('confidence')}
Raw Content: {trigger.get('raw_content', '')[:500]}
{research_section}

Write the brief as a JSON object with these exact keys:

{{
  "individual_profile": "Who they are, confirmed identity, role, ownership stake, net worth and wealth composition. Draw directly from the research dossier. Be honest about confidence levels.",

  "event_summary": "What happened and what it means for their wealth, control, and liquidity. Be specific about the mechanism and implications.",

  "wealth_control_analysis": "Strategic wealth implications. What doors does this open or close? What decisions are they now facing? What is the window of relevance?",

  "network_signal": "List up to 5 high-profile individuals (tech founders, major investors, board members, well-known executives or families) who are factually and specifically connected to this individual based on the research dossier and source context. For each name, state the specific documented connection (e.g. co-investor, board peer, shared backer). Do NOT claim relationship strength or warmth. Do NOT fabricate connections. If no relevant names are identifiable from the available context, say so. Format: Name — Connection.",

  "behavioural_signals": "Evidence of active wealth exploration or structural change. Only include what is evidenced — do not speculate.",

  "iconiq_value_prop": "Specific ICONIQ value tied to this trigger and this individual's situation. Not generic — what is genuinely relevant right now?",

  "suggested_conversation": "Concrete recommended approach. What insight earns attention? What is the opening framing? Strategic counsel, not a sales pitch.",

  "key_facts": ["List of up to 10 specific verifiable facts drawn strictly from the source material and research dossier — numbers, transaction values, share counts, ownership percentages, dates, net worth estimates, acceleration multiples (only if the full calculation is available), cumulative dollar amounts. Each entry is a single short factual statement. Do not include interpretation. Do not fabricate. Do not include a rate multiplier unless both the numerator and denominator are available in the source context."],

  "why_this_matters": ["2-3 bullets only. Specific client development relevance of this trigger for ICONIQ. Focus on what decision or window this creates, what strategic signal it sends, or what approach it enables. Must be specific to this individual and event — no generic statements like 'this is a liquidity event'. Examples of acceptable bullets: 'CFO is likely moving from equity-heavy to diversified portfolio for the first time', 'Lock-up expiry creates a 60-day window before selling restrictions lift', 'Governance change signals a generational transition with the next-gen taking control'."]
}}

Respond with JSON only. No markdown. No preamble."""

    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text
    except Exception as exc:
        log.error("Brief generation API error for %s: %s", trigger.get("individual_name", ""), exc)
        return None

    content = parse_llm_json(
        raw, BriefContent,
        context=f"generate_brief:{trigger.get('individual_name', '')[:30]}"
    )
    if content is None:
        log.warning("Brief generation produced invalid output for %s — skipping",
                    trigger.get("individual_name", ""))
        return None

    # Build source_context for grounded Q&A — stored alongside the brief
    source_context = _build_source_context(trigger, research)
    if content.key_facts:
        source_context["key_facts"] = content.key_facts
    if content.why_this_matters:
        source_context["why_this_matters"] = content.why_this_matters

    confidence_level = _compute_confidence_level(source_context, research)

    return {
        "individual_name": trigger.get("individual_name"),
        "company": trigger.get("company"),
        "last_trigger_type": trigger.get("trigger_type"),
        "event_summary": content.event_summary,
        "wealth_control_analysis": content.wealth_control_analysis,
        "individual_profile": content.individual_profile,
        "network_signal": content.network_signal,
        "behavioural_signals": content.behavioural_signals,
        "iconiq_value_prop": content.iconiq_value_prop,
        "suggested_conversation": content.suggested_conversation,
        "why_this_matters": content.why_this_matters,
        "urgency_score": trigger.get("urgency_score", 5),
        "wealth_score": trigger.get("wealth_score", 5),
        "confidence": trigger.get("confidence", "Medium"),
        "confidence_level": confidence_level,
        "workflow_status": "New",
        "source_context": source_context,
    }


def _build_source_context(trigger: dict, research: dict | None) -> dict:
    """
    Assemble the source context dict stored for later Q&A grounding.
    Keeps only facts — no generated narrative.

    Structure:
      trigger       — filing metadata + raw content
      detection_metadata — structured numeric extraction from raw content
      research      — synthesised dossier fields
      research_sources  — web search result citations (title + snippet + url)
      key_facts     — added by caller after LLM extraction
    """
    ctx: dict = {
        "trigger": {
            "raw_content": trigger.get("raw_content", "")[:3000],
            "headline": trigger.get("headline", ""),
            "significance": trigger.get("significance", ""),
            "source": trigger.get("source", ""),
            "source_url": trigger.get("source_url", ""),
            "event_date": trigger.get("event_date", ""),
            "trigger_type": trigger.get("trigger_type", ""),
            "country": trigger.get("country", ""),
            "confidence": trigger.get("confidence", ""),
            "tier": trigger.get("tier"),
            "estimated_net_worth_notes": trigger.get("estimated_net_worth_notes", ""),
        },
        "detection_metadata": _extract_detection_metadata(trigger),
    }
    if research:
        # Dossier — all synthesised fields except raw_results (stored separately)
        ctx["research"] = {k: v for k, v in research.items() if k not in ("raw_results",)}
        # Source citations — the web snippets that back up the dossier
        raw_results = research.get("raw_results") or []
        if raw_results:
            ctx["research_sources"] = [
                {
                    "title": r.get("title", ""),
                    "snippet": r.get("snippet", ""),
                    "url": r.get("url", ""),
                    "source": r.get("source", ""),
                }
                for r in raw_results[:10]
            ]
    return ctx


def _extract_detection_metadata(trigger: dict) -> dict:
    """
    Extract structured numeric and detection facts from the trigger dict.

    Covers all trigger types: insider pattern analysis, SC 13D/G ownership
    changes, lock-up expiries, and generic numeric signals.
    Returns a flat dict of named values — nothing inferred, only parsed.
    """
    meta: dict = {}
    content = trigger.get("raw_content", "")

    # Scores and tier (always include if present)
    for field in ("urgency_score", "wealth_score", "tier"):
        val = trigger.get(field)
        if val is not None:
            meta[field] = val

    # Insider selling — genuine acceleration (has a real baseline)
    m = re.search(r"at ([\d.]+)x baseline rate", content)
    if m:
        meta["acceleration_factor"] = float(m.group(1))
    m = re.search(r"Recent selling rate: \$([\d,]+(?:\.\d+)?)/day over the last (\d+) days", content)
    if m:
        meta["recent_rate_per_day_usd"] = float(m.group(1).replace(",", ""))
        meta["selling_window_days"] = int(m.group(2))
    m = re.search(r"Historical baseline rate: \$([\d,]+(?:\.\d+)?)/day", content)
    if m:
        meta["baseline_rate_per_day_usd"] = float(m.group(1).replace(",", ""))
    m = re.search(r"total: \$([\d,]+(?:\.\d+)?)\)", content)
    if m:
        meta["recent_total_usd"] = int(m.group(1).replace(",", ""))

    # First-time selling (no baseline — do NOT record acceleration_factor)
    m = re.search(
        r"FIRST-TIME SELLING.*?Recent sales total: \$([\d,]+(?:\.\d+)?) over the last (\d+) days",
        content, re.IGNORECASE | re.DOTALL,
    )
    if m:
        meta["first_time_selling_total_usd"] = int(m.group(1).replace(",", ""))
        meta["first_time_selling_window_days"] = int(m.group(2))
        meta["acceleration_note"] = "No prior selling history — multiplier comparison not applicable"

    # Cumulative insider sales (legacy pattern from older records)
    m = re.search(r"CUMULATIVE:.*?sold \$([\d,]+(?:\.\d+)?) in (\d+) days", content)
    if m:
        meta["cumulative_sales_usd"] = int(m.group(1).replace(",", ""))
        meta["cumulative_days"] = int(m.group(2))

    # SC 13D/G ownership percentage
    m = re.search(r"OWNERSHIP[^%]*?([\d.]+)%", content, re.IGNORECASE)
    if m:
        meta["ownership_pct"] = float(m.group(1))
    elif "SC 13" in content:
        m = re.search(r"([\d.]+)\s*%", content)
        if m:
            meta["ownership_pct"] = float(m.group(1))

    # Lock-up expiry date
    m = re.search(r"LOCK-UP EXPIRY.*?on (\d{4}-\d{2}-\d{2})", content, re.IGNORECASE)
    if m:
        meta["lockup_expiry_date"] = m.group(1)

    # Dollar amounts (keep up to 5 unique values)
    amounts = re.findall(
        r"\$[\d,]+(?:\.\d+)?(?:\s*(?:million|billion|M|B|K))?",
        content, re.IGNORECASE,
    )
    if amounts:
        seen: set = set()
        unique = [a for a in amounts if not (a in seen or seen.add(a))]
        meta["mentioned_amounts"] = unique[:5]

    # Share counts
    shares = re.findall(r"[\d,]+\s+shares?", content, re.IGNORECASE)
    if shares:
        meta["mentioned_shares"] = shares[:3]

    return meta


def _compute_confidence_level(source_context: dict, research: dict | None) -> str:
    """
    Evidence-quality heuristic. Not the same as the classifier's 'confidence'
    field — this scores how well the brief's claims can be substantiated.

    High  (score >= 5): real numeric baseline + research sources + identity confirmed
    Medium (score 2–4): some structured data but gaps present
    Low   (score < 2):  thin source, no numeric facts, no research citations
    """
    score = 0
    dm = source_context.get("detection_metadata", {})

    # Genuine acceleration (not the no-baseline sentinel, which has no factor)
    af = dm.get("acceleration_factor")
    if af is not None and 0 < af < 900:
        score += 2

    # First-time selling with a real dollar figure is still structured evidence
    if dm.get("first_time_selling_total_usd"):
        score += 1

    # Baseline and recent rate both present → calculation is fully grounded
    if dm.get("baseline_rate_per_day_usd") and dm.get("recent_rate_per_day_usd"):
        score += 1

    # Other structured numeric signals
    for field in ("cumulative_sales_usd", "recent_total_usd", "ownership_pct", "lockup_expiry_date"):
        if dm.get(field):
            score += 1

    # Research source citations present (web evidence behind claims)
    if source_context.get("research_sources"):
        score += 1

    # Research quality from the synthesis step
    r_conf = (research or {}).get("research_confidence", "Low")
    if r_conf == "High":
        score += 2
    elif r_conf == "Medium":
        score += 1

    # Net worth estimate is substantiated (not "Unknown")
    nw = (research or {}).get("net_worth_estimate", "Unknown")
    if nw and nw not in ("Unknown", ""):
        score += 1

    if score >= 5:
        return "High"
    elif score >= 2:
        return "Medium"
    else:
        return "Low"
