import React from 'react'

interface HeaderProps {
  onClear: () => void
}

export default function Header({ onClear }: HeaderProps) {
  return (
    <header className="header">
      <div className="header-content">
        <div className="header-left">
          <h1 className="header-title">Contract Analyzer</h1>
          <p className="header-subtitle">AI-powered contract analysis and risk assessment</p>
        </div>
        <div className="header-right">
          <button className="btn btn-outline" onClick={onClear}>
            Clear All
          </button>
        </div>
      </div>
    </header>
  )
}