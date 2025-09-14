import React, { ChangeEvent, useMemo, useState } from 'react'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function App() {
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')

  const canAnalyze = useMemo(() => !!file && !loading, [file, loading])

  const onUpload = async () => {
    if (!file) return
    setLoading(true)
    setAnswer('')
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch(`${API}/analyze`, { method: 'POST', body: form })
      const data = await res.json()
      setResult(data)
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

      {result && (
        <div className="grid">
          <section className="card full">
            <h2>In simple terms</h2>
            <pre className="pre">{result.plain}</pre>
          </section>
          <section className="card">
            <h3>Purpose</h3>
            <pre className="pre">{result.purpose}</pre>
          </section>
          <section className="card">
            <h3>Commercial</h3>
            <pre className="pre">{result.commercial}</pre>
          </section>
          <section className="card">
            <h3>Legal Risks</h3>
            <pre className="pre">{result.legal_risks}</pre>
          </section>
          <section className="card">
            <h3>Mitigations</h3>
            <pre className="pre">{result.mitigations}</pre>
          </section>
          <section className="card">
            <h3>Exploitative?</h3>
            <pre className="pre">{result.alert}</pre>
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
