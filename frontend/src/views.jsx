import React, { useMemo, useState } from "react";
import {
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  Check,
  ChevronRight,
  Clock3,
  Database,
  FileText,
  Fingerprint,
  Info,
  Search,
  ShieldCheck,
  Sparkles,
  TriangleAlert,
  X,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { pct, money, human, Dialog } from "./ui.jsx";
import PremiumChart from "./PremiumChart.jsx";
import { FindingWorkbench, StatusBadge } from "./Workflow.jsx";

const colors = {
  rose: "#ec9ab9",
  muted: "#7c85a6",
  red: "#f48094",
  green: "#83d5b4",
};
export function EvidenceChips({ refs, onEvidence }) {
  return (
    <div className="evidence-chips">
      {refs?.map((ref) => (
        <button key={ref} onClick={() => onEvidence(ref)}>
          <Fingerprint size={12} />
          {ref}
          <ArrowUpRight size={11} />
        </button>
      ))}
    </div>
  );
}
function MetricCard({ label, value, description, onClick, accent = false }) {
  return (
    <button
      className={`metric-card ${accent ? "accent" : ""}`}
      onClick={onClick}
    >
      <div className="metric-label">
        {label}
        <ArrowUpRight size={16} />
      </div>
      <div
        className={`metric-value ${value === "Unavailable" ? "unavailable" : ""}`}
      >
        {value}
      </div>
      <p>{description}</p>
    </button>
  );
}
function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <strong>{label || payload[0]?.payload?.segment_id}</strong>
      {payload.map((p, i) => (
        <div key={i}>
          <span style={{ color: p.color }}>{p.name}</span>
          <b>{pct(p.value)}</b>
        </div>
      ))}
    </div>
  );
}
function RateChart({ rows, threshold, onEvidence, comparison = false }) {
  const data = rows.map((r) => ({
    ...r,
    change: Number(r.rate_change_pct),
    reported:
      r.reported_change_pct == null ? null : Number(r.reported_change_pct),
  }));
  return (
    <div
      className="chart-wrap"
      role="img"
      aria-label="Calculated segment changes. The segment table provides the exact values."
    >
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart
          data={data}
          margin={{ top: 15, right: 18, left: -20, bottom: 5 }}
        >
          <CartesianGrid stroke="#262a34" vertical={false} />
          <XAxis
            dataKey="segment_id"
            tick={{ fill: "#969eaf", fontSize: 10 }}
            tickLine={false}
            axisLine={false}
            interval={data.length > 30 ? "preserveStartEnd" : 3}
          />
          <YAxis
            tickFormatter={(v) => `${v}%`}
            tick={{ fill: "#969eaf", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip content={<ChartTooltip />} cursor={{ fill: "#ffffff06" }} />
          <ReferenceLine
            y={Number(threshold)}
            stroke="#e6b37a"
            strokeDasharray="4 5"
            label={{
              value: `${threshold}% screen`,
              fill: "#d6ae83",
              fontSize: 10,
              position: "insideTopRight",
            }}
          />
          <Bar
            isAnimationActive={false}
            name="Calculated"
            dataKey="change"
            radius={[3, 3, 0, 0]}
            maxBarSize={24}
            onClick={(r) => onEvidence(`calc:${r.segment_id}`)}
            cursor="pointer"
          >
            {data.map((r) => (
              <Cell
                key={r.segment_id}
                fill={
                  Math.abs(r.change) > Number(threshold)
                    ? colors.red
                    : colors.rose
                }
                fillOpacity={Math.abs(r.change) > Number(threshold) ? 1 : 0.72}
              />
            ))}
          </Bar>
          {comparison && (
            <Line
              isAnimationActive={false}
              dataKey="reported"
              name="Reported"
              stroke="#9aa9d7"
              strokeWidth={1.5}
              dot={{ r: 3 }}
              connectNulls={false}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export function Overview({ envelope, setView, onEvidence }) {
  const r = envelope.result,
    m = r.deterministic.metrics,
    meta = envelope.filing.metadata,
    high = r.findings.filter((f) => f.severity === "high"),
    rate = r.agents.find((a) => a.agent === "rate_analysis"),
    doc = r.agents.find((a) => a.agent === "documentation_review");
  return (
    <div className="view-enter">
      <div className="metrics-grid">
        <MetricCard
          label="Portfolio premium impact"
          value={pct(m.fixed_exposure_portfolio.value)}
          description="Fixed exposures · modeled premium"
          accent
          onClick={() => onEvidence("metric:fixed_exposure_portfolio")}
        />
        <MetricCard
          label="Exposure-weighted change"
          value={pct(m.exposure_weighted.value)}
          description="Average segment rate change"
          onClick={() => onEvidence("metric:exposure_weighted")}
        />
        <MetricCard
          label="High-priority findings"
          value={high.length}
          description={`${r.findings.length} total findings across this review`}
          onClick={() => setView("findings")}
        />
        <MetricCard
          label="Rating segments"
          value={r.deterministic.rows.length}
          description="Source-linked calculation records"
          onClick={() => setView("portfolio")}
        />
      </div>
      <div className="overview-grid">
        <section className="panel chart-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">PORTFOLIO DISTRIBUTION</p>
              <h2>What’s changing, segment by segment</h2>
            </div>
            <button
              className="text-button"
              onClick={() => setView("portfolio")}
            >
              Explore <ArrowRight size={15} />
            </button>
          </div>
          <div className="chart-legend">
            <span>
              <i style={{ background: colors.rose }} />
              Calculated rate change
            </span>
            <span>
              <i className="dash" />
              General review screen
            </span>
          </div>
          <RateChart
            rows={r.deterministic.rows}
            threshold={r.deterministic.config.large_change_threshold_pct}
            onEvidence={onEvidence}
          />
          <p className="chart-note">
            Select a bar to inspect its calculation. Screening is a review
            heuristic, not a Connecticut requirement.
          </p>
        </section>
        <section className="panel assessment">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">RECONCILIATION</p>
              <h2>Claim meets calculation</h2>
            </div>
            <Fingerprint size={20} />
          </div>
          <div className="claim-line">
            <span>Submitted overall claim</span>
            <b>{pct(meta.claimed_overall_change_pct)}</b>
          </div>
          <div className="claim-line computed">
            <span>Calculated on claimed basis</span>
            <b>{pct(m[meta.claimed_overall_basis]?.value)}</b>
          </div>
          <p className="small-text muted">
            Basis: {human(meta.claimed_overall_basis)}
          </p>
          <div className="assessment-note">
            <Info size={17} />
            <p>
              {r.deterministic.findings.find((f) => f.affected === "portfolio")
                ?.message ||
                "The overall reconciliation returned no portfolio-level finding. Review the supporting measures and assumptions."}
            </p>
          </div>
          <button
            className="text-button"
            onClick={() => onEvidence(`metric:${meta.claimed_overall_basis}`)}
          >
            Inspect portfolio evidence <ArrowRight size={15} />
          </button>
        </section>
      </div>
      <div className="section-heading">
        <div>
          <p className="eyebrow">THE ANALYST BRIEF</p>
          <h2>Two perspectives. One evidence trail.</h2>
        </div>
        <span className="badge">
          <Sparkles size={12} />
          Validated AI interpretation
        </span>
      </div>
      <div className="brief-grid">
        {[rate, doc].map((a, i) => (
          <section key={a.agent} className="panel agent-brief">
            <div className="agent-heading">
              <span className="agent-icon">
                {i === 0 ? <Database size={19} /> : <FileText size={19} />}
              </span>
              <div>
                <h3>{human(a.agent)}</h3>
                <span
                  className={`tiny-status ${a.status === "complete" ? "green" : "amber-text"}`}
                >
                  {human(a.status)} · {a.tool_calls} tool calls
                </span>
              </div>
            </div>
            {a.result ? (
              <>
                <h3 className="brief-title">{a.result.summary.title}</h3>
                <p>{a.result.summary.explanation}</p>
                <div className="next-action">
                  <span>NEXT ACTION</span>
                  <p>{a.result.summary.recommended_action}</p>
                </div>
                <EvidenceChips
                  refs={a.result.summary.evidence_refs}
                  onEvidence={onEvidence}
                />
              </>
            ) : (
              <div className="notice warning">
                <TriangleAlert size={18} />
                <p>
                  Stage incomplete: {human(a.error)}. Deterministic evidence
                  remains available.
                </p>
              </div>
            )}
          </section>
        ))}
      </div>
      <section className="panel measures">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">MEASURES & ASSUMPTIONS</p>
            <h2>Different weights answer different questions</h2>
          </div>
          <button
            className="text-button"
            onClick={() => onEvidence("config:calculation")}
          >
            Review tolerances <ArrowRight size={15} />
          </button>
        </div>
        <div className="measure-grid">
          {[
            [
              "exposure_weighted",
              "Rate level",
              "Weights each segment’s rate change by annual vehicle exposures.",
            ],
            [
              "fixed_exposure_portfolio",
              "Premium impact",
              "Compares modeled total premiums with the exposure mix held fixed.",
            ],
            [
              "current_premium_weighted",
              "Premium weights",
              "Weights rate changes by supplied current premiums, when usable.",
            ],
          ].map(([key, title, desc]) => (
            <button key={key} onClick={() => onEvidence(`metric:${key}`)}>
              <span>{title}</span>
              <strong className={m[key].value === null ? "unavailable" : ""}>
                {pct(m[key].value, 4)}
              </strong>
              <p>
                {m[key].reason ? `Unavailable: ${human(m[key].reason)}. ` : ""}
                {desc}
              </p>
            </button>
          ))}
        </div>
        <div className="premium-totals">
          <span>
            Current modeled premium{" "}
            <b>{money(m.current_modeled_premium.value)}</b>
          </span>
          <ArrowRight size={16} />
          <span>
            Proposed modeled premium{" "}
            <b>{money(m.proposed_modeled_premium.value)}</b>
          </span>
        </div>
      </section>
    </div>
  );
}

export function Portfolio({ envelope, onEvidence }) {
  const [query, setQuery] = useState(""),
    [sort, setSort] = useState("segment_id"),
    [direction, setDirection] = useState(1),
    [chart, setChart] = useState("change"),
    [onlyFlagged, setOnlyFlagged] = useState(false),
    [territory, setTerritory] = useState("all"),
    [page, setPage] = useState(0);
  const result = envelope.result,
    flagged = new Set(result.findings.flatMap((f) => f.affected_segments)),
    inputs = Object.fromEntries(
      envelope.filing.rows.map((r) => [r.segment_id, r]),
    );
  const rows = useMemo(
    () =>
      result.deterministic.rows
        .map((r) => ({ ...inputs[r.segment_id], ...r }))
        .filter(
          (r) =>
            (!onlyFlagged || flagged.has(r.segment_id)) &&
            (territory === "all" || r.territory === territory) &&
            `${r.segment_id} ${r.territory} ${r.driver_class}`
              .toLowerCase()
              .includes(query.toLowerCase()),
        )
        .sort(
          (a, b) =>
            direction *
            (sort === "segment_id"
              ? a[sort].localeCompare(b[sort])
              : Number(a[sort]) - Number(b[sort])),
        ),
    [envelope, query, sort, direction, onlyFlagged, territory],
  );
  function sortBy(key) {
    setDirection(sort === key ? -direction : 1);
    setSort(key);
    setPage(0);
  }
  const pageRows = rows.slice(page * 25, (page + 1) * 25);
  return (
    <div className="view-enter">
      <section className="panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">SEGMENT EXPLORER</p>
            <h2>See the movement. Follow the inputs.</h2>
          </div>
          <div className="segmented-control compact">
            <button
              className={chart === "change" ? "selected" : ""}
              onClick={() => setChart("change")}
            >
              Rate changes
            </button>
            <button
              className={chart === "scatter" ? "selected" : ""}
              onClick={() => setChart("scatter")}
            >
              Rate comparison
            </button>
          </div>
        </div>
        <div className="filter-bar">
          <label className="search-box">
            <Search size={16} />
            <input
              aria-label="Search segments"
              placeholder="Search segments, territory, driver…"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setPage(0);
              }}
            />
          </label>
          <select
            aria-label="Filter territory"
            value={territory}
            onChange={(e) => {
              setTerritory(e.target.value);
              setPage(0);
            }}
          >
            <option value="all">All territories</option>
            {[...new Set(envelope.filing.rows.map((r) => r.territory))].map(
              (t) => (
                <option key={t}>{t}</option>
              ),
            )}
          </select>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={onlyFlagged}
              onChange={(e) => {
                setOnlyFlagged(e.target.checked);
                setPage(0);
              }}
            />
            With findings
          </label>
        </div>
        {rows.length ? (
          chart === "change" ? (
            <>
              <div className="chart-legend">
                <span>
                  <i style={{ background: colors.rose }} />
                  Calculated
                </span>
                <span>
                  <i style={{ background: "#9aa9d7" }} />
                  Reported
                </span>
              </div>
              <RateChart
                rows={rows}
                threshold={
                  result.deterministic.config.large_change_threshold_pct
                }
                onEvidence={onEvidence}
                comparison
              />
            </>
          ) : (
            <>
              <div className="chart-wrap">
                <ResponsiveContainer>
                  <ScatterChart
                    margin={{ left: 20, right: 30, bottom: 25, top: 15 }}
                  >
                    <CartesianGrid stroke="#272c38" />
                    <XAxis
                      type="number"
                      dataKey="current"
                      name="Current rate"
                      tick={{ fill: "#939cac", fontSize: 11 }}
                      label={{
                        value: "Current modeled rate · USD / exposure",
                        position: "bottom",
                        fill: "#939cac",
                        fontSize: 11,
                      }}
                    />
                    <YAxis
                      type="number"
                      dataKey="proposed"
                      name="Proposed rate"
                      tick={{ fill: "#939cac", fontSize: 11 }}
                    />
                    <Tooltip
                      cursor={{ strokeDasharray: "3 3" }}
                      content={({ active, payload }) =>
                        active && payload?.length ? (
                          <div className="chart-tooltip">
                            <strong>{payload[0].payload.segment_id}</strong>
                            <p>Current {money(payload[0].payload.current)}</p>
                            <p>Proposed {money(payload[0].payload.proposed)}</p>
                          </div>
                        ) : null
                      }
                    />
                    <Scatter
                      isAnimationActive={false}
                      name="Rate per annual exposure"
                      data={rows.map((r) => ({
                        ...r,
                        current: Number(r.current_modeled_rate),
                        proposed: Number(r.proposed_modeled_rate),
                      }))}
                      fill={colors.rose}
                      onClick={(r) => onEvidence(r.evidence_id)}
                      cursor="pointer"
                    />
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
              <p className="chart-note">
                Vertical axis: proposed modeled rate in USD per exposure. Select
                a point for evidence.
              </p>
            </>
          )
        ) : (
          <div className="empty">
            <Search size={25} />
            <h3>No segments match</h3>
            <p>Clear the search or adjust the filters.</p>
          </div>
        )}
      </section>
      <PremiumChart envelope={envelope} onEvidence={onEvidence} />
      <section className="panel table-panel">
        <div className="panel-heading">
          <div>
            <h2>Segment rate exhibit</h2>
            <p className="muted small-text">
              {rows.length} matching segments · rates in USD per annual exposure
              · display rounded
            </p>
          </div>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                {[
                  ["segment_id", "Segment / territory"],
                  ["current_modeled_rate", "Current rate"],
                  ["proposed_modeled_rate", "Proposed rate"],
                  ["rate_change_pct", "Calculated Δ"],
                  ["reported_change_pct", "Reported Δ"],
                  ["exposure", "Exposures"],
                ].map(([key, label]) => (
                  <th key={key}>
                    <button onClick={() => sortBy(key)}>
                      {label}
                      {sort === key ? (direction === 1 ? " ↑" : " ↓") : ""}
                    </button>
                  </th>
                ))}
                <th>Source</th>
              </tr>
            </thead>
            <tbody>
              {pageRows.map((r) => (
                <tr key={r.segment_id}>
                  <td>
                    <button
                      className="segment-link"
                      onClick={() => onEvidence(r.evidence_id)}
                    >
                      {flagged.has(r.segment_id) && (
                        <span className="flag-dot" />
                      )}
                      {r.segment_id}
                    </button>
                    <small>
                      {r.territory} · {r.driver_class}
                    </small>
                  </td>
                  <td>{money(r.current_modeled_rate)}</td>
                  <td>{money(r.proposed_modeled_rate)}</td>
                  <td
                    className={
                      Math.abs(Number(r.rate_change_pct)) >
                      Number(
                        result.deterministic.config.large_change_threshold_pct,
                      )
                        ? "rose-text"
                        : ""
                    }
                  >
                    {pct(r.rate_change_pct, 3)}
                  </td>
                  <td>{pct(r.reported_change_pct, 3)}</td>
                  <td>
                    {r.exposure === null
                      ? "Unavailable"
                      : Number(r.exposure).toLocaleString()}
                  </td>
                  <td>
                    <button
                      className="icon-button"
                      aria-label={`Source for ${r.segment_id}`}
                      onClick={() => onEvidence(`row:${r.segment_id}`)}
                    >
                      <ArrowUpRight size={17} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="table-footer">
          <span>
            {rows.length
              ? `${page * 25 + 1}–${Math.min((page + 1) * 25, rows.length)} of ${rows.length}`
              : "0 rows"}
          </span>
          <div>
            <button
              className="button secondary small"
              disabled={page === 0}
              onClick={() => setPage(page - 1)}
            >
              Previous
            </button>
            <button
              className="button secondary small"
              disabled={(page + 1) * 25 >= rows.length}
              onClick={() => setPage(page + 1)}
            >
              Next
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}

export function Findings({ envelope, workflow, onWorkflow, onEvidence }) {
  const [severity, setSeverity] = useState("all"),
    [origin, setOrigin] = useState("all"),
    [query, setQuery] = useState(""),
    [selected, setSelected] = useState(null);
  const all = envelope.result.findings;
  const findings = all
    .filter(
      (f) =>
        (severity === "all" || f.severity === severity) &&
        (origin === "all" || f.origin === origin) &&
        `${f.title} ${f.explanation} ${f.affected_segments?.join(" ")}`
          .toLowerCase()
          .includes(query.toLowerCase()),
    )
    .sort(
      (a, b) =>
        ["high", "medium", "low"].indexOf(a.severity) -
        ["high", "medium", "low"].indexOf(b.severity),
    );
  return (
    <div className="view-enter">
      <div className="finding-summary">
        {["high", "medium", "low"].map((level) => (
          <button
            key={level}
            className={`severity-summary ${severity === level ? "selected" : ""}`}
            onClick={() => setSeverity(severity === level ? "all" : level)}
          >
            <span className={`severity-dot ${level}`} />
            <strong>{all.filter((f) => f.severity === level).length}</strong>
            <span>{level} severity</span>
          </button>
        ))}
        <div className="finding-summary-note">
          <ShieldCheck size={20} />
          <p>
            Every finding links to evidence.
            <br />
            All recommendations require analyst judgment.
          </p>
        </div>
      </div>
      <div className="filter-bar">
        <label className="search-box">
          <Search size={16} />
          <input
            value={query}
            aria-label="Search findings"
            placeholder="Search findings or segments…"
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <select
          aria-label="Finding origin"
          value={origin}
          onChange={(e) => setOrigin(e.target.value)}
        >
          <option value="all">All origins</option>
          <option value="deterministic">Deterministic</option>
          <option value="ai">AI interpretation</option>
        </select>
        <select
          aria-label="Finding severity"
          value={severity}
          onChange={(e) => setSeverity(e.target.value)}
        >
          <option value="all">All severities</option>
          {["high", "medium", "low"].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
        <span className="muted small-text">{findings.length} findings</span>
      </div>
      <div className="findings-list">
        {findings.map((f) => (
          <article className="panel finding-card" key={f.finding_id}>
            <div className="finding-top">
              <div>
                <span
                  className={`badge ${f.severity === "high" ? "red" : f.severity === "medium" ? "amber" : ""}`}
                >
                  {f.severity}
                </span>
                <span className="origin-label">
                  {f.origin === "deterministic" ? (
                    <Database size={13} />
                  ) : (
                    <Sparkles size={13} />
                  )}{" "}
                  {f.origin === "deterministic"
                    ? "Python reconciliation"
                    : "AI interpretation"}
                </span>
                <span className="category-label">{human(f.category)}</span>
                <StatusBadge status={workflow?.current?.[f.finding_id]?.status} />
              </div>
              <code>{f.finding_id}</code>
            </div>
            <h3>{f.title}</h3>
            <p>{f.explanation}</p>
            {f.numerical_evidence?.calculated_value !== null &&
              f.numerical_evidence?.calculated_value !== undefined && (
                <div className="numerical-strip">
                  {[
                    ["reported_value", "Reported"],
                    ["calculated_value", "Calculated"],
                    ["difference", "Reported − calculated"],
                  ].map(([key, label]) => (
                    <div key={key}>
                      <span>{label}</span>
                      <strong>
                        {f.numerical_evidence[key] === null
                          ? "Not supplied"
                          : Number(f.numerical_evidence[key]).toLocaleString(
                              "en-US",
                              { maximumFractionDigits: 6 },
                            )}
                        <small> {f.numerical_evidence.unit}</small>
                      </strong>
                    </div>
                  ))}
                </div>
              )}
            {f.source_quotes?.map((q, i) => (
              <blockquote key={i}>
                <span>SUBMITTED TEXT · UNTRUSTED</span>“{q.quote}”
              </blockquote>
            ))}
            <div className="next-action">
              <span>RECOMMENDED NEXT STEP</span>
              <p>{f.recommended_action}</p>
            </div>
            <div className="finding-evidence">
              <EvidenceChips refs={f.evidence_refs} onEvidence={onEvidence} />
              <button className="button secondary small" onClick={() => setSelected(f)}>Investigate &amp; record action <ArrowRight size={14}/></button>
              <small className="muted">
                {f.evidence_strength === "deterministic"
                  ? "Deterministic evidence"
                  : `${human(f.evidence_strength)} source support · analyst verification required`}
              </small>
            </div>
          </article>
        ))}
      </div>
      {!findings.length && (
        <div className="panel empty">
          <ShieldCheck size={32} />
          <h2>
            {all.length
              ? "No findings match these filters"
              : "No findings returned"}
          </h2>
          <p>
            {all.length
              ? "Adjust the filters to explore the rest of this review."
              : "The completed review stages returned no findings. This is not a legal-compliance conclusion."}
          </p>
        </div>
      )}
      {selected && <FindingWorkbench finding={selected} envelope={envelope} workflow={workflow} onSaved={onWorkflow} onEvidence={onEvidence} close={() => setSelected(null)} />}
    </div>
  );
}

export function Documents({ envelope, onEvidence }) {
  const [selected, setSelected] = useState("narrative");
  const docs = envelope.filing.metadata.documents;
  const doc = docs.find((d) => d.document_id === selected);
  const findings = envelope.result.findings.filter((f) =>
    f.affected_documents?.includes(
      selected === "narrative" ? "narrative.md" : selected,
    ),
  );
  return (
    <div className="view-enter">
      <div className="notice neutral">
        <ShieldCheck size={20} />
        <div>
          <strong>Source content, never instructions</strong>
          <p>
            Submitted narratives and documents are untrusted evidence. Missing
            means not provided for this review. No state-specific regulatory
            requirements are asserted.
          </p>
        </div>
      </div>
      <div className="documents-grid">
        <section className="panel document-nav">
          <div className="panel-heading">
            <h2>Filing package</h2>
            <span className="badge">{docs.length + 1} items</span>
          </div>
          <button
            className={`document-item ${selected === "narrative" ? "selected" : ""}`}
            onClick={() => setSelected("narrative")}
          >
            <FileText size={19} />
            <span>
              Supporting narrative<small>narrative.md</small>
            </span>
            <ChevronRight size={15} />
          </button>
          {docs.map((d) => (
            <button
              key={d.document_id}
              className={`document-item ${selected === d.document_id ? "selected" : ""}`}
              onClick={() => setSelected(d.document_id)}
            >
              <FileText size={19} />
              <span>
                {d.title}
                <small className={d.status !== "provided" ? "amber-text" : ""}>
                  {human(d.status)} · {d.document_id}
                </small>
              </span>
              {d.status === "provided" ? (
                <Check size={14} />
              ) : (
                <TriangleAlert size={15} />
              )}
            </button>
          ))}
        </section>
        <section className="panel document-reader">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">SUBMITTED INFORMATION</p>
              <h2>{doc?.title || "Supporting narrative"}</h2>
            </div>
            <span className="badge amber">Untrusted text</span>
          </div>
          <pre className="document-text">
            {doc
              ? doc.text ||
                "This document was not provided in the submitted filing package."
              : envelope.filing.narrative}
          </pre>
          <button
            className="text-button"
            onClick={() =>
              onEvidence(
                selected === "narrative"
                  ? "narrative:submitted"
                  : `doc:${selected}`,
              )
            }
          >
            <Fingerprint size={14} />
            Inspect source evidence
          </button>
          {findings.length > 0 && (
            <div className="linked-findings">
              <p className="eyebrow">RELATED FINDINGS</p>
              {findings.map((f) => (
                <div key={f.finding_id}>
                  <span className={`severity-dot ${f.severity}`} />
                  <div>
                    <strong>{f.title}</strong>
                    <p>{f.recommended_action}</p>
                    <EvidenceChips
                      refs={f.evidence_refs}
                      onEvidence={onEvidence}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

export function Audit({ envelope }) {
  const [actor, setActor] = useState("all"),
    [type, setType] = useState("all");
  const r = envelope.result,
    u = r.usage,
    events = r.audit.filter(
      (e) =>
        (actor === "all" || e.actor === actor) &&
        (type === "all" || e.action.includes(type)),
    );
  return (
    <div className="view-enter">
      <div className="metrics-grid usage-metrics">
        {[
          [
            "Model requests",
            u.total_model_calls,
            "Actual requests, including retries",
          ],
          ["Input tokens", u.input_tokens, "Provider-reported input"],
          [
            "Cached input",
            u.cached_input_tokens,
            "Subset of input, not additional tokens",
          ],
          ["Output tokens", u.output_tokens, "Provider-reported completion"],
        ].map(([label, value, desc]) => (
          <div key={label} className="metric-card">
            <div className="metric-label">{label}</div>
            <div className="metric-value">
              {value == null ? "Unavailable" : value.toLocaleString()}
            </div>
            <p>{desc}</p>
          </div>
        ))}
      </div>
      <div className="usage-note">
        <Clock3 size={17} />
        <span>
          {(u.model_latency_ms / 1000).toFixed(2)}s model latency ·{" "}
          {u.total_tokens == null
            ? "Total tokens unavailable"
            : `${u.total_tokens.toLocaleString()} total tokens`}{" "}
          · {r.model}
        </span>
        <span>Exact billing unavailable</span>
      </div>
      <div className="execution-pipeline">
        {r.agents.map((a, i) => (
          <div className="panel" key={a.agent}>
            <div className="agent-heading">
              <span className="step-number">0{i + 1}</span>
              <div>
                <h3>{human(a.agent)}</h3>
                <small>
                  {a.tool_calls} tool calls ·{" "}
                  {(a.duration_ms / 1000).toFixed(2)}s elapsed
                </small>
              </div>
              <span
                className={`badge ${a.status === "complete" ? "green-badge" : "amber"}`}
              >
                {a.status}
              </span>
            </div>
            {a.error && <p className="amber-text">{human(a.error)}</p>}
          </div>
        ))}
      </div>
      <section className="panel ledger">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">EXECUTION LEDGER</p>
            <h2>Every request. Every tool. Every decision.</h2>
          </div>
          <Fingerprint size={22} />
        </div>
        <div className="filter-bar">
          <select
            aria-label="Filter audit actor"
            value={actor}
            onChange={(e) => setActor(e.target.value)}
          >
            <option value="all">All actors</option>
            {[...new Set(r.audit.map((e) => e.actor))].map((a) => (
              <option key={a} value={a}>
                {human(a)}
              </option>
            ))}
          </select>
          <select
            aria-label="Filter audit event"
            value={type}
            onChange={(e) => setType(e.target.value)}
          >
            <option value="all">All events</option>
            <option value="model_">Model requests & responses</option>
            <option value="tool_">Tool interactions</option>
            <option value="rejected">Rejected outputs</option>
            <option value="retry">Retries</option>
          </select>
          <span className="small-text muted">{events.length} events</span>
        </div>
        <div className="audit-list">
          {events.map((e) => (
            <details className="audit-event" key={e.sequence}>
              <summary>
                <code className="sequence">
                  {String(e.sequence).padStart(2, "0")}
                </code>
                <span
                  className={`event-dot ${e.status === "error" ? "red-dot" : ""}`}
                />
                <span className="event-name">
                  <strong>{human(e.action)}</strong>
                  <small>
                    {human(e.actor)}
                    {e.data?.tool_name ? ` / ${e.data.tool_name}` : ""}
                  </small>
                </span>
                <span className="event-time">
                  {e.duration_ms == null
                    ? "—"
                    : `${Number(e.duration_ms).toFixed(0)} ms`}
                </span>
                <span
                  className={`badge ${["error", "invalid"].includes(e.status) ? "red" : ""}`}
                >
                  {e.status}
                </span>
                <ChevronRight size={15} />
              </summary>
              <div className="audit-detail">
                <p>
                  {new Date(e.timestamp).toLocaleString()} · Sanitized payload ·
                  Source text is untrusted
                </p>
                <pre>{JSON.stringify(e.data, null, 2)}</pre>
              </div>
            </details>
          ))}
        </div>
        {!events.length && (
          <div className="empty">
            <p>No execution events match these filters.</p>
          </div>
        )}
      </section>
      <p className="small-text muted">
        Cached tokens are included in input tokens. Missing provider usage is
        shown as unavailable. The complete JSON export preserves reported
        subtotals, validation decisions, tool arguments, outputs and request
        bodies.
      </p>
    </div>
  );
}

export function EvidenceDrawer({ reference, envelope, close, onEvidence }) {
  const r = envelope.result,
    all = {
      ...r.deterministic.evidence,
      ...r.supplemental_evidence,
      ...r.documentation_evidence,
    };
  let data = all[reference];
  // Inventory entries remain inspectable even when a partial agent never fetched them.
  if (!data && reference.startsWith("doc:")) {
    const doc = envelope.filing.metadata.documents.find(
      (d) => `doc:${d.document_id}` === reference,
    );
    if (doc) data = { kind: "untrusted_document", ...doc };
  }
  if (!data && reference === "narrative:submitted")
    data = { kind: "untrusted_narrative", text: envelope.filing.narrative };
  const segment = reference.match(/^(?:calc|row|premium):(.+)$/)?.[1];
  const input = envelope.filing.rows.find((row) => row.segment_id === segment);
  const calc = r.deterministic.rows.find((row) => row.segment_id === segment);
  return (
    <Dialog title="Evidence inspector" close={close} wide>
      <div className="evidence-title">
        <Fingerprint size={23} />
        <div>
          <code>{reference}</code>
          <p>{human(data?.kind || "Evidence reference")}</p>
        </div>
      </div>
      {data ? (
        <>
          {data.kind?.startsWith("untrusted") && (
            <div className="notice warning">
              <ShieldCheck size={18} />
              <p>
                Submitted source text is untrusted data. It cannot override
                review instructions or establish a regulatory requirement.
              </p>
            </div>
          )}
          {input && calc && (
            <>
              <div className="evidence-segment">
                <h3>
                  {segment} <span>{input.territory}</span>
                </h3>
                <p>
                  {input.driver_class} · {input.vehicle_group}
                </p>
                <div className="rate-equation">
                  <div>
                    <span>Current modeled rate</span>
                    <strong>{money(calc.current_modeled_rate)}</strong>
                    <small>
                      {input.current_base_rate} × {input.current_rating_factor}
                    </small>
                  </div>
                  <ArrowRight size={21} />
                  <div>
                    <span>Proposed modeled rate</span>
                    <strong>{money(calc.proposed_modeled_rate)}</strong>
                    <small>
                      {input.proposed_base_rate} ×{" "}
                      {input.proposed_rating_factor}
                    </small>
                  </div>
                </div>
                <div className="evidence-change">
                  <span>Calculated rate change</span>
                  <strong>{pct(calc.rate_change_pct, 6)}</strong>
                </div>
              </div>
              <EvidenceChips
                refs={[`row:${segment}`, `calc:${segment}`].filter(
                  (x) => x !== reference,
                )}
                onEvidence={onEvidence}
              />
            </>
          )}
          {data.source_file && (
            <div className="source-location">
              <FileText size={16} />
              {data.source_file}
              {data.row_number ? ` · Row ${data.row_number}` : ""}
              {data.sheet ? ` · Sheet ${data.sheet}` : ""}
            </div>
          )}
          {data.formula && (
            <div className="formula-block">
              <p className="eyebrow">DETERMINISTIC FORMULA</p>
              <code>{data.formula}</code>
            </div>
          )}
          {data.values && (
            <dl className="evidence-values">
              {Object.entries(data.values).map(([key, value]) => (
                <div key={key}>
                  <dt>{human(key)}</dt>
                  <dd>{value == null ? "Unavailable" : String(value)}</dd>
                </div>
              ))}
            </dl>
          )}
          {data.text && <pre className="document-text">{data.text}</pre>}
          {data.input_refs?.length > 0 && (
            <div>
              <p className="eyebrow">TRACE TO INPUTS</p>
              <EvidenceChips refs={data.input_refs} onEvidence={onEvidence} />
            </div>
          )}
          <details className="raw-evidence">
            <summary>Full evidence record · exact values</summary>
            <pre>{JSON.stringify(data, null, 2)}</pre>
          </details>
        </>
      ) : (
        <div className="notice warning">
          <Info size={19} />
          <p>
            This reference was not captured in the available evidence. Inspect
            the audit record for the corresponding stage.
          </p>
        </div>
      )}
    </Dialog>
  );
}
