import { useState } from 'react'
import FileBrowser from './FileBrowser'
import FileTreeEditor from './FileTreeEditor'
import ImageRectEditor from './ImageRectEditor'

function relativePath(base, target) {
  const baseParts = base.split('/').filter(Boolean)
  const targetParts = target.split('/').filter(Boolean)
  let i = 0
  while (i < baseParts.length && i < targetParts.length && baseParts[i] === targetParts[i]) i++
  return [...Array(baseParts.length - i).fill('..'), ...targetParts.slice(i)].join('/')
}

function SlideEditor({ slide, onChange, scriptPath }) {
  const [clipboard, setClipboard] = useState(null)
  const [showImageBrowser, setShowImageBrowser] = useState(false)

  if (!slide) {
    return <div className="slide-editor empty">Select or add a slide to edit it.</div>
  }

  function set(field, value) {
    onChange({ ...slide, [field]: value })
  }

  const filePaths = slide.type === 'code' ? slide.file_tree.filter((p) => !p.endsWith('/')) : []

  return (
    <div className="slide-editor">
      <label>
        Voice line
        <input type="text" value={slide.voice} onChange={(e) => set('voice', e.target.value)} />
      </label>

      {slide.type === 'code' ? (
        <>
          <label>
            Language
            <select value={slide.language} onChange={(e) => set('language', e.target.value)}>
              <option value="python">Python</option>
            </select>
          </label>
          <label>
            Active file
            <select value={slide.active_file} onChange={(e) => set('active_file', e.target.value)}>
              <option value="">— none —</option>
              {filePaths.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
              {slide.active_file && !filePaths.includes(slide.active_file) && (
                <option value={slide.active_file}>{slide.active_file} (not in tree)</option>
              )}
            </select>
          </label>

          <FileTreeEditor
            key={`tree-${slide._key}`}
            fileTree={slide.file_tree}
            onChange={(file_tree) => set('file_tree', file_tree)}
            clipboard={clipboard}
            onCopy={setClipboard}
          />

          <label>
            Code
            <textarea
              className="code-textarea"
              value={slide.code}
              onChange={(e) => set('code', e.target.value)}
              spellCheck={false}
            />
          </label>
        </>
      ) : (
        <>
          <label>
            Image src
            <div className="image-src-row">
              <span className="image-src-value">{slide.src || 'No image selected'}</span>
              <button type="button" onClick={() => setShowImageBrowser(true)} disabled={!scriptPath}>
                Browse…
              </button>
            </div>
          </label>

          {showImageBrowser && (
            <FileBrowser
              startPath={scriptPath.slice(0, scriptPath.lastIndexOf('/'))}
              extensions="png,jpg,jpeg,gif,webp,bmp"
              onSelect={(p) => {
                set('src', relativePath(scriptPath.slice(0, scriptPath.lastIndexOf('/')), p))
                setShowImageBrowser(false)
              }}
              onClose={() => setShowImageBrowser(false)}
            />
          )}

          {slide.src && (
            <ImageRectEditor
              key={`rect-${slide._key}`}
              scriptPath={scriptPath}
              src={slide.src}
              rect={slide.rect}
              onChange={(rect) => set('rect', rect)}
            />
          )}
        </>
      )}
    </div>
  )
}

export default SlideEditor
