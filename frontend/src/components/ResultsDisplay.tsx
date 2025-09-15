import React, { useState } from 'react'

interface AnalysisResult {
  purpose: string
  commercial?: string
  legal_risks?: string
  mitigations?: string
  alert?: string
  contract_text?: string
  plain?: string
  report_url?: string
  raw_report_url?: string
  raw_text_url?: string
  meta?: any
}

interface ResultsDisplayProps {
  result: AnalysisResult
  apiUrl: string
}

export default function ResultsDisplay({ result, apiUrl }: ResultsDisplayProps) {
  const [activeTab, setActiveTab] = useState('summary')
  const [showContract, setShowContract] = useState(false)
  const [showRawOutput, setShowRawOutput] = useState(false)

  // Helpers to extract JSON even if wrapped in triple quotes or code fences
  const unwrapCodeOrQuotes = (txt?: string): string => {
    if (!txt || typeof txt !== 'string') return ''
    const raw = txt.trim()
    // First preference: locate ```json anywhere in the original text
    const jsonStart = raw.search(/```json\s*/i)
    if (jsonStart !== -1) {
      const tail = raw.slice(jsonStart).replace(/```json/i, '')
      // If a closing fence exists, cut at it; else use entire tail
      const closeIdx = tail.indexOf('```')
      const body = closeIdx !== -1 ? tail.slice(0, closeIdx) : tail
      return body.trim()
    }
    // Otherwise, drop to first generic code fence if any and try to use its content
    const firstFenceIdx = raw.indexOf('```')
    if (firstFenceIdx === -1) {
      return ''
    }
    let s = raw.slice(firstFenceIdx)
    const anyFence = s.match(/```\s*([\s\S]*?)```/)
    if (anyFence && anyFence[1]) {
      return anyFence[1].trim()
    }
    // Or a generic opening fence without closing: take everything after it
    const anyStart = s.indexOf('```')
    if (anyStart !== -1) {
      return s.slice(anyStart + 3).trim()
    }
    return ''
  }

  // Strictly collect all ```json fenced blocks in order
  const getAllJsonFences = (txt?: string): string[] => {
    if (!txt || typeof txt !== 'string') return []
    const raw = txt.trim()
    const regex = /```json\s*([\s\S]*?)```/gi
    const blocks: string[] = []
    let m: RegExpExecArray | null
    while ((m = regex.exec(raw)) !== null) {
      const body = m[1]?.trim()
      if (body) blocks.push(body)
    }
    return blocks
  }

  const extractFirstBalanced = (s: string, openCh: string, closeCh: string): string | null => {
    let started = false
    let startIdx = -1
    let depth = 0
    let inStr = false
    let escape = false
    for (let i = 0; i < s.length; i++) {
      const ch = s[i]
      if (inStr) {
        if (escape) {
          escape = false
        } else if (ch === '\\') {
          escape = true
        } else if (ch === '"') {
          inStr = false
        }
        continue
      }
      if (ch === '"') {
        inStr = true
        continue
      }
      if (!started) {
        if (ch === openCh) {
          started = true
          startIdx = i
          depth = 1
        }
        continue
      }
      if (ch === openCh) depth++
      else if (ch === closeCh) depth--
      if (started && depth === 0) {
        return s.slice(startIdx, i + 1)
      }
    }
    return null
  }

  const sliceToFirstJSON = (s: string): string => {
    // Prefer first balanced array; if not found, first balanced object.
    const arr = extractFirstBalanced(s, '[', ']')
    if (arr) return arr
    const obj = extractFirstBalanced(s, '{', '}')
    if (obj) return obj
    return s
  }

  // Recovery: collect balanced JSON objects from a string (used when arrays are malformed)
  const extractAllBalancedObjects = (s: string): any[] => {
    const out: any[] = []
    let inStr = false
    let escape = false
    let depth = 0
    let start = -1
    for (let i = 0; i < s.length; i++) {
      const ch = s[i]
      if (inStr) {
        if (escape) {
          escape = false
        } else if (ch === '\\') {
          escape = true
        } else if (ch === '"') {
          inStr = false
        }
        continue
      }
      if (ch === '"') { inStr = true; continue }
      if (ch === '{') {
        if (depth === 0) start = i
        depth++
      } else if (ch === '}') {
        if (depth > 0) depth--
        if (depth === 0 && start !== -1) {
          const seg = s.slice(start, i + 1)
          try {
            const obj = JSON.parse(seg)
            if (obj && typeof obj === 'object' && !Array.isArray(obj)) out.push(obj)
          } catch { /* ignore bad segment */ }
          start = -1
        }
      }
    }
    return out
  }

  const extractArray = (txt?: string): any[] | null => {
    const fences = getAllJsonFences(txt)
    if (!fences.length) return null
    // Try direct array per fence
    for (const f of fences) {
      try {
        const parsed = JSON.parse(f)
        if (Array.isArray(parsed)) return parsed
      } catch {}
    }
    // Try sliced-first-JSON per fence
    for (const f of fences) {
      try {
        const sliced = sliceToFirstJSON(f)
        const parsed = JSON.parse(sliced)
        if (Array.isArray(parsed)) return parsed
      } catch {}
    }
    // Recovery: collect balanced objects across all fences
    const recovered: any[] = []
    for (const f of fences) {
      const objs = extractAllBalancedObjects(f)
      if (objs.length) recovered.push(...objs)
    }
    return recovered.length ? recovered : null
  }

  const extractObject = (txt?: string): Record<string, any> | null => {
    const fences = getAllJsonFences(txt)
    if (!fences.length) return null
    for (const f of fences) {
      try {
        const parsed = JSON.parse(f)
        if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) return parsed
      } catch {}
    }
    for (const f of fences) {
      try {
        const sliced = sliceToFirstJSON(f)
        const parsed = JSON.parse(sliced)
        if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) return parsed
      } catch {}
    }
    return null
  }

  // Raw strings from raw.json
  const risksRaw = result?.legal_risks || ''
  const mitigationsRaw = result?.mitigations || ''
  const commercialRaw = (result as any)?.commercial || ''
  const alertRaw = result?.alert || ''
  const purposeRaw = result?.purpose || ''
  const plainRaw = result?.plain || ''

  // Attempt to parse JSON arrays/objects in these raw strings for nicer rendering
  const commercialArr = extractArray(commercialRaw)
  const risksArr = extractArray(risksRaw)
  const mitigationsArr = extractArray(mitigationsRaw)
  const alertObj = extractObject(alertRaw)
  const purposeObj = extractObject(purposeRaw)
  const tabs = [
    { id: 'summary', label: 'Summary', icon: '📋' },
  { id: 'commercial', label: 'Commercial Terms', icon: '💰' },
  { id: 'risks', label: 'Legal Risks', icon: '⚠️' },
  { id: 'mitigations', label: 'Mitigations', icon: '🛡️' },
  { id: 'assessment', label: 'Assessment', icon: '🔍' }
  ]

  return (
    <div className="results-display">
      <div className="results-header">
        <h2>Analysis Results</h2>
        <div className="results-actions">
          <button 
            className="btn btn-outline btn-sm"
            onClick={() => setShowContract(!showContract)}
          >
            {showContract ? 'Hide' : 'Show'} Contract Text
          </button>
          <button
            className="btn btn-outline btn-sm"
            onClick={() => setShowRawOutput(!showRawOutput)}
          >
            {showRawOutput ? 'Hide Raw' : 'Show Raw'}
          </button>
          {result.report_url && (
            <a 
              href={`${apiUrl.replace(/\/$/, '')}${result.report_url}`}
              target="_blank" 
              rel="noreferrer"
              className="btn btn-outline btn-sm"
            >
              Download Report
            </a>
          )}
          {result.raw_report_url && (
            <a 
              href={`${apiUrl.replace(/\/$/, '')}${result.raw_report_url}`}
              target="_blank" 
              rel="noreferrer"
              className="btn btn-outline btn-sm"
              style={{ marginLeft: 8 }}
            >
              raw.json
            </a>
          )}
          {result.raw_text_url && (
            <a 
              href={`${apiUrl.replace(/\/$/, '')}${result.raw_text_url}`}
              target="_blank" 
              rel="noreferrer"
              className="btn btn-outline btn-sm"
              style={{ marginLeft: 8 }}
            >
              raw.txt
            </a>
          )}
        </div>
      </div>

      {showContract && result.contract_text && (
        <div className="contract-text-section">
          <h3>Original Contract Text</h3>
          <div className="contract-text">
            {result.contract_text}
          </div>
        </div>
      )}

      <div className="tabs-container">
        {showRawOutput && (
          <div className="content-card" style={{margin: '16px'}}>
            <h4>Raw Outputs (debug)</h4>
            <details open>
              <summary>Legal Risks</summary>
              <pre className="plain-text">{risksRaw}</pre>
            </details>
            <details>
              <summary>Mitigations</summary>
              <pre className="plain-text">{mitigationsRaw}</pre>
            </details>
            <details>
              <summary>Alert</summary>
              <pre className="plain-text">{alertRaw}</pre>
            </details>
          </div>
        )}
        <div className="tabs-nav">
          {tabs.map(tab => (
            <button
              key={tab.id}
              className={`tab ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              <span className="tab-icon">{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </div>

        <div className="tab-content">
          {activeTab === 'summary' && (
            <div className="tab-panel">
              <div className="summary-section">
                <h3>Contract Purpose</h3>
                {purposeObj ? (
                  <div className="content-card">
                    {typeof purposeObj.summary === 'string' && purposeObj.summary.trim() ? (
                      <div className="plain-text" style={{ whiteSpace: 'pre-wrap' }}>
                        {purposeObj.summary}
                      </div>
                    ) : (
                      <pre className="plain-text" style={{ margin: 0 }}>{JSON.stringify(purposeObj, null, 2)}</pre>
                    )}
                  </div>
                ) : (
                  <>
                    <div className="content-card">
                      <div className="muted">Expected JSON object not found inside ```json fenced block.</div>
                    </div>
                    <div className="content-card">
                      <pre className="plain-text" style={{ margin: 0 }}>{purposeRaw}</pre>
                    </div>
                  </>
                )}
              </div>
              
              {plainRaw && (
                <div className="summary-section">
                  <h3>Key Points</h3>
                  <div className="content-card">
                    <pre className="plain-text">{plainRaw}</pre>
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'commercial' && (
            <div className="tab-panel">
              <h3>Commercial Terms</h3>
              <div className="content-card">
                {commercialArr ? (
                  <ul className="list">
                    {commercialArr.map((item, idx) => (
                      <li key={idx}>
                        {typeof item === 'string' ? (
                          item
                        ) : (
                          <div>
                            {item.clause && (<div><strong>Clause:</strong> {String(item.clause)}</div>)}
                            {item.summary && (<div><strong>Summary:</strong> {String(item.summary)}</div>)}
                            {item.terms && (<div><strong>Terms:</strong> {String(item.terms)}</div>)}
                            {!item.clause && !item.summary && !item.terms && (
                              <pre className="plain-text" style={{ margin: 0 }}>{JSON.stringify(item, null, 2)}</pre>
                            )}
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="muted">Expected JSON array not found inside ```json fenced block.</div>
                )}
              </div>
            </div>
          )}

          {activeTab === 'risks' && (
            <div className="tab-panel">
              <h3>Legal Risks</h3>
              <div className="content-card">
                {risksArr ? (
                  <ul className="list">
                    {risksArr.map((r, idx) => (
                      <li key={idx}>
                        {typeof r === 'string' ? (
                          r
                        ) : (
                          <div>
                            <div>
                              <strong>{r.clause || r.title || `Risk ${idx + 1}`}</strong>
                              {r.severity && (
                                <span style={{ marginLeft: 8 }}>
                                  [<em>{String(r.severity).toUpperCase()}</em>]
                                </span>
                              )}
                            </div>
                            {r.description && (<div>{r.description}</div>)}
                            {r.fairness && (<div>Fairness: {String(r.fairness)}</div>)}
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="muted">Expected JSON array not found inside ```json fenced block.</div>
                )}
              </div>
            </div>
          )}

          {activeTab === 'mitigations' && (
            <div className="tab-panel">
              <h3>Risk Mitigations</h3>
              <div className="content-card">
                {mitigationsArr ? (
                  <ul className="list">
                    {mitigationsArr.map((m, idx) => (
                      <li key={idx}>
                        {typeof m === 'string' ? (
                          m
                        ) : (
                          <div>
                            <strong>{m.clause || m.title || `Mitigation ${idx + 1}`}</strong>
                            {m.strategy && (<div>Strategy: {m.strategy}</div>)}
                            {Array.isArray(m.negotiation_points) && m.negotiation_points.length > 0 && (
                              <div>
                                <div>Negotiation points:</div>
                                <ul>
                                  {m.negotiation_points.map((p: any, i: number) => (
                                    <li key={i}>{String(p)}</li>
                                  ))}
                                </ul>
                              </div>
                            )}
                            {m.actions && Array.isArray(m.actions) && m.actions.length > 0 && (
                              <div>
                                <div>Actions:</div>
                                <ul>
                                  {m.actions.map((a: any, i: number) => (
                                    <li key={i}>{String(a)}</li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="muted">Expected JSON array not found inside ```json fenced block.</div>
                )}
              </div>
            </div>
          )}

          {activeTab === 'assessment' && (
            <div className="tab-panel">
              <h3>Contract Assessment</h3>
              <div className="content-card">
                {alertObj ? (
                  <div className="grid">
                    {typeof alertObj.exploitative !== 'undefined' && (
                      <div><strong>Exploitative:</strong> {String(alertObj.exploitative)}</div>
                    )}
                    {alertObj.rationale && (
                      <div><strong>Rationale:</strong> {String(alertObj.rationale)}</div>
                    )}
                    {Array.isArray(alertObj.top_unfair_clauses) && alertObj.top_unfair_clauses.length > 0 && (
                      <div>
                        <strong>Top unfair clauses:</strong>
                        <ul>
                          {alertObj.top_unfair_clauses.map((c: any, i: number) => (
                            <li key={i}>{String(c)}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="muted">Expected JSON object not found inside ```json fenced block.</div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}