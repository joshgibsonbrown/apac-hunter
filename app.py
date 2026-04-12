import os
import logging
import threading
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from dotenv import load_dotenv

load_dotenv()

# ── Fail-fast on required secrets ─────────────────────────────────────────────
_REQUIRED = ["SECRET_KEY", "DASHBOARD_PASSWORD", "ANTHROPIC_API_KEY", "SUPABASE_URL", "SUPABASE_KEY"]
_missing = [k for k in _REQUIRED if not os.getenv(k)]
if _missing:
    raise RuntimeError(
        f"Missing required environment variables: {', '.join(_missing)}\n"
        "Copy .env.example to .env and fill in all required values."
    )

from apac_hunter.database import (
    get_all_briefs, get_brief_by_id, get_recent_events, get_briefs_by_region,
    get_briefs, update_brief_status, WORKFLOW_STATUSES,
    save_scan_job, update_scan_job, get_scan_job, get_latest_scan_job,
)
from apac_hunter.scanner import run_scan, get_last_scan_stats
from apac_hunter.regions import ALL_REGIONS
from apac_hunter.intelligence.lockup_tracker import get_upcoming_lockups
from apac_hunter.intelligence.classifier import TRIGGER_ARCHETYPES
from apac_hunter.intelligence.insider_tracker import (
    get_recent_insider_transactions, get_insider_transaction_count,
)

log = logging.getLogger(__name__)

app = Flask(__name__, template_folder="apac_hunter/templates", static_folder="apac_hunter/static")
app.secret_key = os.environ["SECRET_KEY"]
DASHBOARD_PASSWORD = os.environ["DASHBOARD_PASSWORD"]

def logged_in():
    return session.get("authenticated")

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == DASHBOARD_PASSWORD:
            session["authenticated"] = True
            return redirect(url_for("dashboard"))
        error = "Incorrect password"
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
def dashboard():
    if not logged_in():
        return redirect(url_for("login"))
    status_filter = request.args.get("status")
    trigger_filter = request.args.get("trigger")
    sort_by = request.args.get("sort", "newest")
    briefs = get_briefs(status_filter=status_filter, trigger_filter=trigger_filter, sort_by=sort_by)
    events = get_recent_events(limit=20)
    lockups = get_upcoming_lockups(days_ahead=30)
    insider_count = get_insider_transaction_count(days=30)
    insider_sales = get_recent_insider_transactions(days=30, limit=10)
    scan_stats = get_last_scan_stats()
    return render_template("dashboard.html", briefs=briefs, events=events,
                           all_regions=ALL_REGIONS, lockups=lockups,
                           insider_count=insider_count, insider_sales=insider_sales,
                           scan_stats=scan_stats,
                           workflow_statuses=WORKFLOW_STATUSES,
                           trigger_types=TRIGGER_ARCHETYPES,
                           active_status=status_filter,
                           active_trigger=trigger_filter,
                           active_sort=sort_by)

@app.route("/brief/<brief_id>")
def brief_detail(brief_id):
    if not logged_in():
        return redirect(url_for("login"))
    brief = get_brief_by_id(brief_id)
    if not brief:
        return "Brief not found", 404
    return render_template("brief.html", brief=brief[0])

@app.route("/briefs/<region_id>")
def briefs_by_region(region_id):
    if not logged_in():
        return redirect(url_for("login"))
    if region_id not in ALL_REGIONS:
        return jsonify({"error": f"Unknown region: {region_id}"}), 404
    status_filter = request.args.get("status")
    trigger_filter = request.args.get("trigger")
    sort_by = request.args.get("sort", "newest")
    briefs = get_briefs(region_id=region_id, status_filter=status_filter,
                        trigger_filter=trigger_filter, sort_by=sort_by)
    events = get_recent_events(limit=20)
    lockups = get_upcoming_lockups(days_ahead=30)
    insider_count = get_insider_transaction_count(days=30)
    insider_sales = get_recent_insider_transactions(days=30, limit=10)
    scan_stats = get_last_scan_stats()
    return render_template("dashboard.html", briefs=briefs, events=events,
                           all_regions=ALL_REGIONS, active_region=region_id,
                           lockups=lockups, insider_count=insider_count,
                           insider_sales=insider_sales, scan_stats=scan_stats,
                           workflow_statuses=WORKFLOW_STATUSES,
                           trigger_types=TRIGGER_ARCHETYPES,
                           active_status=status_filter,
                           active_trigger=trigger_filter,
                           active_sort=sort_by)

