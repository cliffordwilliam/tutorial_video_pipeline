const RECT_FIELDS = ['x', 'y', 'w', 'h']

function SlideEditor({ slide, onChange }) {
  if (!slide) {
    return <div className="slide-editor empty">Select or add a slide to edit it.</div>
  }

  function set(field, value) {
    onChange({ ...slide, [field]: value })
  }

  function setFileTreeItem(i, value) {
    const file_tree = [...slide.file_tree]
    file_tree[i] = value
    set('file_tree', file_tree)
  }

  function removeFileTreeItem(i) {
    set('file_tree', slide.file_tree.filter((_, idx) => idx !== i))
  }

  function setRectField(field, value) {
    set('rect', { ...slide.rect, [field]: Number(value) || 0 })
  }

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
            <input
              type="text"
              value={slide.language}
              onChange={(e) => set('language', e.target.value)}
            />
          </label>
          <label>
            Active file
            <input
              type="text"
              value={slide.active_file}
              onChange={(e) => set('active_file', e.target.value)}
            />
          </label>

          <div className="file-tree-editor">
            <span>File tree</span>
            {slide.file_tree.map((path, i) => (
              <div key={i} className="file-tree-row">
                <input type="text" value={path} onChange={(e) => setFileTreeItem(i, e.target.value)} />
                <button type="button" onClick={() => removeFileTreeItem(i)} aria-label="Remove path">
                  ×
                </button>
              </div>
            ))}
            <button type="button" onClick={() => set('file_tree', [...slide.file_tree, ''])}>
              + Add path
            </button>
          </div>

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

          <label>
            Transition
            <select value={slide.transition} onChange={(e) => set('transition', e.target.value)}>
              <option value="fade">fade</option>
              <option value="lerp_rect">lerp_rect</option>
            </select>
          </label>
        </>
      )}
    </div>
  )
}

export default SlideEditor
