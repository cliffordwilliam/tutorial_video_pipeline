import { useState } from 'react'

function SlideList({ slides, selectedIndex, onSelect, onAddCode, onAddImage, onDelete, onReorder }) {
  const [draggedIndex, setDraggedIndex] = useState(null)
  const [dragOverIndex, setDragOverIndex] = useState(null)

  return (
    <div className="slide-list">
      <div className="slide-list-actions">
        <button type="button" onClick={onAddCode}>
          + Code slide
        </button>
        <button type="button" onClick={onAddImage}>
          + Image slide
        </button>
      </div>
      <ul>
        {slides.map((slide, i) => (
          <li
            key={slide._key}
            className={[
              i === selectedIndex && 'selected',
              i === draggedIndex && 'dragging',
              i === dragOverIndex && 'drag-over',
            ]
              .filter(Boolean)
              .join(' ')}
            onDragOver={(e) => {
              e.preventDefault()
              setDragOverIndex(i)
            }}
            onDragLeave={() => setDragOverIndex(null)}
            onDrop={(e) => {
              e.preventDefault()
              if (draggedIndex !== null) onReorder(draggedIndex, i)
              setDraggedIndex(null)
              setDragOverIndex(null)
            }}
          >
            <span
              className="slide-drag-handle"
              draggable
              onDragStart={(e) => {
                setDraggedIndex(i)
                e.dataTransfer.effectAllowed = 'move'
                // Firefox cancels the drag outright unless setData() is called at least once.
                e.dataTransfer.setData('text/plain', String(i))
              }}
              onDragEnd={() => {
                setDraggedIndex(null)
                setDragOverIndex(null)
              }}
              aria-label="Drag to reorder"
            >
              ⠿
            </span>
            <button type="button" className="slide-row" onClick={() => onSelect(i)}>
              <span className="slide-type">{slide.type}</span>
              <span className="slide-voice">{slide.voice || '(no voice line)'}</span>
            </button>
            <button
              type="button"
              className="slide-delete"
              onClick={() => onDelete(i)}
              aria-label="Delete slide"
            >
              ×
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default SlideList