@app.route("/analysis/<brief_id>")
def analysis(brief_id):
    if not logged_in():
        return redirect(url_for("login"))
    brief = get_brief_by_id(brief_id)
    if not brief:
        return "Brief not found", 404
    return render_template("analysis_template.html", brief=brief[0])

@app.route("/analysis/<brief_id>/generate", methods=["POST"])
def generate_analysis_route(brief_id):
    if not logged_in():
        return jsonify({"error": "Not authenticated"}), 401
    brief = get_brief_by_id(brief_id)
    if not brief:
        return jsonify({"error": "Brief not found"}), 404
    try:
        from apac_hunter.intelligence.analysis_engine import build_template_analysis
        result = build_template_analysis(brief[0])
        return jsonify({"success": True, "result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/scan", methods=["POST"])
def trigger_scan():
    if not logged_in():
        return jsonify({"error": "Not authenticated"}), 401

    days_back = int(request.form.get("days_back", 7))
    regions_raw = request.form.get("regions", "apac")
    regions = [r.strip().lower() for r in regions_raw.split(",") if r.strip()]
    if not regions:
        regions = ["apac"]
    scan_mode = request.form.get("scan_mode", "quick")

    params = {"days_back": days_back, "regions": regions, "scan_mode": scan_mode}
    job_id = save_scan_job(params)
    if not job_id:
        return jsonify({"error": "Failed to create scan job"}), 500

    def progress_callback(progress: int, status: str) -> None:
        try:
            update_scan_job(job_id, {"progress": progress, "status_message": status})
        except Exception as exc:
            log.warning("Failed to update scan job %s: %s", job_id, exc)

    def run_scan_thread():
        update_scan_job(job_id, {"status": "running", "progress": 5,
                                  "status_message": f"Starting {scan_mode} scan..."})
        try:
            briefs = run_scan(
                days_back=days_back,
                regions=regions,
                scan_mode=scan_mode,
                progress_callback=progress_callback,
            )
            update_scan_job(job_id, {
                "status": "complete",
                "progress": 100,
                "status_message": f"Complete — {len(briefs)} brief(s) generated",
                "briefs_generated": len(briefs),
            })
        except Exception as exc:
            log.exception("Scan job %s failed", job_id)
            update_scan_job(job_id, {
                "status": "failed",
                "progress": 0,
                "status_message": f"Error: {exc}",
                "error": str(exc),
            })

    thread = threading.Thread(target=run_scan_thread, daemon=True)
    thread.start()
    return jsonify({"success": True, "job_id": job_id, "message": "Scan started"})


@app.route("/scan/status")
def scan_status():
    if not logged_in():
        return jsonify({"error": "Not authenticated"}), 401

    job_id = request.args.get("job_id")
    if job_id:
        job = get_scan_job(job_id)
    else:
        job = get_latest_scan_job()

    if not job:
        return jsonify({"running": False, "progress": 0, "status": "No scan run yet", "error": None})

    # Normalise to the shape the dashboard JS expects
    return jsonify({
        "job_id": job.get("id"),
        "running": job.get("status") == "running",
        "progress": job.get("progress", 0),
        "status": job.get("status_message", ""),
        "error": job.get("error"),
        "briefs_generated": job.get("briefs_generated", 0),
    })

@app.route("/brief/<brief_id>/status", methods=["PATCH"])
def update_workflow_status(brief_id):
    if not logged_in():
        return jsonify({"error": "Not authenticated"}), 401
    data = request.get_json(silent=True) or {}
    status = data.get("status", "").strip()
    if not status:
        return jsonify({"error": "Missing status"}), 400
    if status not in WORKFLOW_STATUSES:
        return jsonify({"error": f"Invalid status. Must be one of: {', '.join(WORKFLOW_STATUSES)}"}), 400
    ok = update_brief_status(brief_id, status)
    if not ok:
        return jsonify({"error": "Update failed"}), 500
    return jsonify({"success": True, "status": status})


@app.route("/brief/<brief_id>/ask", methods=["POST"])
def ask_brief(brief_id):
    if not logged_in():
        return jsonify({"error": "Not authenticated"}), 401

    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "Missing question"}), 400
    if len(question) > 500:
        return jsonify({"error": "Question too long (max 500 characters)"}), 400

    brief_rows = get_brief_by_id(brief_id)
    if not brief_rows:
        return jsonify({"error": "Brief not found"}), 404
    brief = brief_rows[0]

    answer = _answer_brief_question(brief, question)
    return jsonify({"answer": answer})


