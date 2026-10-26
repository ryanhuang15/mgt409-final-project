import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  ArrowDownToLine,
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Check,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  FileCheck2,
  FileSpreadsheet,
  FileText,
  Fingerprint,
  LayoutDashboard,
  LoaderCircle,
  LockKeyhole,
  Plus,
  Search,
  ShieldCheck,
  Sparkles,
  Upload,
  X,
  ChartNoAxesCombined,
  TriangleAlert,
  Clock3,
} from "lucide-react";
import {
  Overview,
  Portfolio,
  Findings,
  Documents,
  Audit,
  EvidenceDrawer,
} from "./views.jsx";
import "./styles.css";
import { pct, money, human, api, Dialog } from "./ui.jsx";
import { RevisionComparison } from "./Workflow.jsx";

const scenarios = [
  {
    id: "flawed",
    tag: "INVESTIGATE",
    title: "A filing that needs a closer look",
    description:
      "Trace reported discrepancies, a large segment movement, and gaps in the supporting documents.",
    icon: Search,
  },
  {
    id: "clean",
    tag: "ESTABLISH A BASELINE",
    title: "A consistent rate revision",
    description:
      "Explore an internally consistent filing and see how the three weighting measures differ.",
    icon: FileCheck2,
  },
  {
    id: "adversarial",
    tag: "TEST THE BOUNDARIES",
    title: "Valid rates. Untrusted instructions.",
    description:
      "Inspect a narrative that attempts to redirect the agents, alongside valid numerical data.",
    icon: ShieldCheck,
  },
];
const navigation = [
  ["overview", "Review overview", LayoutDashboard],
  ["portfolio", "Segment analytics", ChartNoAxesCombined],
  ["findings", "Findings & actions", Search],
  ["comparison", "Revision comparison", FileCheck2],
  ["documents", "Documentation", FileText],
  ["audit", "Execution & usage", Activity],
];

