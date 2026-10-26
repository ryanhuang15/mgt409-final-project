import React, {useEffect, useState} from 'react';
import {ArrowRight, Check, Clock3, FileText, Fingerprint, Info, Search, ShieldCheck} from 'lucide-react';
import {Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis} from 'recharts';
import {api, Dialog, human, money, pct} from './ui.jsx';

export const STATUSES = [
  ['open', 'Open'], ['under_review', 'Under review'], ['resolved', 'Resolved'],
  ['accepted_risk', 'Accepted risk'], ['not_applicable', 'Not applicable'],
];
const closed = new Set(['resolved', 'accepted_risk', 'not_applicable']);
const pp = value => value == null ? 'Unavailable' : `${Number(value).toLocaleString('en-US',{minimumFractionDigits:4,maximumFractionDigits:4})} pp`;

function statusLabel(value) { return STATUSES.find(([key]) => key === value)?.[1] || 'Open'; }
export function StatusBadge({status}) {return <span className={`badge workflow-badge status-${status || 'open'}`}>{statusLabel(status || 'open')}</span>;}

function SupportingEvidence({finding,envelope,onEvidence}) {
  const records = envelope.result.deterministic.evidence;
  const extras = envelope.result.supplemental_evidence;
  const queue = [...finding.evidence_refs];
  const seen = new Set(), rows = [], formulas = [];
  while (queue.length && seen.size < 70) {
    const ref = queue.shift();
    if (seen.has(ref)) continue;
    seen.add(ref);
    const item = records[ref] || extras[ref];
    if (item?.kind === 'source_row') rows.push(item);
    if (item?.formula) formulas.push([ref, item.formula]);
    queue.push(...(item?.input_refs || []));
  }
  return <div className="workbench-evidence">
    <h3>Supporting source rows</h3>
    {rows.length ? rows.slice(0,8).map(row=><button key={row.evidence_id} className="source-row-link" onClick={()=>onEvidence(row.evidence_id)}><Fingerprint size={15}/><span>{row.evidence_id}<small>{row.source_file} · row {row.row_number}{row.values?.exposure ? ` · ${row.values.exposure} exposures` : ''}</small></span><ArrowRight size={15}/></button>) : <p className="muted small-text">This finding cites portfolio or document evidence. Open its evidence references below.</p>}
    {formulas.length>0&&<><h3>Verified calculation formula</h3>{formulas.slice(0,3).map(([ref,formula])=><div className="formula-block" key={ref}><code>{formula}</code><button className="text-button" onClick={()=>onEvidence(ref)}>Inspect <ArrowRight size={13}/></button></div>)}</>}
    <div className="evidence-chips">{finding.evidence_refs.map(ref=><button key={ref} onClick={()=>onEvidence(ref)}><Fingerprint size={12}/>{ref}</button>)}</div>
  </div>;
}