def _answer_brief_question(brief: dict, question: str) -> str:
    """
    Answer a factual question grounded strictly in the brief and its source context.
    Returns a short answer string.
    """
    import anthropic as _anthropic

    # Assemble context — brief narrative sections
    why_bullets = brief.get("why_this_matters") or []
    why_text = ("\n".join(f"- {b}" for b in why_bullets)) if why_bullets else ""
    brief_text = "\n\n".join(filter(None, [
        f"INDIVIDUAL: {brief.get('individual_name')} | COMPANY: {brief.get('company')}",
        f"TRIGGER: {brief.get('last_trigger_type')}",
        f"EVIDENCE CONFIDENCE: {brief.get('confidence_level', 'Unknown')}",
        f"PROFILE:\n{brief.get('individual_profile', '')}",
        f"EVENT:\n{brief.get('event_summary', '')}",
        f"WHY THIS MATTERS:\n{why_text}" if why_text else "",
        f"WEALTH & CONTROL:\n{brief.get('wealth_control_analysis', '')}",
        f"NETWORK SIGNAL:\n{brief.get('network_signal', '')}",
        f"BEHAVIOURAL SIGNALS:\n{brief.get('behavioural_signals', '')}",
        f"ICONIQ VALUE:\n{brief.get('iconiq_value_prop', '')}",
        f"SUGGESTED APPROACH:\n{brief.get('suggested_conversation', '')}",
    ]))

    # Raw source context (filing content + research facts), if stored
    source_text = ""
    ctx = brief.get("source_context") or {}
    if ctx:
        trigger_ctx = ctx.get("trigger", {})
        research_ctx = ctx.get("research", {})
        research_sources = ctx.get("research_sources", [])
        detection_meta = ctx.get("detection_metadata", {})
        key_facts = ctx.get("key_facts", [])
        parts = []

        if trigger_ctx.get("raw_content"):
            parts.append(f"SOURCE FILING CONTENT:\n{trigger_ctx['raw_content'][:2000]}")
        if trigger_ctx.get("headline"):
            parts.append(f"HEADLINE: {trigger_ctx['headline']}")
        if trigger_ctx.get("significance"):
            parts.append(f"SIGNIFICANCE: {trigger_ctx['significance']}")
        if trigger_ctx.get("estimated_net_worth_notes"):
            parts.append(f"NET WORTH NOTES: {trigger_ctx['estimated_net_worth_notes']}")

        if detection_meta:
            meta_lines = "\n".join(f"  {k}: {v}" for k, v in detection_meta.items())
            parts.append(f"DETECTION FACTS (structured):\n{meta_lines}")

        if key_facts:
            parts.append("KEY FACTS (extracted at brief generation time):\n" +
                         "\n".join(f"- {f}" for f in key_facts))

        why_this_matters = ctx.get("why_this_matters", [])
        if why_this_matters:
            parts.append("WHY THIS MATTERS (client development relevance):\n" +
                         "\n".join(f"- {b}" for b in why_this_matters))

        if research_ctx:
            dossier_lines = "\n".join(
                f"{k}: {v}" for k, v in research_ctx.items() if v and v != "Unknown"
            )
            if dossier_lines:
                parts.append(f"RESEARCH DOSSIER:\n{dossier_lines}")

        if research_sources:
            citations = "\n\n".join(
                f"[{i+1}] {s.get('source', '')} — {s.get('title', '')}\n"
                f"    {s.get('snippet', '')}\n"
                f"    URL: {s.get('url', '')}"
                for i, s in enumerate(research_sources)
            )
            parts.append(f"RESEARCH SOURCE CITATIONS:\n{citations}")

        source_text = "\n\n".join(parts)

    prompt = f"""You are answering a specific factual question about the following intelligence brief.

Work through the evidence in this strict priority order:
1. DETECTION FACTS (structured) — use first for any quantitative question
2. KEY FACTS — use for specific factual claims
3. RESEARCH SOURCE CITATIONS — use for source attribution or background
4. RESEARCH DOSSIER / BRIEF SUMMARY — use as last resort only

Be concise and direct. If the answer is present, give it in one or two sentences.
If the answer is not in any section, respond with: "This information is not in the brief context." and name the specific section or data type that would be needed (e.g. "The calculation inputs were not stored for this brief" or "No research sources were retrieved for this brief").
Do not infer, extrapolate, or use outside knowledge. Do not fabricate numbers or facts.

--- BRIEF CONTEXT ---
{brief_text}

--- SOURCE CONTEXT ---
{source_text if source_text else "[No additional source context stored for this brief]"}

--- QUESTION ---
{question}

Answer:"""

    try:
        _client = _anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        response = _client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()
    except Exception as exc:
        log.error("Q&A API error for brief %s: %s", brief.get("id", ""), exc)
        return "Unable to answer at this time — API error."


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
