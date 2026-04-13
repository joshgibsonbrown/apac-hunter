from __future__ import annotations
import logging
import os
import anthropic
from dotenv import load_dotenv

from apac_hunter.intelligence.schemas import (
    ClassifiedTrigger, AccessScore, parse_llm_json,
)

load_dotenv()

log = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

TRIGGER_ARCHETYPES = [
    "IPO liquidity event",
    "M&A / asset sale proceeds",
    "Large dividend distribution",
    "Block trade / large insider sale",
    "Voting structure change",
    "Founder stock unlock / vesting cliff",
    "Holding company / family office formation",
    "Entity restructuring (trust, SPV, subsidiary)",
    "Secondary market activity",
    "CFO / IR / Strategic Finance hire",
    "Accelerated insider selling",
    "10b5-1 selling plan filed/modified",
    "Secondary tender offer / employee liquidity program",
    "Pre-IPO secondary market sale",
    "Other significant corporate event",
]


def classify_filing(filing: dict, region_config: dict = None) -> dict | None:
    """
    Classify a single filing. Used as fallback when batch classification fails.
    Returns a trigger dict or None.
    """
    mandate_text, country_list = _get_mandate(region_config)

    prompt = f"""You are an intelligence analyst at ICONIQ Capital, a wealth management firm serving ultra-high-net-worth individuals. ICONIQ works with founders and families with $50M+ in liquid assets.

Analyse this filing or news item and determine if it represents a meaningful wealth trigger event.

FILING/NEWS:
Source: {filing.get('source', '')}
Company: {filing.get('company', '')}
Title: {filing.get('title', '')}
Date: {filing.get('date', '')}
Content: {filing.get('content', '')[:1500]}
URL: {filing.get('url', '')}

TRIGGER ARCHETYPES (classify into one if relevant):
{chr(10).join(f'- {t}' for t in TRIGGER_ARCHETYPES)}

MANDATE:
{mandate_text}

GEOGRAPHY — relevant countries: {country_list}

HARD REJECTIONS — return {{"relevant": false}} immediately if ANY of these apply:
- The named individual is clearly based outside the target geography (e.g. an American executive when scanning APAC)
- The entity is an institutional investor: sovereign wealth fund (GIC, Temasek, ADIA, CIC, Mubadala, CPP, GIC rebalancing), pension fund, PE firm acting as buyer/acquirer, large bank treasury operation
- It is a company fundraising round (Series A/B/C/D/E) where NO named founder is confirmed to receive personal liquidity proceeds
- The event clearly occurred more than 6 months ago (historical article, not a current event)
- The "individual" is a corporation, fund, or government entity — not a human being
- It is routine executive compensation: standard RSU vesting, option grants, salary disclosure under $10M total

Only return relevant=true if ALL of these are true:
- A specific named human individual (founder/owner/family member) is clearly identifiable
- Their personal wealth event is $30M+ in value OR their personal net worth is $50M+
- The individual's primary base or nationality matches the target geography
- It is a genuine current trigger archetype, not general business news

Respond with JSON only. If NOT relevant: {{"relevant": false}}
If relevant: {{"relevant": true, "individual_name": "...", "company": "...", "country": "...", "trigger_type": "...", "tier": 1-3, "headline": "...", "significance": "...", "urgency_score": 1-10, "wealth_score": 1-10, "confidence": "High/Medium/Low", "estimated_net_worth_notes": "..."}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text
    except Exception as exc:
        log.error("Classifier API error for %s: %s", filing.get("title", ""), exc)
        return None

    result = parse_llm_json(raw, ClassifiedTrigger, context=f"classify_filing:{filing.get('title','')[:40]}")
    if result is None or not result.relevant:
        return None
    return result.to_trigger_dict(filing)


def classify_batch(filings: list, region_config: dict = None) -> list:
    """
    Classify up to 10 filings in a single API call.

    Returns a list with one entry per filing: a trigger dict or None.
    Falls back to individual classification on parse or validation failure.
    """
    if not filings:
        return []

    mandate_text, country_list = _get_mandate(region_config)

    items_text = ""
    for i, f in enumerate(filings):
        items_text += f"""
--- ITEM {i+1} ---
Source: {f.get('source', '')}
Company: {f.get('company', '')}
Title: {f.get('title', '')}
Date: {f.get('date', '')}
Content: {f.get('content', '')[:800]}
URL: {f.get('url', '')}
"""

    prompt = f"""You are an intelligence analyst at ICONIQ Capital, a wealth management firm serving ultra-high-net-worth individuals ($50M+ liquid assets).

Analyse these {len(filings)} filings/news items and determine which represent meaningful wealth trigger events.

{items_text}

