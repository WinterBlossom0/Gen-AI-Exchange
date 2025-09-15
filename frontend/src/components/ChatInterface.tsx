import React, { useState } from 'react'

interface ChatInterfaceProps {
  result: any
  apiUrl: string
  onAsk: (question: string) => Promise<string>
  isLoading: boolean
}

interface ChatMessage {
  id: string
  type: 'question' | 'answer'
  content: string
  timestamp: Date
}

export default function ChatInterface({ result, apiUrl, onAsk, isLoading }: ChatInterfaceProps) {
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!question.trim() || isLoading) return

    const questionId = Date.now().toString()
    const questionMessage: ChatMessage = {
      id: questionId,
      type: 'question',
      content: question.trim(),
      timestamp: new Date()
    }

    setMessages(prev => [...prev, questionMessage])
    const currentQuestion = question
    setQuestion('')

    try {
      const answer = await onAsk(currentQuestion)
      const answerMessage: ChatMessage = {
        id: questionId + '_answer',
        type: 'answer',
        content: answer,
        timestamp: new Date()
      }
      setMessages(prev => [...prev, answerMessage])
    } catch (error) {
      const errorMessage: ChatMessage = {
        id: questionId + '_error',
        type: 'answer',
        content: 'Sorry, I encountered an error processing your question.',
        timestamp: new Date()
      }
      setMessages(prev => [...prev, errorMessage])
    }
  }

  const clearChat = () => {
    setMessages([])
    setQuestion('')
  }

  if (!result) {
    return null
  }

  return (
    <section className="chatgpt-pane">
        <div className="chatgpt-header">
          <h3>Ask Questions About This Contract</h3>
          {messages.length > 0 && (
            <button className="btn btn-outline btn-sm" onClick={clearChat}>
              Clear Chat
            </button>
          )}
        </div>

        <div className="chatgpt-scroll">
          {messages.length === 0 && (
            <div className="chatgpt-empty">Start a conversation about this contract.</div>
          )}
          {messages.map(message => (
            <div key={message.id} className={`chatgpt-row ${message.type}`}>
              <div className={`bubble ${message.type === 'question' ? 'user' : 'ai'}`}>
                {message.type === 'question' ? (
                  <div className="bubble-text">{message.content}</div>
                ) : (
                  <div className="bubble-text answer-text">{message.content}</div>
                )}
              </div>
            </div>
          ))}
        </div>

        <form onSubmit={handleSubmit} className="chatgpt-inputbar">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask a question about this contract..."
            className="chatgpt-input"
            disabled={isLoading}
          />
          <button
            type="submit"
            className="btn btn-primary"
            disabled={!question.trim() || isLoading}
          >
            {isLoading ? 'Thinking…' : 'Ask'}
          </button>
        </form>
    </section>
  )
}