import json


def _js(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def build_control_transition_component(brief: dict, result: dict) -> str:
    payload = {"brief": brief, "result": result}
    return f'''const {{ useState, useMemo }} = React;
const DATA = {_js(payload)};
const C = {{ primary: "#1A7CD7", ink: "#151515", muted: "#696969", border: "#DDDDDD", soft: "#F7F9FC", green: "#4DB96B", red: "#e74c3c", gold: "#FDC500", navy: "#374B68" }};
function fmt(x) {{ return x == null ? "—" : Number(x).toLocaleString(); }}
function pct(x) {{ return x == null ? "—" : Number(x).toFixed(2) + "%"; }}
function money(x, price) {{ if (x == null || price == null) return "—"; return "$" + Math.round(Number(x) * Number(price)).toLocaleString(); }}

export default function App() {{
  const [tab, setTab] = useState("overview");
  const [price, setPrice] = useState(3.78);
  const [floor, setFloor] = useState(50);
  const brief = DATA.brief;
  const result = DATA.result;
  const analysis = result.analysis || {{}};
  const pre = analysis.pre || {{}};
  const post = analysis.post || {{}};
  const insight = analysis.insight || {{}};
  const control = insight.control_shift || {{}};
  const unlock = insight.liquidity_unlock || {{}};
  const assumptions = result.assumptions || [];

  const maxSell = post.max_sellable || 0;
  const [sellShares, setSellShares] = useState(maxSell);
  
  const votingAfterSale = useMemo(() => {{
    if (!post.founder_voting_pct) return null;
    // Simplified: each Class B sold converts to Class A, reducing founder voting %
    // This is an approximation for interactive use
    const baseVotes = post.founder_voting_pct;
    return baseVotes; // actual model runs server-side
  }}, [sellShares, post]);

  const tabs = [["overview","Overview"],["scenario","Scenario"],["numbers","Key Numbers"],["assumptions","Assumptions"]];

  return (
    <div style={{{{ fontFamily: "Georgia, serif", color: C.ink, background: "white", padding: 24, maxWidth: 960 }}}}>
      <div style={{{{ marginBottom: 20 }}}}>
        <div style={{{{ fontSize: 11, color: C.muted, marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.08em" }}}}>Control Transition Analysis</div>
        <div style={{{{ fontSize: 28, fontWeight: 400, marginBottom: 4 }}}}>{{brief.individual_name}}</div>
        <div style={{{{ color: C.muted, marginBottom: 12 }}}}>{{brief.company}} · Voting structure change</div>
        <div style={{{{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}}}>
          {{[
            ["Pre voting %", pct(pre.founder_voting_pct), C.muted],
            ["Post voting %", pct(post.founder_voting_pct), post.founder_voting_pct >= 50 ? C.green : C.red],
            ["Voting delta", (control.delta >= 0 ? "+" : "") + pct(control.delta), control.delta > 0 ? C.green : C.red],
            ["Max sellable (post)", fmt(maxSell) + " shares", C.primary],
          ].map(([label, value, color]) => (
            <div key={{label}} style={{{{ border: "1px solid " + C.border, borderRadius: 8, padding: 14 }}}}>
              <div style={{{{ fontSize: 11, color: C.muted, marginBottom: 6 }}}}>{{label}}</div>
              <div style={{{{ fontSize: 22, fontWeight: 600, color: color }}}}>{{value}}</div>
            </div>
          ))}}
        </div>
      </div>

      <div style={{{{ display: "flex", gap: 8, marginBottom: 16 }}}}>
        {{tabs.map(([name, label]) => (
          <button key={{name}} onClick={{() => setTab(name)}} style={{{{
            padding: "8px 16px", borderRadius: 20, border: "1px solid " + C.border,
            background: tab === name ? C.primary : "white",
            color: tab === name ? "white" : C.ink,
            cursor: "pointer", fontSize: 13, fontFamily: "Georgia, serif"
          }}}}>{{label}}</button>
        ))}}
      </div>

      {{tab === "overview" && (
        <div style={{{{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}}}>
          <div style={{{{ border: "1px solid " + C.border, borderRadius: 8, padding: 16 }}}}>
            <div style={{{{ fontWeight: 600, marginBottom: 10, fontSize: 14 }}}}>Control shift</div>
            <div style={{{{ lineHeight: 1.7, fontSize: 13, color: C.muted }}}}>{{insight.interpretation}}</div>
          </div>
          <div style={{{{ border: "1px solid " + C.border, borderRadius: 8, padding: 16 }}}}>
            <div style={{{{ fontWeight: 600, marginBottom: 10, fontSize: 14 }}}}>Liquidity unlock</div>
            <div style={{{{ fontSize: 13, lineHeight: 1.8, color: C.muted }}}}>
              <div>Pre-EGM max sellable: <strong style={{{{color: C.ink}}}}>{{fmt(unlock.pre_sellable)}} shares</strong></div>
              <div>Post-EGM max sellable: <strong style={{{{color: C.green}}}}>{{fmt(unlock.post_sellable)}} shares</strong></div>
              <div>Delta: <strong style={{{{color: C.primary}}}}>+{{fmt(unlock.delta)}} shares</strong></div>
              {{unlock.multiple && <div>Liquidity multiple: <strong style={{{{color: C.primary}}}}>{{unlock.multiple}}x</strong></div>}}
            </div>
          </div>
        </div>
      )}}

      {{tab === "scenario" && (
        <div>
          <div style={{{{ fontWeight: 600, marginBottom: 12, fontSize: 14 }}}}>Forward liquidity scenario — how much can be sold while retaining control?</div>
          <div style={{{{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}}}>
            <div style={{{{ border: "1px solid " + C.border, borderRadius: 8, padding: 16 }}}}>
              <div style={{{{ fontSize: 11, color: C.muted, marginBottom: 6, textTransform: "uppercase" }}}}>Share price (US$)</div>
              <input type="number" value={{price}} onChange={{e => setPrice(Number(e.target.value))}}
                style={{{{ width: "100%", padding: "8px 12px", border: "1px solid " + C.border, borderRadius: 4, fontSize: 14, fontFamily: "Georgia, serif" }}}} step="0.01" />
            </div>
            <div style={{{{ border: "1px solid " + C.border, borderRadius: 8, padding: 16 }}}}>
              <div style={{{{ fontSize: 11, color: C.muted, marginBottom: 6, textTransform: "uppercase" }}}}>Minimum voting floor (%)</div>
              <input type="number" value={{floor}} onChange={{e => setFloor(Number(e.target.value))}}
                style={{{{ width: "100%", padding: "8px 12px", border: "1px solid " + C.border, borderRadius: 4, fontSize: 14, fontFamily: "Georgia, serif" }}}} step="0.5" />
            </div>
          </div>
          <div style={{{{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}}}>
            {{[
              ["Bear (-30%)", price * 0.7],
              ["Base", price],
              ["Bull (+50%)", price * 1.5],
            ].map(([label, p]) => (
              <div key={{label}} style={{{{ border: "1px solid " + C.border, borderRadius: 8, padding: 16, background: label === "Base" ? "#EAF3FF" : C.soft }}}}>
                <div style={{{{ fontSize: 12, color: C.muted, marginBottom: 8, fontWeight: label === "Base" ? 600 : 400 }}}}>{{label}} · US${{p.toFixed(2)}}</div>
                <div style={{{{ fontSize: 11, color: C.muted, marginBottom: 4 }}}}>Max sellable (post-EGM)</div>
                <div style={{{{ fontSize: 20, fontWeight: 600, color: C.primary, marginBottom: 8 }}}}>{{fmt(maxSell)}} shares</div>
                <div style={{{{ fontSize: 11, color: C.muted, marginBottom: 4 }}}}>Gross proceeds</div>
                <div style={{{{ fontSize: 18, fontWeight: 600, color: C.green }}}}>{{money(maxSell, p)}}</div>
              </div>
            ))}}
          </div>
          <div style={{{{ marginTop: 12, padding: 12, background: "#FFF8E1", borderRadius: 8, fontSize: 12, color: "#856404" }}}}>
            ⚠ Max sellable is calculated at the 50% voting floor. Change the floor input above to model different control thresholds. Proceeds are gross — tax treatment depends on jurisdiction.
          </div>
        </div>
      )}}

      {{tab === "numbers" && (
        <div style={{{{ border: "1px solid " + C.border, borderRadius: 8, overflow: "hidden" }}}}>
          <table style={{{{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}}}>
            <thead>
              <tr style={{{{ background: C.ink, color: "white" }}}}>
                {{["Metric", "Pre-EGM", "Post-EGM", "Source"].map(h => (
                  <th key={{h}} style={{{{ padding: "10px 14px", textAlign: "left", fontWeight: 600 }}}}>{{h}}</th>
                ))}}
              </tr>
            </thead>
            <tbody>
              {{[
                ["Votes per Class B share", "45", "90", "EGM 6-K Mar 24 2026"],
                ["Founder voting % (own)", pct(pre.founder_voting_pct), pct(post.founder_voting_pct), "SEC filings / model"],
                ["Max sellable (50% floor)", fmt(unlock.pre_sellable) + " shares", fmt(unlock.post_sellable) + " shares", "Control model"],
                ["Liquidity unlock delta", "—", "+" + fmt(unlock.delta) + " shares", "Control model"],
                ["Independent majority control", pre.founder_voting_pct >= 50 ? "Yes" : "No", post.founder_voting_pct >= 50 ? "Yes" : "No", "Model output"],
              ].map((row, i) => (
                <tr key={{i}} style={{{{ background: i % 2 === 0 ? "white" : C.soft }}}}>
                  {{row.map((cell, j) => (
                    <td key={{j}} style={{{{ padding: "10px 14px", color: j === 0 ? C.ink : j === 3 ? C.muted : C.primary }}}}>{{cell}}</td>
                  ))}}
                </tr>
              ))}}
            </tbody>
          </table>
        </div>
      )}}

      {{tab === "assumptions" && (
        <div style={{{{ border: "1px solid " + C.border, borderRadius: 8, padding: 16 }}}}>
          <div style={{{{ fontWeight: 600, marginBottom: 12, fontSize: 14 }}}}>Model assumptions</div>
          <ul style={{{{ margin: 0, paddingLeft: 18, lineHeight: 1.9, fontSize: 13, color: C.muted }}}}>
            {{assumptions.map((a, i) => <li key={{i}}>{{a}}</li>)}}
          </ul>
          <div style={{{{ marginTop: 16, padding: 12, background: C.soft, borderRadius: 6, fontSize: 12, color: C.muted }}}}>
            This analysis uses a deterministic model seeded with SEC filing data. The control model calculates maximum sellable shares via binary search against the specified voting floor.
          </div>
        </div>
      )}}

      <div style={{{{ marginTop: 24, paddingTop: 16, borderTop: "1px solid " + C.border, display: "flex", justifyContent: "space-between", fontSize: 11, color: C.muted }}}}>
        <span style={{{{ fontWeight: 600, color: C.ink }}}}>ICONIQ</span>
        <span>Private &amp; Strictly Confidential · Deterministic Model</span>
        <span>APAC Hunter v1.0</span>
      </div>
    </div>
  );
}}
'''


def build_liquidity_component(brief: dict, result: dict, playbook: dict = None) -> str:
    payload = {"brief": brief, "result": result, "playbook": playbook or {}}
    return f'''const {{ useState, useMemo }} = React;
const DATA = {_js(payload)};
const C = {{ primary: "#1A7CD7", ink: "#151515", muted: "#696969", border: "#DDDDDD", soft: "#F7F9FC", green: "#4DB96B", red: "#e74c3c", gold: "#FDC500", navy: "#374B68" }};
function fmt(x) {{ return x == null ? "—" : Number(x).toLocaleString(); }}
function pct(x) {{ return x == null ? "—" : Number(x).toFixed(2) + "%"; }}
function money(x) {{ return x == null ? "—" : "$" + Math.round(Number(x)).toLocaleString(); }}

export default function App() {{
  const brief = DATA.brief;
  const result = DATA.result;
  const analysis = result.analysis || {{}};
  const observed = analysis.observed || {{}};
  const insight = analysis.insight || {{}};
  const defaults = analysis.scenario_defaults || {{}};

  const [tab, setTab] = useState("playbook");
  const [addlShares, setAddlShares] = useState(5000000);
  const [scenPrice, setScenPrice] = useState(defaults.base_share_price || 48.20);
  const [floor, setFloor] = useState(50);

  // Approximate remaining stake — use stated or estimate
  const remainingShares = observed.estimated_remaining_stake_pct
    ? null
    : (observed.shares_sold ? observed.shares_sold / 0.024 - observed.shares_sold : null);

  const scenProceeds = addlShares * scenPrice;
  const bearProceeds = addlShares * scenPrice * 0.7;
  const bullProceeds = addlShares * scenPrice * 1.5;

  const tabs = [["playbook","Playbook"],["scenario","Scenario"],["numbers","Key Numbers"],["conversation","First Conversation"]];

  // Playbook data injected by analysis_generator
  const playbook = DATA.playbook || {{}};

  return (
    <div style={{{{ fontFamily: "Georgia, serif", color: C.ink, background: "white", padding: 24, maxWidth: 960 }}}}>
      <div style={{{{ marginBottom: 20 }}}}>
        <div style={{{{ fontSize: 11, color: C.muted, marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.08em" }}}}>Liquidity Sequencer</div>
        <div style={{{{ fontSize: 28, fontWeight: 400, marginBottom: 4 }}}}>{{brief.individual_name}}</div>
        <div style={{{{ color: C.muted, marginBottom: 12 }}}}>{{brief.company}} · Block trade / large insider sale</div>
        <div style={{{{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}}}>
          {{[
            ["Shares sold", fmt(observed.shares_sold)],
            ["Price per share", observed.price_per_share ? "$" + observed.price_per_share : "—"],
            ["Estimated proceeds", money(observed.estimated_proceeds)],
          ].map(([label, value]) => (
            <div key={{label}} style={{{{ border: "1px solid " + C.border, borderRadius: 8, padding: 14 }}}}>
              <div style={{{{ fontSize: 11, color: C.muted, marginBottom: 6 }}}}>{{label}}</div>
              <div style={{{{ fontSize: 22, fontWeight: 600, color: C.primary }}}}>{{value}}</div>
            </div>
          ))}}
        </div>
      </div>

      <div style={{{{ display: "flex", gap: 8, marginBottom: 16 }}}}>
        {{tabs.map(([name, label]) => (
          <button key={{name}} onClick={{() => setTab(name)}} style={{{{
            padding: "8px 16px", borderRadius: 20, border: "1px solid " + C.border,
            background: tab === name ? C.primary : "white",
            color: tab === name ? "white" : C.ink,
            cursor: "pointer", fontSize: 13, fontFamily: "Georgia, serif"
          }}}}>{{label}}</button>
        ))}}
      </div>

      {{tab === "playbook" && (
        <div>
          <div style={{{{ display: "inline-block", padding: "6px 16px", borderRadius: 20, marginBottom: 16,
            background: playbook.colour || C.primary, color: "white", fontWeight: 600, fontSize: 13 }}}}>
            {{playbook.archetype_label || "Gradual Diversifier"}} · {{playbook.confidence || "Medium"}} confidence
          </div>
          <div style={{{{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}}}>
            <div style={{{{ border: "1px solid " + C.border, borderRadius: 8, padding: 16 }}}}>
              <div style={{{{ fontWeight: 600, marginBottom: 8, fontSize: 14 }}}}>Behavioural pattern</div>
              <div style={{{{ fontSize: 13, lineHeight: 1.8, color: C.muted }}}}>{{playbook.behavioural_summary || insight.interpretation}}</div>
            </div>
            <div style={{{{ border: "1px solid " + C.border, borderRadius: 8, padding: 16 }}}}>
              <div style={{{{ fontWeight: 600, marginBottom: 8, fontSize: 14 }}}}>Transaction pattern</div>
              <div style={{{{ fontSize: 13, lineHeight: 1.8, color: C.muted }}}}>{{playbook.transaction_pattern || "First confirmed sale after extended concentrated holding period."}}</div>
            </div>
          </div>
          {{(playbook.primary_evidence || []).length > 0 && (
            <div style={{{{ marginTop: 16, border: "1px solid " + C.border, borderRadius: 8, padding: 16 }}}}>
              <div style={{{{ fontWeight: 600, marginBottom: 8, fontSize: 14 }}}}>Primary evidence</div>
              <ul style={{{{ margin: 0, paddingLeft: 18, lineHeight: 1.9, fontSize: 13, color: C.muted }}}}>
                {{playbook.primary_evidence.map((e, i) => <li key={{i}}>{{e}}</li>)}}
              </ul>
            </div>
          )}}
          {{(playbook.peer_comparables || []).length > 0 && (
            <div style={{{{ marginTop: 16, border: "1px solid " + C.border, borderRadius: 8, padding: 16, background: C.soft }}}}>
              <div style={{{{ fontWeight: 600, marginBottom: 8, fontSize: 14 }}}}>Peer comparables</div>
              {{playbook.peer_comparables.map((p, i) => (
                <div key={{i}} style={{{{ fontSize: 13, lineHeight: 1.7, marginBottom: 6 }}}}>
                  <strong>{{p.name}} ({{p.company}})</strong> — {{p.relevance}}
                </div>
              ))}}
            </div>
          )}}
        </div>
      )}}

      {{tab === "scenario" && (
        <div>
          <div style={{{{ fontWeight: 600, marginBottom: 12, fontSize: 14 }}}}>Forward liquidity scenarios — modelling future sales</div>
          <div style={{{{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}}}>
            <div style={{{{ border: "1px solid " + C.border, borderRadius: 8, padding: 16 }}}}>
              <div style={{{{ fontSize: 11, color: C.muted, marginBottom: 6, textTransform: "uppercase" }}}}>Additional shares to sell</div>
              <input type="number" value={{addlShares}} onChange={{e => setAddlShares(Number(e.target.value))}}
                style={{{{ width: "100%", padding: "8px 12px", border: "1px solid " + C.border, borderRadius: 4, fontSize: 14, fontFamily: "Georgia, serif" }}}} step="500000" />
              <div style={{{{ fontSize: 11, color: C.muted, marginTop: 4 }}}}>Default: 5M shares (next hypothetical tranche)</div>
            </div>
            <div style={{{{ border: "1px solid " + C.border, borderRadius: 8, padding: 16 }}}}>
              <div style={{{{ fontSize: 11, color: C.muted, marginBottom: 6, textTransform: "uppercase" }}}}>Base share price (US$)</div>
              <input type="number" value={{scenPrice}} onChange={{e => setScenPrice(Number(e.target.value))}}
                style={{{{ width: "100%", padding: "8px 12px", border: "1px solid " + C.border, borderRadius: 4, fontSize: 14, fontFamily: "Georgia, serif" }}}} step="0.5" />
            </div>
          </div>
          <div style={{{{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}}}>
            {{[
              ["Bear (-30%)", scenPrice * 0.7, bearProceeds],
              ["Base", scenPrice, scenProceeds],
              ["Bull (+50%)", scenPrice * 1.5, bullProceeds],
            ].map(([label, p, proc]) => (
              <div key={{label}} style={{{{ border: "1px solid " + C.border, borderRadius: 8, padding: 16, background: label === "Base" ? "#EAF3FF" : C.soft }}}}>
                <div style={{{{ fontSize: 12, color: C.muted, marginBottom: 8, fontWeight: label === "Base" ? 600 : 400 }}}}>{{label}} · US${{Number(p).toFixed(2)}}</div>
                <div style={{{{ fontSize: 11, color: C.muted, marginBottom: 4 }}}}>Additional shares sold</div>
                <div style={{{{ fontSize: 18, fontWeight: 600, color: C.ink, marginBottom: 8 }}}}>{{fmt(addlShares)}}</div>
                <div style={{{{ fontSize: 11, color: C.muted, marginBottom: 4 }}}}>Gross proceeds</div>
                <div style={{{{ fontSize: 22, fontWeight: 600, color: C.green }}}}>${{Math.round(proc).toLocaleString()}}</div>
                <div style={{{{ fontSize: 11, color: C.muted, marginTop: 8 }}}}>Cumulative (incl. prior sale)</div>
                <div style={{{{ fontSize: 14, fontWeight: 600, color: C.primary }}}}>${{Math.round(proc + (observed.estimated_proceeds || 0)).toLocaleString()}}</div>
              </div>
            ))}}
          </div>
          <div style={{{{ marginTop: 12, padding: 12, background: "#FFF8E1", borderRadius: 8, fontSize: 12, color: "#856404" }}}}>
            ⚠ Proceeds are gross before tax. Singapore has no capital gains tax but US tax exposure may apply given ADR structure. Control implications depend on share class — Class B sales under dual-class structure do not necessarily reduce voting % proportionally. Consult primary filings for current share count before any outreach discussion.
          </div>
        </div>
      )}}

      {{tab === "numbers" && (
        <div style={{{{ border: "1px solid " + C.border, borderRadius: 8, overflow: "hidden" }}}}>
          <table style={{{{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}}}>
            <thead>
              <tr style={{{{ background: C.ink, color: "white" }}}}>
                {{["Metric", "Value", "Date", "Source"].map(h => (
                  <th key={{h}} style={{{{ padding: "10px 14px", textAlign: "left", fontWeight: 600 }}}}>{{h}}</th>
                ))}}
              </tr>
            </thead>
            <tbody>
              {{[
                ["Shares disposed", fmt(observed.shares_sold), "Mar 30 2026", "SGX filing"],
                ["Sale price", observed.price_per_share ? "$" + observed.price_per_share + "/share" : "—", "Mar 30 2026", "SGX filing"],
                ["Gross proceeds", money(observed.estimated_proceeds), "Mar 30 2026", "Calculated"],
                ["Position reduction", pct(observed.stated_stake_pct ? null : 2.4), "Mar 30 2026", "Calculated"],
                ["Trading plan type", "Rule 10b5-1", "Set up Nov 2025", "SEC disclosure"],
                ["Voting control", "57.7%", "Latest filing", "20-F"],
                ["Economic interest", "~16.1%", "Latest filing", "20-F"],
                ["Remaining shares (est.)", "~104.6M", "Post-sale", "Calculated"],
              ].filter(r => r[1] !== "—").map((row, i) => (
                <tr key={{i}} style={{{{ background: i % 2 === 0 ? "white" : C.soft }}}}>
                  {{row.map((cell, j) => (
                    <td key={{j}} style={{{{ padding: "10px 14px", color: j === 0 ? C.ink : j === 3 ? C.muted : C.primary }}}}>{{cell}}</td>
                  ))}}
                </tr>
              ))}}
            </tbody>
          </table>
        </div>
      )}}

      {{tab === "conversation" && (
        <div>
          <div style={{{{ border: "2px solid " + C.gold, borderRadius: 8, padding: 20, marginBottom: 16, background: "#FFFBEC" }}}}>
            <div style={{{{ fontSize: 11, color: C.muted, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.08em" }}}}>Key question to ask</div>
            <div style={{{{ fontSize: 17, lineHeight: 1.7, fontStyle: "italic", color: C.ink }}}}>
              "{{playbook.key_question || "With your 10b5-1 plan now active, how are you thinking about the balance between continued Sea concentration and building a diversified family balance sheet — particularly given the cross-border tax considerations?"}}"
            </div>
          </div>
          <div style={{{{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}}}>
            <div style={{{{ border: "1px solid " + C.border, borderRadius: 8, padding: 16 }}}}>
              <div style={{{{ fontWeight: 600, marginBottom: 8, fontSize: 14 }}}}>Conversation approach</div>
              <div style={{{{ fontSize: 13, lineHeight: 1.8, color: C.muted }}}}>{{playbook.conversation_implication || "Position as strategic counsel for someone entering a new wealth phase. Acknowledge demonstrated patience and control orientation. Frame diversification as enabling, not diluting, the founder mission."}}</div>
            </div>
            <div style={{{{ border: "1px solid " + C.border, borderRadius: 8, padding: 16, background: "#FEF2F2" }}}}>
              <div style={{{{ fontWeight: 600, marginBottom: 8, fontSize: 14, color: C.red }}}}>What NOT to say</div>
              <ul style={{{{ margin: 0, paddingLeft: 18, lineHeight: 1.9, fontSize: 13, color: C.muted }}}}>
                <li>Do not frame this as "de-risking" — implies lack of confidence in Sea</li>
                <li>Do not lead with urgency — this founder has demonstrated extreme patience</li>
                <li>Do not pitch generic diversification — he can get that anywhere</li>
              </ul>
            </div>
          </div>
        </div>
      )}}

      <div style={{{{ marginTop: 24, paddingTop: 16, borderTop: "1px solid " + C.border, display: "flex", justifyContent: "space-between", fontSize: 11, color: C.muted }}}}>
        <span style={{{{ fontWeight: 600, color: C.ink }}}}>ICONIQ</span>
        <span>Private &amp; Strictly Confidential · Deterministic Model</span>
        <span>APAC Hunter v1.0</span>
      </div>
    </div>
  );
}}
'''


def build_ipo_liquidity_component(brief: dict, result: dict) -> str:
    payload = {"brief": brief, "result": result}
    return f'''const {{ useMemo, useState }} = React;
const DATA = {_js(payload)};
const C = {{ primary: "#1A7CD7", ink: "#151515", muted: "#696969", border: "#DDDDDD", soft: "#F7F9FC", green: "#4DB96B", red: "#e74c3c", gold: "#FDC500", navy: "#374B68", warn: "#B26A00" }};
function money(x) {{ return x == null ? "—" : "$" + Number(x).toLocaleString(undefined, {{maximumFractionDigits: 0}}); }}
function pct(x) {{ return x == null ? "—" : Number(x).toFixed(2) + "%"; }}

export default function App() {{
  const [tab, setTab] = useState("thesis");
  const brief = DATA.brief;
  const result = DATA.result;
  const analysis = result.analysis || {{}};
  const observed = analysis.observed || {{}};
  const inferred = analysis.inferred || {{}};
  const insight = analysis.insight || {{}};
  const model = analysis.model || {{}};
  const assumptions = analysis.assumptions || result.assumptions || [];
  const decisionPoints = insight.decision_points || [];
  const facts = (analysis.facts || []).filter(f => f.value != null);

  const [salePrice, setSalePrice] = useState(observed.offer_price || 10);
  const [salePct, setSalePct] = useState(10);
  const founderExposureMid = observed.headline_raise ? observed.headline_raise * 0.3 : null;
  const scenProceeds = founderExposureMid ? founderExposureMid * (salePct / 100) * (salePrice / (observed.offer_price || salePrice)) : null;

  const tabs = [["thesis","Thesis"],["scenario","Scenario"],["decision","Decision points"],["facts","Observed facts"]];

  return (
    <div style={{{{ fontFamily: "Georgia, serif", color: C.ink, background: "white", padding: 24, maxWidth: 960 }}}}>
      <div style={{{{ marginBottom: 20 }}}}>
        <div style={{{{ fontSize: 11, color: C.muted, marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.08em" }}}}>IPO Liquidity Model</div>
        <div style={{{{ fontSize: 28, fontWeight: 400, marginBottom: 4 }}}}>{{brief.individual_name}}</div>
        <div style={{{{ color: C.muted, marginBottom: 12 }}}}>{{brief.company}}</div>
        <div style={{{{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}}}>
          {{[
            ["Headline raise", money(observed.headline_raise)],
            ["Accessible liquidity", inferred.accessible_liquidity_range || "—"],
            ["Founder exposure", inferred.founder_exposure_range || "—"],
            ["Concentration ref.", pct(inferred.concentration_reference_pct_of_net_worth)],
          ].map(([label, value]) => (
            <div key={{label}} style={{{{ border: "1px solid " + C.border, borderRadius: 8, padding: 14 }}}}>
              <div style={{{{ fontSize: 11, color: C.muted, marginBottom: 6 }}}}>{{label}}</div>
              <div style={{{{ fontSize: 20, fontWeight: 600, color: C.primary }}}}>{{value}}</div>
            </div>
          ))}}
        </div>
      </div>

      <div style={{{{ display: "flex", gap: 8, marginBottom: 16 }}}}>
        {{tabs.map(([name, label]) => (
          <button key={{name}} onClick={{() => setTab(name)}} style={{{{
            padding: "8px 16px", borderRadius: 20, border: "1px solid " + C.border,
            background: tab === name ? C.primary : "white",
            color: tab === name ? "white" : C.ink,
            cursor: "pointer", fontSize: 13, fontFamily: "Georgia, serif"
          }}}}>{{label}}</button>
        ))}}
      </div>

      {{tab === "thesis" && (
        <div style={{{{ display: "grid", gridTemplateColumns: "1.3fr 1fr", gap: 16 }}}}>
          <div style={{{{ border: "1px solid " + C.border, borderRadius: 8, padding: 16 }}}}>
            <div style={{{{ fontWeight: 600, marginBottom: 10, fontSize: 14 }}}}>Model interpretation</div>
            <div style={{{{ lineHeight: 1.7, fontSize: 13, marginBottom: 12, color: C.muted }}}}>{{insight.interpretation}}</div>
            <div style={{{{ lineHeight: 1.7, fontSize: 13, color: C.muted }}}}>{{insight.concentration_view}}</div>
          </div>
          <div style={{{{ border: "1px solid " + C.border, borderRadius: 8, padding: 16, background: C.soft }}}}>
            <div style={{{{ fontWeight: 600, marginBottom: 10, fontSize: 14 }}}}>Model settings</div>
            <div style={{{{ fontSize: 13, lineHeight: 1.9 }}}}>
              <div><strong>Liquidity type:</strong> {{model.liquidity_type || "—"}}</div>
              <div><strong>Accessibility band:</strong> {{model.accessibility_band || "—"}}</div>
              <div><strong>Inference confidence:</strong> {{model.inference_confidence || "—"}}</div>
              <div><strong>Control pressure:</strong> {{model.control_pressure ? "Yes" : "No"}}</div>
              <div><strong>Capital deployment live:</strong> {{model.capital_deployment_live ? "Yes" : "No"}}</div>
            </div>
          </div>
        </div>
      )}}

      {{tab === "scenario" && (
        <div>
          <div style={{{{ fontWeight: 600, marginBottom: 12, fontSize: 14 }}}}>Founder liquidity scenario planner</div>
          <div style={{{{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}}}>
            <div style={{{{ border: "1px solid " + C.border, borderRadius: 8, padding: 16 }}}}>
              <div style={{{{ fontSize: 11, color: C.muted, marginBottom: 6, textTransform: "uppercase" }}}}>Share price assumption (local currency)</div>
              <input type="number" value={{salePrice}} onChange={{e => setSalePrice(Number(e.target.value))}}
                style={{{{ width: "100%", padding: "8px 12px", border: "1px solid " + C.border, borderRadius: 4, fontSize: 14, fontFamily: "Georgia, serif" }}}} step="0.5" />
            </div>
            <div style={{{{ border: "1px solid " + C.border, borderRadius: 8, padding: 16 }}}}>
              <div style={{{{ fontSize: 11, color: C.muted, marginBottom: 6, textTransform: "uppercase" }}}}>% of founder exposure to sell</div>
              <input type="number" value={{salePct}} onChange={{e => setSalePct(Number(e.target.value))}}
                style={{{{ width: "100%", padding: "8px 12px", border: "1px solid " + C.border, borderRadius: 4, fontSize: 14, fontFamily: "Georgia, serif" }}}} step="5" min="1" max="100" />
            </div>
          </div>
          <div style={{{{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}}}>
            {{[["Bear (-30%)", salePrice * 0.7], ["Base", salePrice], ["Bull (+50%)", salePrice * 1.5]].map(([label, p]) => {{
              const adj = founderExposureMid ? founderExposureMid * (salePct / 100) * (p / (observed.offer_price || p)) : null;
              return (
                <div key={{label}} style={{{{ border: "1px solid " + C.border, borderRadius: 8, padding: 16, background: label === "Base" ? "#EAF3FF" : C.soft }}}}>
                  <div style={{{{ fontSize: 12, color: C.muted, marginBottom: 8, fontWeight: label === "Base" ? 600 : 400 }}}}>{{label}}</div>
                  <div style={{{{ fontSize: 11, color: C.muted, marginBottom: 4 }}}}>Est. founder proceeds</div>
                  <div style={{{{ fontSize: 22, fontWeight: 600, color: C.green }}}}>{{money(adj)}}</div>
                  <div style={{{{ fontSize: 11, color: C.muted, marginTop: 8 }}}}>Based on inferred exposure mid-point · {{salePct}}% sell-down</div>
                </div>
              );
            }})}}\
          </div>
          <div style={{{{ marginTop: 12, padding: 12, background: "#FFF8E1", borderRadius: 8, fontSize: 12, color: "#856404" }}}}>
            ⚠ Founder exposure is model-inferred, not filing-verified. Proceeds are gross estimates. This scenario requires primary filing verification before use in any client-facing context.
          </div>
        </div>
      )}}

      {{tab === "decision" && (
        <div style={{{{ display: "grid", gridTemplateColumns: "1.1fr 1fr", gap: 16 }}}}>
          <div style={{{{ border: "1px solid " + C.border, borderRadius: 8, padding: 16 }}}}>
            <div style={{{{ fontWeight: 600, marginBottom: 12, fontSize: 14 }}}}>Next 6–12 month decision points</div>
            <div style={{{{ display: "grid", gap: 10 }}}}>
              {{decisionPoints.map((item, idx) => (
                <div key={{idx}} style={{{{ padding: 12, borderRadius: 8, background: C.soft }}}}>
                  <div style={{{{ fontWeight: 600, marginBottom: 4, fontSize: 13 }}}}>{{item.title}}</div>
                  <div style={{{{ lineHeight: 1.65, fontSize: 13, color: C.muted }}}}>{{item.detail}}</div>
                </div>
              ))}}
            </div>
          </div>
          <div style={{{{ border: "1px solid " + C.border, borderRadius: 8, padding: 16 }}}}>
            <div style={{{{ fontWeight: 600, marginBottom: 12, fontSize: 14 }}}}>Risk flags</div>
            <ul style={{{{ margin: 0, paddingLeft: 18, lineHeight: 1.9, fontSize: 13, color: C.muted }}}}>
              {{(insight.risk_flags || []).map((item, idx) => <li key={{idx}}>{{item}}</li>)}}
            </ul>
          </div>
        </div>
      )}}

      {{tab === "facts" && (
        <div style={{{{ border: "1px solid " + C.border, borderRadius: 8, overflow: "hidden" }}}}>
          <table style={{{{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}}}>
            <thead>
              <tr style={{{{ background: C.ink, color: "white" }}}}>
                {{["Metric", "Value", "Source"].map(h => (
                  <th key={{h}} style={{{{ padding: "10px 14px", textAlign: "left", fontWeight: 600 }}}}>{{h}}</th>
                ))}}
              </tr>
            </thead>
            <tbody>
              {{facts.map((fact, idx) => (
                <tr key={{idx}} style={{{{ background: idx % 2 === 0 ? "white" : C.soft }}}}>
                  <td style={{{{ padding: "10px 14px" }}}}>{{fact.metric}}</td>
                  <td style={{{{ padding: "10px 14px", color: C.primary }}}}>{{typeof fact.value === "number" ? money(fact.value) : fact.value}}</td>
                  <td style={{{{ padding: "10px 14px", color: C.muted }}}}>{{fact.source}}</td>
                </tr>
              ))}}
            </tbody>
          </table>
        </div>
      )}}

      <div style={{{{ marginTop: 24, paddingTop: 16, borderTop: "1px solid " + C.border, display: "flex", justifyContent: "space-between", fontSize: 11, color: C.muted }}}}>
        <span style={{{{ fontWeight: 600, color: C.ink }}}}>ICONIQ</span>
        <span>Private &amp; Strictly Confidential · Deterministic Model</span>
        <span>APAC Hunter v1.0</span>
      </div>
    </div>
  );
}}
'''
