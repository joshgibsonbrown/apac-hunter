import os
import json
import requests
import anthropic
from dotenv import load_dotenv
from apac_hunter.intelligence.form4_history import fetch_form4_history

load_dotenv()

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

ARCHETYPES = {
    "gradual_diversifier": {
        "label": "Gradual Diversifier",
        "colour": "#1A7CD7",
        "description": "Systematic, patient monetisation. Sells methodically over years, prioritises tax efficiency and market impact minimisation over timing. Often uses 10b5-1 plans.",
        "signals": [
            "Regular small sales over extended period",
            "Sales unrelated to stock price peaks",
            "Pre-established trading plans (10b5-1)",
            "Held through significant drawdowns before selling",
            "No correlation between sale timing and news events"
        ]
    },
    "control_maximiser": {
        "label": "Control Maximiser",
        "colour": "#374B68",
        "description": "Governance-first. Prioritises retaining voting control above liquidity. Structures sales carefully to avoid diluting governance position. May use structured solutions.",
        "signals": [
            "Minimal or no open market sales despite large paper wealth",
            "Sells economic interest while retaining voting control",
            "Dual-class share structure maintenance or strengthening",
            "Proxy arrangements with co-founders",
            "Sales only from non-voting or low-voting share classes"
        ]
    },
    "opportunistic_seller": {
        "label": "Opportunistic Seller",
        "colour": "#e74c3c",
        "description": "Valuation-aware. Times sales to perceived peaks or ahead of anticipated weakness. Sales cluster around high prices or positive news events.",
        "signals": [
            "Sales concentrated near stock price highs",
            "Large block trades rather than systematic programs",
            "Sales preceded or followed by significant news",
            "Inconsistent selling cadence",
            "Sales correlate with analyst upgrades or positive earnings"
        ]
    },
    "liquidity_event_driven": {
        "label": "Liquidity Event Driven",
        "colour": "#4DB96B",
        "description": "Triggered by specific events — IPO lock-up expiry, M&A completion, vesting cliff. Sells in concentrated windows around catalysts rather than continuously.",
        "signals": [
            "First significant sales post lock-up expiry",
            "Sales clustered around vesting events",
            "Inactivity between major corporate events",
            "Large concentrated sales rather than drip selling",
            "Sales follow announced corporate transactions"
        ]
    },
    "undetermined": {
        "label": "Insufficient Data",
        "colour": "#A5A5A5",
        "description": "Insufficient transaction history or behavioural data to classify reliably.",
        "signals": []
    }
}


def search_founder_behaviour(name: str, company: str) -> list:
    queries = [
        f"{name} {company} insider sales history stake reduction",
        f"{name} 10b5-1 trading plan shares sold",
    ]
    results = []
    for query in queries[:2]:
        try:
            params = {
                "engine": "google",
                "q": query,
                "api_key": SERPAPI_KEY,
                "num": 4,
                "gl": "us",
            }
            r = requests.get("https://serpapi.com/search", params=params, timeout=15)
            if r.status_code == 200:
                for item in r.json().get("organic_results", []):
                    results.append({
                        "title": item.get("title", ""),
                        "snippet": item.get("snippet", ""),
                        "source": item.get("displayed_link", "")
                    })
        except Exception:
            continue
    return results[:8]