export function FindingWorkbench({finding,envelope,workflow,onSaved,onEvidence,close}) {
  const current=workflow?.current?.[finding.finding_id];
  const [status,setStatus]=useState(current?.status||'open'),[note,setNote]=useState(''),[resolution,setResolution]=useState(current?.resolution||''),[saving,setSaving]=useState(false),[error,setError]=useState('');
  const history=(workflow?.history||[]).filter(item=>item.finding_id===finding.finding_id);
  const related=envelope.result.agents.flatMap(agent=>agent.result?.interpretations||[]).filter(item=>item.related_deterministic_finding_ids?.includes(finding.finding_id));
  const evidence=finding.numerical_evidence;
  async function save(){setSaving(true);setError('');try{const updated=await api(`/api/reviews/${encodeURIComponent(envelope.job_id)}/findings/${encodeURIComponent(finding.finding_id)}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status,note,resolution})});onSaved(updated);setNote('');}catch(error){setError(error.message);}finally{setSaving(false);}}
  return <Dialog title="Investigate finding" close={close} wide><div className="workbench-title"><StatusBadge status={current?.status}/><span className="badge">{finding.severity} severity</span><span className="origin-label">{finding.origin==='deterministic'?'Python calculation':'AI interpretation'}</span></div><h2 className="workbench-heading">{finding.title}</h2><p className="muted">{finding.explanation}</p>
    {evidence&&['reported_value','calculated_value','difference'].some(k=>evidence[k]!=null)&&<div className="workbench-numbers">{[['reported_value','Reported figure'],['calculated_value','Calculated figure'],['difference','Reported − calculated']].map(([key,label])=><div key={key}><span>{label}</span><strong>{evidence[key]==null?'Not supplied':Number(evidence[key]).toLocaleString('en-US',{maximumFractionDigits:8})}</strong><small>{key==='difference'&&evidence.unit==='percentage_points'?'percentage points':evidence.unit||''}</small></div>)}</div>}
    <SupportingEvidence finding={finding} envelope={envelope} onEvidence={onEvidence}/>
    {related.length>0&&<div className="agent-note"><p className="eyebrow">RATE ANALYSIS AGENT</p>{related.map((item,index)=><div key={index}><strong>{item.title}</strong><p>{item.explanation}</p></div>)}</div>}
    {finding.source_quotes?.map((quote,index)=><blockquote key={index}><span>SUBMITTED TEXT · UNTRUSTED</span>“{quote.quote}”</blockquote>)}
    <div className="next-action"><span>RECOMMENDED NEXT STEP</span><p>{finding.recommended_action}</p></div>
    <div className="reviewer-panel"><div className="panel-heading"><div><p className="eyebrow">REVIEWER WORKFLOW</p><h2>Record your decision</h2></div><ShieldCheck size={19}/></div><label>Disposition<select aria-label="Reviewer disposition" value={status} onChange={e=>setStatus(e.target.value)}>{STATUSES.map(([value,label])=><option value={value} key={value}>{label}</option>)}</select></label><label>Reviewer note<textarea aria-label="Reviewer note" value={note} maxLength={2000} placeholder="What did you verify or ask for?" onChange={e=>setNote(e.target.value)}/></label><label>Resolution explanation {closed.has(status)?'(required)':'(if applicable)'}<textarea aria-label="Resolution explanation" value={resolution} maxLength={4000} placeholder="Describe how the evidence addresses this issue" onChange={e=>setResolution(e.target.value)}/></label><p className="small-text muted">Reviewer actions are stored separately. The original finding, severity and cited evidence remain unchanged. Notes are never sent to agents.</p>{error&&<div className="notice error" role="alert"><p>{error}</p></div>}<button className="button primary" disabled={saving||(closed.has(status)&&!resolution.trim())||(!note.trim()&&!resolution.trim()&&status==='open')} onClick={save}>{saving?'Saving…':'Save reviewer action'}</button></div>
    {history.length>0&&<div className="workbench-history"><h3>Activity history</h3>{history.map((entry,index)=><div key={index}><Clock3 size={14}/><div><strong>{statusLabel(entry.status)}</strong> <span className="muted">· {new Date(entry.created*1000).toLocaleString()}</span>{entry.note&&<p>{entry.note}</p>}{entry.resolution&&<p>Resolution: {entry.resolution}</p>}</div></div>)}</div>}
  </Dialog>;
}

const comparisonNames={resolved_by_revised_evidence:'Resolved by revised evidence',still_present:'Still present',newly_identified:'Newly identified',not_comparable_requires_review:'Needs further review'};
export function RevisionComparison({envelope,onEvidence,onOriginalEvidence}) {
  const [comparison,setComparison]=useState(null),[error,setError]=useState(''),[filter,setFilter]=useState('all');
  useEffect(()=>{let active=true;api(`/api/reviews/${encodeURIComponent(envelope.job_id)}/comparison`).then(value=>{if(active)setComparison(value);}).catch(error=>{if(active)setError(error.message);});return()=>{active=false;};},[envelope.job_id]);
  if(error)return <div className="notice error" role="alert">{error}</div>;
  if(!comparison)return <div className="loading-state" role="status"><h2>Comparing source evidence</h2><p>Loading both immutable reviews and their numerical conditions.</p></div>;
  const c=comparison, rows=c.segments.filter(s=>s.before_pct!=null&&s.after_pct!=null).map(s=>({...s,before:Number(s.before_pct),after:Number(s.after_pct)}));
  const issues=c.issues.filter(item=>filter==='all'||item.status===filter);
  return <div className="view-enter"><div className="comparison-intro"><div><p className="eyebrow">LINKED REVISION</p><h2>What changed in the evidence?</h2><p>Original and revised reviews remain separate. A changed AI phrase cannot resolve a finding by itself.</p></div><div className="comparison-ids"><span>ORIGINAL <code>{c.original_review_id.slice(0,10)}</code></span><ArrowRight size={17}/><span>REVISED <code>{c.revised_review_id.slice(0,10)}</code></span></div></div>
    <div className="comparison-metrics"><div className="panel"><span>Original premium impact</span><strong>{pct(c.portfolio.before_pct,4)}</strong><small>Fixed-exposure basis</small></div><div className="panel"><span>Revised premium impact</span><strong>{pct(c.portfolio.after_pct,4)}</strong><small>Fixed-exposure basis</small></div><div className="panel"><span>Change between reviews</span><strong>{pp(c.portfolio.difference_pp)}</strong><small>Percentage points · calculated in Python</small></div><div className="panel"><span>Remaining revised findings</span><strong>{c.current_finding_count}</strong><small>Review status: {human(c.revised_status)}</small></div></div>
    <section className="panel comparison-chart"><div className="panel-heading"><div><p className="eyebrow">SEGMENT RATES</p><h2>Before and after, by segment</h2></div><span className="badge">{rows.length} comparable</span></div><div className="chart-legend"><span><i style={{background:'#8490a9'}}/>Original</span><span><i style={{background:'#e99fbc'}}/>Revised</span></div><div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><BarChart data={rows} margin={{left:-14,right:12,top:10,bottom:5}}><CartesianGrid stroke="#272c38" vertical={false}/><XAxis dataKey="segment_id" tick={{fill:'#9ca8b9',fontSize:9}} interval={rows.length>20?2:0} tickLine={false} axisLine={false}/><YAxis tickFormatter={v=>`${v}%`} tick={{fill:'#9ca8b9',fontSize:10}} tickLine={false} axisLine={false}/><Tooltip content={({active,payload})=>active&&payload?.length?<div className="chart-tooltip"><strong>{payload[0]?.payload?.segment_id}</strong><div>Original <b>{pct(payload[0]?.payload?.before,3)}</b></div><div>Revised <b>{pct(payload[0]?.payload?.after,3)}</b></div></div>:null}/><Bar name="Original" dataKey="before" fill="#8490a9" maxBarSize={18} isAnimationActive={false} onClick={row=>onOriginalEvidence(row.before_evidence)} cursor="pointer"/><Bar name="Revised" dataKey="after" fill="#e99fbc" maxBarSize={18} isAnimationActive={false} onClick={row=>onEvidence(row.after_evidence)} cursor="pointer"/></BarChart></ResponsiveContainer></div><p className="chart-note">Select a gray bar for original calculation evidence; pink bars open the revised evidence.</p></section>
    <section className="panel comparison-findings"><div className="panel-heading"><div><p className="eyebrow">ISSUE MOVEMENT</p><h2>Which concerns changed?</h2></div><span className="muted small-text">{c.original_status} original · {c.revised_status} revised</span></div><div className="comparison-statuses">{Object.entries(comparisonNames).map(([key,label])=><button className={filter===key?'selected':''} key={key} onClick={()=>setFilter(filter===key?'all':key)}><strong>{c.counts[key]}</strong><span>{label}</span></button>)}</div>{issues.map(item=><article className="comparison-issue" key={item.issue_key}><span className={`badge comparison-${item.status}`}>{comparisonNames[item.status]}</span><div><h3>{item.before?.title||item.after?.title||item.issue_key}</h3><p>{item.reason}</p><small>{item.origin==='deterministic'?'Deterministic condition':'Documentation interpretation'} · {item.issue_key}</small></div><div className="comparison-evidence">{item.before?.evidence_refs?.[0]&&<button onClick={()=>onOriginalEvidence(item.before.evidence_refs[0])}>Original source <ArrowRight size={13}/></button>}{item.after?.evidence_refs?.[0]&&<button onClick={()=>onEvidence(item.after.evidence_refs[0])}>Revised source <ArrowRight size={13}/></button>}</div></article>)}{issues.length===0&&<div className="empty"><Info size={22}/><p>No issues in this comparison category.</p></div>}</section>
    <section className="panel comparison-table"><div className="panel-heading"><h2>Segment change ledger</h2><span className="muted small-text">Backend calculated, full precision in JSON export</span></div><div className="table-scroll"><table><thead><tr><th>Segment</th><th>Original change</th><th>Revised change</th><th>Difference</th><th>Status</th><th>Source</th></tr></thead><tbody>{c.segments.map(row=><tr key={row.segment_id}><td>{row.segment_id}</td><td>{pct(row.before_pct,4)}</td><td>{pct(row.after_pct,4)}</td><td>{row.difference_pp==null?'Unavailable':pp(row.difference_pp)}</td><td>{human(row.status)}</td><td>{row.after_evidence&&<button className="text-button" onClick={()=>onEvidence(row.after_evidence)}>Inspect <ArrowRight size={12}/></button>}</td></tr>)}</tbody></table></div></section>
  </div>;
}
