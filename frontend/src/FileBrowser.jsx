import { useEffect, useState } from 'react'

function dirname(path) {
  const idx = path.lastIndexOf('/')
  return idx > 0 ? path.slice(0, idx) : '/'
}

function FileBrowser({ startPath, extensions, onSelect, onClose }) {
  const [currentPath, setCurrentPath] = useState(startPath || '')
  const [entries, setEntries] = useState([])
  const [filename, setFilename] = useState('')
  const [error, setError] = useState(null)

  useEffect(() => {
    let ignore = false
    setError(null)
    const params = new URLSearchParams()
    if (currentPath) params.set('path', currentPath)
    if (extensions) params.set('extensions', extensions)

    fetch(`/api/browse?${params}`)
      .then(async (res) => {
        const data = await res.json()
        if (!res.ok) throw new Error(data.detail || 'Failed to browse')
        if (!ignore) {
          setCurrentPath(data.path)
          setEntries(data.entries)
        }
      })
      .catch((err) => {
        if (!ignore) setError(err.message)
      })

    return () => {
      ignore = true
    }
  }, [currentPath, extensions])

  function openDir(name) {
    setCurrentPath(`${currentPath}/${name}`)
  }

  function goUp() {
    setCurrentPath(dirname(currentPath))
  }

  function confirm() {
    if (!filename) return
    onSelect(filename.startsWith('/') ? filename : `${currentPath}/${filename}`)
  }

  return (
    <div className="modal-overlay">
      <div className="file-browser">
        <div className="file-browser-header">
          <button type="button" onClick={goUp}>
            ↑ Up
          </button>
          <span className="file-browser-path">{currentPath}</span>
          <button type="button" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        {error && <div className="file-browser-error">{error}</div>}

        <ul className="file-browser-list">
          {entries.map((entry) => (
            <li key={entry.name}>
              <button
                type="button"
                onClick={() => (entry.type === 'dir' ? openDir(entry.name) : setFilename(entry.name))}
              >
                {entry.type === 'dir' ? '📁' : '📄'} {entry.name}
              </button>
            </li>
          ))}
        </ul>

        <div className="file-browser-footer">
          <input
            type="text"
            value={filename}
            onChange={(e) => setFilename(e.target.value)}
            placeholder="filename"
          />
          <button type="button" onClick={confirm} disabled={!filename}>
            Select
          </button>
        </div>
      </div>
    </div>
  )
}

export default FileBrowser