function App() {
  const [config, setConfig] = useState(null),
    [envelope, setEnvelope] = useState(null),
    [view, setView] = useState("overview"),
    [loading, setLoading] = useState(false),
    [error, setError] = useState(""),
    [modal, setModal] = useState(null),
    [evidence, setEvidence] = useState(null),
    [job, setJob] = useState(null),
    [stage, setStage] = useState("validating"),
    [history, setHistory] = useState([]),
    [reportMenu, setReportMenu] = useState(false);
  const [workflow, setWorkflow] = useState(null);
  const [originalEnvelope, setOriginalEnvelope] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    let active = true;
    api("/api/session")
      .then((c) => {
        if (!active) return;
        setConfig(c);
        refreshHistory();
        const last = sessionStorage.getItem("lumen-selection");
        if (last) {
          const [type, id] = JSON.parse(last);
          if (type === "saved") loadExample(id);
          else resume(id);
        }
      })
      .catch((e) => setError(e.message));
    return () => {
      active = false;
    };
  }, []);
  function refreshHistory() {
    api("/api/reviews")
      .then(setHistory)
      .catch(() => {});
  }
  function select(data) {
    setEnvelope(data);
    setView(data.parent_id ? "comparison" : "overview");
    setWorkflow(null);
    if (data.result) {
      const key = data.source === "saved" ? `example-${data.result.deterministic.scenario_id}` : data.job_id;
      api(`/api/reviews/${encodeURIComponent(key)}/workflow`).then(setWorkflow).catch(() => setWorkflow(null));
    }
    if (data.parent_id) api(data.parent_id.startsWith("example-") ? `/api/examples/${data.parent_id.slice(8)}` : `/api/reviews/${encodeURIComponent(data.parent_id)}`).then(setOriginalEnvelope).catch(() => setOriginalEnvelope(null));
    else setOriginalEnvelope(null);
    setError("");
    setEvidence(null);
    setReportMenu(false);
    sessionStorage.setItem(
      "lumen-selection",
      JSON.stringify([
        data.source,
        data.source === "saved"
          ? data.result.deterministic.scenario_id
          : data.job_id,
      ]),
    );
  }
  async function loadExample(id) {
    setLoading(true);
    setError("");
    try {
      select(await api(`/api/examples/${id}`));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }
  async function resume(id) {
    setLoading(true);
    try {
      const data = await api(`/api/reviews/${id}`);
      if (data.result) select(data);
      else if (["failed", "interrupted"].includes(data.stage))
        setError(
          "This review was interrupted. Start a new review when ready; no request was automatically repeated.",
        );
      else {
        setJob(id);
        setStage(data.stage);
      }
    } catch (e) {
      setError(e.message);
      sessionStorage.removeItem("lumen-selection");
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    if (!job) return;
    let stopped = false,
      timer;
    setElapsed(0);
    const ticker = setInterval(() => setElapsed((s) => s + 1), 1000);
    async function poll() {
      try {
        const data = await api(`/api/reviews/${job}`);
        if (stopped) return;
        setStage(data.stage);
        if (data.result) {
          select(data);
          setJob(null);
          refreshHistory();
          return;
        }
        if (["failed", "interrupted"].includes(data.stage)) {
          setError(
            "The review was interrupted before a result could be saved. No automatic retry was made. Please try a saved example or start a new review.",
          );
          setJob(null);
          refreshHistory();
          return;
        }
        timer = setTimeout(poll, 1200);
      } catch (e) {
        if (!stopped) {
          setError(
            e.message + " You can reopen this review from recent activity.",
          );
          setJob(null);
        }
      }
    }
    poll();
    return () => {
      stopped = true;
      clearTimeout(timer);
      clearInterval(ticker);
    };
  }, [job]);
  async function startReview({ scenario, files, code }) {
    setError("");
    try {
      let body,
        headers = {};
      if (files) {
        body = new FormData();
        Object.entries(files).forEach(([key, value]) =>
          body.append(key, value),
        );
      } else {
        body = JSON.stringify({ scenario });
        headers["Content-Type"] = "application/json";
      }
      if (code) headers["X-Review-Code"] = code;
      const revisionOf = modal === "revision" ? (envelope.source === "saved" ? `example-${result.deterministic.scenario_id}` : envelope.job_id) : null;
      const data = await api(revisionOf ? `/api/reviews/${encodeURIComponent(revisionOf)}/revisions` : files ? "/api/reviews/upload" : "/api/reviews", {
        method: "POST",
        body,
        headers,
      });
      setJob(data.job_id);
      setStage(data.stage);
      setModal(null);
      sessionStorage.setItem(
        "lumen-selection",
        JSON.stringify(["live", data.job_id]),
      );
      refreshHistory();
    } catch (e) {
      throw e;
    }
  }
  const result = envelope?.result;
  function goHome() {
    setEnvelope(null);
    setWorkflow(null);
    setView("overview");
    sessionStorage.removeItem("lumen-selection");
  }
  const exportBase = envelope
    ? `/api/exports/${envelope.source === "saved" ? "example" : "review"}/${envelope.source === "saved" ? result.deterministic.scenario_id : envelope.job_id}`
    : "";
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button className="brand" onClick={goHome} aria-label="Lumen home">
          <span className="brand-mark">
            L<span />
          </span>
          <span>
            lumen<span className="brand-sub">RATE INTELLIGENCE</span>
          </span>
        </button>
        <div className="workspace-label">ANALYST WORKSPACE</div>
        <button
          className={`nav-link ${!envelope ? "active" : ""}`}
          onClick={goHome}
        >
          <BookOpen size={18} />
          Getting started
        </button>
        <div className="nav-separator" />
        {navigation.map(([key, label, Icon]) => (
          <button
            key={key}
            title={label}
            className={`nav-link ${envelope && view === key ? "active" : ""}`}
            disabled={!envelope || (key === "comparison" && !envelope.parent_id)}
            onClick={() => {
              setView(key);
              setEvidence(null);
              window.scrollTo(0, 0);
            }}
          >
            <Icon size={18} />
            {label}
            {key === "findings" && result && (
              <span className="nav-count">{result.findings.length}</span>
            )}
          </button>
        ))}
        <div className="sidebar-bottom">
          <div className="trust-card">
            <ShieldCheck size={19} />
            <strong>Evidence before conclusions.</strong>
            <p>
              Independent calculations.
              <br />
              Traceable AI interpretation.
              <br />
              Human judgment, always.
            </p>
          </div>
          <div className="workspace-footer">
            <span className="avatar">JA</span>
            <div>
              Actuarial workspace<small>Connecticut · Personal Auto</small>
            </div>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            Workspace <ChevronRight size={14} />
            <span>{envelope ? "Filing review" : "Getting started"}</span>
          </div>
          <div className="header-actions">
            <span className="synthetic-label">
              <span />
              Synthetic data only
            </span>
            <button
              className="button primary small"
              onClick={() => setModal("review")}
              disabled={!!job || !config}
            >
              <Plus size={16} />
              New review
            </button>
          </div>
        </header>
        <main className="content">
          {error && (
            <div className="notice error" role="alert">
              <TriangleAlert size={19} />
              <div>
                <strong>We couldn’t complete that action</strong>
                <p>{error}</p>
              </div>
              <button
                className="icon-button"
                aria-label="Dismiss error"
                onClick={() => setError("")}
              >
                <X size={18} />
              </button>
            </div>
          )}
          {loading ? (
            <div className="loading-state" role="status">
              <LoaderCircle className="spin" size={30} />
              <h2>Opening the evidence</h2>
              <p>Loading the filing, calculations and execution ledger.</p>
            </div>
          ) : job ? (
            <div className="running-panel" role="status">
              <div className="pulse-orbit">
                <Sparkles size={32} />
              </div>
              <p className="eyebrow">REVIEW IN PROGRESS</p>
              <h1>Following the evidence.</h1>
              <p>
                The agents are reviewing your filing with read-only tools.
                <br />
                You can leave this page and reopen the review from recent
                activity.
              </p>
              <div className="stage-list">
                {[
                  [
                    "validating",
                    "Validate & calculate",
                    "Independent Python calculations",
                  ],
                  [
                    "rate_analysis",
                    "Rate Analysis Agent",
                    "Interpret portfolio and segment evidence",
                  ],
                  [
                    "documentation_review",
                    "Documentation Review Agent",
                    "Check supporting information and narrative",
                  ],
                ].map(([key, title, sub], i) => {
                  const current = [
                    "validating",
                    "rate_analysis",
                    "documentation_review",
                  ].indexOf(stage);
                  return (
                    <div
                      className={`stage-row ${i === current ? "current" : ""}`}
                      key={key}
                    >
                      {i < current ? (
                        <Check size={19} />
                      ) : i === current ? (
                        <LoaderCircle className="spin" size={19} />
                      ) : (
                        <span className="step-number">{i + 1}</span>
                      )}
                      <div>
                        <strong>{title}</strong>
                        <small>{sub}</small>
                      </div>
                      {i === current && (
                        <span className="badge rose">Running</span>
                      )}
                    </div>
                  );
                })}
              </div>
              <span className="muted">
                {elapsed}s observed in this view · Bounded requests · No
                automatic resubmission
              </span>
            </div>
          ) : !envelope ? (
            <>
              <section className="welcome">
                <div className="welcome-copy">
                  <p className="eyebrow">
                    <span className="tiny-line" /> CLARITY AT EVERY RATE CHANGE
                  </p>
                  <h1>
                    A sharper view of
                    <br />
                    your next filing.
                  </h1>
                  <p className="hero-description">
                    Turn rate revisions into a clear, evidence-led review.
                    <br />
                    Find the discrepancies. Understand the impact.
                    <br />
                    Give every decision a source.
                  </p>
                  <div className="hero-buttons">
                    <button
                      className="button primary"
                      onClick={() => loadExample("flawed")}
                    >
                      Explore a filing <ArrowRight size={17} />
                    </button>
                    <button
                      className="button secondary"
                      onClick={() => setModal("review")}
                      disabled={!config}
                    >
                      <Upload size={17} />
                      Upload your data
                    </button>
                  </div>
                  <p className="hero-footnote">
                    <ShieldCheck size={14} />
                    Deterministic calculations + two specialized AI agents
                  </p>
                </div>
                <div className="hero-art" aria-hidden="true">
                  <div className="orbital ring-one" />
                  <div className="orbital ring-two" />
                  <div className="orbital ring-three" />
                  <div className="art-center">
                    <Fingerprint size={82} strokeWidth={0.7} />
                  </div>
                  <div className="art-label label-one">
                    <span />
                    CALCULATE
                  </div>
                  <div className="art-label label-two">
                    <span />
                    INVESTIGATE
                  </div>
                  <div className="art-label label-three">
                    <span />
                    SUBSTANTIATE
                  </div>
                </div>
              </section>
              <div className="section-heading">
                <div>
                  <p className="eyebrow">START WITH THE EVIDENCE</p>
                  <h2>Three filings. Three perspectives.</h2>
                </div>
                <span className="muted small-text">
                  Saved real AI reviews · No model usage
                </span>
              </div>
              <div className="scenario-grid">
                {scenarios.map(
                  ({ id, tag, title, description, icon: Icon }) => (
                    <button
                      key={id}
                      className="scenario-card"
                      onClick={() => loadExample(id)}
                    >
                      <div className="scenario-top">
                        <span className="tile-icon">
                          <Icon size={21} />
                        </span>
                        <ArrowRight size={20} />
                      </div>
                      <span className="eyebrow">{tag}</span>
                      <h3>{title}</h3>
                      <p>{description}</p>
                      <span className="scenario-link">
                        Open {id} filing <ChevronRight size={14} />
                      </span>
                    </button>
                  ),
                )}
              </div>
              <div className="getting-started">
                <div>
                  <span className="step-number">01</span>
                  <strong>Start with a filing</strong>
                  <p>
                    Use a built-in example or upload a synthetic CSV/XLSX
                    package.
                  </p>
                </div>
                <div>
                  <span className="step-number">02</span>
                  <strong>Investigate the impact</strong>
                  <p>
                    Follow calculations to source rows and inspect each finding.
                  </p>
                </div>
                <div>
                  <span className="step-number">03</span>
                  <strong>Take a review forward</strong>
                  <p>
                    Download a complete memo, segment exhibit and audit record.
                  </p>
                </div>
              </div>
              {history.length > 0 && (
                <section className="panel recent">
                  <div className="section-heading">
                    <h2>Recent activity</h2>
                    <span className="muted">
                      This browser · {config?.retention_hours}h retention
                    </span>
                  </div>
                  {history.map((h) => (
                    <button
                      className="history-row"
                      key={h.job_id}
                      onClick={() => resume(h.job_id)}
                    >
                      <FileText size={18} />
                      <span>
                        {h.insurer}
                        <small>
                          {new Date(h.created * 1000).toLocaleString()}
                        </small>
                      </span>
                      <span className="badge">{human(h.stage)}</span>
                      <ChevronRight size={17} />
                    </button>
                  ))}
                </section>
              )}
            </>
          ) : (
            <>
              <div className="review-heading">
                <div>
                  <p className="eyebrow">CONNECTICUT / PERSONAL AUTO</p>
                  <h1>
                    {view === "overview"
                      ? "Rate revision review"
                      : navigation.find((n) => n[0] === view)?.[1]}
                  </h1>
                  <p className="review-subtitle">
                    {envelope.filing.metadata.insurer.replace(
                      " Insurance Company (fictional)",
                      "",
                    )}{" "}
                    <span>•</span> Effective{" "}
                    {envelope.filing.metadata.effective_date}
                  </p>
                </div>
                <div className="report-controls">
                  <button className="button secondary small" onClick={() => setModal("revision")} disabled={!!job || !config?.live_enabled}>
                    <Upload size={15} /> Upload revision
                  </button>
                  <span
                    className={`badge ${result.status === "partial" ? "amber" : "rose"}`}
                  >
                    {result.status === "partial"
                      ? "Partial review"
                      : "Human review required"}
                  </span>
                  <div className="dropdown">
                    <button
                      className="button secondary small"
                      aria-expanded={reportMenu}
                      onClick={() => setReportMenu(!reportMenu)}
                    >
                      <ArrowDownToLine size={16} />
                      Export review
                      <ChevronDown size={14} />
                    </button>
                    {reportMenu && (
                      <div className="dropdown-menu">
                        <a href={`${exportBase}/html`} download>
                          <FileText size={17} />
                          <span>
                            Review memo<small>Styled HTML · Print to PDF</small>
                          </span>
                        </a>
                        <a href={`${exportBase}/csv`} download>
                          <FileSpreadsheet size={17} />
                          <span>
                            Segment exhibit<small>Full-precision CSV</small>
                          </span>
                        </a>
                        <a href={`${exportBase}/json`} download>
                          <Activity size={17} />
                          <span>
                            Complete audit record
                            <small>Structured JSON with evidence</small>
                          </span>
                        </a>
                      </div>
                    )}
                  </div>
                </div>
              </div>
              <div className="provenance">
                <Clock3 size={14} />
                <span>
                  {envelope.source === "saved"
                    ? "Saved real AI review"
                    : "Live AI review"}{" "}
                  · {new Date(result.timestamp).toLocaleString()} ·{" "}
                  {result.model}
                </span>
                <code>{result.review_id.slice(0, 8)}</code>
                {envelope.source === "saved" && (
                  <button onClick={() => setModal("review")}>
                    Run a fresh review <ArrowRight size={13} />
                  </button>
                )}
              </div>
              {result.status === "partial" && (
                <div className="notice warning">
                  <TriangleAlert size={20} />
                  <div>
                    <strong>AI interpretation is incomplete</strong>
                    <p>
                      All deterministic calculations and findings are retained.
                      Inspect the execution view for the failed stage and
                      reason.
                    </p>
                  </div>
                </div>
              )}
              {view === "overview" && (
                <Overview
                  envelope={envelope}
                  setView={setView}
                  onEvidence={setEvidence}
                />
              )}
              {view === "portfolio" && (
                <Portfolio envelope={envelope} onEvidence={setEvidence} />
              )}
              {view === "findings" && (
                <Findings envelope={envelope} workflow={workflow} onWorkflow={setWorkflow} onEvidence={setEvidence} />
              )}
              {view === "comparison" && envelope.parent_id && (
                <RevisionComparison envelope={envelope} onEvidence={setEvidence} onOriginalEvidence={(ref) => setEvidence({reference:ref, original:true})} />
              )}
              {view === "documents" && (
                <Documents envelope={envelope} onEvidence={setEvidence} />
              )}
              {view === "audit" && <Audit envelope={envelope} />}
              <footer className="review-footer">
                <ShieldCheck size={15} />
                <span>
                  Analyst decision support. Connecticut requirements are not
                  verified or implemented. No compliance or submission approval
                  is implied.
                </span>
              </footer>
            </>
          )}
        </main>
        <footer className="app-footer">
          <span>
            LUMEN <span className="muted">/</span> RATE INTELLIGENCE
          </span>
          <span>Synthetic Personal Auto · Independent review</span>
        </footer>
      </div>
      {(modal === "review" || modal === "revision") && (
        <ReviewModal
          config={config}
          revisionOf={modal === "revision" ? envelope : null}
          initialScenario={result?.deterministic.scenario_id}
          close={() => setModal(null)}
          start={startReview}
        />
      )}
      {evidence && envelope && (
        <EvidenceDrawer
          reference={typeof evidence === "string" ? evidence : evidence.reference}
          envelope={typeof evidence === "string" || !evidence.original ? envelope : originalEnvelope || envelope}
          close={() => setEvidence(null)}
          onEvidence={setEvidence}
        />
      )}
    </div>
  );
}

