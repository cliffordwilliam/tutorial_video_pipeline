import { useState } from 'react'
import FileTreeEditor from './FileTreeEditor'

const RECT_FIELDS = ['x', 'y', 'w', 'h']

function SlideEditor({ slide, onChange }) {
  const [clipboard, setClipboard] = useState(null)

  if (!slide) {
    return <div className="slide-editor empty">Select or add a slide to edit it.</div>
  }

  function set(field, value) {
    onChange({ ...slide, [field]: value })
  }

  function setRectField(field, value) {
    set('rect', { ...slide.rect, [field]: Number(value) || 0 })
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
            key={slide._key}
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
            <input type="text" value={slide.src} onChange={(e) => set('src', e.target.value)} />
          </label>

          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={slide.rect !== null}
              onChange={(e) => set('rect', e.target.checked ? { x: 0, y: 0, w: 0, h: 0 } : null)}
            />
            Annotation rect
          </label>

          {slide.rect !== null && (
            <div className="rect-editor">
              {RECT_FIELDS.map((field) => (
                <label key={field}>
                  {field}
                  <input
                    type="number"
                    value={slide.rect[field]}
                    onChange={(e) => setRectField(field, e.target.value)}
                  />
                </label>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}

export default SlideEditor
