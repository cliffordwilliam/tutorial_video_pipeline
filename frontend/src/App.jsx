import { useState } from 'react'
import './App.css'
import SlideList from './SlideList'
import SlideEditor from './SlideEditor'

function titleFromPath(path) {
  const base = path.split('/').pop() || ''
  const dot = base.lastIndexOf('.')
  return dot > 0 ? base.slice(0, dot) : base
}

function newCodeSlide() {
  return {
    _key: crypto.randomUUID(),
    type: 'code',
    voice: '',
    language: 'python',
    active_file: '',
    file_tree: [],
    code: '',
  }
}

function newImageSlide() {
  return {
    _key: crypto.randomUUID(),
    type: 'image',
    voice: '',
    src: '',
    rect: null,
  }
}

function App() {
  const [path, setPath] = useState('')
  const [slides, setSlides] = useState([])
  const [selectedIndex, setSelectedIndex] = useState(null)
  const [status, setStatus] = useState('')
  const [rendering, setRendering] = useState(false)

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
      const slidesWithKeys = data.slides.map((s) => ({ ...s, _key: crypto.randomUUID() }))
      setSlides(slidesWithKeys)
      setSelectedIndex(slidesWithKeys.length ? 0 : null)
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
        body: JSON.stringify({
          path,
          slides: slides.map(({ _key, ...rest }) => rest),
        }),
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

  async function handleRender() {
    setRendering(true)
    setStatus('Rendering...')
    try {
      const res = await fetch('/api/render', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path }),
      })
      const data = await res.json()
      if (!res.ok) {
        setStatus(data.detail || 'Failed to render')
        return
      }
      setStatus(`Rendered -> ${data.output_path}`)
    } catch (err) {
      setStatus(`Failed to render: ${err.message}`)
    } finally {
      setRendering(false)
    }
  }

  function addSlide(slide) {
    setSlides((prev) => {
      setSelectedIndex(prev.length)
      return [...prev, slide]
    })
  }

  function deleteSlide(i) {
    setSlides((prev) => prev.filter((_, idx) => idx !== i))
    setSelectedIndex((prev) => {
      if (prev === null || i === prev) return null
      return i < prev ? prev - 1 : prev
    })
  }

  function updateSelectedSlide(updated) {
    setSlides((prev) => prev.map((s, idx) => (idx === selectedIndex ? updated : s)))
  }

  function moveSlide(from, to) {
    if (from === to) return
    setSlides((prev) => {
      const next = [...prev]
      const [moved] = next.splice(from, 1)
      next.splice(to, 0, moved)
      return next
    })
    setSelectedIndex((prev) => {
      if (prev === null) return prev
      if (prev === from) return to
      if (from < to && prev > from && prev <= to) return prev - 1
      if (from > to && prev >= to && prev < from) return prev + 1
      return prev
    })
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
        <button type="button" onClick={handleRender} disabled={!path || rendering}>
          {rendering ? 'Rendering…' : 'Render'}
        </button>
      </div>

      <div className="title-bar">{title ? `Title: ${title}` : 'No file open'}</div>

      <div className="main">
        <SlideList
          slides={slides}
          selectedIndex={selectedIndex}
          onSelect={setSelectedIndex}
          onAddCode={() => addSlide(newCodeSlide())}
          onAddImage={() => addSlide(newImageSlide())}
          onDelete={deleteSlide}
          onReorder={moveSlide}
        />
        <SlideEditor
          slide={selectedIndex !== null ? slides[selectedIndex] : null}
          onChange={updateSelectedSlide}
        />
      </div>

      <div className="status-bar">{status}</div>
    </div>
  )
}

export default App