function ReviewModal({ config, initialScenario, revisionOf, close, start }) {
  const [mode, setMode] = useState(revisionOf ? "upload" : "example"),
    [scenario, setScenario] = useState(
      ["clean", "flawed", "adversarial"].includes(initialScenario)
        ? initialScenario
        : "flawed",
    ),
    [files, setFiles] = useState({}),
    [preview, setPreview] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [code, setCode] = useState("");
  async function validate() {
    setError("");
    setBusy(true);
    try {
      const form = new FormData();
      Object.entries(files).forEach(([k, v]) => form.append(k, v));
      setPreview(
        await api("/api/uploads/preview", { method: "POST", body: form }),
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function run() {
    setBusy(true);
    setError("");
    try {
      await start({ scenario, files: mode === "upload" ? files : null, code });
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  }
  return (
    <Dialog
      title={revisionOf ? "Upload a revised filing" : "Start a filing review"}
      close={() => {
        if (!busy) close();
      }}
      wide
    >
      <p className="muted">{revisionOf ? "Submit a corrected version for an independent review. The original remains unchanged." : "Independent calculations. Two specialized agents. A traceable result."}</p>
      <div className="context-pills">
        <span>Connecticut</span>
        <span>Personal Auto</span>
        <span>Synthetic only</span>
      </div>
      {!revisionOf && <div className="segmented-control">
        <button
          className={mode === "example" ? "selected" : ""}
          onClick={() => {
            setMode("example");
            setError("");
          }}
        >
          Built-in example
        </button>
        <button
          className={mode === "upload" ? "selected" : ""}
          onClick={() => {
            setMode("upload");
            setError("");
          }}
        >
          Upload filing
        </button>
      </div>}
      {mode === "example" ? (
        <div className="example-options">
          {scenarios.map((s) => (
            <label
              className={`example-option ${scenario === s.id ? "selected" : ""}`}
              key={s.id}
            >
              <input
                type="radio"
                name="scenario"
                value={s.id}
                checked={scenario === s.id}
                onChange={() => setScenario(s.id)}
              />
              <div>
                <strong>{human(s.id)} filing</strong>
                <span>{s.description}</span>
              </div>
            </label>
          ))}
        </div>
      ) : (
        <>
          <p className="small-text muted">
            Upload three files, up to 2 MB combined and 500 segments. XLSX must
            contain a values-only <code>rates</code> sheet. Document text is
            supplied in the JSON inventory.
          </p>
          <div className="template-links">
            {revisionOf ? "Corrected flawed example:" : "Download a template:"}{" "}
            {["rates.csv", "rates.xlsx", "filing.json", "narrative.md"].map(
              (f) => (
                <a key={f} href={revisionOf ? `/api/examples/revised/files/${f}` : `/api/examples/clean/files/${f}`} download>
                  {f}
                  <ArrowDownToLine size={12} />
                </a>
              ),
            )}
          </div>
          <div className="upload-fields">
            {[
              ["rates", "Rate data", ".csv,.xlsx"],
              ["metadata", "Filing & document inventory", ".json"],
              ["narrative", "Supporting narrative", ".md,.txt"],
            ].map(([key, label, accept]) => (
              <label
                key={key}
                className={`upload-field ${files[key] ? "has-file" : ""}`}
              >
                <span>
                  <FileSpreadsheet size={19} />
                  <strong>{label}</strong>
                  {files[key] && <Check size={16} />}
                </span>
                <input
                  type="file"
                  accept={accept}
                  aria-label={label}
                  onChange={(e) => {
                    setFiles({ ...files, [key]: e.target.files[0] });
                    setPreview(null);
                    setError("");
                  }}
                />
                <small>
                  {files[key]?.name ||
                    `Choose ${accept.replaceAll(",", " or ")} file`}
                </small>
              </label>
            ))}
          </div>
          <button
            className="button secondary"
            onClick={validate}
            disabled={busy || Object.values(files).filter(Boolean).length !== 3}
          >
            {busy ? (
              <LoaderCircle className="spin" size={16} />
            ) : (
              <Check size={16} />
            )}
            Validate package
          </button>
          {preview && (
            <div className="notice success">
              <Check size={20} />
              <div>
                <strong>
                  Ready for review · {preview.analysis.rows.length} validated
                  segments
                </strong>
                <p>
                  {preview.analysis.findings.length} deterministic findings.
                  Fixed-exposure premium impact:{" "}
                  {pct(
                    preview.analysis.metrics.fixed_exposure_portfolio.value,
                    4,
                  )}
                  . AI interpretation has not run.
                </p>
              </div>
            </div>
          )}
        </>
      )}
      {config?.access_code_required && (
        <label className="code-field">
          Review access code
          <input
            type="password"
            value={code}
            autoComplete="off"
            onChange={(e) => setCode(e.target.value)}
            placeholder="Provided by the project owner"
          />
        </label>
      )}
      {!config?.live_enabled && (
        <div className="notice warning">
          <LockKeyhole size={19} />
          <p>
            Live reviews are unavailable on this server. You can still validate
            uploads and explore the saved real AI reviews.
          </p>
        </div>
      )}
      {error && (
        <div className="notice error" role="alert">
          <TriangleAlert size={19} />
          <p>{error}</p>
        </div>
      )}
      <div className="modal-bottom">
        <p>
          <LockKeyhole size={13} />
          Uses the server’s bounded AI allowance.
          <br />
          {config?.session_reviews} reviews per browser /{" "}
          {config?.daily_reviews} shared per 24 hours. Results retained{" "}
          {config?.retention_hours}h.
        </p>
        <button
          className="button primary"
          disabled={
            busy ||
            !config?.live_enabled ||
            (mode === "upload" && !preview) ||
            (config?.access_code_required && !code)
          }
          onClick={run}
        >
          {busy ? (
            <LoaderCircle className="spin" size={17} />
          ) : (
            <Sparkles size={17} />
          )}
          {revisionOf ? "Review revision" : "Run AI review"}
        </button>
      </div>
    </Dialog>
  );
}

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (this.state.failed)
      return (
        <div className="fatal">
          <h1>This view couldn’t be displayed.</h1>
          <p>
            Your saved review remains on the server. Reload the workspace to try
            again.
          </p>
          <button
            className="button primary"
            onClick={() => {
              sessionStorage.removeItem("lumen-selection");
              location.reload();
            }}
          >
            Reload workspace
          </button>
        </div>
      );
    return this.props.children;
  }
}
createRoot(document.getElementById("root")).render(
  <ErrorBoundary>
    <App />
  </ErrorBoundary>,
);
