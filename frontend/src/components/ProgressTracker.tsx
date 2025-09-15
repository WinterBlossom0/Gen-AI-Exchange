import React from 'react'

interface JobState {
  id: string
  status: string
  step: number
  total: number
  message?: string
  agent?: string
  label?: string
}

interface ProgressTrackerProps {
  job: JobState
  onCancel: () => void
}

const steps = [
  { key: 'purpose', label: 'Analyzing Purpose', icon: '🎯' },
  { key: 'commercial', label: 'Extracting Commercial Terms', icon: '💰' },
  { key: 'legal_risks', label: 'Assessing Legal Risks', icon: '⚠️' },
  { key: 'mitigations', label: 'Identifying Mitigations', icon: '🛡️' },
  { key: 'alert', label: 'Final Assessment', icon: '🔍' },
  { key: 'save', label: 'Generating Report', icon: '📋' }
]

export default function ProgressTracker({ job, onCancel }: ProgressTrackerProps) {
  const progress = job.total > 0 ? (job.step / job.total) * 100 : 0

  return (
    <div className="progress-tracker">
      <div className="progress-header">
        <h3>Analysis in Progress</h3>
        <button className="btn btn-outline btn-sm" onClick={onCancel}>
          Cancel
        </button>
      </div>
      
      <div className="progress-bar-container">
        <div className="progress-bar">
          <div 
            className="progress-fill" 
            style={{ width: `${progress}%` }}
          />
        </div>
        <span className="progress-text">{Math.round(progress)}%</span>
      </div>
      
      <div className="steps-container">
        {steps.map((step, index) => (
          <div 
            key={step.key}
            className={`step ${index < job.step ? 'completed' : index === job.step - 1 ? 'active' : 'pending'}`}
          >
            <div className="step-icon">{step.icon}</div>
            <div className="step-label">{step.label}</div>
          </div>
        ))}
      </div>
      
      {job.agent && (
        <div className="current-agent">
          Currently running: <strong>{job.agent}</strong>
        </div>
      )}
      
      {job.status === 'error' && job.message && (
        <div className="error-message">
          Error: {job.message}
        </div>
      )}
    </div>
  )
}