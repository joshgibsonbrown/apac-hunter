import os
import anthropic
from dotenv import load_dotenv

from apac_hunter.intelligence.analysis_engine import build_template_analysis
from apac_hunter.intelligence.deterministic_component_builder import (
    build_control_transition_component,
    build_liquidity_component,
    build_ipo_liquidity_component,
)

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

COMPANY_TICKERS = {
    "Sea Limited": "SE",
    "Grab Holdings": "GRAB",
    "Grab Holdings Limited": "GRAB",
    "Baidu": "BIDU",
    "JD.com": "JD",
    "PDD Holdings": "PDD",
    "NIO Inc": "NIO",
    "Futu Holdings": "FUTU",
    "Bilibili": "BILI",
}


def _run_playbook_classification(brief: dict) -> dict:
    name = brief.get("individual_name", "Unknown")
    company = brief.get("company", "Unknown")
    try:
        from apac_hunter.intelligence.playbook_classifier import classify_founder
        ticker = COMPANY_TICKERS.get(company)
        print(f"  Running playbook classification for {name}...")
        result = classify_founder(brief, ticker=ticker)
        print(f"  Classification: {result.get('archetype_label')} ({result.get('confidence')})")
        return result
    except Exception as e:
        print(f"  Classification error: {e}")
        return {
            "archetype_label": "Unknown",
            "archetype_colour": "#A5A5A5",
            "archetype_description": "Classification unavailable",
            "confidence": "Low",
            "behavioural_summary": "Insufficient data for classification.",
            "transaction_pattern": "No transaction history available.",
            "key_question": "What is your approach to managing your equity position?",
            "conversation_implication": "Manual research required before outreach.",
            "primary_evidence": [],
            "peer_comparables": [],
        }


def _generate_llm_analysis(brief: dict, playbook: dict) -> str:
    trigger_type = brief.get("last_trigger_type", "")
    name = brief.get("individual_name", "Unknown")
    company = brief.get("company", "Unknown")

    facts = ". ".join(filter(None, [
        (brief.get("event_summary") or "")[:400],
        (brief.get("individual_profile") or "")[:250],
        (brief.get("wealth_control_analysis") or "")[:200],
    ]))

    evidence_text = "\n".join([f"- {e}" for e in playbook.get("primary_evidence", [])[:4]])
    peer_text = "; ".join([
        f"{p.get('name')} ({p.get('company')}) — {p.get('relevance', '')}"
        for p in playbook.get("peer_comparables", [])[:2]
    ]) or "None identified"

    prompt = f"""You are building a React component for ICONIQ Capital.

INDIVIDUAL: {name}
COMPANY: {company}
TRIGGER: {trigger_type}

PLAYBOOK:
Archetype: {playbook.get('archetype_label')} ({playbook.get('confidence')} confidence)
{playbook.get('archetype_description', '')}
Behavioural Summary: {playbook.get('behavioural_summary', '')}
Transaction Pattern: {playbook.get('transaction_pattern', '')}
Evidence:
{evidence_text}
Peers: {peer_text}
Key Question: {playbook.get('key_question', '')}
Conversation Implication: {playbook.get('conversation_implication', '')}

FACTS: {facts[:700]}

Build a React component with 4 tabs: Playbook / Scenario / Key Numbers / First Conversation.
Scenario: forward-looking bear/base/bull scenarios for future sales, NOT the transaction already done.

RULES:
- const {{ useState }} = React; at top. No imports.
- Max 200 lines. Break style objects with 3+ properties across lines.
- Colors: #1A7CD7, #151515, #FDC500, #374B68, #4DB96B, #e74c3c
- export default function App()

Return ONLY the component code."""

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )

    code = response.content[0].text.strip()
    lines = []
    for line in code.split("\n"):
        if line.strip().startswith("import ") or line.strip().startswith("```"):
            continue
        lines.append(line)
    code = "\n".join(lines).strip()
    if "const { useState }" not in code and "useState" in code:
        code = "const { useState } = React;\n" + code
    return code


def generate_analysis(brief: dict) -> str:
    # Always run playbook classification first
    playbook = _run_playbook_classification(brief)

    # Try deterministic template
    template_result = build_template_analysis(brief)

    if template_result.get("status") == "ok" and template_result.get("analysis"):
        template_type = template_result["analysis"].get("template_type")

        if template_type == "control_transition":
            return build_control_transition_component(brief, template_result)

        if template_type == "liquidity_sequencing":
            return build_liquidity_component(brief, template_result, playbook=playbook)

        if template_type == "ipo_liquidity":
            return build_ipo_liquidity_component(brief, template_result)

    return _generate_llm_analysis(brief, playbook)
