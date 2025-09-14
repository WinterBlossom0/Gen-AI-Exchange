import React, { ChangeEvent, useEffect, useMemo, useState } from 'react'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

type JobState = {
  id: string
  status: string
  step: number
  total: number
  message?: string
  agent?: string
  label?: string
  partials?: any
}

type Risk = { clause: string; risk: string; fairness: string; favours: string; severity: string }
type Mitigation = { clause: string; mitigation: string; negotiation_points?: string }
type AlertDecision = { exploitative: boolean; rationale?: string; top_unfair_clauses?: string[] }

export default function App() {
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [job, setJob] = useState<JobState | null>(null)
  const [restored, setRestored] = useState(false)
  const [showJson, setShowJson] = useState(false)
  const [reportJson, setReportJson] = useState<any>(null)
  const [reportLoading, setReportLoading] = useState(false)
  const [showContract, setShowContract] = useState(false)
  const [stopping, setStopping] = useState(false)

  const USE_ASYNC = true

  // restore persisted state on first load
  useEffect(() => {
    try {
      const j = localStorage.getItem('job')
      const r = localStorage.getItem('result')
      if (j) setJob(JSON.parse(j))
      if (r) setResult(JSON.parse(r))
    } catch {}
    setRestored(true)
  }, [])

  // persist on change
  useEffect(() => {
    try {
      job ? localStorage.setItem('job', JSON.stringify(job)) : localStorage.removeItem('job')
    } catch {}
  }, [job])
  useEffect(() => {
    try {
      result ? localStorage.setItem('result', JSON.stringify(result)) : localStorage.removeItem('result')
    } catch {}
  }, [result])

  const canAnalyze = useMemo(() => !!file && !loading, [file, loading])

  const safeParseJson = <T,>(val: any): T | null => {
    if (!val || typeof val !== 'string') return null
    try {
      return JSON.parse(val) as T
    } catch {
      return null
    }
  }

  const bulletLines = (text: string): string[] => {
    if (!text) return []
    const lines = text.split(/\r?\n/).map(s => s.trim()).filter(Boolean)
    if (lines.some(l => /^[-*•]/.test(l))) {
      return lines.map(l => l.replace(/^[-*•]\s*/, '')).slice(0, 10)
    }
    const chunks = text.split(/[\n\r]+|(?<=[.!?])\s+/).map(s => s.trim()).filter(Boolean)
    return chunks.slice(0, 10)
  }

  const limitText = (text: string, max = 360): string => {
    if (!text) return ''
    if (text.length <= max) return text
    return text.slice(0, max - 1).trimEnd() + '…'
  }

  const onUpload = async () => {
    if (!file) return
    setLoading(true)
    setAnswer('')
    setResult(null)
    try {
      const form = new FormData()
      form.append('file', file)
      if (USE_ASYNC) {
        const start = await fetch(`${API}/analyze/start`, { method: 'POST', body: form })
        const startData = await start.json()
        if (!start.ok || !startData.job_id) throw new Error('Failed to start analysis')
        const jobId = startData.job_id as string
        setJob({ id: jobId, status: 'pending', step: 0, total: 7 })

        const poll = async () => {
          const st = await fetch(`${API}/analyze/status/${jobId}`)
          const sdata = await st.json()
          const total = sdata.total_steps || 7
          const step = sdata.step || 0
          setJob({
            id: jobId,
            status: sdata.status,
            step,
            total,
            message: sdata.message,
            agent: sdata.current_agent,
            label: sdata.current_label,
            partials: sdata.partials,
          })
          if (sdata.status === 'done' && sdata.result) {
            setResult(sdata.result)
            return
          }
          if (sdata.status === 'cancelled') {
            return
          }
          if (sdata.status === 'error') {
            throw new Error(sdata.message || 'Analysis failed')
          }
          setTimeout(poll, 1500)
        }
        await poll()
      } else {
        const res = await fetch(`${API}/analyze`, { method: 'POST', body: form })
        const data = await res.json()
        setResult(data)
      }
    } catch (e: any) {
      alert('Upload failed. Make sure the backend is running at ' + API + '\n' + (e?.message || e))
    } finally {
      setLoading(false)
    }
  }

  const onAsk = async () => {
    if (!result || !question.trim()) return
    setLoading(true)
    try {
      const res = await fetch(`${API}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contract_text: result.contract_text,
          analysis: JSON.stringify({
            purpose: result.purpose,
            commercial: result.commercial,
            legal_risks: result.legal_risks,
            mitigations: result.mitigations,
            alert: result.alert,
            plain: result.plain,
          }),
          question,
        }),
      })
      const data = await res.json()
      setAnswer(data.answer || '')
    } catch (e: any) {
      alert('Chat failed: ' + (e?.message || e))
    } finally {
      setLoading(false)
    }
  }

  // Load saved JSON report on demand
  useEffect(() => {
    const fetchReport = async () => {
      if (!result?.report_url || !showJson) return
      try {
        setReportLoading(true)
        setReportJson(null)
        const url = `${API.replace(/\/$/, '')}${result.report_url}`
        const res = await fetch(url)
        if (!res.ok) throw new Error('Failed to load JSON report')
        const data = await res.json()
        setReportJson(data)
      } catch (e) {
        setReportJson({ error: 'Could not load report JSON' })
      } finally {
        setReportLoading(false)
      }
    }
    fetchReport()
  }, [showJson, result])

  // Derived views with partial fallbacks
  const fullText: string = (result?.contract_text ?? job?.partials?.contract_text ?? '') as string
  const plainText: string = (result?.plain ?? job?.partials?.plain ?? '') as string
  const purposeText: string = (result?.purpose ?? job?.partials?.purpose ?? '') as string
  const commercialMap: Record<string, any> | null = (result?.commercial_parsed ?? job?.partials?.commercial_parsed) || (result?.commercial ? safeParseJson<Record<string, any>>(result.commercial) : null)
  const risksList: Risk[] = (result?.legal_risks_parsed ?? job?.partials?.legal_risks_parsed) || (result?.legal_risks ? (safeParseJson<Risk[]>(result.legal_risks) || []) : [])
  const mitigationsList: Mitigation[] = (result?.mitigations_parsed ?? job?.partials?.mitigations_parsed) || (result?.mitigations ? (safeParseJson<Mitigation[]>(result.mitigations) || []) : [])
  const alertObj: AlertDecision | null = (result?.alert_parsed ?? job?.partials?.alert_parsed) || (result?.alert ? safeParseJson<AlertDecision>(result.alert) : null)

  return (
    <div className="container">
      <h1 className="title">Contract Analyzer</h1>
      <p className="subtitle">Upload a PDF. We’ll explain it in simple terms and highlight important legal and commercial points.</p>

      <div className="row">
        <input className="input" type="file" accept="application/pdf" onChange={(e: ChangeEvent<HTMLInputElement>) => setFile(e.target.files?.[0] || null)} />
        <button className="btn" onClick={onUpload} disabled={!canAnalyze}>{loading ? 'Analyzing…' : 'Analyze'}</button>
      </div>

      {job && (
        <div className="card full" style={{ marginBottom: 16 }}>
          <div className="row space">
            <div>Step {Math.min(job.step, job.total)} / {job.total}</div>
            <div className="row" style={{gap: 8}}>
              <div className="text small">{job.status.toUpperCase()} {job.message ? `– ${job.message}` : ''}</div>
              {(job.status === 'pending' || job.status === 'running') && (
                <button className="btn" onClick={async () => {
                  if (!job?.id) return
                  try {
                    setStopping(true)
                    await fetch(`${API}/analyze/cancel/${job.id}`, { method: 'POST' })
                  } finally {
                    setStopping(false)
                  }
                }} disabled={stopping}>
                  {stopping ? 'Stopping…' : 'Stop'}
                </button>
              )}
            </div>
          </div>
          {job.agent && (
            <div className="text small" style={{ marginTop: 6 }}>
              Working: <strong>{job.agent}</strong> {job.label ? `(${job.label})` : ''}
            </div>
          )}
          <div className="progress"><div className="bar" style={{ width: `${job.total > 0 ? (Math.max(0, Math.min(job.step, job.total)) / job.total) * 100 : 0}%` }} /></div>
        </div>
      )}

      {(!!fullText || !!plainText || !!purposeText || (commercialMap && Object.keys(commercialMap).length) || risksList.length || mitigationsList.length || alertObj) && (
        <div className="grid">
          <section className="card full">
            <div className="row space">
              <h2>Contract text</h2>
              <button className="btn" onClick={() => setShowContract(v => !v)}>{showContract ? 'Hide' : 'Show'}</button>
            </div>
            {showContract && (
              <pre className="pre" style={{maxHeight: 320, overflow: 'auto'}}>{fullText || '(No text extracted)'}</pre>
            )}
          </section>
          <section className="card full">
            <h2>In simple terms</h2>
            {bulletLines(plainText).length > 0 ? (
              <ul className="bullets">
                {bulletLines(plainText).map((b, i) => (
                  <li key={i}>{b}</li>
                ))}
              </ul>
            ) : (
              <div className="text small">Waiting for summary…</div>
            )}
          </section>

          <section className="card">
            <h3>Purpose</h3>
            {bulletLines(purposeText).length > 0 ? (
              <ul className="bullets">
                {bulletLines(purposeText).map((b, i) => (
                  <li key={i}>{b}</li>
                ))}
              </ul>
            ) : (
              <p className="text">{limitText(purposeText)}</p>
            )}
          </section>

          <section className="card">
            <h3>Commercial</h3>
            {commercialMap && Object.keys(commercialMap).length > 0 ? (
              <dl className="kv">
                {Object.entries(commercialMap).map(([k, v]) => (
                  <div className="kv-row" key={k}>
                    <dt>{k.replace(/_/g, ' ')}</dt>
                    <dd>{String((v as unknown) ?? '—')}</dd>
                  </div>
                ))}
              </dl>
            ) : (
              <div className="text small">No commercial terms parsed. Check the JSON Summary for raw output.</div>
            )}
          </section>

          <section className="card">
            <h3>Legal Risks</h3>
            {Array.isArray(risksList) && risksList.length > 0 ? (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Clause</th>
                      <th>Risk</th>
                      <th>Fairness</th>
                      <th>Favours</th>
                      <th>Severity</th>
                    </tr>
                  </thead>
                  <tbody>
                    {risksList.map((r, idx) => (
                      <tr key={idx}>
                        <td>{r.clause}</td>
                        <td>{r.risk}</td>
                        <td><span className={`badge ${r.fairness === 'unfair' ? 'bad' : 'good'}`}>{r.fairness}</span></td>
                        <td>{r.favours}</td>
                        <td><span className={`badge sev-${(r.severity || '').toLowerCase()}`}>{r.severity}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text small">No legal risks parsed. Check the JSON Summary for raw output.</div>
            )}
          </section>

          <section className="card">
            <h3>Mitigations</h3>
            {Array.isArray(mitigationsList) && mitigationsList.length > 0 ? (
              <div className="table-wrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Clause</th>
                      <th>Mitigation</th>
                      <th>Negotiation Points</th>
                    </tr>
                  </thead>
                  <tbody>
                    {mitigationsList.map((m, idx) => (
                      <tr key={idx}>
                        <td>{m.clause}</td>
                        <td>{m.mitigation}</td>
                        <td>{m.negotiation_points || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text small">No mitigations parsed. Check the JSON Summary for raw output.</div>
            )}
          </section>

          <section className="card">
            <h3>Exploitative?</h3>
            {alertObj ? (
              <div>
                <div className="row space">
                  <span className={`pill ${alertObj.exploitative ? 'pill-bad' : 'pill-good'}`}>
                    {alertObj.exploitative ? 'Exploitative' : 'Not exploitative'}
                  </span>
                </div>
                {alertObj.rationale && <p className="text small">{alertObj.rationale}</p>}
                {alertObj.top_unfair_clauses?.length ? (
                  <ul className="bullets compact">
                    {alertObj.top_unfair_clauses.slice(0, 5).map((c: string, i: number) => (
                      <li key={i}>{c}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ) : (
              <div className="text small">No decision yet.</div>
            )}
          </section>

          {result?.report_url && (
            <section className="card full">
              <div className="row space">
                <a className="link" href={`${API.replace(/\/$/, '')}${result.report_url}`} target="_blank" rel="noreferrer">Download JSON report</a>
                <button className="btn" onClick={() => setShowJson(v => !v)}>
                  {showJson ? 'Hide JSON Summary' : 'Show JSON Summary'}
                </button>
              </div>
              {showJson && (
                reportLoading ? (
                  <div className="text small" style={{ marginTop: 8 }}>Loading JSON…</div>
                ) : (
                  <pre className="pre" style={{ marginTop: 8 }}>{JSON.stringify(reportJson ?? { note: 'No report loaded' }, null, 2)}</pre>
                )
              )}
            </section>
          )}
        </div>
      )}

          {(result || answer) && (
        <div className="chat">
          <h2>Ask questions</h2>
          <div className="row">
            <input className="input" value={question} onChange={e => setQuestion(e.target.value)} placeholder="e.g., Who pays for delays?" />
            <button className="btn" onClick={onAsk} disabled={loading || !question.trim()}>Ask</button>
          </div>
          {answer && (
                <div className="card">
                  <ul className="bullets">
                    {bulletLines(answer).map((line, idx) => (
                      <li key={idx}>{line}</li>
                    ))}
                  </ul>
                </div>
          )}
        </div>
      )}
    </div>
  )
}
