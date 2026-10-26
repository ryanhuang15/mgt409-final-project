"""Escaped, self-contained analyst memo. No model-generated HTML or scripts."""

import csv
import io
import json
from decimal import Decimal
from html import escape
from datetime import datetime, timezone


def e(value):
    return escape(str(value if value is not None else "Unavailable"), quote=True)


def number(value, places=2):
    return "Unavailable" if value is None else f"{Decimal(str(value)):,.{places}f}"


def segment_csv(envelope):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    rows = envelope["result"]["deterministic"]["rows"]
    writer.writerow(["segment_id", "current_modeled_rate_USD", "proposed_modeled_rate_USD", "absolute_rate_change_USD_per_exposure", "rate_change_pct"])
    for row in rows:
        identifier = row["segment_id"]
        if identifier.startswith(("=", "+", "-", "@")):
            identifier = "'" + identifier  # Keep text identifiers from becoming spreadsheet formulas.
        writer.writerow([identifier, *[row[key] for key in ("current_modeled_rate", "proposed_modeled_rate", "absolute_rate_change", "rate_change_pct")]])
    return output.getvalue()


def render_memo(envelope):
    result, filing = envelope["result"], envelope["filing"]
    analysis = result["deterministic"]
    metric_labels = {"fixed_exposure_portfolio": "Fixed-exposure portfolio premium impact", "exposure_weighted": "Exposure-weighted average rate change", "current_premium_weighted": "Current-premium-weighted rate change", "current_modeled_premium": "Current modeled portfolio premium", "proposed_modeled_premium": "Proposed modeled portfolio premium"}
    metrics = "".join(f"<tr><th>{e(metric_labels.get(key,key))}</th><td>{number(m['value'], 4 if m['unit']=='percent' else 2)} {'%' if m['value'] is not None and m['unit']=='percent' else 'USD' if m['value'] is not None else ''}</td><td>{e(m.get('reason') or m['category'])}</td></tr>" for key,m in analysis["metrics"].items())
    findings = "".join(f"<article><p class='eyebrow'>{e(f['severity'])} · {e(f['origin'])} · {e(f['finding_id'])}</p><h3>{e(f['title'])}</h3><p>{e(f['explanation'])}</p><p><b>Next action:</b> {e(f['recommended_action'])}</p><p class='small'>Evidence: {e(', '.join(f['evidence_refs']))}</p></article>" for f in result["findings"]) or "<p>No findings were returned in the completed portions of this review. This is not a compliance conclusion.</p>"
    agents = "".join(f"<article><h3>{e(a['agent'].replace('_',' ').title())} · {e(a['status'])}</h3><p>{e(a['result']['summary']['explanation'] if a['result'] else a.get('error','Incomplete'))}</p></article>" for a in result["agents"])
    segments = "".join(f"<tr><th>{e(r['segment_id'])}</th><td>{number(r['current_modeled_rate'])}</td><td>{number(r['proposed_modeled_rate'])}</td><td>{number(r['absolute_rate_change'])}</td><td>{number(r['rate_change_pct'],4)}%</td><td>{e(r['evidence_id'])}</td></tr>" for r in analysis["rows"])
    documents = "".join(f"<article><h3>{e(d['document_id'])} · {e(d['title'])}</h3><p>{e(d['status'])}</p><pre>{e(d['text'])}</pre></article>" for d in filing["metadata"]["documents"])
    evidence = {**analysis["evidence"], **result["supplemental_evidence"], **result["documentation_evidence"]}
    refs = sorted({ref for f in result["findings"] for ref in f["evidence_refs"]})
    appendices = "".join(f"<details><summary>{e(ref)}</summary><pre>{e(json.dumps(evidence.get(ref, {}), indent=2))}</pre></details>" for ref in refs)
    usage = result["usage"]
    hashes = "".join(f"<li>{e(name)}: <code>{e(value)}</code></li>" for name,value in analysis["source_file_sha256"].items())
    workflow = envelope.get("workflow") or {"current": {}, "history": []}
    reviewer_items = "".join(
        f"<article><h3>{e(fid)} · {e(item['status'].replace('_',' ').title())}</h3>"
        f"<p><b>Resolution:</b> {e(item['resolution'] or 'No resolution explanation recorded')}</p>"
        f"<p class='small'>Updated {e(datetime.fromtimestamp(item['updated_at'], timezone.utc).isoformat())}</p>"
        + "".join(f"<p><b>Reviewer note:</b> {e(note['note'])} <span class='small'>({e(datetime.fromtimestamp(note['created'], timezone.utc).isoformat())})</span></p>"
                  for note in workflow["history"] if note["finding_id"] == fid and note["note"])
        + "</article>" for fid,item in workflow["current"].items()
    ) or "<p>No reviewer actions recorded for this browser session.</p>"
    comparison = envelope.get("comparison")
    revision = ""
    if comparison:
        changes = "".join(f"<tr><th>{e(item['issue_key'])}</th><td>{e(item['status'].replace('_',' ').title())}</td><td>{e(item['reason'])}</td></tr>" for item in comparison["issues"])
        revision = (f"<h2>Revision comparison</h2><p>Original review: {e(comparison['original_review_id'])}. "
                    f"Revised review: {e(comparison['revised_review_id'])}. "
                    f"Fixed-exposure portfolio premium impact: {number(comparison['portfolio']['before_pct'],4)}% to "
                    f"{number(comparison['portfolio']['after_pct'],4)}%; difference "
                    f"{number(comparison['portfolio']['difference_pp'],4)} percentage points. "
                    f"Current revised findings: {e(comparison['current_finding_count'])}.</p>"
                    f"<p class='small'>{e(comparison['method'])}</p><table><thead><tr><th>Issue anchor</th><th>Comparison</th><th>Reason</th></tr></thead><tbody>{changes}</tbody></table>")
    return f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Lumen · Review memo</title>
