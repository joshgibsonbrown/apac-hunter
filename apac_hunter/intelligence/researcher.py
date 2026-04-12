import logging
import os
import requests
import anthropic
from dotenv import load_dotenv

from apac_hunter.intelligence.schemas import ResearchDossier, parse_llm_json

load_dotenv()

log = logging.getLogger(__name__)

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def search_web(query: str, num_results: int = 5) -> list:
    """Run a single web search via SerpApi and return results."""
    if not SERPAPI_KEY:
        return []
    try:
        params = {
            "engine": "google",
            "q": query,
            "api_key": SERPAPI_KEY,
            "num": num_results,
            "hl": "en",
            "gl": "sg",
        }
        response = requests.get("https://serpapi.com/search", params=params, timeout=15)
        if response.status_code != 200:
            return []
        data = response.json()
        return [
            {
                "title": r.get("title", ""),
                "snippet": r.get("snippet", ""),
                "url": r.get("link", ""),
                "source": r.get("displayed_link", ""),
            }
            for r in data.get("organic_results", [])
        ]
    except Exception as exc:
        log.warning("Search error for query '%s': %s", query[:60], exc)
        return []


def research_individual(name: str, company: str, trigger_type: str, country: str = None) -> dict:
    """
    Run targeted web research on an individual before brief generation.
    Returns a structured research dossier dict.
    """
    print(f"    Running pre-brief research for {name}...")

    location = country or "Singapore"
    all_results: list = []

    queries = [
        f"{name} {company} founder wealth net worth",
        f"{name} {company} Singapore family background",
        f"{name} board director investments portfolio",
        f"{name} {company} shareholder stake ownership",
        f"{name} family office wealth management Singapore",
        f"{name} interview profile biography",
    ]

    if "family" in name.lower() or "family" in trigger_type.lower():
        queries.extend([
            f"{name} Singapore patriarch principal shareholder",
            f"{name} {company} major shareholder family member",
            f"{company} controlling shareholder family Singapore",
        ])

    if "IPO" in trigger_type or "listing" in trigger_type.lower():
        queries.append(f"{name} {company} IPO listing founder stake")

    if "voting" in trigger_type.lower() or "structure" in trigger_type.lower():
        queries.append(f"{name} {company} voting rights dual class shares control")

    for query in queries[:6]:
        for r in search_web(query, num_results=4):
            if r not in all_results:
                all_results.append(r)

    if not all_results:
        return ResearchDossier(
            confirmed_identity=f"{name} — no web results found",
            research_confidence="Low",
            gaps="No search results available",
        ).model_dump()

    results_text = "\n\n".join([
        f"Source: {r['source']}\nTitle: {r['title']}\nSnippet: {r['snippet']}"
        for r in all_results[:20]
    ])

    prompt = f"""You are a research analyst at ICONIQ Capital preparing background intelligence on a potential client.

Synthesise the following web search results into a structured research dossier on:
Individual: {name}
Company: {company}
Trigger: {trigger_type}
Location: {location}

SEARCH RESULTS:
{results_text}

Produce a JSON response with these fields. Be specific and factual — only include what is evidenced in the search results. If uncertain, say so. Do not invent facts.

{{
  "confirmed_identity": "Who this person actually is — full name, role, background. If a family name, identify the most likely principal individual.",
  "net_worth_estimate": "Best estimate of net worth with source and confidence level",
  "wealth_composition": "How their wealth is structured — listed equity, private assets, real estate, etc.",
  "family_background": "Relevant family context — dynasty, other family members in business, succession situation",
  "board_roles": "Current and recent board memberships beyond their primary company",
  "known_investments": "Notable personal investments, co-investments, or portfolio companies",
  "advisors_and_bankers": "Known advisors, private bankers, lawyers, or institutional relationships",
  "public_profile": "How public/private this person is — media appearances, interviews, conference presence",
  "recent_news": "Most relevant recent developments beyond the trigger event",
  "research_confidence": "High/Medium/Low — how complete is this picture",
  "gaps": "What we don't know that would be useful"
}}

Respond with JSON only."""

    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text
    except Exception as exc:
        log.error("Research synthesis API error for %s: %s", name, exc)
        return _fallback_dossier(name, all_results)

    dossier = parse_llm_json(raw, ResearchDossier, context=f"research:{name[:30]}")
    if dossier is None:
        log.warning("Research dossier parse failed for %s — using fallback", name)
        return _fallback_dossier(name, all_results)

    result = dossier.model_dump()
    result["raw_results"] = all_results[:10]
    return result


def _fallback_dossier(name: str, raw_results: list) -> dict:
    return ResearchDossier(
        confirmed_identity=f"{name} — synthesis failed, raw results available",
        research_confidence="Low",
        gaps="Research synthesis failed",
    ).model_dump() | {"raw_results": raw_results[:10]}
