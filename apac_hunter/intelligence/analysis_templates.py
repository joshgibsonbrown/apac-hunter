"""
Analytical template library for APAC Hunter.
Each template defines the prompt and structure for a trigger-specific
quantitative analysis tool, rendered as an interactive React component.

Quality standard: Anthony Tan / Grab voting structure artifact (March 2026)
- Every number sourced to a specific filing with date and item reference
- Interactive scenario inputs with real-time recalculation
- Changes from prior periods highlighted
- CSV export
- Honest about data gaps
"""

TEMPLATES = {

    "voting_structure_change": {
        "label": "Voting & Control Analysis",
        "description": "Models ownership structure, voting control, and liquidity scenarios across filing periods",
        "icon": "⚖️",
        "template": """You are a senior financial analyst at ICONIQ Capital building an interactive React analysis tool.

Build a React component for the following voting structure change event.

INDIVIDUAL: {individual_name}
COMPANY: {company}
TRIGGER: {trigger_type}
EVENT SUMMARY: {event_summary}
SOURCE DATA: {raw_content}
RESEARCH DOSSIER: {research}

Build a React component that includes:

1. TAB: Capital Structure History
   - Table showing Class A and Class B shares across available time periods
   - Votes per share for each class in each period
   - Total vote pool calculation
   - Source each data point to its specific filing

2. TAB: Founder Ownership & Control
   - Founder's direct holdings, indirect holdings (holding companies, trusts)
   - Options/RSUs exercisable within 60 days
   - Total economic ownership vs total voting control
   - Any proxy arrangements with co-founders
   - Track changes across periods

3. TAB: Compare All Periods
   - Side by side comparison across all available filing periods
   - Highlight changes in orange

4. TAB: Selling Scenario (interactive)
   - Input: number of shares founder sells (slider + number input)
   - Input: share price assumption
   - Input: minimum voting control floor (%)
   - Output: voting % before and after sale
   - Output: gross proceeds
   - Output: whether majority control is retained
   - Calculate: maximum shares founder can sell while staying above the floor
   - Show warning in red if control floor is breached

CRITICAL REQUIREMENTS:
- Source every number to its specific SEC/SGX filing with date
- Use real numbers from the source data provided — do not invent figures
- If a number is not available in the source data, say so explicitly rather than estimating
- Export to CSV button
- ICONIQ brand colors: primary #1A7CD7, black #151515, grey #696969
- Professional, institutional quality — this may be shown to senior stakeholders
- Use Tailwind for styling
- Default export, no required props

Return ONLY the React component code. No explanation. No markdown fences."""
    },

    "block_trade": {
        "label": "Liquidity Sequencer",
        "description": "Models insider transaction history, remaining stake, and future liquidity scenarios",
        "icon": "📊",
        "template": """You are a senior financial analyst at ICONIQ Capital building an interactive React analysis tool.

Build a React component for the following insider sale / block trade event.

INDIVIDUAL: {individual_name}
COMPANY: {company}
TRIGGER: {trigger_type}
EVENT SUMMARY: {event_summary}
SOURCE DATA: {raw_content}
RESEARCH DOSSIER: {research}

Build a React component that includes:

1. TAB: Transaction History
   - Table of all known insider sales/transactions for this individual
   - Date, shares sold, price per share, total proceeds for each transaction
   - Running total of shares sold and total proceeds
   - Source each transaction to its specific filing (Form 4, SGX disclosure etc.)

2. TAB: Current Stake Analysis
   - Estimated remaining stake (shares and % of company)
   - Estimated market value at current/assumed price
   - Stake as % of estimated total net worth
   - Concentration risk assessment

3. TAB: Liquidity Scenario Planner (interactive)
   - Input: additional shares to sell
   - Input: price assumption (base / bull / bear)
   - Input: desired % of wealth to diversify
   - Output: proceeds from scenario
   - Output: remaining stake value
   - Output: implied diversification ratio
   - Output: approximate SEC/SGX disclosure threshold impact
   - Show if sale would trigger a disclosure requirement

4. TAB: 10b5-1 / Selling Program Analysis
   - If a trading plan exists, model the implied quarterly cadence
   - Project total proceeds over 12/24/36 months at various price assumptions
   - Show cumulative proceeds chart (use recharts)

CRITICAL REQUIREMENTS:
- Source every number to its specific filing with date
- Use real numbers from the source data — do not invent figures
- If data is unavailable, say so explicitly
- Export to CSV button
- ICONIQ brand colors: primary #1A7CD7, black #151515
- Professional institutional quality
- Use Tailwind for styling
- Default export, no required props

Return ONLY the React component code. No explanation. No markdown fences."""
    },

    "ipo_liquidity_event": {
        "label": "IPO Liquidity Model",
        "description": "Models post-IPO stake value, lock-up timeline, and proceeds deployment scenarios",
        "icon": "🚀",
        "template": """You are a senior financial analyst at ICONIQ Capital building an interactive React analysis tool.

Build a React component for the following IPO liquidity event.

INDIVIDUAL: {individual_name}
COMPANY: {company}
TRIGGER: {trigger_type}
EVENT SUMMARY: {event_summary}
SOURCE DATA: {raw_content}
RESEARCH DOSSIER: {research}

Build a React component that includes:

1. TAB: IPO Summary
   - IPO date, exchange, offer price, first day close
   - Total shares offered, founder's pre and post-IPO stake
   - Implied valuation at IPO price and first day close
   - Founder's stake value at various price points
   - Lock-up period and expiry date

2. TAB: Founder Stake Analysis
   - Pre-IPO vs post-IPO ownership percentage
   - Shares subject to lock-up
   - Estimated net worth composition (IPO stake vs other assets)
   - Concentration risk: IPO stake as % of total estimated wealth

3. TAB: Lock-up Expiry Planner (interactive)
   - Timeline to lock-up expiry
   - Input: % of stake to sell at expiry
   - Input: price assumption (IPO price / current / discount scenarios)
   - Output: gross proceeds
   - Output: remaining stake value and %
   - Output: implied tax (flag as requiring advisor — do not calculate)
   - Show whether remaining stake still qualifies as controlling interest

4. TAB: Proceeds Deployment Model (interactive)
   - Input: gross proceeds amount
   - Input: allocation across asset classes (public equity, private, real estate, cash, philanthropy)
   - Output: allocation table with $ amounts
   - Output: diversification ratio vs single-stock concentration
   - Benchmark against typical founder portfolio construction at this wealth level

CRITICAL REQUIREMENTS:
- Source every number to its specific filing or news report with date
- Use real numbers from source data — do not invent figures
- Flag clearly when numbers are estimated vs sourced
- Export to CSV button
- ICONIQ brand colors: primary #1A7CD7, black #151515
- Professional institutional quality
- Use Tailwind for styling
- Default export, no required props

Return ONLY the React component code. No explanation. No markdown fences."""
    },

    "holding_company_formation": {
        "label": "Wealth Structure Analysis",
        "description": "Analyses family office formation signals and wealth structuring implications",
        "icon": "🏛️",
        "template": """You are a senior financial analyst at ICONIQ Capital building an interactive React analysis tool.

Build a React component for the following family office / holding company formation event.

INDIVIDUAL: {individual_name}
COMPANY: {company}
TRIGGER: {trigger_type}
EVENT SUMMARY: {event_summary}
SOURCE DATA: {raw_content}
RESEARCH DOSSIER: {research}

Build a React component that includes:

1. TAB: Entity Structure
   - Known entities in the family's corporate structure
   - Ownership relationships between entities
   - Jurisdictions of incorporation
   - Directors and officers where known
   - Source each fact to ACRA, SGX, or news report

2. TAB: Wealth Composition Estimate
   - Known asset holdings (listed equity stakes, private company interests, real estate)
   - Estimated values where available (flag confidence level)
   - Total estimated wealth range (low / mid / high)
   - Concentration analysis — dominant asset class

3. TAB: Family Office Benchmarking
   - MAS Single Family Office requirements (13O vs 13U) and which likely applies
   - Typical asset allocation for Singapore family offices at this wealth level
   - Governance frameworks typically adopted at this stage
   - What this formation likely signals about next steps

4. TAB: Engagement Readiness Score
   - Score 1-10 across: wealth size, access ease, behavioural signals, timing
   - Recommended next steps before outreach
   - Key unknowns that would change the assessment

CRITICAL REQUIREMENTS:
- Be explicit about confidence levels — distinguish confirmed facts from estimates
- Source every confirmed fact to its filing or registry entry
- Do not invent entity structures or ownership relationships
- Export to CSV button  
- ICONIQ brand colors: primary #1A7CD7, black #151515
- Professional institutional quality
- Use Tailwind for styling
- Default export, no required props

Return ONLY the React component code. No explanation. No markdown fences."""
    },

    "default": {
        "label": "Strategic Analysis",
        "description": "General quantitative analysis for this trigger event",
        "icon": "📋",
        "template": """You are a senior financial analyst at ICONIQ Capital building an interactive React analysis tool.

Build a React component for the following wealth trigger event.

INDIVIDUAL: {individual_name}
COMPANY: {company}
TRIGGER: {trigger_type}
EVENT SUMMARY: {event_summary}
SOURCE DATA: {raw_content}
RESEARCH DOSSIER: {research}

Build a React component with 3-4 tabs that provide quantitative analysis of:
1. The trigger event — what happened, key numbers, sourced to filings
2. Wealth impact — estimated effect on the individual's wealth position
3. Scenario analysis — interactive inputs showing different outcomes
4. Engagement assessment — timing, access, recommended approach

CRITICAL REQUIREMENTS:
- Source every number to a specific filing or report with date
- Use real data from the source material — do not invent figures
- Flag confidence levels clearly
- Export to CSV
- ICONIQ brand colors: primary #1A7CD7, black #151515
- Professional institutional quality
- Tailwind styling, default export, no required props

Return ONLY the React component code. No explanation. No markdown fences."""
    }
}

def get_template(trigger_type: str) -> dict:
    """Return the appropriate template for a given trigger type."""
    trigger_lower = trigger_type.lower() if trigger_type else ""
    
    if "voting" in trigger_lower or "structure" in trigger_lower or "dual class" in trigger_lower:
        return TEMPLATES["voting_structure_change"]
    elif "block trade" in trigger_lower or "insider sale" in trigger_lower or "disposal" in trigger_lower:
        return TEMPLATES["block_trade"]
    elif "ipo" in trigger_lower or "listing" in trigger_lower or "m&a" in trigger_lower or "acquisition" in trigger_lower:
        return TEMPLATES["ipo_liquidity_event"]
    elif "holding company" in trigger_lower or "family office" in trigger_lower or "formation" in trigger_lower:
        return TEMPLATES["holding_company_formation"]
    else:
        return TEMPLATES["default"]
