import { useState } from 'react'
import './App.css'

function titleFromPath(path) {
  const base = path.split('/').pop() || ''
  const dot = base.lastIndexOf('.')
  return dot > 0 ? base.slice(0, dot) : base
}

function App() {
  const [path, setPath] = useState('')
  const [content, setContent] = useState('')
  const [status, setStatus] = useState('')

  const title = titleFromPath(path)

  async function handleOpen() {
    setStatus('Opening...')
    try {
      const res = await fetch(`/api/file?path=${encodeURIComponent(path)}`)
      const data = await res.json()
      if (!res.ok) {
        setStatus(data.detail || 'Failed to open')
        return
      }
      setContent(data.content)
      setStatus('Opened')
    } catch (err) {
      setStatus(`Failed to open: ${err.message}`)
    }
  }

  async function handleSave() {
    setStatus('Saving...')
    try {
      const res = await fetch('/api/file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, content }),
      })
      const data = await res.json()
      if (!res.ok) {
        setStatus(data.detail || 'Failed to save')
        return
      }
      setStatus('Saved')
    } catch (err) {
      setStatus(`Failed to save: ${err.message}`)
    }
  }

  return (
    <div className="app">
      <div className="toolbar">
        <input
          className="path-input"
          type="text"
          placeholder="/path/to/project.yaml"
          value={path}
          onChange={(e) => setPath(e.target.value)}
        />
        <button type="button" onClick={handleOpen} disabled={!path}>
          Open
        </button>
        <button type="button" onClick={handleSave} disabled={!path}>
          Save
        </button>
      </div>

      <div className="title-bar">{title ? `Title: ${title}` : 'No file open'}</div>

      <textarea
        className="editor"
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder="Content goes here..."
        spellCheck={false}
      />

      <div className="status-bar">{status}</div>
    </div>
  )
}

export default App