def classify_founder(brief: dict, ticker: str = None) -> dict:
    name = brief.get("individual_name", "Unknown")
    company = brief.get("company", "Unknown")

    print(f"    Running playbook classification for {name}...")

    # Pull Form 4 history from EDGAR
    form4_data = fetch_form4_history(name, company, ticker)

    # Supplementary web research
    behaviour_research = search_founder_behaviour(name, company)
    research_text = "\n".join([
        f"- {r['title']}: {r['snippet']}"
        for r in behaviour_research
    ])

    # Format Form 4 data
    form4_summary = form4_data.get("summary", {})
    transactions = form4_data.get("transactions", [])
    ownership_history = form4_data.get("ownership_history", [])

    transaction_text = "No Form 4 open market sales found in EDGAR.\n"
    if transactions:
        transaction_text = f"EDGAR Form 4 transactions ({len(transactions)} found):\n"
        for t in transactions:
            transaction_text += (
                f"  {t.get('transaction_date')} | {t.get('type')} | "
                f"{t.get('shares')} shares | {t.get('price_per_share')} | "
                f"Total: {t.get('total_value')} | Security: {t.get('security')}\n"
            )

    ownership_text = ""
    if ownership_history:
        ownership_text = f"\n20-F OWNERSHIP HISTORY ({len(ownership_history)} annual filings):\n"
        for o in ownership_history:
            ownership_text += (
                f"  {o.get('filing_date')} | "
                f"Ownership %: {o.get('ownership_percentages')} | "
                f"Shares: {o.get('share_counts')}\n"
            )

    # Note about foreign private issuers
    fpi_note = ""
    if not transactions or form4_summary.get("total_sales", 0) == 0:
        fpi_note = """
NOTE ON DATA GAPS: This company may be a foreign private issuer (FPI). FPIs are exempt from
real-time Form 4 insider reporting. Sales may instead be disclosed via:
- SGX filings (for Singapore-listed or Singapore-incorporated companies)
- 6-K filings (current reports for foreign private issuers)
- 20-F annual reports (Item 7 beneficial ownership)
The trigger event data in the brief below should be treated as primary source data
even if not reflected in Form 4s.
"""

    prompt = f"""You are a senior wealth advisor at ICONIQ Capital classifying a founder's liquidity behaviour archetype.

FOUNDER: {name}
COMPANY: {company}
TRIGGER EVENT: {brief.get('last_trigger_type', '')}

CONFIRMED TRIGGER EVENT (PRIMARY SOURCE DATA):
{(brief.get('event_summary') or '')[:600]}

INDIVIDUAL PROFILE:
{(brief.get('individual_profile') or '')[:500]}

WEALTH & CONTROL ANALYSIS:
{(brief.get('wealth_control_analysis') or '')[:400]}

SEC EDGAR FORM 4 DATA:
{transaction_text}
{fpi_note}
{ownership_text}

SUPPLEMENTARY WEB RESEARCH:
{research_text[:800]}

CLASSIFICATION INSTRUCTIONS:
Classify this founder's liquidity archetype based on ALL available evidence including:
1. The confirmed trigger event data (treat as primary source even if not in Form 4)
2. Form 4 transaction history (or note its absence for FPIs)
3. Ownership history from 20-F filings
4. Web research on historical behaviour
5. Structural factors (dual-class shares, voting control, 10b5-1 plans)

Key analytical questions:
- Has this founder sold before? When, how much, at what price relative to history?
- Is the current sale the first known liquidity event, or part of a pattern?
- Does the use of 10b5-1 suggest programmatic vs opportunistic intent?
- What does the sale size (as % of position) suggest about intent?
- Did the founder hold through major drawdowns before selling?
- How does voting control compare to economic interest?

ARCHETYPES:
1. gradual_diversifier — Systematic selling via 10b5-1, patient, not price-driven
2. control_maximiser — Minimal selling, prioritises governance over liquidity
3. opportunistic_seller — Sells at peaks, inconsistent timing, price-driven
4. liquidity_event_driven — Sells around specific catalysts (IPO, lock-up, vesting)
5. undetermined — Genuinely insufficient data to classify

Only use "undetermined" if you truly cannot distinguish between archetypes.
If this is the founder's first known sale after years of holding, that IS meaningful data.

Respond with JSON only:
{{
  "archetype": "gradual_diversifier|control_maximiser|opportunistic_seller|liquidity_event_driven|undetermined",
  "confidence": "High|Medium|Low",
  "data_quality": "description of data available",
  "primary_evidence": ["evidence 1 with source", "evidence 2", "evidence 3"],
  "counter_evidence": ["complicating factors"],
  "transaction_pattern": "plain language description of what the data shows",
  "behavioural_summary": "2-3 sentences on the overall pattern",
  "peer_comparables": [
    {{"name": "founder name", "company": "company", "archetype": "archetype", "relevance": "why comparable"}}
  ],
  "conversation_implication": "how this should shape ICONIQ outreach",
  "key_question": "single most important question to ask this founder"
}}"""

    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )

        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip().rstrip("```").strip()

        result = json.loads(text)

        archetype_key = result.get("archetype", "undetermined")
        archetype_meta = ARCHETYPES.get(archetype_key, ARCHETYPES["undetermined"])
        result["archetype_label"] = archetype_meta["label"]
        result["archetype_colour"] = archetype_meta["colour"]
        result["archetype_description"] = archetype_meta["description"]
        result["archetype_signals"] = archetype_meta["signals"]
        result["form4_raw"] = form4_data

        return result

    except Exception as e:
        print(f"    Classifier error: {e}")
        return {
            "archetype": "undetermined",
            "archetype_label": "Insufficient Data",
            "archetype_colour": "#A5A5A5",
            "confidence": "Low",
            "data_quality": f"Classification failed: {e}",
            "primary_evidence": [],
            "counter_evidence": [],
            "transaction_pattern": "Classification failed.",
            "behavioural_summary": "Manual research required.",
            "peer_comparables": [],
            "conversation_implication": "Manual research required before outreach.",
            "key_question": "What is your approach to managing your equity position over time?",
            "form4_raw": form4_data
        }
