import React from 'react'

interface FileUploadProps {
  file: File | null
  onFileSelect: (file: File | null) => void
  onAnalyze: () => void
  isLoading: boolean
  recipientEmail: string
  onRecipientChange: (email: string) => void
}

export default function FileUpload({ file, onFileSelect, onAnalyze, isLoading, recipientEmail, onRecipientChange }: FileUploadProps) {
  return (
    <section className="file-upload-section">
      <div className="upload-icon" aria-hidden>📄</div>
      <h2 className="upload-title">Upload Contract</h2>
      <p className="upload-description">Select a PDF contract to analyze</p>

      <div className="upload-controls">
        <input
          type="file"
          accept="application/pdf"
          onChange={(e) => onFileSelect(e.target.files?.[0] || null)}
          className="file-input"
          id="file-upload"
        />
        <label htmlFor="file-upload" className="btn btn-outline">
          Choose PDF File
        </label>
      </div>

      <div className="input-group" style={{ marginTop: 12 }}>
        <label htmlFor="recipient-email" className="input-label">Recipient email (optional)</label>
        <input
          id="recipient-email"
          type="email"
          placeholder="alerts@yourdomain.com"
          value={recipientEmail}
          onChange={(e) => onRecipientChange(e.target.value)}
          className="text-input"
        />
      </div>

      {file && (
        <div className="selected-file">
          <span className="file-name" title={file.name}>{file.name}</span>
          <button
            className="btn btn-primary"
            onClick={onAnalyze}
            disabled={isLoading}
          >
            {isLoading ? 'Analyzing…' : 'Analyze Contract'}
          </button>
        </div>
      )}
    </section>
  )
}