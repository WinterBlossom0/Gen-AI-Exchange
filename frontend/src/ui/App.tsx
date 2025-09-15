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
  const abortPollRef = useRef(false)
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
    abortPollRef.current = true
    
    if (job?.id) {
      try {
        await fetch(`${API}/analyze/clear/${job.id}`, { method: 'POST' })
      } catch (error) {
        console.warn('Failed to clear job:', error)
      }
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
    abortPollRef.current = false
    setResult(null)

    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch(`${API}/analyze/start`, {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        throw new Error('Failed to start analysis')
      }

      const { job_id } = await response.json()
      setJob({
        id: job_id,
        status: 'pending',
        step: 0,
        total: 6
      })

      // Start polling for status
      pollJobStatus(job_id)
    } catch (error) {
      console.error('Analysis failed:', error)
      setLoading(false)
      alert('Failed to start analysis. Please check your connection and try again.')
    }
  }

  const pollJobStatus = async (jobId: string) => {
    try {
      while (!abortPollRef.current) {
        const response = await fetch(`${API}/analyze/status/${jobId}`)
        
        if (!response.ok) {
          throw new Error('Failed to get job status')
        }

        const statusData = await response.json()

        if (abortPollRef.current) break

        setJob({
          id: jobId,
          status: statusData.status,
          step: statusData.step || 0,
          total: statusData.total_steps || 6,
          message: statusData.message,
          agent: statusData.current_agent,
          label: statusData.current_label,
          partials: statusData.partials
        })

        if (statusData.status === 'done' && statusData.result) {
          // Strictly load raw.json and display only that
          const rr = statusData?.result?.raw_report_url as string | undefined
          if (rr) {
            try {
              let fr = await fetch(`${API}${rr}`, { cache: 'no-store' as RequestCache })
              if (!fr.ok && fr.status === 304) {
                fr = await fetch(`${API}${rr}`, { cache: 'reload' as RequestCache })
              }
              if (fr.ok) {
                const raw = await fr.json()
                setResult({
                  report_url: statusData?.result?.report_url,
                  raw_report_url: rr,
                  raw_text_url: statusData?.result?.raw_text_url,
                  // Prefer the full contract text if available from partials for Chat/optional view
                  contract_text: statusData?.partials?.contract_text || '(Contract text unavailable in this session)',
                  // Values strictly from raw.json
                  purpose: raw?.purpose ?? '',
                  plain: raw?.plain ?? '',
                  commercial: raw?.commercial ?? '',
                  legal_risks: raw?.legal_risks ?? '',
                  mitigations: raw?.mitigations ?? '',
                  alert: raw?.alert ?? '',
                  meta: raw?.meta,
                })
                setLoading(false)
                break
              } else {
                throw new Error('raw.json not yet available')
              }
            } catch (e) {
              alert(`Could not fetch raw.json: ${e}`)
            }
          } else {
            alert('raw_report_url missing; cannot display results')
          }
          setLoading(false)
          break
        }

        if (statusData.status === 'error') {
          setLoading(false)
          alert(`Analysis failed: ${statusData.message || 'Unknown error'}`)
          break
        }

        if (statusData.status === 'cancelled') {
          setLoading(false)
          break
        }

        // Wait before next poll
        await new Promise(resolve => setTimeout(resolve, 1500))
      }
    } catch (error) {
      console.error('Polling failed:', error)
      setLoading(false)
      alert('Lost connection to analysis. Please try again.')
    }
  }

  const handleCancelJob = async () => {
    if (!job?.id) return

    abortPollRef.current = true
    
    try {
      await fetch(`${API}/analyze/cancel/${job.id}`, { method: 'POST' })
    } catch (error) {
      console.warn('Failed to cancel job:', error)
    }

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