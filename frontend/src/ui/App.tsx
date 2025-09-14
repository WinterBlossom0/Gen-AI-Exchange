import React, { ChangeEvent, useMemo, useState } from 'react'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function App() {
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [job, setJob] = useState<{ id: string; status: string; step: number; total: number; message?: string } | null>(null)

  const USE_ASYNC = true

  const canAnalyze = useMemo(() => !!file && !loading, [file, loading])

  const safeParseJson = <T,>(val: any): T | null => {
    if (!val || typeof val !== 'string') return null
    try {
      return JSON.parse(val) as T
    } catch {
      return null
    }
  }

  const parsed = useMemo(() => {
    if (!result) return { commercial: null, risks: null, mitigations: null, alert: null }
    // Prefer backend-parsed fields, fallback to local parse
    const commercial = result.commercial_parsed ?? safeParseJson<Record<string, string>>(result.commercial)
    const risks = result.legal_risks_parsed ?? safeParseJson<Array<{ clause: string; risk: string; fairness: string; favours: string; severity: string }>>(result.legal_risks)
    const mitigations = result.mitigations_parsed ?? safeParseJson<Array<{ clause: string; mitigation: string; negotiation_points?: string }>>(result.mitigations)
    const alert = result.alert_parsed ?? safeParseJson<{ exploitative: boolean; rationale?: string; top_unfair_clauses?: string[] }>(result.alert)
    return { commercial, risks, mitigations, alert }
  }, [result])

  const bulletLines = (text: string): string[] => {
    if (!text) return []
    const lines = text
      .split(/\r?\n/)
      .map(l => l.trim())
      .filter(Boolean)
    // If lines look like bullets already, keep them; otherwise, take first 8 sentences-like chunks
    if (lines.some(l => /^[-*•]/.test(l))) {
      return lines.map(l => l.replace(/^[-*•]\s*/, '')).slice(0, 8)
    }
    const chunks = text.split(/[\n\r]+|(?<=[.!?])\s+/).map(s => s.trim()).filter(Boolean)
    return chunks.slice(0, 8)
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
    try {
      const form = new FormData()
      form.append('file', file)
      if (USE_ASYNC) {
        // Start job
        const start = await fetch(`${API}/analyze/start`, { method: 'POST', body: form })
        const startData = await start.json()
        if (!start.ok || !startData.job_id) throw new Error('Failed to start analysis')
        const jobId = startData.job_id as string
        setJob({ id: jobId, status: 'pending', step: 0, total: 4 })
        // Poll status
        const poll = async () => {
          const st = await fetch(`${API}/analyze/status/${jobId}`)
          const sdata = await st.json()
          setJob({ id: jobId, status: sdata.status, step: sdata.step, total: sdata.total_steps, message: sdata.message })
          if (sdata.status === 'done' && sdata.result) {
            setResult(sdata.result)
            return
          }
          if (sdata.status === 'error') {
            throw new Error(sdata.message || 'Analysis failed')
          }
          setTimeout(poll, 900)
        }
        await poll()
      } else {
        const res = await fetch(`${API}/analyze`, { method: 'POST', body: form })
        const data = await res.json()
        setResult(data)
      }
    } catch (e:any) {
      alert('Upload failed. Make sure the backend is running at ' + API + ' and try again.\n' + (e?.message || e))
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
        })
      })
      const data = await res.json()
      setAnswer(data.answer || '')
    } catch (e:any) {
      alert('Chat failed: ' + (e?.message || e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="container">
      <h1 className="title">Contract Analyzer</h1>
      <p className="subtitle">Upload a PDF. We’ll explain it in simple terms and highlight important legal and commercial points.</p>

      <div className="row">
        <input className="input" type="file" accept="application/pdf" onChange={(e: ChangeEvent<HTMLInputElement>) => setFile(e.target.files?.[0] || null)} />
        <button className="btn" onClick={onUpload} disabled={!canAnalyze}>{loading ? 'Analyzing…' : 'Analyze'}</button>
      </div>

      {job && (
        <div className="card full" style={{marginBottom: 16}}>
          <div className="row space">
            <div>Step {job.step} / {job.total}</div>
            <div className="text small">{job.status.toUpperCase()} {job.message ? `– ${job.message}` : ''}</div>
          </div>
          <div className="progress">
            <div className="bar" style={{width: `${(Math.max(0, Math.min(job.step, job.total)) / job.total) * 100}%`}} />
          </div>
        </div>
      )}

      {result && (
        <div className="grid">
          <section className="card full">
            <h2>In simple terms</h2>
            <ul className="bullets">
              {bulletLines(result.plain).map((b, i) => (
                <li key={i}>{b}</li>
              ))}
            </ul>
          </section>
          <section className="card">
            <h3>Purpose</h3>
            <p className="text">{limitText(result.purpose)}</p>
          </section>
          <section className="card">
            <h3>Commercial</h3>
            {parsed.commercial ? (
              <dl className="kv">
                {Object.entries(parsed.commercial).map(([k, v]) => (
                  <div className="kv-row" key={k}>
                    <dt>{k.replace(/_/g, ' ')}</dt>
                    <dd>{String((v as unknown) ?? '—')}</dd>
                  </div>
                ))}
              </dl>
            ) : (
              <pre className="pre">{result.commercial}</pre>
            )}
          </section>
          <section className="card">
            <h3>Legal Risks</h3>
            {Array.isArray(parsed.risks) ? (
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
                    {parsed.risks.map((r, idx) => (
                      <tr key={idx}>
                        <td>{r.clause}</td>
                        <td>{r.risk}</td>
                        <td><span className={`badge ${r.fairness === 'unfair' ? 'bad' : 'good'}`}>{r.fairness}</span></td>
                        <td>{r.favours}</td>
                        <td><span className={`badge sev-${(r.severity||'').toLowerCase()}`}>{r.severity}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <pre className="pre">{result.legal_risks}</pre>
            )}
          </section>
          <section className="card">
            <h3>Mitigations</h3>
            {Array.isArray(parsed.mitigations) ? (
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
                    {parsed.mitigations.map((m, idx) => (
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
              <pre className="pre">{result.mitigations}</pre>
            )}
          </section>
          <section className="card">
            <h3>Exploitative?</h3>
            {parsed.alert ? (
              <div>
                <div className="row space">
                  <span className={`pill ${parsed.alert.exploitative ? 'pill-bad' : 'pill-good'}`}>
                    {parsed.alert.exploitative ? 'Exploitative' : 'Not exploitative'}
                  </span>
                </div>
                {parsed.alert.rationale && <p className="text small">{parsed.alert.rationale}</p>}
                {parsed.alert.top_unfair_clauses?.length ? (
                  <ul className="bullets compact">
                    {parsed.alert.top_unfair_clauses.slice(0, 5).map((c: string, i: number) => (
                      <li key={i}>{c}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ) : (
              <pre className="pre">{result.alert}</pre>
            )}
          </section>
          {result.report_url && (
            <section className="card full">
              <a className="link" href={`${API.replace(/\/$/, '')}${result.report_url}`} target="_blank" rel="noreferrer">Download JSON report</a>
            </section>
          )}
        </div>
      )}

      {result && (
        <div className="chat">
          <h2>Ask questions</h2>
          <div className="row">
            <input className="input" value={question} onChange={e => setQuestion(e.target.value)} placeholder="e.g., Who pays for delays?" />
            <button className="btn" onClick={onAsk} disabled={loading || !question.trim()}>Ask</button>
          </div>
          {answer && (
            <pre className="pre answer">{answer}</pre>
          )}
        </div>
      )}
    </div>
  )
}