<style>body{{margin:0;background:#edf0f3;color:#172334;font:15px/1.65 system-ui,sans-serif}}main{{max-width:960px;margin:35px auto;background:white;padding:60px;border-top:6px solid #c53573}}h1{{font-size:40px;letter-spacing:-1.5px;line-height:1.1}}h2{{margin-top:38px;border-bottom:1px solid #ccd3dc;padding-bottom:10px}}h3{{margin-bottom:6px}}.eyebrow{{text-transform:uppercase;letter-spacing:2px;font-size:11px;color:#a42760}}.small,footer{{font-size:12px;color:#586477}}.notice{{background:#fcf0f5;border-left:3px solid #c53573;padding:14px 20px}}article{{padding:12px 0;border-bottom:1px solid #e0e5eb;break-inside:avoid}}table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{text-align:left;padding:10px 8px;border-bottom:1px solid #e0e5eb}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;background:#f4f6f8;padding:15px}}code{{overflow-wrap:anywhere}}summary{{cursor:pointer;padding:10px}}@media print{{body{{background:white}}main{{margin:0;padding:12mm;max-width:none}}details>*{{display:block}}thead{{display:table-header-group}}h2,h3{{break-after:avoid}}}}@page{{size:A4;margin:12mm}}</style>
<main><p class="eyebrow">LUMEN / RATE INTELLIGENCE</p><h1>Independent filing<br>review memo</h1><p>{e(filing['metadata']['insurer'])}<br>Connecticut · Personal Auto · Effective {e(filing['metadata']['effective_date'])}</p>
<p class="small">Review {e(result['review_id'])} · {e(result['timestamp'])}<br>{'Saved real AI review' if envelope['source']=='saved' else 'Live review'} · Status: {e(result['status'])}</p>
<div class="notice"><b>Human review required.</b> Synthetic data only. Connecticut is context; state-specific regulatory requirements have not been verified or implemented. This memo is analyst decision support and makes no legal-compliance or submission-approval determination.</div>
<h2>Executive assessment</h2><p>{len(result['findings'])} findings returned; {sum(f['severity']=='high' for f in result['findings'])} high severity. {'One or more AI stages are incomplete. Numerical results remain available; review stage errors below.' if result['status']!='complete' else 'Both specialized agent stages completed.'}</p>{agents}
<h2>Portfolio impact</h2><table><thead><tr><th>Measure</th><th>Calculated</th><th>Basis / limitation</th></tr></thead><tbody>{metrics}</tbody></table><p>Submitted overall claim: {e(filing['metadata']['claimed_overall_change_pct'])}% on {e(filing['metadata']['claimed_overall_basis'])} basis.</p>
<h2>Findings and recommended actions</h2>{findings}
<h2>Reviewer actions</h2>{reviewer_items}{revision}
<h2>Segment exhibit</h2><table><thead><tr><th>Segment</th><th>Current $</th><th>Proposed $</th><th>Change $ / exposure</th><th>Change %</th><th>Evidence</th></tr></thead><tbody>{segments}</tbody></table>
<h2>Methods and assumptions</h2><p>Current rate = current base × current factor; proposed rate = proposed base × proposed factor. Segment change d = 100 × (proposed − current) / current. Exposure-weighted average = Σ(E × d) / ΣE. Fixed-exposure premium impact = 100 × [Σ(E × proposed) / Σ(E × current) − 1]. Current-premium-weighted change = Σ(P × d) / ΣP. Weights are never substituted. Missing, incomplete, negative or all-zero weights make the corresponding measure unavailable. Inconsistent supplied premiums invalidate premium weighting.</p><p>USD per annual vehicle exposure; fixed coverage and portfolio mix. Excludes taxes, fees, minimum premiums, policy rounding, retention and demand. Percentages are displayed rounded; source Decimal values remain in the JSON export. Large-change screening is a review heuristic, not a legal threshold.</p><pre>{e(json.dumps(analysis['config'],indent=2))}</pre>
<h2>Submitted documentation · untrusted source text</h2><pre>{e(filing['narrative'])}</pre>{documents}
<h2>Evidence appendix</h2>{appendices}<h3>Input fingerprints</h3><ul>{hashes}</ul>
<h2>Execution and usage</h2><p>Model: {e(result['model'])}. {e(usage['total_model_calls'])} model requests; {number(usage['model_latency_ms']/1000)} seconds of measured model latency. Input: {e(usage['input_tokens'])}; cached input (subset): {e(usage['cached_input_tokens'])}; output: {e(usage['output_tokens'])}; total: {e(usage['total_tokens'])} tokens. Exact billing is unavailable. The JSON export includes the full sanitized execution ledger.</p>
<footer>Lumen / Insurance Rate Filing Assistant · Synthetic Personal Auto analysis · Print this memo to PDF using your browser.</footer></main></html>"""
