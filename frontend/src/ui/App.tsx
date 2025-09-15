import React, { useState, useEffect, useRef } from 'react'
import Header from '../components/Header'
import FileUpload from '../components/FileUpload'
import ProgressTracker from '../components/ProgressTracker'
import ResultsDisplay from '../components/ResultsDisplay'
import ChatInterface from '../components/ChatInterface'
import '../styles/app.css'

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

export default function App() {
  const [file, setFile] = useState<File | null>(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [job, setJob] = useState<JobState | null>(null)
  const [recipientEmail, setRecipientEmail] = useState<string>("")
  const abortRef = useRef(false)
  // Removed Load Existing Reports feature; no listing/persistence of past reports

  // Restore state on load
  useEffect(() => {
    try {
      const savedJob = localStorage.getItem('contract_analyzer_job')
      const savedResult = localStorage.getItem('contract_analyzer_result')
      if (savedJob) setJob(JSON.parse(savedJob))
      if (savedResult) setResult(JSON.parse(savedResult))
    } catch (error) {
      console.warn('Failed to restore state:', error)
    }
  }, [])

  // Persist state changes
  useEffect(() => {
    try {
      if (job) {
        localStorage.setItem('contract_analyzer_job', JSON.stringify(job))
      } else {
        localStorage.removeItem('contract_analyzer_job')
      }
    } catch (error) {
      console.warn('Failed to persist job state:', error)
    }
  }, [job])

  useEffect(() => {
    try {
      if (result) {
        localStorage.setItem('contract_analyzer_result', JSON.stringify(result))
      } else {
        localStorage.removeItem('contract_analyzer_result')
      }
    } catch (error) {
      console.warn('Failed to persist result state:', error)
    }
  }, [result])

  const clearAll = async () => {
    abortRef.current = true
    // Clear uploaded file if using new multi-call flow (job.id as file_id)
    if (job?.id) {
      try { await fetch(`${API}/upload/clear/${job.id}`, { method: 'POST' }) } catch {}
    }

    setFile(null)
    setJob(null)
    setResult(null)
    setLoading(false)

    try {
      localStorage.removeItem('contract_analyzer_job')
      localStorage.removeItem('contract_analyzer_result')
    } catch (error) {
      console.warn('Failed to clear localStorage:', error)
    }

    // Full page reload for complete reset
    window.location.reload()
  }

  const handleFileSelect = (selectedFile: File | null) => {
    setFile(selectedFile)
  }

  const startAnalysis = async () => {
    if (!file) return

    setLoading(true)
  abortRef.current = false
    setResult(null)

    try {
      // Upload first
      const upload = new FormData()
      upload.append('file', file)
      const up = await fetch(`${API}/upload`, { method: 'POST', body: upload })
      if (!up.ok) throw new Error('Upload failed')
      const upJson = await up.json()
      const fileId: string = upJson.file_id
      const contractText: string = upJson.contract_text
      setJob({ id: fileId, status: 'running', step: 0, total: 6 })

      const labels = ['purpose','commercial','legal_risks','mitigations','alert'] as const
      const outputs: Record<string, string> = {}
      for (let i = 0; i < labels.length; i++) {
        if (abortRef.current) throw new Error('Cancelled')
        const label = labels[i]
        const payload: any = { file_id: fileId, label }
        if (label === 'alert' && recipientEmail) payload.recipient = recipientEmail
        const res = await fetch(`${API}/analyze/section`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
        if (!res.ok) throw new Error(`Section ${label} failed`)
        const data = await res.json()
        outputs[label] = data.output || ''
        setJob({ id: fileId, status: 'running', step: i + 1, total: 6, label })
      }

      // finalize
      const fin = await fetch(`${API}/analyze/finalize`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
        file_id: fileId,
        purpose: outputs['purpose'] || '',
        commercial: outputs['commercial'] || '',
        legal_risks: outputs['legal_risks'] || '',
        mitigations: outputs['mitigations'] || '',
        alert: outputs['alert'] || '',
        plain: ''
      }) })
      if (!fin.ok) throw new Error('Finalize failed')
      const finJson = await fin.json()
      const rr = finJson?.raw_report_url as string | undefined
      if (!rr) throw new Error('No raw_report_url')
      const rawRes = await fetch(`${API}${rr}`, { cache: 'no-store' as RequestCache })
      if (!rawRes.ok) throw new Error('raw.json fetch failed')
      const raw = await rawRes.json()

      setResult({
        report_url: finJson?.report_url,
        raw_report_url: rr,
        raw_text_url: finJson?.raw_text_url,
        contract_text: contractText,
        purpose: raw?.purpose ?? outputs['purpose'] ?? '',
        plain: raw?.plain ?? '',
        commercial: raw?.commercial ?? outputs['commercial'] ?? '',
        legal_risks: raw?.legal_risks ?? outputs['legal_risks'] ?? '',
        mitigations: raw?.mitigations ?? outputs['mitigations'] ?? '',
        alert: raw?.alert ?? outputs['alert'] ?? '',
        meta: raw?.meta,
      })
      setJob({ id: fileId, status: 'done', step: 6, total: 6 })
      setLoading(false)
    } catch (error) {
      console.error('Analysis failed:', error)
      setLoading(false)
      alert('Failed to analyze. Please check your connection and try again.')
    }
  }

  const handleCancelJob = async () => {
    abortRef.current = true
    setLoading(false)
    setJob(null)
  }

  const handleChatQuestion = async (question: string): Promise<string> => {
    if (!result) throw new Error('No analysis result available')

    const response = await fetch(`${API}/chat`, {
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

    if (!response.ok) {
      throw new Error('Failed to get answer')
    }

    const data = await response.json()
    return data.answer || 'No answer available'
  }

  return (
    <div className="app">
      <Header onClear={clearAll} />
      
      <main className="main-content">
        {!result && (
          <FileUpload
            file={file}
            onFileSelect={handleFileSelect}
            onAnalyze={startAnalysis}
            isLoading={loading}
            recipientEmail={recipientEmail}
            onRecipientChange={setRecipientEmail}
          />
        )}

        {/* Removed Load Existing Reports UI */}

        {job && job.status !== 'done' && (
          <ProgressTracker
            job={job}
            onCancel={handleCancelJob}
          />
        )}

        {result && (
          <>
            <ResultsDisplay
              result={result}
              apiUrl={API}
            />
            
            <ChatInterface
              result={result}
              apiUrl={API}
              onAsk={handleChatQuestion}
              isLoading={loading}
            />
          </>
        )}
      </main>
    </div>
  )
}