TRIGGER ARCHETYPES:
{chr(10).join(f'- {t}' for t in TRIGGER_ARCHETYPES)}

MANDATE: {mandate_text}
GEOGRAPHY: {country_list}

HARD REJECTIONS — mark {{"relevant": false}} immediately if ANY apply:
- Individual is clearly based outside target geography (e.g. American for APAC scan)
- Entity is institutional: sovereign wealth fund (GIC, Temasek, ADIA, CIC, Mubadala, CPP), pension fund, PE firm as buyer, bank treasury
- Company fundraising round with no named founder confirmed receiving personal proceeds
- Event clearly occurred more than 6 months ago
- "Individual" is a corporation, fund, or government entity — not a human being
- Routine executive compensation under $10M (RSU vesting, option grants, salary)

Only flag relevant=true if ALL true:
- Specific named human individual (founder/owner/family member) is identifiable
- Personal wealth event $30M+ OR personal net worth $50M+
- Individual's primary base or nationality matches target geography
- Genuine current trigger event, not historical or general business news

Respond with a JSON array of exactly {len(filings)} objects, one per item in order.
For items NOT relevant: {{"relevant": false}}
For items that ARE relevant: {{"relevant": true, "individual_name": "...", "company": "...", "country": "...", "trigger_type": "...", "tier": 1-3, "headline": "...", "significance": "...", "urgency_score": 1-10, "wealth_score": 1-10, "confidence": "High/Medium/Low", "estimated_net_worth_notes": "..."}}

Return ONLY the JSON array. No markdown, no preamble."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text
    except Exception as exc:
        log.error("Batch classifier API error: %s — falling back to individual", exc)
        return [classify_filing(f, region_config=region_config) for f in filings]

    # Parse the outer JSON array
    import json
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1].lstrip("json").strip() if len(parts) > 1 else text
    text = text.rstrip("```").strip()

    try:
        batch_raw = json.loads(text)
        if not isinstance(batch_raw, list):
            raise ValueError("Expected JSON array from batch classifier")
    except (json.JSONDecodeError, ValueError) as exc:
        log.warning("Batch classification parse failed (%s) — falling back to individual", exc)
        return [classify_filing(f, region_config=region_config) for f in filings]

    processed: list = []
    for i, raw_item in enumerate(batch_raw):
        if i >= len(filings):
            break
        if not isinstance(raw_item, dict):
            processed.append(None)
            continue
        try:
            item = ClassifiedTrigger.model_validate(raw_item)
        except Exception as exc:
            log.warning("Batch item %d validation failed: %s — skipping", i + 1, exc)
            processed.append(None)
            continue

        if not item.relevant:
            processed.append(None)
        else:
            processed.append(item.to_trigger_dict(filings[i]))

    # Pad to match input length
    while len(processed) < len(filings):
        processed.append(None)

    return processed


def score_access(individual_name: str, company: str) -> dict:
    """Quick access pathway scoring based on public information."""

    prompt = f"""You are a relationship intelligence analyst at ICONIQ Capital.

Research the following individual and identify potential access pathways.

Individual: {individual_name}
Company: {company}

Search your knowledge for:
1. Board memberships (current and past)
2. Co-investors or known investment relationships
3. Shared advisors, lawyers, or bankers
4. Career history connections
5. Conference appearances

Respond with JSON only:
{{
  "access_score": 1-10,
  "pathways": [
    {{"type": "board interlock/co-investment/shared advisor/career/other", "description": "specific connection", "strength": "Strong/Medium/Weak"}}
  ],
  "linkedin_search_prompt": "exact search string",
  "notes": "any other relevant access context"
}}

If you have no information, return access_score of 2 and empty pathways. Do not invent connections."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text
    except Exception as exc:
        log.error("Access scorer API error for %s: %s", individual_name, exc)
        return {"access_score": 1, "pathways": [], "notes": "Access research unavailable"}

    result = parse_llm_json(raw, AccessScore, context=f"score_access:{individual_name[:30]}")
    if result is None:
        return {"access_score": 1, "pathways": [], "notes": "Access research parse failed"}
    return result.model_dump()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_mandate(region_config):
    if region_config is not None:
        mandate_text = region_config["classifier_mandate"]
        country_list = ", ".join(region_config["countries"][:20])
    else:
        mandate_text = (
            "ICONIQ's APAC mandate covers founders, private business owners, and "
            "business-owning families based in or originating from the Asia-Pacific "
            "region. Wealth threshold: $50M+ net worth OR event involves $30M+ in value."
        )
        country_list = (
            "Singapore, Hong Kong, China, Taiwan, Japan, South Korea, "
            "Indonesia, Malaysia, Thailand, Philippines, Vietnam, India, "
            "Australia, New Zealand"
        )
    return mandate_text, country_list
